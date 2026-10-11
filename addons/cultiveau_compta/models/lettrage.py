"""Le lettrage des tiers : les factures d'un client face à ses règlements, et rien qui traîne."""

import itertools
import re

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare

from .formats import normaliser


class Ecriture(models.Model):
    _inherit = "account.move.line"

    cultiveau_a_lettrer = fields.Boolean("À lettrer", compute="_compute_a_lettrer", search="_search_a_lettrer")

    @api.depends("reconciled", "parent_state", "account_id.account_type")
    def _compute_a_lettrer(self):
        for l in self:
            l.cultiveau_a_lettrer = l.parent_state == "posted" and not l.reconciled and l.account_id.account_type in ("asset_receivable", "liability_payable")

    def _search_a_lettrer(self, operator, value):
        domaine = [("parent_state", "=", "posted"), ("reconciled", "=", False), ("account_id.account_type", "in", ("asset_receivable", "liability_payable"))]
        return domaine if (operator == "=" and value) or (operator == "!=" and not value) else ["!"] + domaine

    def action_cultiveau_lettrer(self):
        """Lettre la sélection : même compte, même tiers ; le reste éventuel reste ouvert (lettrage partiel)."""
        lignes = self.filtered("cultiveau_a_lettrer")
        if len(lignes) < 2:
            raise UserError("Sélectionnez au moins deux écritures à lettrer (une facture et son règlement, par exemple).")
        if len(lignes.account_id) > 1:
            raise UserError("Les écritures sélectionnées ne sont pas sur le même compte (clients et fournisseurs ne se lettrent pas ensemble).")
        if len(lignes.partner_id) > 1:
            raise UserError("Les écritures sélectionnées concernent plusieurs tiers.")
        lignes.reconcile()
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"title": "Lettrage", "message": f"{len(lignes)} écritures lettrées.", "sticky": False, "next": {"type": "ir.actions.client", "tag": "soft_reload"}}}

    @api.model
    def cultiveau_lettrer_auto(self, societe):
        """Par tiers et par compte : montants égaux, puis règlement qui cite la facture, puis règlement = somme de factures. Renvoie le nombre d'écritures lettrées."""
        ouvertes = self.search([("company_id", "=", societe.id), ("cultiveau_a_lettrer", "=", True)], order="date, id")
        total = 0
        for (compte, tiers), groupe in itertools.groupby(ouvertes.sorted(lambda l: (l.account_id.id, l.partner_id.id, l.date, l.id)), key=lambda l: (l.account_id, l.partner_id)):
            if not tiers:
                continue
            lignes = self.browse([l.id for l in groupe])
            total += self._cultiveau_lettrer_groupe(lignes)
        return total

    @api.model
    def _cultiveau_lettrer_groupe(self, lignes):
        fait = 0
        debits = list(lignes.filtered(lambda l: l.amount_residual > 0))
        credits = list(lignes.filtered(lambda l: l.amount_residual < 0))
        # 1. une facture et un règlement du même montant
        for c in list(credits):
            for d in list(debits):
                if float_compare(d.amount_residual, -c.amount_residual, precision_rounding=0.01) == 0:
                    (d + c).reconcile()
                    debits.remove(d)
                    credits.remove(c)
                    fait += 2
                    break
        # 2. le règlement cite le numéro de la facture
        for c in list(credits):
            texte = normaliser(" ".join(x for x in (c.name, c.ref, c.move_id.ref, c.move_id.name) if x))
            texte_plat = re.sub(r"[^A-Z0-9]", "", texte)
            visees = [d for d in debits if d.move_id.name and re.sub(r"[^A-Z0-9]", "", normaliser(d.move_id.name)) in texte_plat and d.move_id.name != c.move_id.name]
            if visees and abs(sum(d.amount_residual for d in visees) + c.amount_residual) < 0.01 * (len(visees) + 1) + 0.005:
                (self.browse([d.id for d in visees]) + c).reconcile()
                for d in visees:
                    debits.remove(d)
                credits.remove(c)
                fait += len(visees) + 1
        # 3. un règlement qui fait la somme de plusieurs factures (ou l'inverse)
        for c in list(credits):
            if len(debits) > 12:
                break
            for n in range(2, min(len(debits), 6) + 1):
                trouve = next((combo for combo in itertools.combinations(debits, n) if float_compare(sum(d.amount_residual for d in combo), -c.amount_residual, precision_rounding=0.01) == 0), None)
                if trouve:
                    (self.browse([d.id for d in trouve]) + c).reconcile()
                    for d in trouve:
                        debits.remove(d)
                    credits.remove(c)
                    fait += n + 1
                    break
        return fait


class LettrageAuto(models.TransientModel):
    _name = "cultiveau.lettrage"
    _description = "Lettrage automatique des tiers"

    company_id = fields.Many2one("res.company", "Société", required=True, default=lambda self: self.env.company)

    def action_lettrer(self):
        self.ensure_one()
        n = self.env["account.move.line"].with_company(self.company_id).cultiveau_lettrer_auto(self.company_id)
        action = self.env["ir.actions.act_window"]._for_xml_id("cultiveau_compta.action_a_lettrer")
        action["display_name"] = f"Lettrage : {n} écritures lettrées, voici ce qui reste"
        return action
