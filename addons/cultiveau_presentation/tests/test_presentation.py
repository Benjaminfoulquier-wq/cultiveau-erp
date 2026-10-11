from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPresentation(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = cls.env["res.partner"].create({"name": "Client Présentation"})
        cls.pompe = cls.env["product.product"].create({"name": "Pompe immergée 30 m³/h", "list_price": 2500, "type": "consu"})
        cls.tube = cls.env["product.product"].create({"name": "Tube PE 63", "list_price": 3, "type": "consu"})
        cls.pose = cls.env["product.product"].create({"name": "Pose et mise en service", "list_price": 1200, "type": "service"})
        cls.visserie = cls.env["product.product"].create({"name": "Colliers et visserie", "list_price": 40, "type": "consu"})
        cls.devis = cls.env["sale.order"].create({"partner_id": cls.client.id, "order_line": [
            Command.create({"display_type": "line_section", "name": "Lot 1 — Station de pompage"}),
            Command.create({"product_id": cls.pompe.id, "product_uom_qty": 1}),
            Command.create({"product_id": cls.visserie.id, "product_uom_qty": 1, "cultiveau_masque": True}),
            Command.create({"display_type": "line_section", "name": "Lot 2 — Réseau"}),
            Command.create({"product_id": cls.tube.id, "product_uom_qty": 400}),
            Command.create({"display_type": "line_note", "name": "Essais de pression avant remblaiement."}),
            Command.create({"product_id": cls.pose.id, "product_uom_qty": 1})]})

    def _noms(self, lignes):
        return [l.name for l in lignes]

    def test_niveaux_du_devis(self):
        d = self.devis
        self.assertEqual(d.cultiveau_detail, "complet")
        complet = d._get_order_lines_to_report()
        self.assertNotIn("Colliers et visserie", self._noms(complet))
        self.assertIn("Fournitures diverses et petites pièces", self._noms(complet))
        self.assertAlmostEqual(sum(complet.filtered(lambda l: not l.display_type).mapped("price_subtotal")), d.amount_untaxed, places=2)
        d.cultiveau_detail = "lots"
        lots = d._get_order_lines_to_report()
        self.assertEqual(self._noms(lots), ["Lot 1 — Station de pompage", "Lot 2 — Réseau", "Essais de pression avant remblaiement."])
        self.assertAlmostEqual(lots[0].price_subtotal, 2540)
        self.assertAlmostEqual(lots[1].price_subtotal, 400 * 3 + 1200)
        d.cultiveau_detail = "forfait"
        forfait = d._get_order_lines_to_report()
        self.assertEqual(len(forfait), 1)
        self.assertAlmostEqual(forfait.price_subtotal, d.amount_untaxed)
        d.cultiveau_detail = "materiel_mo"
        mo = d._get_order_lines_to_report()
        self.assertEqual(self._noms(mo), ["Matériel et fournitures", "Main-d'œuvre, pose et prestations"])
        self.assertAlmostEqual(mo[1].price_subtotal, 1200)
        # le PDF suit : les lots, pas les articles
        html = self.env["ir.actions.report"]._render_qweb_html("sale.report_saleorder", d.ids)[0].decode()
        self.assertIn("Matériel et fournitures", html)
        self.assertNotIn("Pompe immergée", html)

    def test_facture(self):
        d = self.devis
        d.cultiveau_detail = "lots"
        d.action_confirm()
        facture = d._create_invoices()
        self.assertEqual(facture.cultiveau_detail, "lots", "sans réglage propre aux factures, la facture suit le devis")
        self.assertTrue(facture.invoice_line_ids.filtered(lambda l: l.product_id == self.visserie).cultiveau_masque)
        lignes = facture.cultiveau_lignes_presentees()
        self.assertEqual([l.name for l in lignes][:2], ["Lot 1 — Station de pompage", "Lot 2 — Réseau"])
        facture.cultiveau_detail = "complet"
        self.assertIn("Fournitures diverses et petites pièces", [l.name for l in facture.cultiveau_lignes_presentees()])
        facture.action_post()
        html = self.env["ir.actions.report"]._render_qweb_html("account.report_invoice", facture.ids)[0].decode()
        self.assertIn("Fournitures diverses", html)
        self.assertNotIn("Colliers et visserie", html)
