from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "cultiveau")
class TestExpediteur(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write({"name": "Durand Irrigation", "email": "contact@durand-irrigation.test", "cultiveau_envoi": "reseau"})
        cls.agri = cls.env["res.partner"].create({"name": "Earl du Moulin", "email": "moulin@example.test", "cultiveau_type": "agriculteur"})
        cls.produit = cls.env["product.product"].create({"name": "Filtre", "list_price": 100.0, "type": "consu"})
        cls.devis = cls.env["sale.order"].create({"partner_id": cls.agri.id, "order_line": [Command.create({"product_id": cls.produit.id, "product_uom_qty": 1})]})

    def test_reseau_au_nom_de_l_adherent(self):
        self.assertIn("Durand Irrigation <notification@cultiveau.fr>", self.company.cultiveau_expediteur_apercu)
        m = self.env["mail.mail"].create({"subject": "Votre devis", "body_html": "<p>Bonjour</p>", "email_to": "moulin@example.test", "model": "sale.order", "res_id": self.devis.id})
        self.assertEqual(m.email_from, "Durand Irrigation <notification@cultiveau.fr>")
        self.assertEqual(m.reply_to, "Durand Irrigation <contact@durand-irrigation.test>")
        self.assertFalse(m.mail_server_id)
        # un message du fil (réponse au client) suit la même règle
        msg = self.devis.with_context(mail_notify_force_send=False).message_post(body="Bonjour, voici le devis.", message_type="comment", subtype_xmlid="mail.mt_comment", partner_ids=self.agri.ids)
        mails = self.env["mail.mail"].search([("mail_message_id", "=", msg.id)])
        self.assertTrue(mails)
        self.assertTrue(all(x.email_from == "Durand Irrigation <notification@cultiveau.fr>" for x in mails))

    def test_boite_de_l_adherent(self):
        serveur = self.env["ir.mail_server"].create({"name": "Boîte Durand", "smtp_host": "smtp.example.test", "smtp_user": "devis@durand-irrigation.test", "from_filter": "devis@durand-irrigation.test"})
        boite = self.env["cultiveau.boite"].create({"name": "Devis", "adresse": "devis@durand-irrigation.test", "fournisseur": "imap", "company_id": self.company.id, "partagee": True})
        boite.write({"mail_server_id": serveur.id, "etat": "connectee"})
        self.company.write({"cultiveau_envoi": "boite", "cultiveau_boite_envoi_id": boite.id})
        self.assertIn("devis@durand-irrigation.test", self.company.cultiveau_expediteur_apercu)
        m = self.env["mail.mail"].create({"subject": "Commande", "body_html": "<p>Merci</p>", "email_to": "moulin@example.test", "model": "sale.order", "res_id": self.devis.id})
        self.assertEqual(m.email_from, "Durand Irrigation <devis@durand-irrigation.test>")
        self.assertEqual(m.mail_server_id, serveur)
        # boîte débranchée : le réseau reprend
        boite.etat = "a_connecter"
        m2 = self.env["mail.mail"].create({"subject": "Commande", "body_html": "<p>Merci</p>", "email_to": "moulin@example.test", "model": "sale.order", "res_id": self.devis.id})
        self.assertEqual(m2.email_from, "Durand Irrigation <notification@cultiveau.fr>")

    def test_envoi_automatique_ecrit_dans_le_fil(self):
        avant = len(self.devis.message_ids)
        m = self.env["mail.mail"].create({"subject": "Relance automatique", "body_html": "<p>…</p>", "email_to": "moulin@example.test", "model": "sale.order", "res_id": self.devis.id})
        m.write({"state": "sent"})
        m._postprocess_sent_message(success_pids=[])
        notes = self.devis.message_ids[: len(self.devis.message_ids) - avant]
        self.assertTrue(any("Relance automatique" in (n.body or "") for n in notes))
        self.assertTrue(any("notification@cultiveau.fr" in (n.body or "") for n in notes))
