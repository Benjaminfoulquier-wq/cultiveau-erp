from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "cultiveau_tarifs")
class TestHaussePrix(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.famille = self.env["product.category"].create({"name": "Compression test"})
        self.article = self.env["product.template"].create({
            "name": "Raccord test", "categ_id": self.famille.id, "type": "consu",
            "standard_price": 100.0, "list_price": 150.0, "purchase_ok": True, "sale_ok": True, "company_id": self.company.id})

    def test_hausse_achat_tout(self):
        w = self.env["cultiveau.hausse.prix"].create({"cible": "achat", "perimetre": "tout", "pct": 10.0, "repercuter": False})
        w.action_appliquer()
        self.assertEqual(self.article.with_company(self.company).standard_price, 110.0)

    def test_baisse_achat(self):
        w = self.env["cultiveau.hausse.prix"].create({"cible": "achat", "perimetre": "tout", "pct": -20.0, "repercuter": False})
        w.action_appliquer()
        self.assertEqual(self.article.with_company(self.company).standard_price, 80.0)

    def test_hausse_vente_famille(self):
        w = self.env["cultiveau.hausse.prix"].create({"cible": "vente", "perimetre": "famille", "categ_id": self.famille.id, "pct": 20.0})
        w.action_appliquer()
        self.assertEqual(self.article.list_price, 180.0)

    def test_famille_sans_choix_leve(self):
        from odoo.exceptions import UserError
        w = self.env["cultiveau.hausse.prix"].create({"cible": "achat", "perimetre": "famille", "pct": 10.0})
        with self.assertRaises(UserError):
            w.action_appliquer()


@tagged("post_install", "-at_install", "cultiveau_tarifs")
class TestCommissions(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.company.cultiveau_commission_pct = 5.0
        self.commercial = self.env["res.users"].create({
            "name": "Commercial test", "login": "commercial_test_commission", "company_id": self.company.id,
            "company_ids": [(6, 0, [self.company.id])], "cultiveau_commission_pct": 10.0})
        self.article = self.env["product.template"].create({
            "name": "Article commission", "type": "consu", "standard_price": 60.0, "list_price": 100.0, "sale_ok": True, "company_id": False})
        self.client = self.env["res.partner"].create({"name": "Client commission"})

    def _facture(self, user, prix, qte=1.0):
        move = self.env["account.move"].create({
            "move_type": "out_invoice", "partner_id": self.client.id, "invoice_user_id": user.id, "company_id": self.company.id,
            "invoice_line_ids": [(0, 0, {"product_id": self.article.product_variant_id.id, "quantity": qte, "price_unit": prix})]})
        move.action_post()
        return move

    def test_commission_sur_marge(self):
        self._facture(self.commercial, 100.0)  # CA 100, coût 60, marge 40, taux 10 % -> 4
        w = self.env["cultiveau.commission"].create({"base": "marge"})
        w.action_calculer()
        ligne = w.ligne_ids.filtered(lambda l: l.commercial_id == self.commercial)
        self.assertTrue(ligne)
        self.assertAlmostEqual(ligne.ca, 100.0, 2)
        self.assertAlmostEqual(ligne.marge, 40.0, 2)
        self.assertAlmostEqual(ligne.commission, 4.0, 2)

    def test_commission_sur_ca_et_taux_defaut(self):
        autre = self.env["res.users"].create({
            "name": "Sans taux", "login": "commercial_sans_taux", "company_id": self.company.id, "company_ids": [(6, 0, [self.company.id])]})
        self._facture(autre, 200.0)  # taux par défaut 5 % sur CA 200 -> 10
        w = self.env["cultiveau.commission"].create({"base": "ca"})
        w.action_calculer()
        ligne = w.ligne_ids.filtered(lambda l: l.commercial_id == autre)
        self.assertAlmostEqual(ligne.commission, 10.0, 2)
