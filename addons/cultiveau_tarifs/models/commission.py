"""Les commissions des commerciaux : à partir des factures de vente, par commercial, le chiffre d'affaires, la marge estimée
(prix de vente moins le prix d'achat des articles) et la commission, au taux du commercial ou au taux par défaut de la société."""

from odoo import api, fields, models


class Users(models.Model):
    _inherit = "res.users"

    cultiveau_commission_pct = fields.Float("Commission (%)", digits=(5, 2),
                                            help="Taux de commission de ce commercial. Laissé à 0, c'est le taux par défaut de la société qui s'applique.")


class Company(models.Model):
    _inherit = "res.company"

    cultiveau_commission_pct = fields.Float("Commission par défaut (%)", digits=(5, 2), default=0.0,
                                            help="Appliqué aux commerciaux qui n'ont pas leur propre taux.")
    cultiveau_commission_base = fields.Selection([("marge", "La marge"), ("ca", "Le chiffre d'affaires")], "Commission calculée sur", default="marge")


class Commission(models.TransientModel):
    _name = "cultiveau.commission"
    _description = "Commissions des commerciaux"

    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)
    currency_id = fields.Many2one(related="company_id.currency_id")
    date_debut = fields.Date("Du", required=True, default=lambda self: fields.Date.context_today(self).replace(day=1))
    date_fin = fields.Date("Au", required=True, default=fields.Date.context_today)
    base = fields.Selection([("marge", "La marge"), ("ca", "Le chiffre d'affaires")], "Commission sur", required=True,
                            default=lambda self: self.env.company.cultiveau_commission_base or "marge")
    ligne_ids = fields.One2many("cultiveau.commission.ligne", "commission_id", "Par commercial")
    total_ca = fields.Monetary("Chiffre d'affaires", compute="_compute_totaux")
    total_marge = fields.Monetary("Marge estimée", compute="_compute_totaux")
    total_commission = fields.Monetary("Commissions", compute="_compute_totaux")

    @api.depends("ligne_ids.ca", "ligne_ids.marge", "ligne_ids.commission")
    def _compute_totaux(self):
        for w in self:
            w.total_ca = sum(w.ligne_ids.mapped("ca"))
            w.total_marge = sum(w.ligne_ids.mapped("marge"))
            w.total_commission = sum(w.ligne_ids.mapped("commission"))

    def action_calculer(self):
        self.ensure_one()
        self.ligne_ids.unlink()
        company = self.company_id or self.env.company
        lignes = self.env["account.move.line"].sudo().search([
            ("move_id.state", "=", "posted"),
            ("move_id.move_type", "in", ("out_invoice", "out_refund")),
            ("company_id", "=", company.id),
            ("date", ">=", self.date_debut),
            ("date", "<=", self.date_fin),
            ("display_type", "=", "product"),
            ("product_id", "!=", False),
        ])
        par_commercial = {}
        for l in lignes:
            commercial = l.move_id.invoice_user_id
            signe = -1 if l.move_id.move_type == "out_refund" else 1
            d = par_commercial.setdefault(commercial.id, {"commercial": commercial, "ca": 0.0, "cout": 0.0})
            d["ca"] += signe * l.price_subtotal
            d["cout"] += signe * l.quantity * l.product_id.with_company(company).standard_price
        valeurs = []
        for d in par_commercial.values():
            commercial = d["commercial"]
            taux = commercial.cultiveau_commission_pct or company.cultiveau_commission_pct
            marge = d["ca"] - d["cout"]
            assiette = marge if self.base == "marge" else d["ca"]
            valeurs.append({"commission_id": self.id, "commercial_id": commercial.id or False, "ca": d["ca"], "cout": d["cout"],
                            "marge": marge, "taux": taux, "commission": round(max(assiette, 0.0) * taux / 100.0, 2)})
        valeurs.sort(key=lambda v: -v["commission"])
        self.env["cultiveau.commission.ligne"].create(valeurs)
        return {"type": "ir.actions.act_window", "res_model": "cultiveau.commission", "res_id": self.id, "view_mode": "form",
                "target": "new", "name": "Commissions des commerciaux"}


class Settings(models.TransientModel):
    _inherit = "res.config.settings"

    cultiveau_commission_pct = fields.Float(related="company_id.cultiveau_commission_pct", readonly=False)
    cultiveau_commission_base = fields.Selection(related="company_id.cultiveau_commission_base", readonly=False)


class CommissionLigne(models.TransientModel):
    _name = "cultiveau.commission.ligne"
    _description = "Commission d'un commercial"
    _order = "commission desc"

    commission_id = fields.Many2one("cultiveau.commission", required=True, ondelete="cascade")
    currency_id = fields.Many2one(related="commission_id.currency_id")
    commercial_id = fields.Many2one("res.users", "Commercial")
    ca = fields.Monetary("Chiffre d'affaires")
    cout = fields.Monetary("Coût estimé")
    marge = fields.Monetary("Marge estimée")
    taux = fields.Float("Taux (%)", digits=(5, 2))
    commission = fields.Monetary("Commission")
