import json
from unittest import mock

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from ..models import mathis


def _reponse(message):
    """La réponse du modèle, au format de son API : des blocs de texte et d'appel d'outil (avec un bloc de réflexion, ignoré)."""
    blocs = [{"type": "thinking", "thinking": "", "signature": "sig"}]
    if message.get("content"):
        blocs.append({"type": "text", "text": message["content"]})
    for a in message.get("tool_calls") or []:
        blocs.append({"type": "tool_use", "id": a["id"], "name": a["function"]["name"], "input": json.loads(a["function"]["arguments"])})
    return mock.Mock(status_code=200, text="", json=lambda: {"role": "assistant", "content": blocs, "stop_reason": "tool_use" if message.get("tool_calls") else "end_turn"})


@tagged("post_install", "-at_install", "cultiveau")
class TestMathis(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["ir.config_parameter"].sudo().set_param("cultiveau.mathis_cle", "cle-test")
        cls.agri = cls.env["res.partner"].create({"name": "Agriculteur Mathis", "cultiveau_type": "agriculteur", "company_id": cls.env.company.id, "phone": "0600000000"})

    def test_sans_cle(self):
        self.env["ir.config_parameter"].sudo().set_param("cultiveau.mathis_cle", "")
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
        self.assertEqual(roles, ["user", "assistant", "user"])
        self.assertEqual(envoi["messages"][1]["content"][-1]["type"], "tool_use")
        resultat = envoi["messages"][-1]["content"][0]
        self.assertEqual((resultat["type"], resultat["tool_use_id"]), ("tool_result", "abc123def"))
        self.assertIn("Agriculteur Mathis", resultat["content"])
        self.assertTrue(any(o["name"] == "equipe" and "input_schema" in o for o in envoi["tools"]))
        self.assertEqual(envoi["model"], "claude-opus-5-5")
        self.assertNotIn("thinking", json.dumps(envoi["messages"]))
        self.assertEqual(post.call_args_list[1].args[0], "https://api.anthropic.com/v1/messages")
        self.assertEqual(post.call_args_list[1].kwargs["headers"]["x-api-key"], "cle-test")
        self.assertIn("cache_control", envoi["system"][0])
        self.assertNotIn("il est", envoi["system"][0]["text"])
        self.assertIn("il est", envoi["system"][1]["text"])
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

    def test_dictee(self):
        import base64
        self.env["ir.config_parameter"].sudo().set_param("cultiveau.mistral_cle", "cle-test")
        reponse = mock.Mock(status_code=200, raise_for_status=lambda: None, json=lambda: {"text": " Qui est en intervention cet après-midi ? "})
        with mock.patch.object(mathis.requests, "post", return_value=reponse) as post:
            r = self.env["cultiveau.mathis"].transcrire(base64.b64encode(b"son").decode(), "audio/webm;codecs=opus")
        self.assertEqual(r["texte"], "Qui est en intervention cet après-midi ?")
        self.assertIn("/audio/transcriptions", post.call_args.args[0])
        self.assertEqual(post.call_args.kwargs["data"]["model"], "voxtral-mini-latest")
        self.assertEqual(post.call_args.kwargs["files"]["file"][0], "dictee.webm")
        with self.assertRaises(UserError):
            self.env["cultiveau.mathis"].transcrire("", "audio/webm")
        self.env["ir.config_parameter"].sudo().set_param("cultiveau.mistral_cle", "")
        with self.assertRaises(UserError):
            self.env["cultiveau.mathis"].transcrire(base64.b64encode(b"son").decode())


@tagged("post_install", "-at_install", "cultiveau")
class TestMathisTout(TransactionCase):
    """Mathis fait ce que la personne peut faire : lire, créer, modifier, appuyer sur un bouton, avec confirmation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["ir.config_parameter"].sudo().set_param("cultiveau.mathis_cle", "cle-test")
        cls.client = cls.env["res.partner"].create({"name": "GAEC du Test Mathis", "company_id": cls.env.company.id})
        cls.article = cls.env["product.product"].create({"name": "Vanne de test Mathis", "list_price": 42.0, "sale_ok": True})
        cls.M = cls.env["cultiveau.mathis"]

    def test_outils_generaux_presents(self):
        noms = {o["function"]["name"] for o in self.M._outils()}
        self.assertTrue({"types_de_fiche", "champs_et_boutons", "trouver_fiches", "compter_fiches", "creer_fiche", "modifier_fiche", "appuyer_bouton"} <= noms)
        self.assertTrue({"creer_fiche", "modifier_fiche", "appuyer_bouton"} <= self.M._ecritures())
        self.assertIn("types_de_fiche", self.M._systeme())

    def test_cle_depuis_le_panneau(self):
        self.env["ir.config_parameter"].sudo().set_param("cultiveau.mathis_cle", "")
        self.assertFalse(self.M.ouvrir()["pret"])
        with self.assertRaises(UserError):
            self.M.regler_cle("trop court")
        r = self.M.regler_cle("  cle-de-test-assez-longue-0123456789  ")
        self.assertTrue(r["pret"])
        self.assertNotIn("cle-de-test", json.dumps(r))
        simple = self.env["res.users"].create({"name": "Salarié sans droit", "login": "salarie.mathis@test.fr", "groups_id": [(6, 0, [self.env.ref("base.group_user").id])]})
        with self.assertRaises(UserError):
            self.M.with_user(simple).regler_cle("cle-de-test-assez-longue-0123456789")
        # un gérant pose la première clé, mais ne remplace pas une clé déjà là
        gerant = self.env["res.users"].create({"name": "Gérant Mathis", "login": "gerant.mathis@test.fr",
                                               "groups_id": [(6, 0, [self.env.ref("base.group_user").id, self.env.ref("sales_team.group_sale_manager").id])]})
        self.assertFalse(self.M.with_user(gerant).ouvrir()["admin"])
        with self.assertRaises(UserError):
            self.M.with_user(gerant).regler_cle("une-autre-cle-assez-longue-0123456789")
        self.env["ir.config_parameter"].sudo().set_param("cultiveau.mathis_cle", "")
        self.assertTrue(self.M.with_user(gerant).ouvrir()["admin"])
        with self.assertRaises(UserError):
            self.M.with_user(simple).regler_cle("cle-de-test-assez-longue-0123456789")
        self.assertTrue(self.M.with_user(gerant).regler_cle("cle-du-gerant-assez-longue-0123456789")["pret"])

    def test_refus_et_cle_refusee(self):
        refus = mock.Mock(status_code=200, text="", json=lambda: {"content": [], "stop_reason": "refusal"})
        with mock.patch.object(mathis.requests, "post", side_effect=[refus]):
            r = self.M.repondre(None, "Une demande déclinée")
        self.assertIn("ne peux pas", r["messages"][-1]["texte"])
        with mock.patch.object(mathis.requests, "post", side_effect=[mock.Mock(status_code=401, text="invalid x-api-key")]):
            with self.assertRaises(UserError) as e:
                self.M.repondre(None, "Bonjour")
        self.assertIn("refusée", str(e.exception))
        self.assertNotIn("nthropic", str(e.exception))

    def test_repli_non_ouvert(self):
        sans = mock.Mock(status_code=400, text='{"error": {"message": "fallbacks: Extra inputs are not permitted"}}')
        with mock.patch.object(mathis.requests, "post", side_effect=[sans, _reponse({"role": "assistant", "content": "Bonjour."})]) as post:
            r = self.M.repondre(None, "Bonjour")
        self.assertEqual(r["messages"][-1]["texte"], "Bonjour.")
        self.assertNotIn("fallbacks", post.call_args_list[1].kwargs["json"])

    def test_lecture(self):
        types, _a = self.M._executer("types_de_fiche", {"texte": "devis"})
        self.assertIn("sale.order", [t["modele"] for t in types])
        fiche, _a = self.M._executer("champs_et_boutons", {"modele": "sale.order"})
        self.assertIn("partner_id", [c["champ"] for c in fiche["champs"]])
        self.assertIn("action_confirm", [b["bouton"] for b in fiche["boutons"]])
        res, _a = self.M._executer("trouver_fiches", {"modele": "res.partner", "texte": "GAEC du Test Mathis"})
        self.assertEqual(res["fiches"][0]["id"], self.client.id)
        res, _a = self.M._executer("trouver_fiches", {"modele": "product.product", "filtres": [{"champ": "list_price", "operateur": "=", "valeur": "42"}, {"champ": "name", "operateur": "ilike", "valeur": "test Mathis"}]})
        self.assertEqual([f["id"] for f in res["fiches"]], [self.article.id])
        res, _a = self.M._executer("compter_fiches", {"modele": "res.partner", "filtres": [{"champ": "id", "operateur": "=", "valeur": str(self.client.id)}]})
        self.assertEqual(res["nombre"], 1)

    def test_garde_fous(self):
        for modele in ("res.users", "ir.config_parameter", "res.groups", "cultiveau.api.cle", "n.existe.pas", "mail.compose.message"):
            with self.assertRaises(UserError):
                self.M._executer("trouver_fiches", {"modele": modele})
        with self.assertRaises(UserError):
            self.M._verifier("creer_fiche", {"modele": "res.partner", "valeurs": {"champ_invente": 1}})
        with self.assertRaises(UserError):
            self.M._verifier("appuyer_bouton", {"modele": "sale.order", "ids": [1], "bouton": "unlink"})
        with self.assertRaises(UserError):
            self.M._verifier("modifier_fiche", {"modele": "res.partner", "ids": [self.client.id], "valeurs": {"signup_token": "x"}})
        with self.assertRaises(UserError):
            self.M._verifier("creer_fiche", {"modele": "sale.order", "valeurs": {"partner_id": "Client qui n'existe nulle part 9731"}})

    def test_devis_cree_puis_confirme(self):
        creer = {"id": "cre000001", "type": "function", "function": {"name": "creer_fiche", "arguments": json.dumps({
            "modele": "sale.order", "valeurs": {"partner_id": "GAEC du Test Mathis", "order_line": [{"product_id": self.article.id, "product_uom_qty": 3}]}})}}
        with mock.patch.object(mathis.requests, "post", side_effect=[_reponse({"role": "assistant", "content": "", "tool_calls": [creer]})]):
            r = self.M.repondre(None, "Fais un devis de 3 vannes de test pour le GAEC du Test Mathis et confirme-le")
        self.assertEqual(len(r["propositions"]), 1)
        self.assertIn("GAEC du Test Mathis", r["propositions"][0]["resume"])
        self.assertIn("1 ligne", r["propositions"][0]["resume"])
        self.assertFalse(self.env["sale.order"].search([("partner_id", "=", self.client.id)]))

        def suite(*a, **k):
            # après la confirmation, le modèle enchaîne : il propose de confirmer le devis qu'il vient de créer
            devis = self.env["sale.order"].search([("partner_id", "=", self.client.id)])
            bouton = {"id": "btn000002", "type": "function", "function": {"name": "appuyer_bouton", "arguments": json.dumps({"modele": "sale.order", "ids": devis.ids, "bouton": "action_confirm"})}}
            return _reponse({"role": "assistant", "content": "Le devis est créé. Je le confirme ?", "tool_calls": [bouton]})

        with mock.patch.object(mathis.requests, "post", side_effect=suite):
            r = self.M.confirmer(r["conversation_id"], "cre000001", True)
        devis = self.env["sale.order"].search([("partner_id", "=", self.client.id)])
        self.assertEqual(len(devis), 1)
        self.assertEqual(devis.order_line.product_uom_qty, 3)
        self.assertEqual(devis.state, "draft")
        self.assertEqual([p["nom"] for p in r["propositions"]], ["appuyer_bouton"])
        self.assertTrue(any(m.get("action") and m["action"].get("modele") == "sale.order" for m in r["messages"]))
        with mock.patch.object(mathis.requests, "post", side_effect=[_reponse({"role": "assistant", "content": "C'est confirmé."})]):
            r = self.M.confirmer(r["conversation_id"], "btn000002", True)
        self.assertEqual(devis.state, "sale")
        self.assertEqual(r["propositions"], [])

    def test_proposition_impossible_rendue_au_modele(self):
        mauvais = {"id": "bad000001", "type": "function", "function": {"name": "creer_fiche", "arguments": json.dumps({"modele": "res.users", "valeurs": {"name": "Intrus"}})}}
        reponses = [_reponse({"role": "assistant", "content": "", "tool_calls": [mauvais]}), _reponse({"role": "assistant", "content": "Je ne peux pas créer de compte."})]
        with mock.patch.object(mathis.requests, "post", side_effect=reponses) as post:
            r = self.M.repondre(None, "Crée un utilisateur Intrus")
        self.assertEqual(r["propositions"], [])
        self.assertIn("erreur", post.call_args_list[1].kwargs["json"]["messages"][-1]["content"][0]["content"])

    def test_modifier_et_archiver(self):
        self.M._executer("modifier_fiche", {"modele": "res.partner", "ids": [self.client.id], "valeurs": {"city": "Gaillac", "active": False}})
        self.assertEqual(self.client.city, "Gaillac")
        self.assertFalse(self.client.active)
