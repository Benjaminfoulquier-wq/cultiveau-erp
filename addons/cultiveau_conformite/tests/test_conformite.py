import base64
import json

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestConformite(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = cls.env["res.partner"].create({"name": "EARL de l'Audit", "email": "earl@audit-test.fr", "phone": "0611223344", "city": "Auch", "is_company": True})
        cls.contact = cls.env["res.partner"].create({"name": "Agnès Audit", "parent_id": cls.client.id, "email": "agnes@audit-test.fr"})

    def test_journal_avant_apres(self):
        Audit = self.env["cultiveau.audit"]
        self.assertTrue(Audit.search_count([("modele", "=", "res.partner"), ("res_id", "=", self.client.id), ("operation", "=", "creation")]))
        self.client.write({"city": "Condom", "phone": "0611223344"})
        a = Audit.search([("modele", "=", "res.partner"), ("res_id", "=", self.client.id), ("operation", "=", "modification")], limit=1)
        changements = json.loads(a.changements)
        self.assertEqual(len(changements), 1, "seul ce qui change est noté")
        self.assertEqual((changements[0]["avant"], changements[0]["apres"]), ("Auch", "Condom"))
        self.assertIn("Auch", a.resume)
        self.assertEqual(a.user_id, self.env.user)
        self.assertIn("Condom", a.changements_html)
        action = self.client.action_cultiveau_historique()
        self.assertEqual(action["res_model"], "cultiveau.audit")
        produit = self.env["product.template"].create({"name": "Vanne auditée", "list_price": 10})
        produit.list_price = 12
        produit.unlink()
        self.assertTrue(Audit.search_count([("modele", "=", "product.template"), ("operation", "=", "suppression")]))

    def test_rgpd_export_et_effacement(self):
        action = self.client.action_cultiveau_rgpd_export()
        piece = self.env["ir.attachment"].browse(int(action["url"].split("/")[3].split("?")[0]))
        donnees = json.loads(base64.b64decode(piece.datas))
        self.assertEqual(donnees["fiche"][0]["email"], "earl@audit-test.fr")
        self.assertEqual(donnees["contacts"][0]["name"], "Agnès Audit")
        self.client.message_post(body="Appelé pour la remise en route")
        w = self.env["cultiveau.rgpd.effacement"].create({"partner_id": self.client.id})
        self.assertEqual(w.mode, "anonymiser")
        with self.assertRaises(UserError):
            w.action_effacer()
        w.confirmation = "EFFACER"
        w.action_effacer()
        self.assertTrue(self.client.name.startswith("Client effacé"))
        self.assertFalse(self.client.email or self.contact.email)
        self.assertFalse(self.client.active)
        self.assertFalse(self.env["mail.message"].search_count([("model", "=", "res.partner"), ("res_id", "=", self.client.id)]))
        self.assertTrue(self.env["cultiveau.audit"].search_count([("operation", "=", "rgpd"), ("res_id", "=", self.client.id)]))

    def test_reinitialiser_demo(self):
        company = self.env.company
        company.cultiveau_map_demo = True
        self.env["cultiveau.pointage"].badger("arrivee", user=self.env.user, source="demo")
        self.env["cultiveau.evenement"].publier("ambiance", None, "Ambiance", demo=True)
        r = self.env["cultiveau.map"].reinitialiser_demo()
        self.assertGreaterEqual(r["pointages"], 1)
        self.assertFalse(self.env["cultiveau.pointage"].search_count([("company_id", "=", company.id), ("source", "=", "demo")]))
        self.assertFalse(self.env["cultiveau.evenement"].search_count([("company_id", "=", company.id), ("demo", "=", True)]))
