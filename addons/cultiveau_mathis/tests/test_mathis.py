import json
from unittest import mock

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from ..models import mathis


def _reponse(message):
    return mock.Mock(status_code=200, json=lambda: {"choices": [{"message": message}]})


@tagged("post_install", "-at_install", "cultiveau")
class TestMathis(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["ir.config_parameter"].sudo().set_param("cultiveau.mistral_cle", "cle-test")
        cls.agri = cls.env["res.partner"].create({"name": "Agriculteur Mathis", "cultiveau_type": "agriculteur", "company_id": cls.env.company.id, "phone": "0600000000"})

    def test_sans_cle(self):
        self.env["ir.config_parameter"].sudo().set_param("cultiveau.mistral_cle", "")
        self.assertFalse(self.env["cultiveau.mathis"].pret())
        with self.assertRaises(UserError):
            self.env["cultiveau.mathis"].repondre(None, "Bonjour")

    def test_question_avec_outil_de_lecture(self):
        Mathis = self.env["cultiveau.mathis"]
        reponses = [
            _reponse({"role": "assistant", "content": "", "tool_calls": [{"id": "abc123def", "type": "function", "function": {"name": "chercher", "arguments": json.dumps({"texte": "Mathis"})}}]}),
            _reponse({"role": "assistant", "content": "J'ai trouvé [[clients:%d|Agriculteur Mathis]], joignable au 06." % self.agri.id}),
        ]
        with mock.patch.object(mathis.requests, "post", side_effect=reponses) as post:
            r = Mathis.repondre(None, "Trouve le client Mathis")
        self.assertEqual(post.call_count, 2)
        envoi = post.call_args_list[1].kwargs["json"]
        roles = [m["role"] for m in envoi["messages"]]
        self.assertEqual(roles[-3:], ["user", "assistant", "tool"])
        self.assertIn("Agriculteur Mathis", envoi["messages"][-1]["content"])
        self.assertTrue(any(o["function"]["name"] == "equipe" for o in envoi["tools"]))
        self.assertEqual(r["messages"][-1]["role"], "assistant")
        self.assertIn("[[clients:", r["messages"][-1]["texte"])
        self.assertEqual(r["propositions"], [])

    def test_action_confirmee(self):
        Mathis = self.env["cultiveau.mathis"]
        appel = {"id": "xyz987uvw", "type": "function", "function": {"name": "creer_intervention", "arguments": json.dumps({"titre": "Pompe en panne", "urgence": "immediate", "client_id": self.agri.id})}}
        with mock.patch.object(mathis.requests, "post", side_effect=[_reponse({"role": "assistant", "content": "Je crée le dépannage ?", "tool_calls": [appel]})]):
            r = Mathis.repondre(None, "Crée un dépannage urgent pour Agriculteur Mathis : pompe en panne")
        self.assertEqual(len(r["propositions"]), 1)
        self.assertEqual(r["propositions"][0]["nom"], "creer_intervention")
        self.assertFalse(self.env["project.task"].search([("name", "=", "Pompe en panne")]))
        with mock.patch.object(mathis.requests, "post", side_effect=[_reponse({"role": "assistant", "content": "C'est fait, l'intervention est déposée."})]):
            r = Mathis.confirmer(r["conversation_id"], "xyz987uvw", True)
        tache = self.env["project.task"].search([("name", "=", "Pompe en panne")])
        self.assertTrue(tache)
        self.assertEqual(tache.partner_id, self.agri)
        self.assertEqual(r["propositions"], [])
        self.assertTrue(any(m.get("action") and m["action"]["modele"] == "project.task" for m in r["messages"]))

    def test_appel_sur_la_map(self):
        a = self.env["cultiveau.appel"].create({"reference": "APPEL-MATHIS-1", "company_id": self.env.company.id, "partner_id": self.agri.id, "sujet": "Pivot arrêté", "urgence": "immediate"})
        e = self.env["cultiveau.evenement"].search([("genre", "=", "appel"), ("res_id", "=", a.id)])
        self.assertTrue(e)
        self.assertIn("Mathis", e.titre)
        f = self.env["cultiveau.map"].fiche("appel", a.id)
        self.assertEqual(f["client"], "Agriculteur Mathis")
        d = self.env["cultiveau.map"].vivant()
        self.assertEqual(d["assistant"]["appels"][0]["id"], a.id)
