from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "cultiveau")
class TestComptoir(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.societe = cls.env.company
        cls.Comptoir = cls.env["cultiveau.comptoir"]
        cls.raccord = cls.env["product.product"].create({"name": "Raccord PE 25 comptoir", "type": "consu", "is_storable": True, "list_price": 2.5,
                                                         "barcode": "3700000000017", "default_code": "RAC25"})
        cls.programmateur = cls.env["product.product"].create({"name": "Programmateur 4 voies comptoir", "type": "consu", "is_storable": True, "list_price": 89})
        emplacement = cls.env["stock.location"].search([("usage", "=", "internal"), ("company_id", "=", cls.societe.id)], limit=1)
        cls.env["stock.quant"]._update_available_quantity(cls.raccord, emplacement, 40)
        cls.agri = cls.env["res.partner"].create({"name": "Agriculteur Comptoir", "cultiveau_type": "agriculteur", "company_id": cls.societe.id, "city": "Alès"})

    def test_contexte_et_recherche(self):
        ctx = self.Comptoir.contexte()
        self.assertEqual(ctx["societe"]["id"], self.societe.id)
        self.assertTrue(ctx["client_defaut"])
        self.assertEqual(self.env["res.partner"].browse(ctx["client_defaut"]).name, "Client de passage")
        douchette = self.Comptoir.chercher("3700000000017")
        self.assertEqual([(a["id"], a["exact"]) for a in douchette], [(self.raccord.id, True)])
        self.assertEqual(douchette[0]["stock"], 40)
        self.assertGreater(douchette[0]["prix_ttc"], 0)
        clavier = self.Comptoir.chercher("comptoir")
        self.assertEqual({a["id"] for a in clavier}, {self.raccord.id, self.programmateur.id})
        self.assertFalse(self.Comptoir.chercher("   "))
        self.assertIn(self.agri.id, [c["id"] for c in self.Comptoir.clients("Alès")])

    def test_encaisser(self):
        """Encaisser : commande confirmée, stock sorti, facture payée."""
        journal = self.env["account.journal"].search([("company_id", "=", self.societe.id), ("type", "=", "cash")], limit=1)
        if not journal:
            self.skipTest("pas de journal de caisse sur cette base")
        with self.assertRaises(UserError):
            self.Comptoir.vendre(self.agri.id, [], "encaisser", journal.id)
        v = self.Comptoir.vendre(self.agri.id, [{"product_id": self.raccord.id, "quantite": 4}, {"product_id": self.programmateur.id, "quantite": 1, "prix_ht": 80}], "encaisser", journal.id)
        commande = self.env["sale.order"].browse(v["commande_id"])
        self.assertEqual(commande.state, "sale")
        self.assertEqual(commande.order_line.filtered(lambda l: l.product_id == self.programmateur).price_unit, 80)
        self.assertEqual(set(commande.picking_ids.mapped("state")), {"done"})
        self.assertEqual(self.raccord.qty_available, 36)
        facture = self.env["account.move"].browse(v["facture_id"])
        self.assertEqual(facture.state, "posted")
        self.assertIn(facture.payment_state, ("paid", "in_payment"))
        self.assertEqual(v["total_ttc"], facture.amount_total)
        self.assertTrue(v["paiement_id"])
        self.assertIn("report_name", self.Comptoir.ticket(facture.id))

    def test_devis_et_commande(self):
        d = self.Comptoir.vendre(None, [{"product_id": self.raccord.id, "quantite": 2}], "devis")
        devis = self.env["sale.order"].browse(d["commande_id"])
        self.assertEqual((devis.state, devis.partner_id.name), ("draft", "Client de passage"))
        c = self.Comptoir.vendre(self.agri.id, [{"product_id": self.raccord.id, "quantite": 2}], "commande")
        commande = self.env["sale.order"].browse(c["commande_id"])
        self.assertEqual(commande.state, "sale")
        self.assertTrue(commande.picking_ids)
        self.assertNotIn("done", commande.picking_ids.mapped("state"))
        self.assertEqual(self.raccord.qty_available, 40)
