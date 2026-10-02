from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    cultiveau_url_assistant = fields.Char("Assistant téléphonique", config_parameter="cultiveau.url_assistant",
                                          help="Ex. https://assistant.cultiveau.fr")
    cultiveau_url_dte = fields.Char("DTe", config_parameter="cultiveau.url_dte", help="Ex. https://dte.cultiveau.fr")
    cultiveau_url_disc = fields.Char("Management (DISC)", config_parameter="cultiveau.url_disc", help="Ex. https://disc.cultiveau.fr")
    cultiveau_url_academie = fields.Char("Académie", config_parameter="cultiveau.url_academie",
                                         help="Ex. https://formations.lesjourneesdecultiveau.fr")
    cultiveau_cle_api = fields.Char("Clé d'accès des outils du réseau", config_parameter="cultiveau.cle_api",
                                    help="La clé que l'assistant téléphonique présente pour écrire dans l'ERP (en-tête X-Cultiveau-Cle). "
                                         "À reporter dans la page « Clés » de l'assistant.")
