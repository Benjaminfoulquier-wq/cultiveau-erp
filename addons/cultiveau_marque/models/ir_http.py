from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        """Le nom qui s'affiche dans l'interface web (titre d'onglet, écran de chargement) est Cultiveau."""
        info = super().session_info()
        info["cultiveau_marque"] = "Cultiveau"
        return info
