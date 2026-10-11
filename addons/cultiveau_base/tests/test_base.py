from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")


class TestEuro(TransactionCase):
    def test_les_societes_sont_en_euros(self):
        dollar = self.env.ref("base.USD")
        dollar.active = True
        societe = self.env["res.company"].create({"name": "Adhérent sans devise"})
        self.assertEqual((societe.currency_id, societe.country_id), (self.env.ref("base.EUR"), self.env.ref("base.fr")))
        societe.write({"currency_id": dollar.id})
        liste = self.env["product.pricelist"].create({"name": "Liste en dollars", "currency_id": dollar.id}) if "product.pricelist" in self.env else None
        self.env["res.company"].cultiveau_tout_en_euros()
        self.assertEqual(societe.currency_id, self.env.ref("base.EUR"))
        if liste:
            self.assertEqual(liste.currency_id, self.env.ref("base.EUR"))
        self.assertEqual(self.env.ref("base.user_admin").lang, "fr_FR")
