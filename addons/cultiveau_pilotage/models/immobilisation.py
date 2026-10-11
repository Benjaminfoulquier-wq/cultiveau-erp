"""Les immobilisations : le camion, la mini-pelle, l'enrouleur de démonstration ; leur amortissement passé chaque mois sans y penser."""

import calendar
from datetime import date, timedelta

from odoo import Command, api, fields, models
from odoo.exceptions import UserError


class Immobilisation(models.Model):
    _name = "cultiveau.immobilisation"
    _description = "Immobilisation"
    _inherit = ["mail.thread"]
    _order = "date_debut desc, id desc"

    name = fields.Char("Immobilisation", required=True, tracking=True)
    company_id = fields.Many2one("res.company", "Société", required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related="company_id.currency_id")
    compte_id = fields.Many2one("account.account", "Compte d'immobilisation (2…)", required=True, domain="[('company_ids', 'in', company_id), ('code', '=like', '2%')]")
    compte_amortissement_id = fields.Many2one("account.account", "Compte d'amortissement (28…)", domain="[('company_ids', 'in', company_id), ('code', '=like', '28%')]",
                                              compute="_compute_comptes", store=True, readonly=False)
    compte_dotation_id = fields.Many2one("account.account", "Compte de dotation (6811…)", domain="[('company_ids', 'in', company_id), ('code', '=like', '68%')]",
                                         compute="_compute_comptes", store=True, readonly=False)
    valeur = fields.Monetary("Valeur d'achat HT", required=True, currency_field="currency_id")
    valeur_residuelle = fields.Monetary("Valeur résiduelle", currency_field="currency_id")
    date_debut = fields.Date("Mise en service", required=True, default=fields.Date.context_today)
    duree_mois = fields.Integer("Durée (mois)", required=True, default=60, help="Véhicule 48 à 60, matériel 60 à 120, informatique 36, bâtiment 240 et plus.")
    etat = fields.Selection([("brouillon", "Brouillon"), ("en_cours", "En cours d'amortissement"), ("amortie", "Amortie"), ("cedee", "Cédée / sortie")], "État", default="brouillon", tracking=True)
    ligne_ids = fields.One2many("cultiveau.immobilisation.ligne", "immobilisation_id", "Plan d'amortissement")
    amorti = fields.Monetary("Amorti à ce jour", compute="_compute_etat_plan", currency_field="currency_id")
    valeur_nette = fields.Monetary("Valeur nette comptable", compute="_compute_etat_plan", currency_field="currency_id")
    facture_line_id = fields.Many2one("account.move.line", "Ligne de facture d'achat", readonly=True)
    partner_id = fields.Many2one("res.partner", "Fournisseur")
    note = fields.Text("Remarques")

    @api.depends("compte_id")
    def _compute_comptes(self):
        Compte = self.env["account.account"]
        for i in self:
            if not i.compte_id:
                continue
            code = i.compte_id.code or ""
            with_c = Compte.with_company(i.company_id)
            amort = with_c.search([("company_ids", "in", i.company_id.id), ("code", "=like", f"28{code[1:4]}%")], limit=1) or \
                with_c.search([("company_ids", "in", i.company_id.id), ("code", "=like", f"28{code[1:3]}%")], limit=1)
            dot = with_c.search([("company_ids", "in", i.company_id.id), ("code", "=like", "6811%")], limit=1)
            i.compte_amortissement_id = i.compte_amortissement_id or amort
            i.compte_dotation_id = i.compte_dotation_id or dot

    @api.depends("ligne_ids.move_id", "ligne_ids.montant", "valeur")
    def _compute_etat_plan(self):
        for i in self:
            i.amorti = sum(i.ligne_ids.filtered("move_id").mapped("montant"))
            i.valeur_nette = i.valeur - i.amorti

    def action_calculer_plan(self):
        """Linéaire, au mois, prorata temporis le premier mois ; la dernière ligne absorbe les arrondis."""
        for i in self:
            if i.ligne_ids.filtered("move_id"):
                raise UserError("Des dotations sont déjà passées : le plan ne se recalcule plus.")
            i.ligne_ids.unlink()
            base = i.valeur - (i.valeur_residuelle or 0.0)
            if base <= 0 or i.duree_mois <= 0:
                raise UserError("Indiquez la valeur et la durée.")
            mensualite = base / i.duree_mois
            premier = i.date_debut
            jours_mois = calendar.monthrange(premier.year, premier.month)[1]
            part_premier = (jours_mois - premier.day + 1) / jours_mois
            lignes, cumul, jour = [], 0.0, premier
            n = i.duree_mois + (1 if part_premier < 0.999 else 0)
            for k in range(n):
                fin_mois = date(jour.year, jour.month, calendar.monthrange(jour.year, jour.month)[1])
                if k == 0:
                    montant = round(mensualite * part_premier, 2)
                elif k == n - 1:
                    montant = round(base - cumul, 2)
                else:
                    montant = round(mensualite, 2)
                cumul += montant
                lignes.append(Command.create({"date": fin_mois, "montant": montant, "cumul": round(cumul, 2), "valeur_nette": round(i.valeur - cumul, 2)}))
                jour = fin_mois + timedelta(days=1)
            i.write({"ligne_ids": lignes, "etat": "en_cours"})
        return True

    def action_passer_dotations(self, aujourdhui=None):
        """Les dotations échues qui n'ont pas encore leur écriture : débit 6811, crédit 28."""
        aujourdhui = aujourdhui or fields.Date.context_today(self)
        for i in self.filtered(lambda i: i.etat == "en_cours"):
            if not (i.compte_amortissement_id and i.compte_dotation_id):
                raise UserError(f"{i.name} : indiquez les comptes d'amortissement et de dotation.")
            od = self.env["account.journal"].search([("company_id", "=", i.company_id.id), ("type", "=", "general")], order="sequence, id", limit=1)
            verrou = i.company_id.fiscalyear_lock_date
            for l in i.ligne_ids.filtered(lambda l: not l.move_id and l.date <= aujourdhui).sorted("date"):
                date_ecriture = l.date if not verrou or l.date > verrou else aujourdhui
                move = self.env["account.move"].with_company(i.company_id).create({
                    "journal_id": od.id, "date": date_ecriture, "ref": f"Amortissement {i.name} — {l.date:%m/%Y}", "move_type": "entry",
                    "line_ids": [Command.create({"account_id": i.compte_dotation_id.id, "name": f"Dotation {i.name} {l.date:%m/%Y}", "debit": l.montant}),
                                 Command.create({"account_id": i.compte_amortissement_id.id, "name": f"Amortissement {i.name} {l.date:%m/%Y}", "credit": l.montant})]})
                move.action_post()
                l.move_id = move
            if i.ligne_ids and all(i.ligne_ids.mapped("move_id")):
                i.etat = "amortie"
        return True

    def action_sortir(self):
        """Sortie du patrimoine (vente, casse) : l'amortissement cumulé et la valeur nette sont soldés ; la vente elle-même est une facture (775)."""
        for i in self.filtered(lambda i: i.etat in ("en_cours", "amortie")):
            od = self.env["account.journal"].search([("company_id", "=", i.company_id.id), ("type", "=", "general")], order="sequence, id", limit=1)
            Compte = self.env["account.account"].with_company(i.company_id)
            vnc_compte = Compte.search([("company_ids", "in", i.company_id.id), ("code", "=like", "675%")], limit=1)
            if not vnc_compte:  # le plan français livré ne l'a pas : on le crée
                vnc_compte = Compte.create({"code": "675000", "name": "Valeurs comptables des éléments d'actif cédés", "account_type": "expense", "company_ids": [(4, i.company_id.id)]})
            lignes = [Command.create({"account_id": i.compte_id.id, "name": f"Sortie {i.name}", "credit": i.valeur})]
            if i.amorti:
                lignes.append(Command.create({"account_id": i.compte_amortissement_id.id, "name": f"Sortie {i.name} — amortissements", "debit": i.amorti}))
            if i.valeur_nette:
                lignes.append(Command.create({"account_id": vnc_compte.id, "name": f"Sortie {i.name} — valeur nette", "debit": i.valeur_nette}))
            move = self.env["account.move"].with_company(i.company_id).create({"journal_id": od.id, "date": fields.Date.context_today(self), "ref": f"Sortie {i.name}", "move_type": "entry", "line_ids": lignes})
            move.action_post()
            i.ligne_ids.filtered(lambda l: not l.move_id).unlink()
            i.etat = "cedee"
            i.message_post(body=f"Sortie du patrimoine : écriture {move.name}.")
        return True

    @api.model
    def _cron_dotations(self):
        self.search([("etat", "=", "en_cours")]).action_passer_dotations()


class ImmobilisationLigne(models.Model):
    _name = "cultiveau.immobilisation.ligne"
    _description = "Dotation d'amortissement"
    _order = "date"

    immobilisation_id = fields.Many2one("cultiveau.immobilisation", required=True, ondelete="cascade")
    date = fields.Date("Fin de mois", required=True)
    montant = fields.Float("Dotation", digits="Product Price")
    cumul = fields.Float("Cumul", digits="Product Price")
    valeur_nette = fields.Float("Valeur nette", digits="Product Price")
    move_id = fields.Many2one("account.move", "Écriture", readonly=True)


class Move(models.Model):
    _inherit = "account.move"

    cultiveau_immobilisation_ids = fields.One2many("cultiveau.immobilisation", "facture_line_id", string="Immobilisations", compute="_compute_immos")
    cultiveau_a_immobiliser = fields.Boolean(compute="_compute_immos")

    @api.depends("line_ids.account_id", "state")
    def _compute_immos(self):
        for m in self:
            lignes = m.line_ids.filtered(lambda l: l.account_id.code and l.account_id.code[0] == "2" and not l.account_id.code.startswith("28") and l.debit > 0)
            immos = self.env["cultiveau.immobilisation"].search([("facture_line_id", "in", lignes.ids)]) if lignes else self.env["cultiveau.immobilisation"]
            m.cultiveau_immobilisation_ids = immos
            m.cultiveau_a_immobiliser = bool(lignes) and m.move_type == "in_invoice" and m.state == "posted" and len(immos) < len(lignes)

    def action_cultiveau_immobiliser(self):
        """Chaque ligne de la facture d'achat passée sur un compte 2… devient une immobilisation, prête à amortir."""
        self.ensure_one()
        Immo = self.env["cultiveau.immobilisation"]
        creees = Immo
        for l in self.line_ids.filtered(lambda l: l.account_id.code and l.account_id.code[0] == "2" and not l.account_id.code.startswith("28") and l.debit > 0):
            if Immo.search_count([("facture_line_id", "=", l.id)]):
                continue
            creees |= Immo.create({"name": l.name or l.product_id.name or self.name, "company_id": self.company_id.id, "compte_id": l.account_id.id, "valeur": l.debit,
                                   "date_debut": self.invoice_date or self.date, "facture_line_id": l.id, "partner_id": self.partner_id.id})
        creees.action_calculer_plan()
        return {"type": "ir.actions.act_window", "res_model": "cultiveau.immobilisation", "view_mode": "list,form", "domain": [("id", "in", creees.ids)], "name": "Immobilisations"}
