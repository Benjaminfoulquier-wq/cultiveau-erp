"""Un appel pris par Mathis au téléphone arrive sur la map : notification, Mathis décroche à l'accueil, la fiche de l'appel."""
from odoo import api, models


class Appel(models.Model):
    _inherit = "cultiveau.appel"

    @api.model_create_multi
    def create(self, vals_list):
        appels = super().create(vals_list)
        prenom = self.env["cultiveau.mathis"].prenom()
        for a in appels:
            qui = a.partner_id.name or a.numero or "un appelant"
            self.env["cultiveau.evenement"].publier("appel", a, f"Appel pris par {prenom}" if a.sens == "entrant" else f"Appel passé par {prenom}",
                                                     f"{qui} — {a.sujet}", {"appel_id": a.id, "partner_id": a.partner_id.id, "urgence": a.urgence or "", "task_id": a.task_id.id, "lead_id": a.lead_id.id},
                                                     company=a.company_id)
        return appels
