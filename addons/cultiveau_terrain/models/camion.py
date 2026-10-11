"""Le stock camion : chaque technicien a son emplacement ; une dotation dit ce qu'il doit avoir à bord."""
from odoo import fields, models
from odoo.exceptions import UserError


class Utilisateur(models.Model):
    _inherit = "res.users"

    cultiveau_camion_id = fields.Many2one("stock.location", "Camion", domain="[('usage', '=', 'internal')]",
                                          help="L'emplacement de stock du camion de ce technicien : les pièces de ses bons en sortent.")
    cultiveau_dotation_ids = fields.One2many("cultiveau.camion.dotation", "user_id", string="Dotation du camion")

    def action_creer_camion(self):
        """Un emplacement « Camion <nom> » sous le stock de la société du technicien."""
        for u in self:
            if u.cultiveau_camion_id:
                continue
            entrepot = self.env["stock.warehouse"].sudo().search([("company_id", "=", u.company_id.id)], limit=1)
            if not entrepot:
                raise UserError(f"Aucun entrepôt pour {u.company_id.name}.")
            u.sudo().cultiveau_camion_id = self.env["stock.location"].sudo().create({
                "name": f"Camion {u.name}", "location_id": entrepot.lot_stock_id.id, "usage": "internal", "company_id": u.company_id.id})

    def action_reassort_camion(self):
        """Le transfert qui remet le camion à sa dotation (depuis le stock du dépôt)."""
        self.ensure_one()
        camion = self.cultiveau_camion_id
        if not camion:
            raise UserError("Ce technicien n'a pas encore de camion.")
        entrepot = self.env["stock.warehouse"].search([("company_id", "=", camion.company_id.id)], limit=1)
        manques = []
        for d in self.cultiveau_dotation_ids:
            a_bord = sum(self.env["stock.quant"].search([("product_id", "=", d.product_id.id), ("location_id", "=", camion.id)]).mapped("quantity"))
            if a_bord < d.quantite:
                manques.append((d.product_id, d.quantite - a_bord))
        if not manques:
            raise UserError("Le camion est complet.")
        type_interne = entrepot.int_type_id
        picking = self.env["stock.picking"].create({
            "picking_type_id": type_interne.id, "location_id": entrepot.lot_stock_id.id, "location_dest_id": camion.id, "origin": f"Réassort {camion.name}",
            "company_id": camion.company_id.id,
            "move_ids": [(0, 0, {"name": p.display_name, "product_id": p.id, "product_uom_qty": q, "product_uom": p.uom_id.id,
                                 "location_id": entrepot.lot_stock_id.id, "location_dest_id": camion.id, "company_id": camion.company_id.id}) for p, q in manques],
        })
        picking.action_confirm()
        picking.action_assign()
        return {"type": "ir.actions.act_window", "res_model": "stock.picking", "res_id": picking.id, "view_mode": "form", "views": [(False, "form")]}

    def action_voir_camion(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "name": f"À bord — {self.cultiveau_camion_id.name}", "res_model": "stock.quant", "view_mode": "list",
                "domain": [("location_id", "child_of", self.cultiveau_camion_id.id)], "context": {"search_default_productgroup": 0}}


class Dotation(models.Model):
    _name = "cultiveau.camion.dotation"
    _description = "Dotation du camion d'un technicien"
    _order = "user_id, product_id"

    user_id = fields.Many2one("res.users", "Technicien", required=True, ondelete="cascade", index=True)
    product_id = fields.Many2one("product.product", "Article", required=True, domain=[("is_storable", "=", True)])
    quantite = fields.Float("Quantité à bord", default=1.0)
