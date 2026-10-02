import json

from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install", "cultiveau")
class TestApi(HttpCase):
    def setUp(self):
        super().setUp()
        self.env["ir.config_parameter"].sudo().set_param("cultiveau.cle_api", "secret-de-test")
        self.env.company.cultiveau_numero_dedie = "+33 9 70 00 00 01"
        self.agri = self.env["res.partner"].create({"name": "Durand Jean", "mobile": "06 11 22 33 44", "zip": "30100", "city": "Alès",
                                                    "cultiveau_type": "agriculteur", "company_id": self.env.company.id,
                                                    "cultiveau_culture_ids": [(0, 0, {"culture_id": self.env.ref("cultiveau_frise.culture_vigne").id, "surface_ha": 9})]})
        self.entetes = {"X-Cultiveau-Cle": "secret-de-test", "Content-Type": "application/json"}

    def test_sans_cle_refuse(self):
        r = self.url_open("/cultiveau/api/client?telephone=0611223344")
        self.assertEqual(r.status_code, 401)
        r = self.url_open("/cultiveau/api/appel", data=json.dumps({}), headers={"Content-Type": "application/json"})
        self.assertEqual(r.status_code, 401)

    def test_fiche_du_client_qui_appelle(self):
        r = self.url_open("/cultiveau/api/client?telephone=%2B33611223344&numero_dedie=0970000001", headers=self.entetes)
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertTrue(d["trouve"])
        self.assertEqual(d["client"]["nom"], "Durand Jean")
        self.assertEqual(d["client"]["departement"], "30")
        self.assertEqual(d["client"]["cultures"][0]["culture"], "Vigne")
        self.assertIsNone(d["client"]["persona"])
        r = self.url_open("/cultiveau/api/client?telephone=0600000000", headers=self.entetes)
        self.assertFalse(r.json()["trouve"])

    def test_appel_panne_cree_une_intervention(self):
        corps = {"numero_dedie": "+33970000001", "reference": "APL-2026-0007", "categorie": "panne", "urgence": "immediate",
                 "client": {"telephone": "06 11 22 33 44"}, "resume": "Pompe arrêtée, vigne en véraison", "transcription": "Allô…"}
        r = self.url_open("/cultiveau/api/appel", data=json.dumps(corps), headers=self.entetes)
        self.assertEqual(r.status_code, 200, r.text)
        d = r.json()
        self.assertEqual(d["type"], "intervention")
        t = self.env["project.task"].browse(d["id"])
        self.assertEqual(t.partner_id, self.agri)
        self.assertEqual(t.cultiveau_urgence, "immediate")
        self.assertEqual(t.cultiveau_reference_appel, "APL-2026-0007")
        self.assertTrue(t.project_id.cultiveau_interventions)
        # Le même appel renvoyé (réessai de l'assistant) ne crée rien de plus.
        r = self.url_open("/cultiveau/api/appel", data=json.dumps(corps), headers=self.entetes)
        self.assertTrue(r.json()["deja"])
        self.assertEqual(self.env["project.task"].search_count([("cultiveau_reference_appel", "=", "APL-2026-0007")]), 1)

    def test_appel_devis_client_inconnu(self):
        corps = {"reference": "APL-2026-0008", "categorie": "devis", "client": {"nom": "Nouveau Paul", "telephone": "07 00 00 00 08", "commune": "Nîmes"},
                 "resume": "Veut un devis goutte à goutte sur 6 ha", "surface_ha": 6}
        r = self.url_open("/cultiveau/api/appel", data=json.dumps(corps), headers=self.entetes)
        d = r.json()
        self.assertEqual(d["type"], "opportunite")
        self.assertTrue(d["client_cree"])
        lead = self.env["crm.lead"].browse(d["id"])
        self.assertEqual(lead.partner_id.name, "Nouveau Paul")
        self.assertEqual(lead.partner_id.cultiveau_type, "agriculteur")
        self.assertEqual(lead.cultiveau_surface_ha, 6)
        self.assertEqual(lead.stage_id, self.env.ref("cultiveau_ventes.stage_demande"))
        # Au prochain appel, il est reconnu.
        r = self.url_open("/cultiveau/api/client?telephone=0700000008", headers=self.entetes)
        self.assertEqual(r.json()["client"]["nom"], "Nouveau Paul")

    def test_appel_autre_cree_une_activite(self):
        corps = {"categorie": "info", "client": {"telephone": "0611223344"}, "resume": "Demande les horaires"}
        r = self.url_open("/cultiveau/api/appel", data=json.dumps(corps), headers=self.entetes)
        self.assertEqual(r.json()["type"], "activite")
        self.assertTrue(self.agri.activity_ids.filtered(lambda a: a.summary == "Demande les horaires"))
