from odoo import fields, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    cultiveau_sale_order_id = fields.Many2one("sale.order", "Devis d'origine", index=True, copy=False, help="Le devis client dont cette commande fournisseur couvre les manquants.")
