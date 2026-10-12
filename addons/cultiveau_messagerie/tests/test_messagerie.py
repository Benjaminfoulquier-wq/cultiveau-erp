import json
from datetime import timedelta
from email.message import EmailMessage
from email.utils import format_datetime, make_msgid
from unittest import mock

from odoo import fields
from odoo.tests import TransactionCase, tagged

from ..models import courriel as module_courriel


def _courriel(de, objet, texte, a="contact@cultiveau-test.fr", en_reponse=None, masse=False):
    m = EmailMessage()
    m["From"] = de
    m["To"] = a
    m["Subject"] = objet
    m["Message-ID"] = make_msgid(domain="exemple-test.fr")
    m["Date"] = format_datetime(fields.Datetime.now().replace(tzinfo=None).astimezone())
    if en_reponse:
        m["In-Reply-To"] = en_reponse
        m["References"] = en_reponse
    if masse:
        m["List-Unsubscribe"] = "<mailto:desabo@exemple-test.fr>"
    m.set_content(texte)
    return m["Message-ID"], m.as_bytes()


class FauxImap:
    """Une messagerie IMAP en mémoire : réception et envoyés. Note tout ce qui pourrait modifier la boîte."""

    def __init__(self):
        self.recus, self.envoyes, self.modifs, self.dossier, self.lecture_seule = [], [], [], None, []

    def select(self, dossier="INBOX", readonly=False):
        self.dossier = dossier
        self.lecture_seule.append(readonly)
        return "OK", [str(len(self._liste())).encode()]

    def _liste(self):
        return self.recus if self.dossier == "INBOX" else self.envoyes

    def search(self, charset, critere):
        return "OK", [b" ".join(str(i + 1).encode() for i in range(len(self._liste())))]

    def fetch(self, num, quoi):
        if "PEEK" not in quoi:
            self.modifs.append(("fetch", quoi))
        return "OK", [(b"1 (BODY[] {1}", self._liste()[int(num) - 1]), b")"]

    def list(self):
        return "OK", [b'(\\HasNoChildren) "/" "INBOX"', b'(\\HasNoChildren \\Sent) "/" "[Gmail]/Messages envoy&AOk-s"']

    def store(self, *args):
        self.modifs.append(("store", args))

    def logout(self):
        pass


@tagged("post_install", "-at_install")
class TestMessagerie(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["ir.config_parameter"].sudo().set_param("cultiveau.mistral_cle", "")
        cls.company = cls.env.company
        cls.client = cls.env["res.partner"].create({"name": "Domaine des Essais", "is_company": True, "email": "accueil@domaine-essais.fr", "city": "Agen"})
        cls.contact = cls.env["res.partner"].create({"name": "Jeanne Essai", "email": "jeanne@domaine-essais.fr", "parent_id": cls.client.id})
        produit = cls.env["product.product"].create({"name": "Goutteur test", "list_price": 10})
        cls.devis = cls.env["sale.order"].create({"partner_id": cls.client.id, "order_line": [(0, 0, {"product_id": produit.id, "product_uom_qty": 3})]})
        cls.boite = cls.env["cultiveau.boite"].create({"name": "Contact", "adresse": "contact@cultiveau-test.fr", "fournisseur": "imap", "imap_hote": "imap.exemple-test.fr",
                                                       "smtp_hote": "smtp.exemple-test.fr", "identifiant": "contact@cultiveau-test.fr", "mot_de_passe": "secret-test",
                                                       "user_id": cls.env.user.id})
        cls.boite._preparer_serveurs()
        cls.boite.etat = "connectee"

    def setUp(self):
        super().setUp()
        self.imap = FauxImap()

    def _relever(self):
        with mock.patch.object(type(self.env["fetchmail.server"]), "connect", return_value=self.imap):
            return self.boite.relever()

    def _dernier(self):
        return self.env["cultiveau.courriel"].search([("boite_id", "=", self.boite.id)], order="id desc", limit=1)

    def test_serveurs_prepares(self):
        self.assertEqual(self.boite.fetchmail_id.object_id.model, "cultiveau.courriel")
        self.assertEqual(self.boite.fetchmail_id.state, "draft", "la relève standard (qui marque comme lu) n'est pas utilisée")
        self.assertEqual(self.boite.mail_server_id.from_filter, "contact@cultiveau-test.fr")

    def test_rangement_sur_le_devis_et_reponse(self):
        _mid, brut = _courriel("Jeanne Essai <jeanne@domaine-essais.fr>", f"Question sur le devis {self.devis.name}", "Bonjour, pouvez-vous ajouter 20 goutteurs ? Merci")
        self.imap.recus.append(brut)
        self.assertEqual(self._relever(), 1)
        c = self._dernier()
        self.assertEqual(c.partner_id, self.contact)
        self.assertEqual(c.document, self.devis, "la référence citée donne le devis")
        self.assertEqual(c.categorie, "demande")
        self.assertEqual(c.etat, "a_traiter")
        self.assertTrue(any("Courriel reçu" in (m.body or "") for m in self.devis.message_ids), "une note sur le devis")
        self.assertTrue(self.env["cultiveau.evenement"].search_count([("genre", "=", "courriel"), ("res_id", "=", c.id)]))
        # la boîte n'est jamais modifiée
        self.assertFalse(self.imap.modifs)
        self.assertTrue(all(self.imap.lecture_seule))
        # pas de doublon à la relève suivante
        self.assertEqual(self._relever(), 0)
        # la réponse part de la boîte, le client répond dans la boîte
        message = c.message_post(body="Bien sûr, je vous envoie le devis modifié.", message_type="comment", subtype_xmlid="mail.mt_comment", partner_ids=c.partner_id.ids)
        self.assertEqual(c.etat, "repondu")
        self.assertIn("contact@cultiveau-test.fr", message.email_from)
        self.assertIn("contact@cultiveau-test.fr", message.reply_to)
        _mid2, brut2 = _courriel("Jeanne Essai <jeanne@domaine-essais.fr>", "Re: devis", "Merci, et pour la livraison ?", en_reponse=message.message_id)
        self.imap.recus.append(brut2)
        self._relever()
        self.assertEqual(c.etat, "a_traiter", "la réponse du client rouvre le courriel")
        self.assertEqual(self.env["cultiveau.courriel"].search_count([("boite_id", "=", self.boite.id)]), 1)

    def test_domaine_masse_et_envoyes(self):
        _mid, brut = _courriel("Service compta <compta@domaine-essais.fr>", "Facture du mois", "Veuillez trouver notre règlement")
        self.imap.recus.append(brut)
        mid_pub, pub = _courriel("Promo <news@marchand-test.fr>", "Les soldes !", "-50 %", masse=True)
        self.imap.recus.append(pub)
        self._relever()
        compta = self.env["cultiveau.courriel"].search([("expediteur", "ilike", "compta@domaine-essais.fr")])
        self.assertEqual(compta.partner_id, self.client, "le domaine de l'entreprise donne le client")
        self.assertEqual(compta.categorie, "facture")
        publicite = self.env["cultiveau.courriel"].search([("expediteur", "ilike", "news@marchand-test.fr")])
        self.assertEqual(publicite.etat, "classe")
        # une réponse faite depuis la messagerie (dossier Envoyés) compte
        premier = compta.message_ids.filtered(lambda m: m.message_type == "email")[:1]
        _m, envoi = _courriel("contact@cultiveau-test.fr", "Re: Facture du mois", "Bien reçu", a="compta@domaine-essais.fr", en_reponse=premier.message_id)
        self.imap.envoyes.append(envoi)
        self._relever()
        self.assertEqual(compta.etat, "repondu")

    def test_sans_reponse(self):
        _mid, brut = _courriel("Jeanne Essai <jeanne@domaine-essais.fr>", "Ma pompe ne démarre plus", "La pompe est en panne depuis ce matin, c'est urgent")
        self.imap.recus.append(brut)
        self._relever()
        c = self._dernier()
        self.assertEqual(c.categorie, "sav")
        self.assertTrue(c.urgent)
        c.date_reception = fields.Datetime.now() - timedelta(days=7)
        self.env["cultiveau.courriel"]._cron_sans_reponse()
        self.assertTrue(c.sans_reponse)
        self.assertTrue(c.activity_ids, "une activité pour le responsable")
        self.assertTrue(self.env["cultiveau.evenement"].search_count([("genre", "=", "courriel_relance"), ("res_id", "=", c.id)]))
        fiche = self.env["cultiveau.map"].fiche("zone", 0, cle="accueil")
        bloc = next(b for b in fiche["blocs"] if b["titre"].startswith("Courriels à traiter"))
        ligne = next(l for l in bloc["lignes"] if l["ouvrir"]["id"] == c.id)
        self.assertIn("sans réponse", ligne["badge"])
        self.assertTrue(any(b["titre"] == "Courriels" for b in self.env["cultiveau.map"].fiche("client", self.client.id)["blocs"]))

    def test_tri_ia_et_brouillon_mathis(self):
        self.env["ir.config_parameter"].sudo().set_param("cultiveau.mistral_cle", "cle-test")
        tri = {"categorie": "sav", "urgent": True, "attend_reponse": True, "resume": "Fuite sur l'enrouleur", "document": f"sale.order,{self.devis.id}"}
        reponse_tri = mock.Mock(status_code=200, raise_for_status=lambda: None, json=lambda: {"choices": [{"message": {"content": json.dumps(tri)}}]})
        _mid, brut = _courriel("Jeanne Essai <jeanne@domaine-essais.fr>", "Fuite", "Il y a une fuite sur l'enrouleur livré la semaine dernière")
        self.imap.recus.append(brut)
        with mock.patch.object(module_courriel.requests, "post", return_value=reponse_tri):
            self._relever()
        c = self._dernier()
        self.assertEqual((c.categorie, c.urgent, c.resume), ("sav", True, "Fuite sur l'enrouleur"))
        self.assertEqual(c.document, self.devis)
        texte = "Bonjour Madame Essai,\n\nNous passons voir l'enrouleur demain.\n\nCordialement"
        reponse = mock.Mock(status_code=200, raise_for_status=lambda: None, json=lambda: {"choices": [{"message": {"content": texte}}]})
        with mock.patch.object(module_courriel.requests, "post", return_value=reponse) as post:
            action = self.env["cultiveau.courriel"].preparer_reponse(c.id, "dire qu'on passe demain")
        demande = post.call_args.kwargs["json"]["messages"][1]["content"]
        self.assertIn("Domaine des Essais", demande)
        self.assertIn("dire qu'on passe demain", demande)
        self.assertEqual(action["res_model"], "mail.compose.message")
        self.assertIn("<p>Nous passons voir l", action["context"]["default_body"])
        # Mathis
        Mathis = self.env["cultiveau.mathis"]
        self.assertTrue({"courriels", "lire_courriel", "preparer_reponse", "classer_courriel"} <= {o["function"]["name"] for o in Mathis._outils()})
        liste, _a = Mathis._executer("courriels", {"client_id": self.client.id})
        self.assertIn(c.id, [x["id"] for x in liste])
        Mathis._executer("classer_courriel", {"id": c.id})
        self.assertEqual(c.etat, "classe")

    def test_boite_personnelle_privee(self):
        collegue = self.env["res.users"].create({"name": "Colette Collègue", "login": "colette-msg@test.fr", "company_id": self.company.id,
                                                 "company_ids": [(6, 0, self.company.ids)], "groups_id": [(6, 0, [self.env.ref("base.group_user").id])]})
        self.boite.partagee = False
        _mid, brut = _courriel("Jeanne Essai <jeanne@domaine-essais.fr>", "Personnel", "Bonjour")
        self.imap.recus.append(brut)
        self._relever()
        c = self._dernier()
        self.assertFalse(self.env["cultiveau.courriel"].with_user(collegue).search([("id", "=", c.id)]), "une boîte personnelle reste privée")
