from datetime import datetime, timedelta

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "cultiveau")
class TestFeuille(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.agri = cls.env["res.partner"].create({"name": "Earl des Chênes", "street": "12 chemin des Vignes", "zip": "30250", "city": "Sommières", "mobile": "06 00 00 00 01", "cultiveau_type": "agriculteur"})
        cls.poseur = cls.env["hr.employee"].create({"name": "Karim Poseur", "company_id": cls.company.id, "work_email": "karim@example.test"})
        cls.inst = cls.env["cultiveau.installation"].create({"name": "Goutte à goutte Chênes", "partner_id": cls.agri.id, "type_systeme": "goutte_surface"})
        projet = cls.env["project.project"].cultiveau_projet_interventions(cls.company)
        cls.F = cls.env["cultiveau.feuille.route"]
        cls.demain = cls.F.prochain_jour(cls.company)
        debut = datetime.combine(cls.demain, datetime.min.time()).replace(hour=7, minute=0)  # 08:00 ou 09:00 heure de Paris selon la saison
        cls.task = cls.env["project.task"].create({"name": "Remplacement régulateur", "project_id": projet.id, "partner_id": cls.agri.id, "cultiveau_installation_id": cls.inst.id,
                                                   "cultiveau_nature": "depannage", "cultiveau_debut": debut, "cultiveau_duree_prevue": 2, "cultiveau_salarie_ids": [(6, 0, [cls.poseur.id])],
                                                   "cultiveau_consignes": "Clé du portail sous le pot"})

    def test_journee_et_html(self):
        items = self.F.journee(self.poseur, self.demain)
        self.assertEqual(len(items), 1)
        i = items[0]
        self.assertEqual(i["client"], "Earl des Chênes")
        self.assertIn("Sommières", i["adresse"])
        self.assertIn("google.com/maps", i["itineraire"])
        self.assertEqual(i["consignes"], "Clé du portail sous le pot")
        html = self.F.html(self.poseur, self.demain)
        self.assertIn("Earl des Chênes", html)
        self.assertIn("Itinéraire", html)
        self.assertIn(self.poseur.cultiveau_feuille_url, html)
        self.assertFalse(self.F.journee(self.poseur, self.demain + timedelta(days=3)))

    def test_lien_et_page(self):
        url = self.poseur.cultiveau_feuille_url
        self.assertIn("/journee/", url)
        jeton = url.rsplit("/", 1)[1]
        self.assertGreaterEqual(len(jeton), 24)
        page = self.F.page(self.poseur, self.demain)
        self.assertIn("<!doctype html>", page)
        self.assertIn("Earl des Chênes", page)
        self.poseur.action_nouveau_jeton()
        self.assertNotEqual(self.poseur.cultiveau_feuille_url, url)

    def test_envoi_et_cron(self):
        avant = self.env["mail.mail"].sudo().search_count([])
        self.assertEqual(self.F.envoyer(self.poseur, self.demain), 1)
        mails = self.env["mail.mail"].sudo().search([], order="id desc", limit=1)
        self.assertEqual(mails.email_to, "karim@example.test")
        self.assertIn("Earl des Chênes", mails.body_html)
        self.assertTrue(self.poseur.cultiveau_feuille_derniere)
        # le robot n'écrit qu'à ceux qui ont quelque chose demain
        oisif = self.env["hr.employee"].create({"name": "Sans rien", "company_id": self.company.id, "work_email": "rien@example.test"})
        n = self.F._cron_veille()
        self.assertGreaterEqual(n, 1)
        self.assertFalse(oisif.cultiveau_feuille_derniere)
        self.assertGreater(self.env["mail.mail"].sudo().search_count([]), avant)

    def test_chantier_du_jour(self):
        ch = self.env["cultiveau.chantier"].create({"titre": "Pose Chênes", "installation_id": self.inst.id, "date_debut": self.demain, "date_fin": self.demain + timedelta(days=3),
                                                    "salarie_ids": [(6, 0, [self.poseur.id])], "machines": "Trancheuse", "acces": "Par le chemin du haut"})
        ch.action_planifier() if hasattr(ch, "action_planifier") else None
        items = self.F.journee(self.poseur, self.demain)
        chantiers = [i for i in items if i["genre"] == "chantier"]
        self.assertEqual(len(chantiers), 1)
        self.assertEqual(chantiers[0]["machines"], "Trancheuse")
        self.assertEqual(chantiers[0]["consignes"], "Par le chemin du haut")
