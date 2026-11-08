import base64
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
        self.ouverte = self.env["res.company"].create({"name": "Irrigation Sud", "cultiveau_site_id": 31, "cultiveau_erp_ouvert": True, "iap_enrich_auto_done": True})

    def test_tout_le_monde_n_a_pas_l_erp(self):
        fermee = dict(charge(email="jean@irrigation-nord.fr", n="n9"), entreprise={"id": 99, "nom": "Irrigation Nord"})
        r = self.url_open("/cultiveau/entree?t=" + fabriquer_jeton(fermee, SECRET), allow_redirects=False)
        self.assertIn("pas encore acc", r.text)
        self.assertFalse(self.env["res.users"].search([("login", "=", "jean@irrigation-nord.fr")]))
        self.assertFalse(self.env["res.company"].search([("name", "=", "Irrigation Nord")]))
        # la question d'éligibilité répond la même chose, signée
        q = {"v": 1, "outil": "erp", "action": "eligible", "exp": int(time.time()) + 60, "email": "jean@irrigation-nord.fr", "entreprise": {"id": 99, "nom": "Irrigation Nord"}}
        r = self.url_open("/cultiveau/entree/eligible?t=" + fabriquer_jeton(q, SECRET))
        self.assertFalse(r.json()["eligible"])
        q["entreprise"] = {"id": 31, "nom": "Irrigation Sud"}
        r = self.url_open("/cultiveau/entree/eligible?t=" + fabriquer_jeton(q, SECRET))
        self.assertTrue(r.json()["eligible"])
        # un compte déjà existant entre toujours, même si son entreprise n'est pas cochée
        q["email"] = "admin"
        r = self.url_open("/cultiveau/entree/eligible?t=" + fabriquer_jeton(q, SECRET))
        self.assertTrue(r.json()["eligible"])

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
        self.assertEqual((user.name, user.company_id, user.company_id.cultiveau_site_id), ("Paul Durand", self.ouverte, 31))
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
        self.assertEqual(self.env["res.company"].search_count([]), n_societes)  # pas de société en double
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


    def test_le_chantier_de_l_erp_tombe_dans_mon_chantier(self):
        from ..models.chantier_site import Connexion as CxEnvoi
        cx = self.env["cultiveau.site.connexion"].create({"company_id": self.ouverte.id, "url": "https://site.test", "cle": "cle-test", "cultiveau_site_ecriture": True})
        agri = self.env["res.partner"].create({"name": "GAEC du Roc", "phone": "05 63 00 00 00", "email": "roc@exemple.fr", "street": "Le Roc", "zip": "81600", "city": "Gaillac", "cultiveau_type": "agriculteur"})
        inst = self.env["cultiveau.installation"].create({"name": "Station de pompage 30 m³/h", "partner_id": agri.id, "type_systeme": "mixte", "company_id": self.ouverte.id})
        envois = []

        def poster(self_, chemin, donnees):
            envois.append((chemin, donnees))
            return 201, {"success": True, "chantierId": 4242, "reference": "CH-26-0051", "phases": [{"id": 1}, {"id": 2}]}
        with patch.object(CxEnvoi, "_poster", poster):
            ch = self.env["cultiveau.chantier"].with_company(self.ouverte).create({"titre": "Station de pompage GAEC du Roc", "installation_id": inst.id, "company_id": self.ouverte.id,
                                                                                    "date_debut": "2026-11-16", "date_fin": "2026-11-20", "etat": "planifie",
                                                                                    "phase_ids": [(0, 0, {"name": "Terrassement", "heures_prevues": 16, "date_debut": "2026-11-16", "date_fin": "2026-11-17"}),
                                                                                                  (0, 0, {"name": "Pose et raccordement", "heures_prevues": 24})]})
            self.assertTrue(ch.cultiveau_site_a_envoyer)
            self.assertEqual(ch.cultiveau_envoyer_vers_site(), 1)
        chemin, d = envois[0]
        self.assertEqual(chemin, "chantiers")
        self.assertEqual((d["name"], d["clientName"], d["clientPostalCode"], d["status"], d["startDate"], d["endDate"]), ("Station de pompage GAEC du Roc", "GAEC du Roc", "81600", "planifie", "2026-11-16", "2026-11-20"))
        self.assertEqual([p["name"] for p in d["phases"]], ["Terrassement", "Pose et raccordement"])
        self.assertEqual(d["phases"][0]["estimatedHours"], 16)
        self.assertEqual(d["estimatedHours"], 40)
        self.assertEqual(ch.cultiveau_site_ref, f"{cx.id}:4242")
        self.assertFalse(ch.cultiveau_site_a_envoyer)
        # un deuxième envoi ne crée rien : le site le connaît déjà
        with patch.object(CxEnvoi, "_poster", poster):
            self.assertEqual(ch.cultiveau_envoyer_vers_site(), 0)
        self.assertEqual(len(envois), 1)

    def test_lancer_le_chantier_ouvre_mon_chantier(self):
        """« Lancer le chantier » depuis la commande : le chantier naît dans Mon Chantier et c'est la fiche du site qui s'ouvre, dans l'ERP."""
        from ..models.chantier_site import Connexion as CxEnvoi
        self.env["cultiveau.site.connexion"].create({"company_id": self.ouverte.id, "url": "https://site.test", "cle": "cle-test", "cultiveau_site_ecriture": True})
        if "cultiveau_decl_chantier" in self.ouverte._fields:  # ici on teste le bouton, pas le déclenchement automatique à la confirmation
            (self.ouverte | self.env.company).write({"cultiveau_decl_chantier": False})
        agri = self.env["res.partner"].create({"name": "EARL des Vergers", "cultiveau_type": "agriculteur", "company_id": self.ouverte.id})
        tube = self.env["product.product"].create({"name": "Tube PE 63", "type": "consu", "list_price": 3})
        commande = self.env["sale.order"].with_company(self.ouverte).create({"partner_id": agri.id, "company_id": self.ouverte.id, "cultiveau_type_systeme": "pivot",
                                                                             "order_line": [(0, 0, {"product_id": tube.id, "product_uom_qty": 50})]})
        commande.action_confirm()
        with patch.object(CxEnvoi, "_poster", lambda self_, chemin, d: (201, {"success": True, "chantierId": 777, "reference": "CH-26-0077"})):
            action = commande.with_company(self.ouverte).action_lancer_chantier()
        self.assertEqual((action["type"], action["tag"], action["params"]["vers"]), ("ir.actions.client", "cultiveau_site.ecran", "/adherent/chantier?id=777"))
        chantier = self.env["cultiveau.chantier"].search([("sale_order_id", "=", commande.id)])
        self.assertEqual(chantier.cultiveau_site_ref.split(":")[-1], "777")
        self.assertEqual(chantier.action_ouvrir_dans_site()["params"]["vers"], "/adherent/chantier?id=777")
        self.assertEqual(commande.action_voir_chantiers()["tag"], "cultiveau_site.ecran")
        # sans liaison au site : la fiche de l'ERP, comme avant
        agri2 = self.env["res.partner"].create({"name": "EARL sans site", "cultiveau_type": "agriculteur"})
        autre = self.env["sale.order"].create({"partner_id": agri2.id, "cultiveau_type_systeme": "pivot", "order_line": [(0, 0, {"product_id": tube.id, "product_uom_qty": 1})]})
        autre.action_confirm()
        self.assertEqual(autre.action_lancer_chantier()["res_model"], "cultiveau.chantier")

    def test_cle_en_lecture_seule_remplacee(self):
        from ..models.chantier_site import Connexion as CxEnvoi
        cx = self.env["cultiveau.site.connexion"].create({"company_id": self.ouverte.id, "url": "https://site.test", "cle": "vieille", "cultiveau_site_adherent_id": 77})
        agri = self.env["res.partner"].create({"name": "EARL Test", "cultiveau_type": "agriculteur"})
        inst = self.env["cultiveau.installation"].create({"name": "Projet", "partner_id": agri.id, "type_systeme": "mixte", "company_id": self.ouverte.id})
        codes = iter([(403, {"error": "scope"}), (201, {"chantierId": 7, "reference": "CH-26-0052"})])
        redemandes = []

        def relier(self_, company, charge, forcer=False):
            redemandes.append((company.name, charge.get("cultiveau_id"), forcer))
            cx.write({"cle": "neuve", "cultiveau_site_ecriture": True})
            return True
        with patch.object(CxEnvoi, "_poster", lambda self_, chemin, d: next(codes)), patch.object(ConnexionModele, "_cultiveau_relier_si_besoin", relier):
            ch = self.env["cultiveau.chantier"].create({"titre": "Essai", "installation_id": inst.id, "company_id": self.ouverte.id})
            self.assertEqual(ch.cultiveau_envoyer_vers_site(), 1)
        self.assertEqual(redemandes, [("Irrigation Sud", 77, True)])
        self.assertEqual(ch.cultiveau_site_ref, f"{cx.id}:7")

    def test_le_logo_vient_de_cultiveau_fr(self):
        import requests as req

        class Reponse:
            status_code = 200
            headers = {"Content-Type": "image/png"}
            content = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")
        appels = []

        def get(url, timeout=20, **kw):
            appels.append(url)
            return Reponse()
        with patch.object(req, "get", get), patch.object(ConnexionModele, "_cultiveau_relier_si_besoin", lambda self_, c, ch, forcer=False: False):
            ch = charge(email="logo@irrigation-sud.fr", n="n7")
            ch["entreprise"]["logo_url"] = "https://site.test/api/adherent-image/77/logo"
            self.url_open("/cultiveau/entree?t=" + fabriquer_jeton(ch, SECRET), allow_redirects=False)
        self.ouverte.invalidate_recordset()
        self.assertEqual(appels, ["https://site.test/api/adherent-image/77/logo"])
        self.assertTrue(self.ouverte.logo)
        self.assertEqual(self.ouverte.cultiveau_site_logo_url, "https://site.test/api/adherent-image/77/logo")
