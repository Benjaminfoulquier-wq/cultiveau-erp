from odoo import fields, models


class Reglages(models.TransientModel):
    _inherit = "res.config.settings"

    cultiveau_copernicus_id = fields.Char("Identifiant du client OAuth Copernicus", config_parameter="cultiveau.copernicus_id")
    cultiveau_copernicus_secret = fields.Char("Secret du client OAuth Copernicus", config_parameter="cultiveau.copernicus_secret")
    cultiveau_parcelles_prevenir_client = fields.Boolean("Prévenir le client automatiquement", config_parameter="cultiveau.parcelles_prevenir_client",
                                                         help="Sinon, l'alerte arrive au commercial, qui prévient le client en un clic après avoir regardé.")
