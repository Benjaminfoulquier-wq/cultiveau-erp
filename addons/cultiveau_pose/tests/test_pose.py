from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPose(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.s = cls.env.company
        cls.s.cultiveau_taux_horaire_vente = 50
        cls.client = cls.env["res.partner"].create({"name": "Client Pose", "cultiveau_type": "agriculteur"})
        cls.tube = cls.env["product.product"].create({"name": "Tube PE 63 PN10", "list_price": 3, "type": "consu", "uom_id": cls.env.ref("uom.product_uom_meter").id, "uom_po_id": cls.env.ref("uom.product_uom_meter").id})
        cls.asperseur = cls.env["product.product"].create({"name": "Asperseur à turbine 3/4", "list_price": 25, "type": "consu"})
        cls.pompe = cls.env["product.product"].create({"name": "Pompe immergée 30 m³/h", "list_price": 2500, "type": "consu"})
        cls.electrovanne = cls.env["product.product"].create({"name": "Électrovanne 2 pouces", "list_price": 80, "type": "consu"})
        cls.inconnu = cls.env["product.product"].create({"name": "Gadget sans geste", "list_price": 5, "type": "consu"})

    def test_calcul_et_retour(self):
        Geste = self.env["cultiveau.geste"]
        self.assertEqual(Geste.pour_produit(self.electrovanne, self.s).name[:16], "Pose et câblage ")
        self.assertIn("asperseur", Geste.pour_produit(self.asperseur, self.s).name.lower())
        self.assertIn("tube", Geste.pour_produit(self.tube, self.s).name.lower())
        self.assertFalse(Geste.pour_produit(self.inconnu, self.s))
        devis = self.env["sale.order"].create({"partner_id": self.client.id, "cultiveau_terrain_caillouteux": True, "order_line": [
            Command.create({"product_id": self.tube.id, "product_uom_qty": 100}),
            Command.create({"product_id": self.asperseur.id, "product_uom_qty": 10}),
            Command.create({"product_id": self.pompe.id, "product_uom_qty": 1}),
            Command.create({"product_id": self.inconnu.id, "product_uom_qty": 3})]})
        devis.action_calculer_pose()
        # tube 100 × 0,8 + asperseurs 10 × 12 + pompe 240 × 2 personnes = 680 min = 11,33 h × 1,3 (caillouteux)
        self.assertAlmostEqual(devis.cultiveau_heures_pose, round(680 / 60 * 1.3, 2))
        mo = devis.order_line.filtered("cultiveau_ligne_pose")
        self.assertEqual((len(mo), mo.product_uom_qty, mo.price_unit), (1, devis.cultiveau_heures_pose, 50))
        self.assertIn("Gadget sans geste", devis.cultiveau_detail_pose)
        devis.action_calculer_pose()  # relancer met la ligne à jour, sans doublon
        self.assertEqual(len(devis.order_line.filtered("cultiveau_ligne_pose")), 1)
        # le chantier fini nourrit la matrice : 20 h pointées pour 14,73 h prévues
        devis.action_confirm()
        installation = self.env["cultiveau.installation"].create({"name": "Aspersion pose", "partner_id": self.client.id, "type_systeme": "couverture_integrale", "company_id": self.s.id})
        chantier = self.env["cultiveau.chantier"].create({"partner_id": self.client.id, "sale_order_id": devis.id, "company_id": self.s.id, "installation_id": installation.id, "titre": "Pose aspersion", "reserves": "Essai de pression refait le lendemain.",
                                                          "pointage_ids": [Command.create({"user_id": self.env.user.id, "heures": 20})]})
        self.assertAlmostEqual(chantier.cultiveau_heures_devis, devis.cultiveau_heures_pose)
        chantier.action_terminer()
        self.assertEqual(len(chantier.cultiveau_retour_ids), 3)
        ratio = chantier.cultiveau_retour_ids[0].ratio
        self.assertAlmostEqual(ratio, 20 * 60 / (680 * 1.3), places=2)
        geste_asp = Geste.pour_produit(self.asperseur, self.s)
        self.assertAlmostEqual(geste_asp.minutes_constatees, 12 * ratio, places=1)
        self.assertEqual(geste_asp.nb_retours, 1)
        geste_asp.action_adopter_constate()
        mien = Geste.search([("company_id", "=", self.s.id), ("name", "=", geste_asp.name)])
        self.assertEqual(len(mien), 1)
        self.assertAlmostEqual(mien.minutes, round(12 * ratio, 1))
        self.assertEqual(Geste.pour_produit(self.asperseur, self.s), mien, "la matrice de la société passe avant celle du réseau")
