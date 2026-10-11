"""La clôture d'un exercice : les comptes de charges et de produits soldés dans le résultat, la période verrouillée."""

from odoo import Command, api, fields, models
from odoo.exceptions import UserError

from .comptes import soldes


class Cloture(models.Model):
    _name = "cultiveau.cloture"
    _description = "Clôture d'exercice"
    _inherit = ["mail.thread"]
    _order = "date_fin desc"

    name = fields.Char("Exercice", compute="_compute_name", store=True)
    company_id = fields.Many2one("res.company", "Société", required=True, default=lambda self: self.env.company)
    date_debut = fields.Date("Du", required=True, default=lambda self: fields.Date.context_today(self).replace(month=1, day=1).replace(year=fields.Date.context_today(self).year - 1))
    date_fin = fields.Date("Au", required=True, default=lambda self: fields.Date.context_today(self).replace(month=12, day=31).replace(year=fields.Date.context_today(self).year - 1))
    etat = fields.Selection([("brouillon", "À clôturer"), ("cloturee", "Clôturée")], "État", default="brouillon", tracking=True)
    resultat = fields.Float("Résultat de l'exercice", readonly=True)
    move_id = fields.Many2one("account.move", "Écriture de clôture", readonly=True)
    verrou_precedent = fields.Date(readonly=True)
    note = fields.Text("Remarques")

    _sql_constraints = [("exercice_unique", "unique(company_id, date_fin)", "Cet exercice est déjà clôturé.")]

    @api.depends("date_debut", "date_fin")
    def _compute_name(self):
        for c in self:
            c.name = f"Exercice {c.date_fin.year}" if c.date_fin else "Exercice"

    def action_cloturer(self):
        """Vérifie qu'il ne reste rien en brouillon, solde les classes 6 et 7 dans le compte 120 (bénéfice) ou 129 (perte), verrouille."""
        for c in self:
            if c.etat == "cloturee":
                continue
            societe = c.company_id
            brouillons = self.env["account.move"].search_count([("company_id", "=", societe.id), ("state", "=", "draft"), ("date", ">=", c.date_debut), ("date", "<=", c.date_fin)])
            if brouillons:
                raise UserError(f"{brouillons} écriture(s) en brouillon sur l'exercice : validez-les ou supprimez-les avant de clôturer.")
            s = soldes(self.env, societe, c.date_debut, c.date_fin)
            Compte = self.env["account.account"].with_company(societe)
            comptes = {a.code: a for a in Compte.search([("company_ids", "in", societe.id), "|", ("code", "=like", "6%"), ("code", "=like", "7%")])}
            lignes, resultat = [], 0.0
            for code, balance in s.items():
                if code[0] not in "67" or abs(balance) < 0.005 or code not in comptes:
                    continue
                lignes.append(Command.create({"account_id": comptes[code].id, "name": f"Clôture {c.date_fin.year} — solde {comptes[code].name}",
                                              "debit": -balance if balance < 0 else 0.0, "credit": balance if balance > 0 else 0.0}))
                resultat -= balance  # produits (crédit) positifs, charges (débit) négatives
            if not lignes:
                raise UserError("Aucune charge ni produit sur l'exercice : rien à clôturer.")
            benefice = Compte.search([("company_ids", "in", societe.id), ("code", "=like", "120%")], limit=1)
            perte = Compte.search([("company_ids", "in", societe.id), ("code", "=like", "129%")], limit=1)
            if not (benefice and perte):
                raise UserError("Les comptes 120000 (bénéfice) et 129000 (perte) manquent au plan comptable.")
            if resultat >= 0:
                lignes.append(Command.create({"account_id": benefice.id, "name": f"Résultat de l'exercice {c.date_fin.year} (bénéfice)", "credit": round(resultat, 2)}))
            else:
                lignes.append(Command.create({"account_id": perte.id, "name": f"Résultat de l'exercice {c.date_fin.year} (perte)", "debit": round(-resultat, 2)}))
            od = self.env["account.journal"].search([("company_id", "=", societe.id), ("type", "=", "general")], order="sequence, id", limit=1)
            move = self.env["account.move"].with_company(societe).create({"journal_id": od.id, "date": c.date_fin, "ref": f"Clôture de l'exercice {c.date_fin.year}", "move_type": "entry", "line_ids": lignes})
            move.action_post()
            c.write({"move_id": move.id, "resultat": round(resultat, 2), "etat": "cloturee", "verrou_precedent": societe.fiscalyear_lock_date})
            societe.sudo().write({"fiscalyear_lock_date": c.date_fin})
            c.message_post(body=f"Exercice clôturé : résultat {resultat:,.2f} €, écriture {move.name}, période verrouillée jusqu'au {c.date_fin:%d/%m/%Y}.".replace(",", " "))
        return True

    def action_rouvrir(self):
        for c in self.filtered(lambda c: c.etat == "cloturee"):
            c.company_id.sudo().write({"fiscalyear_lock_date": c.verrou_precedent})
            if c.move_id:
                c.move_id.button_draft()
                c.move_id.with_context(force_delete=True).unlink()
            c.write({"etat": "brouillon", "move_id": False, "resultat": 0.0})
        return True
