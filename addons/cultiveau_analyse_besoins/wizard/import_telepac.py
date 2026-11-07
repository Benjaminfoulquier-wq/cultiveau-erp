"""L'import Telepac lancé depuis un projet : les parcelles irriguées de la déclaration vont droit dans le projet."""
from odoo import fields, models


class ImportTelepac(models.TransientModel):
    _inherit = "cultiveau.import.telepac"

    installation_id = fields.Many2one("cultiveau.installation", "Projet à remplir")

    def action_importer(self):
        action = super().action_importer()
        if self.installation_id:
            parcelles = self.partner_id.cultiveau_parcelle_ids.filtered(lambda p: p.campagne == self.campagne and p.irriguee and p.culture_id)
            if parcelles:
                self.installation_id.appliquer_parcelles(parcelles)
            params = action.get("params", {})
            params["message"] = params.get("message", "") + f" {len(parcelles)} parcelle(s) irriguée(s) reprise(s) dans le projet : décochez celles qui ne le concernent pas."
            params["next"] = {"type": "ir.actions.client", "tag": "soft_reload"}
        return action
