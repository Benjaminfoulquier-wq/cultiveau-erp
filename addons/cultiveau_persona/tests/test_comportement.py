from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "cultiveau")
class TestComportement(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = cls.env["res.partner"].create(
            {"name": "Durand Ferme", "zip": "30100", "cultiveau_type": "agriculteur", "is_company": True})
        produit = cls.env["product.product"]
        cls.p1 = produit.create({"name": "Goutteur 2 L/h", "list_price": 1.0})
        cls.p2 = produit.create({"name": "Vanne hydraulique", "list_price": 350.0})

    def _devis(self, lignes, etat="sale"):
        o = self.env["sale.order"].create({
            "partner_id": self.client.id,
            "order_line": [(0, 0, {"product_id": p.id, "product_uom_qty": 1, "price_unit": pu}) for p, pu in lignes]})
        o.state = etat
        return o

    def test_sans_signal_pas_de_conclusion(self):
        code, conf, elems = self.client.cultiveau_comportement_signaux()
        self.assertIsNone(code)
        self.assertEqual(elems, [])

    def test_repetition_donne_chat(self):
        for _ in range(3):
            self._devis([(self.p1, 1.0), (self.p1, 1.0)])
        code, conf, elems = self.client.cultiveau_comportement_signaux()
        self.assertEqual(code, "chat")
        self.assertTrue(conf > 0)
        self.assertTrue(any("mêmes" in e for e in elems))

    def test_lecture_ecrit_la_fiche_et_ecart(self):
        for _ in range(3):
            self._devis([(self.p1, 1.0), (self.p1, 1.0)])
        self.client.cultiveau_comportement_lire()
        self.assertEqual(self.client.cultiveau_persona_observe_id.code, "chat")
        self.assertEqual(self.client.cultiveau_persona_id.code, "chat")  # sans questionnaire, l'observé sert
        # on force un déclaré "lion" : l'écart doit s'allumer, et le déclaré prend la main
        lion = self.env["cultiveau.persona"].search([("code", "=", "lion")], limit=1)
        self.env["cultiveau.persona.evaluation"].create(
            {"partner_id": self.client.id, "persona_id": lion.id, "reponses": {}, "scores": {}})
        self.client.invalidate_recordset()
        self.assertEqual(self.client.cultiveau_persona_id.code, "lion")
        self.assertTrue(self.client.cultiveau_persona_ecart)

    def test_observe_sert_quand_pas_de_declare(self):
        for _ in range(3):
            self._devis([(self.p1, 1.0), (self.p1, 1.0)])
        self.client.cultiveau_comportement_lire()
        self.client.invalidate_recordset()
        self.assertEqual(self.client.cultiveau_persona_id.code, "chat")


@tagged("post_install", "-at_install", "cultiveau")
class TestAccompagnement(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env["res.company"].create({"name": "Adhérent Test"})
        cls.client = cls.env["res.partner"].create(
            {"name": "Ferme Vivante", "zip": "30100", "cultiveau_type": "agriculteur", "is_company": True})

    def test_appel_aide_recent_met_a_accompagner(self):
        self.env["cultiveau.appel"].create({
            "reference": "T-ACC-1", "company_id": self.company.id, "partner_id": self.client.id,
            "sujet": "Fuite sur le goutte-à-goutte", "urgence": "journee", "sens": "entrant"})
        self.client.cultiveau_calculer_accompagnement()
        self.assertTrue(self.client.cultiveau_accompagner)
        self.assertGreaterEqual(self.client.cultiveau_accompagner_priorite, 30)
        self.assertIn("rappeler", self.client.cultiveau_accompagner_motif.lower())

    def test_rien_pas_dans_la_liste(self):
        self.client.cultiveau_calculer_accompagnement()
        self.assertFalse(self.client.cultiveau_accompagner)
        self.assertEqual(self.client.cultiveau_accompagner_priorite, 0)

    def test_non_client_ignore(self):
        fournisseur = self.env["res.partner"].create({"name": "Fourn", "cultiveau_type": "autre"})
        fournisseur.cultiveau_calculer_accompagnement()
        self.assertFalse(fournisseur.cultiveau_accompagner)
