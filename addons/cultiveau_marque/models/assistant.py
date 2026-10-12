"""Le compte automatique de la plateforme porte le nom et le logo du réseau, pas ceux de l'éditeur."""
import base64

from odoo import api, models
from odoo.tools import file_open


class Partner(models.Model):
    _inherit = "res.partner"

    @api.model
    def cultiveau_habiller_assistant(self):
        """Nom « Assistant Cultiveau » et avatar au logo, réappliqués à chaque mise à jour (la fiche est protégée des mises à jour par données)."""
        assistant = self.env.ref("base.partner_root", raise_if_not_found=False)
        if not assistant:
            return False
        with file_open("cultiveau_marque/static/src/img/avatar.png", "rb") as f:
            image = base64.b64encode(f.read())
        assistant.sudo().write({"name": "Assistant Cultiveau", "image_1920": image})
        return True
