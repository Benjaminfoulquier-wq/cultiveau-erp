from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")


class TestEuro(TransactionCase):
    def test_les_societes_sont_en_euros(self):
        dollar = self.env.ref("base.USD")
        dollar.active = True
        societe = self.env["res.company"].create({"name": "Adhérent sans devise"})
        self.assertEqual((societe.currency_id, societe.country_id), (self.env.ref("base.EUR"), self.env.ref("base.fr")))
        societe.write({"currency_id": dollar.id})
        self.env["res.company"].cultiveau_tout_en_euros()
        self.assertEqual(societe.currency_id, self.env.ref("base.EUR"))
