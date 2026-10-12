"""Le terrain le dit à la Map vivante : arrivée sur place, bon signé."""
from odoo import models


class Task(models.Model):
    _inherit = "project.task"

    def action_arrive_sur_place(self):
        res = super().action_arrive_sur_place()
        for t in self:
            for u in t.user_ids[:1]:
                self.env["cultiveau.pointage"].badger("depart_intervention", user=u, source="erp", task=t)
        return res


class Bon(models.Model):
    _inherit = "cultiveau.bon"

    def action_signer(self):
        res = super().action_signer()
        for b in self:
            montant = b.montant_ht
            technicien = b.task_id.user_ids[:1] or b.chantier_id.chef_id
            self.env["cultiveau.evenement"].publier("bon_signe", b, "Bon signé sur place", f"{b.partner_id.name} a signé {b.name}" + (f" : {round(montant):,} € HT".replace(",", " ") if montant else ""),
                                                     {"bon_id": b.id, "task_id": b.task_id.id, "user_id": technicien.id, "partner_id": b.partner_id.id, "kpi": "interventions"})
            if b.task_id and b.cloturer:
                for u in b.task_id.user_ids[:1]:
                    self.env["cultiveau.pointage"].badger("retour_intervention", user=u, source="erp", task=b.task_id)
        return res
