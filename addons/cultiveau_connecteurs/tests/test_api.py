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

    def test_tout_ce_qui_est_dit_est_note_sur_la_fiche(self):
        transcription = "Agriculteur : la pompe ne démarre plus depuis ce matin.\n" + "Assistant : je note. " * 800
        corps = {"numero_dedie": "+33970000001", "reference": "APL-2026-0099", "categorie": "panne", "client": {"telephone": "06 11 22 33 44"},
                 "resume": "La pompe de la vigne ne démarre plus depuis ce matin. Le client pense au pressostat. Il est disponible après 14 h.",
                 "transcription": transcription, "duree_s": 245, "lien_appel": "https://assistant.exemple.fr/crm/appels/99/",
                 "audio_url": "https://assistant.exemple.fr/audio/erp/jeton-signe/", "audio_jusqu_au": "2099-12-31"}
        r = self.url_open("/cultiveau/api/appel", data=json.dumps(corps), headers=self.entetes)
        self.assertEqual(r.status_code, 200, r.text)
        appel = self.env["cultiveau.appel"].search([("reference", "=", "APL-2026-0099")])
        # le sujet en une ou deux phrases ; tout ce qui a été dit, sans coupure, sur la fiche de l'appel
        self.assertEqual(appel.sujet, "La pompe de la vigne ne démarre plus depuis ce matin. Le client pense au pressostat.")
        self.assertEqual(appel.transcription.count("je note."), 800)
        self.assertEqual((appel.partner_id, appel.duree, bool(appel.task_id)), (self.agri, "4 min 05 s", True))
        self.assertIn("<audio", appel.lecteur)
        # dans le fil du client : une ligne et le lien, pas la transcription
        ligne = self.agri.message_ids.filtered(lambda m: "Appel reçu par l'assistant" in (m.body or ""))
        self.assertEqual(len(ligne), 1)
        self.assertIn("pressostat", ligne.body)
        self.assertIn("Voir la conversation et écouter", ligne.body)
        self.assertNotIn("je note.", ligne.body)
        self.assertEqual(self.agri.cultiveau_nb_appels, 1)
        # l'audio s'efface à la fin de la durée de conservation ; la transcription reste
        appel.sudo().audio_jusqu_au = "2020-01-01"
        appel.invalidate_recordset(["lecteur", "audio_disponible"])
        self.assertNotIn("<audio", appel.lecteur or "")

    def test_synchro_du_crm(self):
        E = lambda **k: k  # noqa: E731
        elements = [
            E(type="client", reference="CLI-501", nom="Mairie de Synchro", telephone="04 66 00 11 22", commune="Vauvert", genre="administration"),
            E(type="client", reference="CLI-502", nom="Jean Durand", telephone="+33611223344", email="jean.durand@exemple.fr"),
            E(type="note", reference="NOTE-1", client="CLI-502", texte="Veut un devis pour un second pivot.\nRappeler après les vendanges.", auteur="Paul", source="dictee"),
            E(type="tache", reference="TAC-1", client="CLI-502", titre="Rappeler Jean Durand", echeance="2026-11-03", heure="10:30"),
            E(type="equipement", reference="EQ-1", client="CLI-502", famille="station_pompage", marque="Caprari", modele="E6S", pose_le="2019"),
            E(type="note", reference="NOTE-2", client="CLI-999", texte="client jamais envoyé"),
        ]
        r = self.url_open("/cultiveau/api/synchro", data=json.dumps({"numero_dedie": "+33970000001", "elements": elements}), headers=self.entetes)
        self.assertEqual(r.status_code, 200, r.text)
        res = {x["reference"]: x for x in r.json()["resultats"]}
        self.assertFalse(res["NOTE-2"]["ok"])
        mairie = self.env["res.partner"].browse(res["CLI-501"]["id"])
        self.assertEqual((mairie.cultiveau_type, mairie.city, res["CLI-501"]["cree"]), ("collectivite", "Vauvert", True))
        # Jean Durand existait déjà dans l'ERP (même mobile) : il est retrouvé et complété, pas dupliqué
        self.assertEqual(res["CLI-502"]["id"], self.agri.id)
        self.assertEqual(self.agri.email, "jean.durand@exemple.fr")
        self.assertIn("second pivot", self.agri.message_ids.filtered(lambda m: m.id == res["NOTE-1"]["id"]).body)
        activite = self.env["mail.activity"].browse(res["TAC-1"]["id"])
        self.assertEqual((activite.res_id, str(activite.date_deadline)), (self.agri.id, "2026-11-03"))
        pompe = self.env["cultiveau.equipement"].browse(res["EQ-1"]["id"])
        self.assertEqual((pompe.categorie, pompe.annee_pose, pompe.partner_id), ("pompe", 2019, self.agri))
        # tout renvoyer ne crée rien de plus ; la tâche faite dans l'assistant est close dans l'ERP
        elements[3]["etat"] = "fait"
        r = self.url_open("/cultiveau/api/synchro", data=json.dumps({"numero_dedie": "+33970000001", "elements": elements[:5]}), headers=self.entetes)
        self.assertTrue(r.json()["ok"], r.text)
        self.assertEqual(self.env["res.partner"].search_count([("name", "=", "Mairie de Synchro")]), 1)
        self.assertFalse(activite.exists())
        self.assertEqual(len(self.agri.message_ids.filtered(lambda m: "second pivot" in (m.body or ""))), 1)

    def test_cle_d_adherent_limitee_a_sa_societe(self):
        if "cultiveau.cle.api" not in self.env:
            self.skipTest("module des clés absent")
        voisin = self.env["res.company"].create({"name": "Adhérent voisin", "cultiveau_numero_dedie": "+33 9 70 00 00 99"})
        cle = self.env["cultiveau.cle.api"].create({"name": "Assistant de test", "droits": "ecriture", "company_ids": [(6, 0, self.env.company.ids)]})
        entetes = {"X-Cultiveau-Cle": cle.cle_a_copier, "Content-Type": "application/json"}
        # même en visant le numéro du voisin, la clé reste chez son adhérent
        corps = {"numero_dedie": "+33970000099", "elements": [{"type": "client", "reference": "CLI-1", "nom": "Client de la clé"}]}
        r = self.url_open("/cultiveau/api/synchro", data=json.dumps(corps), headers=entetes)
        self.assertEqual(r.json()["adherent"], self.env.company.name, r.text)
        self.assertEqual(self.env["res.partner"].search([("name", "=", "Client de la clé")]).company_id, self.env.company)
        self.assertNotEqual(voisin, self.env.company)
        cle.droits = "lecture"
        r = self.url_open("/cultiveau/api/synchro", data=json.dumps(corps), headers=entetes)
        self.assertEqual(r.status_code, 401)
