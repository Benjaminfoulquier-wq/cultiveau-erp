import base64

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

CLIENTS = "Nom;Exploitation;Téléphone;Code postal;Ville;Culture\nDurand Paul;EARL des Vignes;0600000001;32000;Auch;Maïs\nMairie de Fleurance;;0562000000;32500;Fleurance;\n".encode("cp1252")
ARTICLES = "Référence;Désignation;Famille;Prix de vente HT;Prix d'achat HT;TVA %\nTUB-PE-32;Tube PE 32 PN10;Tuyaux;1,45;0,98;20\nVAN-1P;Vanne 1 pouce;Vannes;12,90;8,10;20\n".encode("cp1252")


@tagged("post_install", "-at_install")
class TestAdhesion(TransactionCase):
    def test_parcours_complet(self):
        a = self.env["cultiveau.adhesion"].with_context(chart_template_load=True).create({
            "name": "Irrigation du Gers", "siret": "123 456 789 00012", "zip": "32000", "city": "Auch", "email": "contact@exemple.fr",
            "numero_dedie": "+33562000001", "assistant_id": 12, "regime_tva": "trimestriel",
            "utilisateur_ids": [Command.create({"name": "Jean Gérant", "email": "jean@exemple.fr", "role": "gerant"}),
                                Command.create({"name": "Léa Terrain", "email": "lea@exemple.fr", "role": "technicien"})]})
        with self.assertRaises(UserError):  # pas de société encore
            a.action_inviter()
        a.action_creer_societe()
        s = a.company_id
        self.assertEqual((s.company_registry, s.country_id.code, s.chart_template, s.cultiveau_regime_tva, a.etat), ("12345678900012", "FR", "fr", "trimestriel", "utilisateurs"))
        self.assertIn(s, self.env.user.company_ids)
        a.action_inviter()
        jean, lea = a.utilisateur_ids.mapped("user_id")
        self.assertTrue(jean.has_group("account.group_account_manager") and jean.has_group("sales_team.group_sale_manager"))
        self.assertTrue(lea.has_group("project.group_project_user") and not lea.has_group("account.group_account_manager"))
        self.assertEqual((jean.company_id, jean.login), (s, "jean@exemple.fr"))
        a.action_assistant()
        self.assertEqual((s.cultiveau_numero_dedie, s.cultiveau_assistant_id), ("+33562000001", 12))
        a.write({"fichier_clients": base64.b64encode(CLIENTS), "nom_fichier_clients": "clients.csv"})
        a.action_importer_clients()
        self.assertIn("2 clients créés", a.bilan_clients)
        clients = self.env["res.partner"].search([("company_id", "=", s.id), ("name", "ilike", "Fleurance")])
        self.assertTrue(clients)
        a.write({"fichier_articles": base64.b64encode(ARTICLES), "nom_fichier_articles": "articles.csv"})
        a.action_importer_articles()
        self.assertIn("2 articles créés", a.bilan_articles)
        self.assertTrue(self.env["product.template"].with_company(s).search([("default_code", "=", "TUB-PE-32")]))
        a.comptable_email = "cabinet@exemple.fr"
        a.action_compta()
        self.assertTrue(s.cultiveau_compta_en_place)
        self.assertTrue(self.env["res.users"].search([("login", "=", "cabinet@exemple.fr")]).has_group("account.group_account_readonly"))
        self.env["ir.config_parameter"].sudo().set_param("auth_totp.policy", "")
        with self.assertRaises(UserError):  # la plateforme exige la double authentification
            a.action_efacture()
        a.action_terminer()
        self.assertEqual(a.etat, "fini")
        self.assertGreaterEqual(a.progression, 85)
