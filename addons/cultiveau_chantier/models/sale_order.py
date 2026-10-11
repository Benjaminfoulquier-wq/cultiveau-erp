from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    cultiveau_chantier_ids = fields.One2many("cultiveau.chantier", "sale_order_id", string="Chantiers")
    cultiveau_nb_chantiers = fields.Integer(compute="_compute_nb_chantiers")

    def _compute_nb_chantiers(self):
        for o in self:
            o.cultiveau_nb_chantiers = len(o.cultiveau_chantier_ids)

    def action_lancer_chantier(self):
        """La commande d'installation devient un chantier : équipe à planifier, matériel prévu d'après les lignes."""
        self.ensure_one()
        if not self.cultiveau_installation_id:
            self.action_creer_installation()
        Chantier = self.env["cultiveau.chantier"]
        chantier = Chantier.create({
            "titre": f"Pose — {self.cultiveau_installation_id.name}", "installation_id": self.cultiveau_installation_id.id, "sale_order_id": self.id,
            "company_id": self.company_id.id, "chef_id": self.user_id.id or self.env.user.id,
            "ligne_ids": [(0, 0, v) for v in Chantier._lignes_depuis_commande(self)],
        })
        return {"type": "ir.actions.act_window", "res_model": "cultiveau.chantier", "res_id": chantier.id, "view_mode": "form"}

    def action_voir_chantiers(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "name": "Chantiers", "res_model": "cultiveau.chantier", "view_mode": "kanban,list,form",
                "domain": [("sale_order_id", "=", self.id)], "context": {"default_sale_order_id": self.id, "default_installation_id": self.cultiveau_installation_id.id}}
