import json

from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install", "cultiveau")
class TestMarque(HttpCase):
    def test_adresse_app_et_couleurs(self):
        # L'ancienne adresse renvoie pour toujours vers /app, avec son chemin et ses paramètres.
        r = self.url_open("/odoo/action-12?debug=1", allow_redirects=False)
        self.assertEqual((r.status_code, r.headers["Location"]), (301, "/app/action-12?debug=1"))
        r = self.url_open("/odoo", allow_redirects=False)
        self.assertEqual((r.status_code, r.headers["Location"]), (301, "/app"))
        # La racine et la connexion mènent à /app, jamais à l'ancienne adresse.
        r = self.url_open("/", allow_redirects=False)
        self.assertEqual(r.headers["Location"], "/app")
        r = self.url_open("/app", allow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertIn("/web/login?redirect=%2Fapp", r.headers["Location"])
        self.assertNotIn("odoo", r.headers["Location"].lower())
        self.authenticate("admin", "admin")
        r = self.url_open("/app/action-cultiveau_base.action_agriculteurs")
        self.assertEqual(r.status_code, 200)
        self.assertIn('<meta name="theme-color" content="#183840"/>', r.text)
        self.assertNotIn("#71639e", r.text)
        self.assertIn("<title>Cultiveau</title>", r.text)
        # Le manifeste de l'application et la page hors ligne sont aux couleurs et au nom de Cultiveau.
        manifeste = json.loads(self.url_open("/web/manifest.webmanifest").text)
        self.assertEqual((manifeste["name"], manifeste["scope"], manifeste["start_url"], manifeste["theme_color"]), ("Cultiveau", "/app", "/app", "#183840"))
        self.assertTrue(all(i["src"].startswith("/cultiveau_marque/") for i in manifeste["icons"]))
        self.assertTrue(all(r["url"].startswith("/app") for r in manifeste["shortcuts"]))
        sw = self.url_open("/web/service-worker.js")
        self.assertEqual(sw.headers["Service-Worker-Allowed"], "/app")
        self.assertNotIn("/odoo", sw.text)
        self.assertEqual(self.url_open("/app/offline").status_code, 200)
