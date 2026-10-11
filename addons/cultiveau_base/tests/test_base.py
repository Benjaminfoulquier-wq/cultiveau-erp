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


class TestTypesDeClients(TransactionCase):
    def test_chaque_type_a_son_vehicule(self):
        import base64
        plombier = self.env["res.partner"].create({"name": "Plomberie Durand", "cultiveau_type": "plombier"})
        self.assertTrue(plombier.cultiveau_est_client)
        svg = base64.b64decode(plombier.avatar_128).decode()
        self.assertIn("<svg", svg)
        self.assertIn("#2f7fc1", svg)  # les tuyaux bleus sur la galerie
        plombier.cultiveau_type = "paysagiste"
        self.assertIn("#5fae3e", base64.b64decode(plombier.avatar_128).decode())  # l'herbe sur le plateau
        adherent = self.env["res.partner"].create({"name": "Irrigation Martin", "cultiveau_type": "adherent"})
        self.assertFalse(adherent.cultiveau_est_client)
        self.assertTrue(base64.b64decode(adherent.avatar_128).startswith(b"\x89PNG"))  # pas de véhicule : le portrait standard

    def test_import_reconnait_le_type(self):
        contenu = "Nom;Ville;Type\nMairie de Test-sur-Vidourle;Vauvert;Collectivité\nPaysages Test du Sud;Nîmes;paysagiste\nGAEC Test des Oliviers;Uzès;exploitation agricole\n".encode()
        self.env["cultiveau.import.clients.moteur"].importer("clients.csv", contenu, "particulier", self.env.company)
        Partner = self.env["res.partner"]
        self.assertEqual(Partner.search([("name", "=", "Mairie de Test-sur-Vidourle")]).cultiveau_type, "collectivite")
        self.assertEqual(Partner.search([("name", "=", "Paysages Test du Sud")]).cultiveau_type, "paysagiste")
        self.assertEqual(Partner.search([("name", "=", "GAEC Test des Oliviers")]).cultiveau_type, "agriculteur")
