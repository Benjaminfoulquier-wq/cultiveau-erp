from datetime import timedelta

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "cultiveau")
class TestReassort(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.fourn = cls.env["res.partner"].create({"name": "Fournisseur R", "is_company": True})
        cls.client = cls.env["res.partner"].create({"name": "Earl du Réassort"})
        cls.raccord = cls.env["product.product"].create({"name": "Raccord 63", "list_price": 6.0, "standard_price": 3.0, "type": "consu", "is_storable": True, "purchase_ok": True,
                                                         "seller_ids": [Command.create({"partner_id": cls.fourn.id, "price": 2.8, "delay": 4})]})
        cls.wh = cls.env["stock.warehouse"].search([("company_id", "=", cls.company.id)], limit=1)
        cls.env["stock.quant"]._update_available_quantity(cls.raccord, cls.wh.lot_stock_id, 125)
        # 120 raccords sortis vers des clients sur l'année : 10 par mois
        t = cls.wh.out_type_id
        picking = cls.env["stock.picking"].create({"picking_type_id": t.id, "partner_id": cls.client.id, "location_id": t.default_location_src_id.id, "location_dest_id": cls.client.property_stock_customer.id,
                                                   "move_ids": [(0, 0, {"name": "Raccord 63", "product_id": cls.raccord.id, "product_uom_qty": 120, "product_uom": cls.raccord.uom_id.id,
                                                                        "location_id": t.default_location_src_id.id, "location_dest_id": cls.client.property_stock_customer.id})]})
        picking.action_confirm()
        picking.action_assign()
        for m in picking.move_ids:
            m.quantity = 120
            m.picked = True
        picking.with_context(skip_backorder=True, skip_sanity_check=True).button_validate()
        picking.move_ids.write({"date": fields.Datetime.now() - timedelta(days=60)})

    def test_proposition_regles_et_commande(self):
        r = self.env["cultiveau.reassort"].create({"company_id": self.company.id})
        r.action_recalculer()
        l = r.ligne_ids.filtered(lambda l: l.product_id == self.raccord)
        self.assertTrue(l)
        self.assertEqual(l.conso_12m, 120)
        self.assertEqual(l.conso_mois, 10)
        self.assertEqual(l.stock, 5)          # 125 - 120 sortis
        self.assertEqual(l.mini_propose, 15)  # 1,5 mois
        self.assertEqual(l.maxi_propose, 30)  # 3 mois
        self.assertEqual(l.fournisseur_id, self.fourn)
        self.assertEqual(l.a_commander, 25)   # jusqu'au maxi
        self.assertEqual(r.nb_sous_minimum, 1)
        r.action_poser_regles()
        op = self.env["stock.warehouse.orderpoint"].search([("product_id", "=", self.raccord.id), ("company_id", "=", self.company.id)])
        self.assertEqual(len(op), 1)
        self.assertEqual((op.product_min_qty, op.product_max_qty, op.trigger), (15, 30, "auto"))
        action = r.action_commander()
        po = self.env["purchase.order"].search(action["domain"])
        self.assertEqual(len(po), 1)
        self.assertEqual(po.partner_id, self.fourn)
        self.assertEqual(po.order_line.product_qty, 25)
        self.assertEqual(po.order_line.price_unit, 2.8)
        # une fois la commande passée, « arrive » couvre : plus rien à commander
        po.button_confirm()
        r.action_recalculer()
        l = r.ligne_ids.filtered(lambda l: l.product_id == self.raccord)
        self.assertEqual(l.arrive, 25)
        self.assertEqual(l.a_commander, 0)

    def test_ouvrir(self):
        a = self.env["cultiveau.reassort"].action_ouvrir()
        self.assertEqual(a["res_model"], "cultiveau.reassort")
