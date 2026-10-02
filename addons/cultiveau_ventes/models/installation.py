from odoo import fields, models


class Installation(models.Model):
    _inherit = "cultiveau.installation"

    sale_order_ids = fields.One2many("sale.order", "cultiveau_installation_id", string="Devis et commandes")
    lead_ids = fields.One2many("crm.lead", "cultiveau_installation_id", string="Opportunités")
    nb_devis = fields.Integer(compute="_compute_nb_ventes")
    nb_opportunites = fields.Integer(compute="_compute_nb_ventes")

    def _compute_nb_ventes(self):
        for i in self:
            i.nb_devis = len(i.sale_order_ids)
            i.nb_opportunites = len(i.lead_ids)

    def action_voir_devis(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "name": "Devis et commandes", "res_model": "sale.order", "view_mode": "list,form",
                "domain": [("cultiveau_installation_id", "=", self.id)],
                "context": {"default_cultiveau_installation_id": self.id, "default_partner_id": self.partner_id.id,
                            "default_cultiveau_type_systeme": self.type_systeme}}

    def action_nouveau_devis(self):
        self.ensure_one()
        modele = self.env["sale.order.template"].search([("cultiveau_type_systeme", "=", self.type_systeme)], limit=1)
        return {"type": "ir.actions.act_window", "name": "Nouveau devis", "res_model": "sale.order", "view_mode": "form",
                "context": {"default_cultiveau_installation_id": self.id, "default_partner_id": self.partner_id.id,
                            "default_cultiveau_type_systeme": self.type_systeme, "default_sale_order_template_id": modele.id if modele else False}}


class SaleOrderTemplate(models.Model):
    _inherit = "sale.order.template"

    cultiveau_type_systeme = fields.Selection(
        [("couverture_integrale", "Aspersion — couverture intégrale"), ("couverture_partielle", "Aspersion — couverture partielle déplacée"),
         ("enrouleur", "Enrouleur"), ("pivot", "Pivot / rampe frontale"), ("goutte_surface", "Goutte à goutte de surface"),
         ("goutte_enterre", "Goutte à goutte enterré"), ("micro_aspersion", "Micro-aspersion"), ("mixte", "Mixte")],
        "Type d'installation", help="Le modèle proposé par défaut pour ce type d'installation.")
