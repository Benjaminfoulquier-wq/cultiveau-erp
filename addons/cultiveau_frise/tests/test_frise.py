from odoo import fields
from odoo.tests import TransactionCase, tagged

from ..models.culture import libelle_mois, mois_couverts


@tagged("post_install", "-at_install", "cultiveau")
class TestFrise(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vigne = cls.env.ref("cultiveau_frise.culture_vigne")
        cls.agri = cls.env["res.partner"].create({"name": "Durand Jean", "zip": "30100", "cultiveau_type": "agriculteur"})

    def test_mois_couverts_passe_l_hiver(self):
        self.assertEqual(mois_couverts(11, 2), [11, 12, 1, 2])
        self.assertEqual(mois_couverts(3, 4), [3, 4])
        self.assertEqual(libelle_mois([11, 12, 1, 2]), "Nov–Fév")

    def test_departement_deduit_du_code_postal(self):
        self.assertEqual(self.agri.departement, "30")
        corse = self.env["res.partner"].create({"name": "Corse", "zip": "20167"})
        self.assertEqual(corse.departement, "2A")

    def test_donnees_du_gard(self):
        stades = self.vigne.stades_pour("30")
        self.assertEqual(len(stades), 4)
        self.assertEqual(stades[0].name, "Débourrement")
        ligne = self.vigne.ligne_frise("30")
        self.assertEqual(ligne["projet"], [11, 12])
        self.assertEqual(ligne["achat"], [1, 2])
        self.assertEqual(ligne["cases"][6]["stade"].name, "Véraison")  # juillet
        self.assertGreater(ligne["cases"][6]["intensite"], ligne["cases"][2]["intensite"])

    def test_repli_sur_les_valeurs_generales(self):
        # Un département sans données : on prend celles valables partout ; sans rien, la ligne est vide.
        self.assertFalse(self.vigne.stades_pour("64"))
        self.env["cultiveau.culture.stade"].create({"culture_id": self.vigne.id, "name": "Général", "mois_debut": "4", "mois_fin": "9", "kc_max": 0.7})
        self.assertEqual(self.vigne.stades_pour("64").name, "Général")
        self.assertEqual(self.vigne.stades_pour("30")[0].name, "Débourrement")

    def test_frise_du_client_et_fenetres(self):
        cc = self.env["cultiveau.culture.client"].create({"partner_id": self.agri.id, "culture_id": self.vigne.id, "surface_ha": 12.5})
        self.assertEqual(cc.departement, "30")
        self.assertEqual(cc.projet_mois, "Nov–Déc")
        self.assertEqual(self.agri.cultiveau_surface_ha, 12.5)
        self.assertIn("Vigne", self.agri.cultiveau_frise_html)
        self.assertIn("Véraison", self.agri.cultiveau_frise_html)
        self.assertIn("projet Nov–Déc", self.agri.cultiveau_fenetres)
        self.assertEqual(cc.fenetres_du_mois(11), {"projet"})
        self.assertEqual(cc.fenetres_du_mois(1), {"achat"})
        self.assertEqual(cc.fenetres_du_mois(6), set())

    def test_a_contacter_ce_mois(self):
        toute_l_annee = self.env["cultiveau.culture"].create({"name": "Test toute l'année", "fenetre_ids": [
            (0, 0, {"genre": "achat", "mois_debut": "1", "mois_fin": "12"})]})
        jamais = self.env["cultiveau.culture"].create({"name": "Test jamais"})
        a = self.env["res.partner"].create({"name": "Toujours", "cultiveau_culture_ids": [(0, 0, {"culture_id": toute_l_annee.id})]})
        b = self.env["res.partner"].create({"name": "Jamais", "cultiveau_culture_ids": [(0, 0, {"culture_id": jamais.id})]})
        self.assertTrue(a.cultiveau_a_contacter)
        self.assertFalse(b.cultiveau_a_contacter)
        trouves = self.env["res.partner"].search([("cultiveau_a_contacter", "=", True)])
        self.assertIn(a, trouves)
        self.assertNotIn(b, trouves)
        n = self.env["cultiveau.culture.client"]._cron_fenetres()
        self.assertGreaterEqual(n, 1)
        self.assertTrue(a.activity_ids.filtered(lambda x: x.summary.startswith("Fenêtre ")))
        self.assertEqual(self.env["cultiveau.culture.client"]._cron_fenetres(), 0, "pas de doublon le même mois")
        self.assertEqual(fields.Date.context_today(a.activity_ids[0]).month, a.activity_ids[0].date_deadline.month)
