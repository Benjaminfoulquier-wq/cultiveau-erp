"""Les contrats d'entretien : hivernage, remise en route et visites vendus à l'année ; les interventions se créent seules."""
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError


class Contrat(models.Model):
    _name = "cultiveau.contrat"
    _description = "Contrat d'entretien"
    _inherit = ["mail.thread"]
    _order = "date_fin desc, id desc"

    name = fields.Char("Contrat", required=True, copy=False, readonly=True, default="Nouveau")
    partner_id = fields.Many2one("res.partner", "Client", required=True, index=True, tracking=True)
    company_id = fields.Many2one("res.company", "Adhérent", required=True, default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one(related="company_id.currency_id")
    installation_ids = fields.Many2many("cultiveau.installation", "cultiveau_contrat_installation_rel", "contrat_id", "installation_id",
                                        string="Installations couvertes", domain="[('partner_id', 'child_of', partner_id)]")
    date_debut = fields.Date("Du", required=True, default=fields.Date.context_today)
    date_fin = fields.Date("Au", required=True, default=lambda self: fields.Date.context_today(self) + relativedelta(years=1, days=-1))
    hivernage = fields.Boolean("Hivernage (octobre)", default=True)
    remise_en_route = fields.Boolean("Remise en route (février–mars)", default=True)
    visites = fields.Integer("Visites de contrôle en saison", default=1, help="Réparties de mai à août.")
    depannage_prioritaire = fields.Boolean("Dépannage prioritaire", help="Les dépannages de ce client passent en tête.")
    prix_annuel = fields.Monetary("Prix annuel HT", tracking=True)
    etat = fields.Selection([("brouillon", "Brouillon"), ("actif", "Actif"), ("expire", "Expiré"), ("resilie", "Résilié")], "État",
                            default="brouillon", required=True, tracking=True, index=True)
    task_ids = fields.One2many("project.task", "cultiveau_contrat_id", string="Interventions du contrat")
    nb_interventions = fields.Integer(compute="_compute_nb")
    invoice_ids = fields.Many2many("account.move", "cultiveau_contrat_facture_rel", "contrat_id", "move_id", string="Factures", copy=False)
    notes = fields.Text("Conditions particulières")

    def _compute_nb(self):
        for c in self:
            c.nb_interventions = len(c.task_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "Nouveau") == "Nouveau":
                vals["name"] = self.env["ir.sequence"].next_by_code("cultiveau.contrat") or "Nouveau"
        return super().create(vals_list)

    def action_activer(self):
        for c in self:
            if not c.installation_ids:
                raise UserError("Indiquez les installations couvertes par le contrat.")
            c.etat = "actif"
            c._generer(fields.Date.context_today(c))

    def action_resilier(self):
        self.write({"etat": "resilie"})

    def action_renouveler(self):
        self.ensure_one()
        nouveau = self.copy({"date_debut": self.date_fin + relativedelta(days=1), "date_fin": self.date_fin + relativedelta(years=1), "etat": "brouillon"})
        return {"type": "ir.actions.act_window", "res_model": self._name, "res_id": nouveau.id, "view_mode": "form", "views": [(False, "form")]}

    def _echeancier(self):
        """(mois, nature, libellé) des passages prévus sur la durée du contrat."""
        self.ensure_one()
        passages = []
        mois = self.date_debut.replace(day=1)
        while mois <= self.date_fin:
            if self.remise_en_route and mois.month == 2:
                passages.append((mois, "remise_en_service", "Remise en route"))
            if self.hivernage and mois.month == 10:
                passages.append((mois, "hivernage", "Hivernage"))
            if self.visites:
                saison = [5, 6, 7, 8]
                choisis = [saison[round(i * (len(saison) - 1) / max(1, self.visites - 1))] for i in range(min(self.visites, 4))] if self.visites > 1 else [6]
                if mois.month in choisis:
                    passages.append((mois, "entretien", "Visite de contrôle en saison"))
            mois += relativedelta(months=1)
        return passages

    def _generer(self, aujourdhui):
        """Les interventions du contrat dont le mois arrive (dans les 30 jours), une par installation, sans doublon."""
        projet_par_societe = {}
        for c in self.filtered(lambda c: c.etat == "actif"):
            projet = projet_par_societe.setdefault(c.company_id.id, self.env["project.project"].cultiveau_projet_interventions(c.company_id))
            for mois, nature, libelle in c._echeancier():
                if not (mois <= aujourdhui + relativedelta(days=30) and mois + relativedelta(months=1) > aujourdhui):
                    continue
                for inst in c.installation_ids:
                    cle = f"{c.name}|{inst.id}|{nature}|{mois.isoformat()}"
                    if self.env["project.task"].search_count([("cultiveau_contrat_cle", "=", cle)]):
                        continue
                    self.env["project.task"].with_company(c.company_id).create({
                        "name": f"{libelle} — {inst.name}", "project_id": projet.id, "partner_id": c.partner_id.id, "company_id": c.company_id.id,
                        "cultiveau_nature": nature, "cultiveau_urgence": "non_urgent", "cultiveau_installation_id": inst.id,
                        "cultiveau_contrat_id": c.id, "cultiveau_contrat_cle": cle, "date_deadline": mois + relativedelta(months=1, days=-1),
                        "description": f"<p>Prévu au contrat d'entretien {c.name}.</p>"})

    @api.model
    def _cron_contrats(self):
        aujourdhui = fields.Date.context_today(self)
        self.search([("etat", "=", "actif"), ("date_fin", "<", aujourdhui)]).write({"etat": "expire"})
        self.search([("etat", "=", "actif")])._generer(aujourdhui)

    def action_facturer(self):
        produit = self.env.ref("cultiveau_terrain.produit_contrat_entretien")
        factures = self.env["account.move"]
        for c in self:
            if not c.prix_annuel:
                raise UserError(f"{c.name} : indiquez le prix annuel.")
            taxes = produit.taxes_id.filtered(lambda t: t.company_id == c.company_id) or c.company_id.account_sale_tax_id
            f = self.env["account.move"].with_company(c.company_id).create({
                "move_type": "out_invoice", "partner_id": c.partner_id.id, "company_id": c.company_id.id, "invoice_origin": c.name,
                "invoice_line_ids": [(0, 0, {"product_id": produit.id, "quantity": 1, "price_unit": c.prix_annuel, "tax_ids": [(6, 0, taxes.ids)],
                                             "name": f"Contrat d'entretien {c.name} du {c.date_debut.strftime('%d/%m/%Y')} au {c.date_fin.strftime('%d/%m/%Y')} — "
                                                     + ", ".join(c.installation_ids.mapped("name"))})]})
            c.invoice_ids = [(4, f.id)]
            factures |= f
        return {"type": "ir.actions.act_window", "res_model": "account.move", "res_id": factures[:1].id, "view_mode": "form", "views": [(False, "form")]}

    def action_voir_interventions(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "name": "Interventions du contrat", "res_model": "project.task", "view_mode": "list,form",
                "domain": [("cultiveau_contrat_id", "=", self.id)]}


class Intervention(models.Model):
    _inherit = "project.task"

    cultiveau_contrat_id = fields.Many2one("cultiveau.contrat", "Contrat d'entretien", index=True, copy=False)
    cultiveau_contrat_cle = fields.Char(index=True, copy=False)
    cultiveau_sous_contrat = fields.Boolean("Client sous contrat", compute="_compute_sous_contrat")
    cultiveau_sous_garantie = fields.Boolean("Équipement sous garantie", compute="_compute_sous_contrat")

    @api.depends("partner_id", "cultiveau_equipement_id.garantie_fin")
    def _compute_sous_contrat(self):
        aujourdhui = fields.Date.context_today(self)
        Contrat = self.env["cultiveau.contrat"]
        for t in self:
            t.cultiveau_sous_contrat = bool(t.partner_id) and bool(Contrat.search_count([("partner_id", "=", t.partner_id.commercial_partner_id.id), ("etat", "=", "actif")]))
            t.cultiveau_sous_garantie = bool(t.cultiveau_equipement_id.garantie_fin and t.cultiveau_equipement_id.garantie_fin >= aujourdhui)

    @api.model_create_multi
    def create(self, vals_list):
        taches = super().create(vals_list)
        # un dépannage chez un client sous contrat « prioritaire » passe en tête
        for t in taches.filtered(lambda t: t.cultiveau_nature == "depannage" and t.partner_id):
            contrat = self.env["cultiveau.contrat"].search([("partner_id", "=", t.partner_id.commercial_partner_id.id), ("etat", "=", "actif"),
                                                            ("depannage_prioritaire", "=", True)], limit=1)
            if contrat:
                t.priority = "1"
                t.message_post(body=f"Client sous contrat d'entretien {contrat.name} avec dépannage prioritaire.")
        return taches


class Equipement(models.Model):
    _inherit = "cultiveau.equipement"

    garantie_fin = fields.Date("Garantie jusqu'au")
    sous_garantie = fields.Boolean("Sous garantie", compute="_compute_sous_garantie")

    def _compute_sous_garantie(self):
        aujourdhui = fields.Date.context_today(self)
        for e in self:
            e.sous_garantie = bool(e.garantie_fin and e.garantie_fin >= aujourdhui)
