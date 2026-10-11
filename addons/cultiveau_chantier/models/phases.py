"""Les phases du chantier, les heures pointées, la rentabilité, le retour du matériel non posé, les conflits d'équipe."""
from odoo import api, fields, models
from odoo.exceptions import UserError

PHASES_TYPE = ["Préparation et implantation", "Tranchées et pose des réseaux", "Station de tête et raccordements", "Essais et mise en service"]


class Societe(models.Model):
    _inherit = "res.company"

    cultiveau_taux_horaire_cout = fields.Float("Coût horaire d'un poseur (€)", default=38.0,
                                               help="Salaire chargé et frais : sert au calcul de la rentabilité des chantiers.")


class Phase(models.Model):
    _name = "cultiveau.chantier.phase"
    _description = "Phase de chantier"
    _order = "chantier_id, sequence, id"

    chantier_id = fields.Many2one("cultiveau.chantier", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="chantier_id.company_id", store=True)
    partner_id = fields.Many2one(related="chantier_id.partner_id", store=True, string="Client")
    sequence = fields.Integer(default=10)
    name = fields.Char("Phase", required=True)
    date_debut = fields.Date("Début")
    date_fin = fields.Date("Fin")
    user_ids = fields.Many2many("res.users", "cultiveau_chantier_phase_user_rel", "phase_id", "user_id", string="Équipe")
    heures_prevues = fields.Float("Heures prévues")
    heures_reelles = fields.Float("Heures pointées", compute="_compute_heures", store=True)
    etat = fields.Selection([("a_faire", "À faire"), ("en_cours", "En cours"), ("termine", "Terminée")], "État", default="a_faire", required=True)
    pointage_ids = fields.One2many("cultiveau.chantier.pointage", "phase_id", string="Pointages")
    depassement = fields.Boolean("Dépassement", compute="_compute_heures", store=True)

    @api.depends("pointage_ids.heures", "heures_prevues")
    def _compute_heures(self):
        for p in self:
            p.heures_reelles = sum(p.pointage_ids.mapped("heures"))
            p.depassement = bool(p.heures_prevues) and p.heures_reelles > p.heures_prevues * 1.1

    @api.depends("chantier_id.name", "name")
    def _compute_display_name(self):
        for p in self:
            p.display_name = f"{p.chantier_id.name} — {p.name}" if p.chantier_id else p.name


class Pointage(models.Model):
    _name = "cultiveau.chantier.pointage"
    _description = "Heures pointées sur un chantier"
    _order = "date desc, id desc"

    chantier_id = fields.Many2one("cultiveau.chantier", required=True, ondelete="cascade", index=True)
    phase_id = fields.Many2one("cultiveau.chantier.phase", "Phase", domain="[('chantier_id', '=', chantier_id)]", index=True)
    company_id = fields.Many2one(related="chantier_id.company_id", store=True)
    user_id = fields.Many2one("res.users", "Poseur", required=True, default=lambda self: self.env.user)
    date = fields.Date(required=True, default=fields.Date.context_today)
    heures = fields.Float("Heures", required=True)
    note = fields.Char("Ce qui a été fait")
    cout = fields.Float("Coût", compute="_compute_cout", store=True)

    @api.depends("heures", "company_id.cultiveau_taux_horaire_cout")
    def _compute_cout(self):
        for p in self:
            p.cout = p.heures * (p.company_id.cultiveau_taux_horaire_cout or 0)


class Chantier(models.Model):
    _inherit = "cultiveau.chantier"

    phase_ids = fields.One2many("cultiveau.chantier.phase", "chantier_id", string="Phases", copy=True)
    pointage_ids = fields.One2many("cultiveau.chantier.pointage", "chantier_id", string="Pointages")
    heures_prevues = fields.Float("Heures prévues", compute="_compute_heures", store=True)
    heures_reelles = fields.Float("Heures pointées", compute="_compute_heures", store=True)
    ca_ht = fields.Float("Vendu HT", compute="_compute_rentabilite", help="La commande du chantier (hors taxes).")
    cout_materiel = fields.Float("Matériel posé (coût)", compute="_compute_rentabilite", help="Quantités posées × coût d'achat.")
    cout_main_oeuvre = fields.Float("Main-d'œuvre (coût)", compute="_compute_rentabilite", help="Heures pointées × coût horaire d'un poseur.")
    marge = fields.Float("Marge", compute="_compute_rentabilite")
    marge_pct = fields.Float("Marge (%)", compute="_compute_rentabilite")
    retour_picking_id = fields.Many2one("stock.picking", "Retour du matériel", readonly=True, copy=False)
    conflits = fields.Char("Équipe déjà prise", compute="_compute_conflits")

    @api.depends("phase_ids.heures_prevues", "pointage_ids.heures")
    def _compute_heures(self):
        for c in self:
            c.heures_prevues = sum(c.phase_ids.mapped("heures_prevues"))
            c.heures_reelles = sum(c.pointage_ids.mapped("heures"))

    @api.depends("sale_order_id.amount_untaxed", "ligne_ids.quantite_posee", "pointage_ids.cout")
    def _compute_rentabilite(self):
        for c in self:
            c.ca_ht = c.sale_order_id.amount_untaxed
            c.cout_materiel = sum(l.quantite_posee * l.product_id.with_company(c.company_id).standard_price for l in c.ligne_ids)
            c.cout_main_oeuvre = sum(c.pointage_ids.mapped("cout"))
            c.marge = c.ca_ht - c.cout_materiel - c.cout_main_oeuvre
            c.marge_pct = (c.marge / c.ca_ht * 100) if c.ca_ht else 0.0

    @api.depends("chef_id", "equipe_ids", "date_debut", "date_fin", "etat")
    def _compute_conflits(self):
        """Les poseurs de ce chantier qui sont aussi sur un autre chantier aux mêmes dates."""
        for c in self:
            c.conflits = False
            if not (c.date_debut and c.date_fin) or c.etat in ("termine", "annule"):
                continue
            equipe = c.equipe_ids | c.chef_id
            autres = self.search([("id", "!=", c.id or 0), ("etat", "in", ("planifie", "en_cours")), ("date_debut", "<=", c.date_fin), ("date_fin", ">=", c.date_debut),
                                  "|", ("equipe_ids", "in", equipe.ids), ("chef_id", "in", equipe.ids)])
            pris = []
            for a in autres:
                for u in (a.equipe_ids | a.chef_id) & equipe:
                    pris.append(f"{u.name} ({a.name}, du {a.date_debut.strftime('%d/%m')} au {a.date_fin.strftime('%d/%m')})")
            c.conflits = " · ".join(dict.fromkeys(pris)) or False

    @api.model_create_multi
    def create(self, vals_list):
        chantiers = super().create(vals_list)
        for c in chantiers.filtered(lambda c: not c.phase_ids):
            c.phase_ids = [(0, 0, {"name": nom, "sequence": (i + 1) * 10}) for i, nom in enumerate(PHASES_TYPE)]
        return chantiers

    def action_retour_materiel(self):
        """Le matériel sorti mais pas posé revient au dépôt."""
        self.ensure_one()
        if not self.picking_id or self.picking_id.state != "done":
            raise UserError("Le matériel n'a pas encore été sorti du magasin (bon de sortie validé).")
        reste = [(l.product_id, l.quantite_prevue - l.quantite_posee) for l in self.ligne_ids if l.quantite_prevue - l.quantite_posee > 0]
        if not reste:
            raise UserError("Tout le matériel sorti a été posé.")
        entrepot = self.env["stock.warehouse"].search([("company_id", "=", self.company_id.id)], limit=1)
        origine = self.partner_id.property_stock_customer
        destination = entrepot.lot_stock_id
        picking = self.env["stock.picking"].create({
            "picking_type_id": entrepot.in_type_id.id, "partner_id": self.partner_id.id, "origin": f"Retour {self.name}", "company_id": self.company_id.id,
            "location_id": origine.id, "location_dest_id": destination.id,
            "move_ids": [(0, 0, {"name": p.display_name, "product_id": p.id, "product_uom_qty": q, "product_uom": p.uom_id.id,
                                 "location_id": origine.id, "location_dest_id": destination.id, "company_id": self.company_id.id}) for p, q in reste],
        })
        picking.action_confirm()
        self.retour_picking_id = picking
        self.message_post(body=f"Retour au dépôt de {len(reste)} article(s) non posé(s) : {picking.name}.")
        return {"type": "ir.actions.act_window", "res_model": "stock.picking", "res_id": picking.id, "view_mode": "form", "views": [(False, "form")]}

    def action_pointer(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "name": "Pointer mes heures", "res_model": "cultiveau.chantier.pointage", "view_mode": "form",
                "views": [(False, "form")], "target": "new",
                "context": {"default_chantier_id": self.id, "default_phase_id": self.phase_ids.filtered(lambda p: p.etat != "termine")[:1].id}}
