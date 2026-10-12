from freezegun import freeze_time

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestRdv(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.s = cls.env.company
        groupes = [cls.env.ref("base.group_user").id, cls.env.ref("sales_team.group_sale_manager").id]
        cls.commercial = cls.env["res.users"].create({"name": "Corinne Commerciale", "login": "corinne-rdv@test.fr", "email": "corinne-rdv@test.fr",
                                                      "company_id": cls.s.id, "company_ids": [(6, 0, cls.s.ids)], "groups_id": [(6, 0, groupes)], "tz": "Europe/Paris"})
        cls.motif = cls.env["cultiveau.rdv.type"].create({"name": "Visite test", "duree_min": 60, "lieu": "chez_client", "company_id": cls.s.id,
                                                          "user_ids": [(6, 0, cls.commercial.ids)], "delai_heures": 24})

    @freeze_time("2026-10-14 08:00:00")
    def test_creneaux_et_reservation(self):
        jours = self.motif.jours_creneaux()
        self.assertTrue(jours)
        premier = jours[0]["creneaux"][0]
        self.assertGreaterEqual(premier["debut_utc"], "2026-10-15 08:00:00", "pas avant le délai de 24 h")
        self.assertEqual(premier["user_id"], self.commercial.id)
        e = self.motif.reserver(premier["debut_utc"], "Jean Essai — EARL du Test", "06 11 22 33 44", "jean@earl-test.fr", "Les Prés, Agen", "Projet goutte à goutte")
        self.assertEqual(e.user_id, self.commercial)
        client = e.partner_ids - self.commercial.partner_id
        self.assertEqual(client.email, "jean@earl-test.fr")
        self.assertEqual(e.location, "Les Prés, Agen")
        self.assertTrue(self.env["cultiveau.evenement"].search_count([("genre", "=", "rdv"), ("res_id", "=", e.id)]))
        # le créneau n'est plus proposé, et on ne peut pas le reprendre
        self.assertNotIn(premier["debut_utc"], [c["debut_utc"] for c in self.motif.creneaux()])
        with self.assertRaises(UserError):
            self.motif.reserver(premier["debut_utc"], "Autre", "0600000000")
        # le même client est retrouvé
        deuxieme = self.motif.creneaux()[0]
        e2 = self.motif.reserver(deuxieme["debut_utc"], "Jean Essai", "", "jean@earl-test.fr")
        self.assertEqual(e2.partner_ids - self.commercial.partner_id, client)

    @freeze_time("2026-10-14 08:00:00")
    def test_conges_et_coordonnees(self):
        with self.assertRaises(UserError):
            self.motif.reserver(self.motif.creneaux()[0]["debut_utc"], "", "", "")
        # en congé toute la semaine prochaine : pas de créneau ces jours-là
        conges = self.env["cultiveau.conges"].with_user(self.commercial)
        c = conges.demander("familial", "2026-10-15", "2026-10-23")
        jours = {c["debut_utc"][:10] for c in self.motif.creneaux(nombre=40)}
        self.assertFalse(jours & {"2026-10-15", "2026-10-16", "2026-10-19", "2026-10-22"})
        self.assertTrue(c["id"])

    def test_pages_et_mathis(self):
        self.env["cultiveau.rdv.type"].preparer(self.s)
        self.assertTrue(self.s.cultiveau_rdv_jeton)
        self.assertTrue(self.motif.url.endswith(self.motif.jeton))
        res, _a = self.env["cultiveau.mathis"].with_user(self.commercial)._executer("liens_rendez_vous", {})
        self.assertIn("/rdv/", res["page"])
        html = self.env["ir.qweb"]._render("cultiveau_rdv.page", {"societe": self.s, "motif": None, "motifs": self.motif, "erreur": None, "jeton": "x",
                                                                   "request": type("R", (), {"csrf_token": lambda self: "t"})()})
        self.assertIn("Visite test", str(html))
