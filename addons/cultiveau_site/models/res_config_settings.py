import secrets

from odoo import fields, models


class Reglages(models.TransientModel):
    _inherit = "res.config.settings"

    cultiveau_erp_lien_secret = fields.Char("Secret partagé avec cultiveau.fr", config_parameter="cultiveau.erp_lien_secret",
                                            help="Même valeur que « Secret partagé avec l'ERP » dans cultiveau.fr, Admin, Clés et services.")

    def action_creer_secret_site(self):
        """Un secret neuf, à recopier ensuite dans cultiveau.fr (les écrans du site ne s'ouvrent plus tant que ce n'est pas fait)."""
        self.env["ir.config_parameter"].sudo().set_param("cultiveau.erp_lien_secret", secrets.token_hex(32))
        return {"type": "ir.actions.client", "tag": "reload"}
