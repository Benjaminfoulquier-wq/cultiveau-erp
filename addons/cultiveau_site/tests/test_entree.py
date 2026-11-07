import time
from unittest.mock import patch

from odoo.tests import HttpCase, tagged

from ..controllers.ecran import fabriquer_jeton
from ..models.entree import Connexion as ConnexionModele

SECRET = "secret-de-test"


def charge(email="paul@irrigation-sud.fr", role="technicien", vers="/app/sales", n="n1", entreprise=None):
    return {"v": 1, "outil": "erp", "source": "cultiveau", "exp": int(time.time()) + 120, "n": n, "cultiveau_id": 77, "email": email, "nom": "Paul Durand",
            "telephone": "06 12 34 56 78", "fonction": "Poseur", "role": role, "vers": vers,
            "entreprise": entreprise or {"id": 31, "nom": "Irrigation Sud", "telephone": "04 67 00 00 00", "email": "contact@irrigation-sud.fr", "adresse": "12 route des Vignes", "site": "https://irrigation-sud.fr", "departement": "34"}}


@tagged("post_install", "-at_install", "cultiveau")
class TestEntree(HttpCase):
    def setUp(self):
        super().setUp()
        self.env["ir.config_parameter"].sudo().set_param("cultiveau.erp_lien_secret", SECRET)
        self.env["ir.config_parameter"].sudo().set_param("cultiveau.url_site", "https://site.test")

    def test_premiere_entree_cree_entreprise_et_acces(self):
        demandes = []

        def relier(self_, company, ch):
            demandes.append((company.name, ch.get("cultiveau_id")))
            return False
        with patch.object(ConnexionModele, "_cultiveau_relier_si_besoin", relier):
            r = self.url_open("/cultiveau/entree?t=" + fabriquer_jeton(charge(), SECRET), allow_redirects=False)
        self.assertEqual((r.status_code, r.headers.get("Location")), (303, "/app/sales"), r.text[:300])
        user = self.env["res.users"].search([("login", "=", "paul@irrigation-sud.fr")])
        self.assertTrue(user)
        self.assertEqual((user.name, user.company_id.name, user.company_id.cultiveau_site_id), ("Paul Durand", "Irrigation Sud", 31))
        self.assertEqual(user.cultiveau_role, "technicien")
        self.assertEqual(user.partner_id.mobile, "06 12 34 56 78")
        self.assertEqual(user.company_id.partner_id.phone, "04 67 00 00 00")
        self.assertEqual(demandes, [("Irrigation Sud", 77)])
        # la session est ouverte : l'application répond sans renvoyer vers la page de connexion
        r2 = self.url_open("/web/session/get_session_info" if False else "/app", allow_redirects=False)
        self.assertEqual(r2.status_code, 200, r2.headers.get("Location"))
        # le même laissez-passer ne sert pas deux fois
        r3 = self.url_open("/cultiveau/entree?t=" + fabriquer_jeton(charge(), SECRET), allow_redirects=False)
        self.assertIn("déjà utilisé", r3.text)

    def test_le_gerant_entre_avec_son_role_et_la_deuxieme_fois_sans_rien_recreer(self):
        with patch.object(ConnexionModele, "_cultiveau_relier_si_besoin", lambda self_, c, ch: False):
            self.url_open("/cultiveau/entree?t=" + fabriquer_jeton(charge(email="marie@irrigation-sud.fr", role="gerant", n="n2", vers="/app"), SECRET), allow_redirects=False)
            n_societes = self.env["res.company"].search_count([])
            r = self.url_open("/cultiveau/entree?t=" + fabriquer_jeton(charge(email="marie@irrigation-sud.fr", role="gerant", n="n3", vers="/app/project"), SECRET), allow_redirects=False)
        self.assertEqual(r.headers.get("Location"), "/app/project")
        self.assertEqual(self.env["res.company"].search_count([]), n_societes)
        user = self.env["res.users"].search([("login", "=", "marie@irrigation-sud.fr")])
        self.assertEqual(user.cultiveau_role, "gerant")
        self.assertTrue(user.has_group("sales_team.group_sale_manager"))

    def test_refus(self):
        r = self.url_open("/cultiveau/entree?t=" + fabriquer_jeton(charge(n="n4"), "mauvais-secret"), allow_redirects=False)
        self.assertIn("refusé", r.text)
        perime = dict(charge(n="n5"), exp=int(time.time()) - 5)
        r = self.url_open("/cultiveau/entree?t=" + fabriquer_jeton(perime, SECRET), allow_redirects=False)
        self.assertIn("expiré", r.text)
        pas_app = dict(charge(n="n6"), vers="https://ailleurs.example")
        with patch.object(ConnexionModele, "_cultiveau_relier_si_besoin", lambda self_, c, ch: False):
            r = self.url_open("/cultiveau/entree?t=" + fabriquer_jeton(pas_app, SECRET), allow_redirects=False)
        self.assertEqual(r.headers.get("Location"), "/app")
        self.assertFalse(self.env["res.users"].search([("login", "=", "admin")]).cultiveau_role not in (False, "libre"))
