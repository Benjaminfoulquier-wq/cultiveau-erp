from odoo import api, fields, models
from odoo.exceptions import UserError


class Choix(models.TransientModel):
    _name = "cultiveau.rapprochement.choix"
    _description = "Rapprocher une ligne de relevé avec des factures"

    ligne_id = fields.Many2one("account.bank.statement.line", required=True)
    montant = fields.Monetary(related="ligne_id.amount")
    currency_id = fields.Many2one(related="ligne_id.currency_id")
    libelle = fields.Char(related="ligne_id.payment_ref")
    partner_id = fields.Many2one("res.partner", "Client ou fournisseur")
    aml_ids = fields.Many2many("account.move.line", string="Factures et écritures à régler",
                               domain="[('cultiveau_a_lettrer', '=', True), ('company_id', '=', company_id), ('partner_id', '=', partner_id)]")
    company_id = fields.Many2one(related="ligne_id.company_id")
    total = fields.Monetary("Total choisi", compute="_compute_total", currency_field="currency_id")

    @api.depends("aml_ids")
    def _compute_total(self):
        for c in self:
            c.total = sum(c.aml_ids.mapped("amount_residual"))

    @api.onchange("partner_id")
    def _onchange_partner(self):
        self.aml_ids = False

    def action_rapprocher(self):
        self.ensure_one()
        if not self.aml_ids:
            raise UserError("Choisissez au moins une facture.")
        self.ligne_id.cultiveau_lettrer_avec(self.aml_ids)
        return {"type": "ir.actions.act_window_close"}


class Compte(models.TransientModel):
    _name = "cultiveau.rapprochement.compte"
    _description = "Passer une ligne de relevé sur un compte"

    ligne_id = fields.Many2one("account.bank.statement.line", required=True)
    montant = fields.Monetary(related="ligne_id.amount")
    currency_id = fields.Many2one(related="ligne_id.currency_id")
    company_id = fields.Many2one(related="ligne_id.company_id")
    account_id = fields.Many2one("account.account", "Compte", required=True, domain="[('company_ids', 'in', company_id), ('deprecated', '=', False)]")
    partner_id = fields.Many2one("res.partner", "Tiers (facultatif)")
    libelle = fields.Char("Libellé")
    tax_ids = fields.Many2many("account.tax", string="TVA", domain="[('company_id', '=', company_id), ('type_tax_use', '=', 'purchase')]",
                               help="Si la banque a prélevé une dépense avec TVA (un abonnement, par exemple) : la TVA déductible est séparée.")
    ttc = fields.Boolean("Montant TTC", default=True)

    def action_passer(self):
        self.ensure_one()
        self.ligne_id.cultiveau_passer_sur_compte(self.account_id, self.partner_id, self.libelle, self.tax_ids, self.ttc)
        return {"type": "ir.actions.act_window_close"}
