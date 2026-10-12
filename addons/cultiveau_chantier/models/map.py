"""Le chantier le dit à la Map vivante : démarré, mis en service, terminé."""
from odoo import models


class Chantier(models.Model):
    _inherit = "cultiveau.chantier"

    def action_demarrer(self):
        res = super().action_demarrer()
        for c in self:
            self.env["cultiveau.evenement"].publier("chantier_demarre", c, "Chantier démarré", f"{c.display_name} — {c.partner_id.name or ''}",
                                                     {"chantier_id": c.id, "installation_id": c.installation_id.id, "equipe": c.equipe_ids.ids + c.chef_id.ids, "kpi": "chantiers"})
        return res

    def action_mise_en_service(self):
        res = super().action_mise_en_service()
        for c in self:
            self.env["cultiveau.evenement"].publier("mise_en_service", c, "Mise en service", f"{c.installation_id.name} — PV signé", {"chantier_id": c.id, "installation_id": c.installation_id.id, "kpi": "chantiers"})
        return res

    def action_terminer(self):
        res = super().action_terminer()
        for c in self:
            self.env["cultiveau.evenement"].publier("chantier_termine", c, "Chantier terminé", f"{c.display_name} — {c.partner_id.name or ''}",
                                                     {"chantier_id": c.id, "installation_id": c.installation_id.id, "equipe": c.equipe_ids.ids + c.chef_id.ids, "kpi": "chantiers"})
        return res
