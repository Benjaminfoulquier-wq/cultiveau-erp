from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestEfacture(TransactionCase):
    def test_etat_et_reglages(self):
        societe = self.env["res.company"].with_context(chart_template_load=True).create({"name": "Adhérent E-facture"})
        self.assertEqual(societe.cultiveau_efacture_etat, "non")
        reglages = self.env["res.config.settings"].with_company(societe).create({})
        with self.assertRaises(UserError):  # pas de SIRET : pas d'inscription
            reglages.action_cultiveau_inscription()

    def test_double_authentification(self):
        Societe = self.env["res.company"]
        self.env["ir.config_parameter"].sudo().set_param("auth_totp.policy", "")
        self.assertFalse(Societe.cultiveau_double_authentification())
        self.env["ir.mail_server"].search([]).unlink()
        self.env["ir.config_parameter"].sudo().set_param("mail.catchall.domain", "")
        with self.assertRaises(UserError):  # sans messagerie, on n'enferme personne dehors
            Societe.cultiveau_activer_double_authentification()
        self.env["ir.mail_server"].create({"name": "Messagerie", "smtp_host": "smtp.exemple.fr"})
        Societe.cultiveau_activer_double_authentification()
        self.assertTrue(Societe.cultiveau_double_authentification())

    def test_pas_de_nom_d_editeur(self):
        for modele in ("res.config.settings", "pdp.registration"):
            arch, _ = self.env[modele]._get_view()
            texte = " ".join(arch.xpath("//text()")) + " ".join(arch.xpath("//@string")) + " ".join(arch.xpath("//@help"))
            self.assertNotIn("Odoo", texte, modele)
            self.assertNotIn("odoo.com", texte, modele)
