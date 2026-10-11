from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestGrille(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.s = cls.env.company
        cls.tuyaux = cls.env["product.category"].create({"name": "Tuyaux grille"})
        cls.pe = cls.env["product.category"].create({"name": "PE", "parent_id": cls.tuyaux.id})
        cls.tube = cls.env["product.template"].create({"name": "Tube PE grille", "categ_id": cls.pe.id, "list_price": 10.0})
        cls.vanne = cls.env["product.template"].create({"name": "Vanne grille", "list_price": 100.0})
        cls.agri = cls.env["res.partner"].create({"name": "Agri Grille", "cultiveau_type": "agriculteur"})
        cls.paysagiste = cls.env["res.partner"].create({"name": "Paysagiste Grille", "cultiveau_type": "paysagiste"})
        Remise = cls.env["cultiveau.remise"]
        Remise.create([
            {"company_id": cls.s.id, "cultiveau_type": "agriculteur", "remise_pct": 5},
            {"company_id": cls.s.id, "cultiveau_type": "agriculteur", "categ_id": cls.tuyaux.id, "remise_pct": 15},
            {"company_id": cls.s.id, "cultiveau_type": "agriculteur", "categ_id": cls.pe.id, "remise_pct": 18},
            {"company_id": cls.s.id, "cultiveau_type": "agriculteur", "categ_id": cls.pe.id, "quantite_min": 500, "remise_pct": 22},
            {"company_id": cls.s.id, "cultiveau_type": "paysagiste", "remise_pct": 10},
            {"company_id": cls.s.id, "partner_id": cls.paysagiste.id, "product_id": cls.vanne.id, "remise_pct": 30},
            {"company_id": False, "cultiveau_type": "collectivite", "remise_pct": 8},
        ])

    def test_la_ligne_la_plus_precise(self):
        Remise = self.env["cultiveau.remise"]
        tube, vanne = self.tube.product_variant_id, self.vanne.product_variant_id
        self.assertEqual(Remise.pour(self.s, self.agri, tube), 18)            # sous-famille PE > famille Tuyaux > typologie
        self.assertEqual(Remise.pour(self.s, self.agri, tube, 600), 22)       # à partir de 500
        self.assertEqual(Remise.pour(self.s, self.agri, vanne), 5)            # pas de famille : la typologie
        self.assertEqual(Remise.pour(self.s, self.paysagiste, tube), 10)
        self.assertEqual(Remise.pour(self.s, self.paysagiste, vanne), 30)     # client + article précis
        inconnu = self.env["res.partner"].create({"name": "Sans type"})
        self.assertEqual(Remise.pour(self.s, inconnu, tube), 0)

    def test_au_devis(self):
        devis = self.env["sale.order"].create({"partner_id": self.agri.id, "order_line": [
            Command.create({"product_id": self.tube.product_variant_id.id, "product_uom_qty": 600}),
            Command.create({"product_id": self.vanne.product_variant_id.id, "product_uom_qty": 1})]})
        tube, vanne = devis.order_line
        self.assertEqual((tube.discount, tube.cultiveau_remise_grille), (22, 22))
        self.assertEqual(vanne.discount, 5)
        self.assertAlmostEqual(tube.price_subtotal, 600 * 10 * 0.78, places=2)
        # la grille réseau se copie sans doublon
        n = self.env["cultiveau.remise"].copier_grille_reseau(self.s)
        self.assertEqual(n, 1)
        self.assertEqual(self.env["cultiveau.remise"].copier_grille_reseau(self.s), 0)
        collectivite = self.env["res.partner"].create({"name": "Mairie", "cultiveau_type": "collectivite"})
        self.assertEqual(self.env["cultiveau.remise"].pour(self.s, collectivite, self.vanne.product_variant_id), 8)
