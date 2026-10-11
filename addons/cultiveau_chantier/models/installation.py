from odoo import fields, models


class Installation(models.Model):
    _inherit = "cultiveau.installation"

    chantier_ids = fields.One2many("cultiveau.chantier", "installation_id", string="Chantiers")
    nb_chantiers = fields.Integer(compute="_compute_nb_chantiers")

    def _compute_nb_chantiers(self):
        for i in self:
            i.nb_chantiers = len(i.chantier_ids)

    def action_voir_chantiers(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "name": "Chantiers", "res_model": "cultiveau.chantier", "view_mode": "kanban,list,form",
                "domain": [("installation_id", "=", self.id)], "context": {"default_installation_id": self.id, "default_titre": f"Pose — {self.name}"}}
