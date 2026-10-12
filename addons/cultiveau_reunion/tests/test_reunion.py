from datetime import datetime, timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "cultiveau")
class TestReunion(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.tz = "Europe/Paris"
        cls.collegue = cls.env["res.users"].create({"name": "Collègue Réunion", "login": "collegue.reunion", "company_id": cls.env.company.id,
                                                    "company_ids": [(6, 0, [cls.env.company.id])], "tz": "Europe/Paris"})
        cls.client = cls.env["res.partner"].create({"name": "Client Réunion", "email": "client.reunion@example.com", "company_id": cls.env.company.id})
        cls.R = cls.env["cultiveau.reunion"]
        # un lundi 9 h (heure de Paris = 7 h UTC en été)
        cls.lundi = datetime(2026, 6, 8, 7, 0)

    def test_creneaux_evitent_les_occupations(self):
        # le collègue est pris de 9 h à 11 h (heure locale) ce lundi
        self.env["calendar.event"].create({"name": "Déjà pris", "start": datetime(2026, 6, 8, 7, 0), "stop": datetime(2026, 6, 8, 9, 0), "partner_ids": [(6, 0, self.collegue.partner_id.ids)]})
        c = self.R.creneaux([self.collegue.id], 60, salle=True, maintenant=self.lundi - timedelta(hours=1))
        self.assertTrue(c)
        premier = fields.Datetime.to_datetime(c[0]["debut_utc"])
        self.assertGreaterEqual(premier, datetime(2026, 6, 8, 9, 0), "pas avant la fin de son rendez-vous")
        self.assertLessEqual(len([x for x in c if x["jour"] == c[0]["jour"]]), 2)
        self.assertTrue(all(fields.Datetime.to_datetime(x["debut_utc"]).weekday() < 5 for x in c))

    def test_planifier_dans_la_salle_avec_visio_integree(self):
        r = self.R.planifier({"titre": "Point chantier", "debut": "2026-06-09 08:00:00", "duree_min": 45, "user_ids": [self.collegue.id], "client_id": self.client.id,
                              "lieu": "salle", "visio": "erp"})
        e = self.env["calendar.event"].browse(r["id"])
        self.assertTrue(e.cultiveau_salle)
        self.assertEqual(e.location, "Salle de réunion")
        self.assertIn("/calendar/join_videocall/", e.videocall_location)
        self.assertIn(self.client, e.partner_ids)
        self.assertIn(self.collegue.partner_id, e.partner_ids)
        self.assertTrue(self.env["cultiveau.evenement"].search([("genre", "=", "reunion"), ("res_id", "=", e.id)]))
        # la salle n'est pas réservable deux fois
        with self.assertRaises(UserError):
            self.R.planifier({"titre": "Doublon", "debut": "2026-06-09 08:30:00", "duree_min": 30, "lieu": "salle", "visio": "aucune"})

    def test_meet_sans_agenda_google_devient_visio_integree(self):
        r = self.R.planifier({"titre": "Visio client", "debut": "2026-06-10 12:00:00", "duree_min": 30, "client_id": self.client.id, "lieu": "visio", "visio": "google_meet"})
        e = self.env["calendar.event"].browse(r["id"])
        self.assertEqual(e.cultiveau_visio, "erp")
        self.assertIn("Google", r["note"])
        self.assertFalse(e.cultiveau_salle)

    def test_la_map_voit_la_salle_et_les_personnes_en_reunion(self):
        self.env["calendar.event"].search([("cultiveau_salle", "=", True)]).unlink()  # la base peut déjà contenir des réunions
        maintenant = fields.Datetime.now()
        self.env["calendar.event"].create({"name": "Réunion en cours", "start": maintenant - timedelta(minutes=10), "stop": maintenant + timedelta(minutes=50),
                                           "partner_ids": [(6, 0, (self.collegue.partner_id | self.env.user.partner_id).ids)], "cultiveau_salle": True,
                                           "user_id": self.collegue.id})
        d = self.env["cultiveau.map"].vivant()
        self.assertEqual(d["reunion"]["salle"]["en_cours"]["titre"], "Réunion en cours")
        p = next(x for x in d["personnes"] if x["id"] == self.collegue.id)
        self.assertEqual(p["statut"], "en_reunion")
        f = self.env["cultiveau.map"].fiche("zone", 0, cle="reunion")
        self.assertTrue(any(a["cle"] == "planifier_reunion" for a in f["actions"]))
        self.assertIn("google", f["synchro"])
        f = self.env["cultiveau.map"].fiche("client", self.client.id)
        self.assertTrue(any(a["cle"] == "planifier_reunion" for a in f["actions"]))

    def test_mathis_propose_et_planifie_apres_confirmation(self):
        Mathis = self.env["cultiveau.mathis"]
        self.assertIn("planifier_reunion", Mathis._ecritures())
        noms = [o["function"]["name"] for o in Mathis._outils()]
        self.assertIn("creneaux_reunion", noms)
        res, action = Mathis._executer("planifier_reunion", {"titre": "Point Mathis", "debut_utc": "2026-06-11 08:00:00", "duree_min": 30, "lieu": "visio", "visio": "erp"})
        self.assertEqual(action["modele"], "calendar.event")
        self.assertTrue(self.env["calendar.event"].browse(res["id"]).videocall_location)
