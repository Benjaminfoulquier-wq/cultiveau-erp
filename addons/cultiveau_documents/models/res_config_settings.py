from odoo import fields, models


class Reglages(models.TransientModel):
    _inherit = "res.config.settings"

    cultiveau_acompte_pct = fields.Float(related="company_id.cultiveau_acompte_pct", readonly=False)
    cultiveau_cgv = fields.Html(related="company_id.cultiveau_cgv", readonly=False)
    cultiveau_mention_reseau = fields.Boolean(related="company_id.cultiveau_mention_reseau", readonly=False)
    cultiveau_relances_devis = fields.Boolean(related="company_id.cultiveau_relances_devis", readonly=False)
    cultiveau_relance_devis_jours = fields.Integer(related="company_id.cultiveau_relance_devis_jours", readonly=False)
    cultiveau_relance_devis_max = fields.Integer(related="company_id.cultiveau_relance_devis_max", readonly=False)
    cultiveau_relances_factures = fields.Boolean(related="company_id.cultiveau_relances_factures", readonly=False)
    cultiveau_relance_facture_jours = fields.Integer(related="company_id.cultiveau_relance_facture_jours", readonly=False)
    cultiveau_relance_facture_max = fields.Integer(related="company_id.cultiveau_relance_facture_max", readonly=False)
