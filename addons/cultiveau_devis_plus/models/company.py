from odoo import fields, models


class Company(models.Model):
    _inherit = "res.company"

    cultiveau_marge_mini_pct = fields.Float("Marge minimale visée (%)", default=20.0, help="En dessous, le devis le signale au vendeur.")
    cultiveau_devis_fiches = fields.Boolean("Joindre les fiches techniques à l'envoi du devis", default=True)
    cultiveau_devis_avis_auto = fields.Boolean("Relire avec le référentiel avant chaque envoi", default=False,
                                               help="Les notes techniques du référentiel sont (re)générées au moment d'envoyer le devis.")


class Reglages(models.TransientModel):
    _inherit = "res.config.settings"

    cultiveau_marge_mini_pct = fields.Float(related="company_id.cultiveau_marge_mini_pct", readonly=False)
    cultiveau_devis_fiches = fields.Boolean(related="company_id.cultiveau_devis_fiches", readonly=False)
    cultiveau_devis_avis_auto = fields.Boolean(related="company_id.cultiveau_devis_avis_auto", readonly=False)

    def action_voir_avis(self):
        return self.env["ir.actions.act_window"]._for_xml_id("cultiveau_devis_plus.action_avis")
