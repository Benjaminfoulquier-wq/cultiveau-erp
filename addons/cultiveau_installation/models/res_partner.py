from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    cultiveau_installation_ids = fields.One2many("cultiveau.installation", "partner_id", string="Installations")
    cultiveau_nb_installations = fields.Integer(compute="_compute_nb_installations")

    def _compute_nb_installations(self):
        groupes = self.env["cultiveau.installation"]._read_group([("partner_id", "in", self.ids)], ["partner_id"], ["__count"])
        compte = {p.id: n for p, n in groupes}
        for p in self:
            p.cultiveau_nb_installations = compte.get(p.id, 0)

    def action_installations(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "name": f"Installations — {self.display_name}", "res_model": "cultiveau.installation",
                "view_mode": "list,form", "domain": [("partner_id", "=", self.id)], "context": {"default_partner_id": self.id}}
