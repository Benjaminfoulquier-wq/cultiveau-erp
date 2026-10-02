from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "cultiveau")
class TestInstallation(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.agri = cls.env["res.partner"].create({"name": "Mas Neuf", "zip": "30300", "cultiveau_type": "agriculteur"})
        cls.vigne = cls.env.ref("cultiveau_frise.culture_vigne")
        cls.inst = cls.env["cultiveau.installation"].create({
            "name": "Goutte à goutte vigne", "partner_id": cls.agri.id, "type_systeme": "goutte_surface", "surface_ha": 12.0,
            "culture_ids": [(6, 0, [cls.vigne.id])]})

    def test_analyse_des_besoins_check_list(self):
        i = self.inst
        self.assertEqual(i.analyse_completude, 0)
        with self.assertRaises(UserError):
            i.action_valider_analyse()
        i.write({"pente_moyenne_pct": 2, "distance_ressource_m": 300, "assolement": "vigne", "culture_pointe_id": self.vigne.id,
                 "sol_texture": "limoneux", "ru_mm": 80, "ressource": "forage", "debit_mobilisable_m3h": 40, "volume_autorise_m3": 30000,
                 "titre_prelevement": "declaration", "energie": "reseau", "puissance_souscrite_kva": 36, "main_d_oeuvre": "1 salarié",
                 "niveau_automatisme": "programmateur", "hierarchie": "eau"})
        self.assertEqual(i.analyse_completude, 8)
        self.assertIn("Non validée", i.analyse_html)
        i.action_valider_analyse()
        self.assertEqual(i.analyse_validee_le, fields.Date.context_today(i))
        self.assertEqual(i.etat, "etude")
        self.assertIn("Validée avec l'exploitant", i.analyse_html)

    def test_calculs_de_dimensionnement(self):
        i = self.inst
        i.write({"besoin_pointe_mm_j": 5.0, "temps_fonctionnement_h_j": 20})
        # 5 mm/j = 50 m³/ha/j = 0,579 l/s/ha ; sur 12 ha en 20 h : 50 × 12 / 20 = 30 m³/h.
        self.assertAlmostEqual(i.dfc_calc, 0.579, places=3)
        self.assertAlmostEqual(i.debit_calc, 30.0, places=1)
        i.action_reprendre_calculs()
        self.assertAlmostEqual(i.debit_equipement_m3_h, 30.0, places=1)
        self.assertIn("2000-4500 €/ha", i.chiffrage_indicatif)
        self.assertIn("24 000 – 54 000 €", i.chiffrage_indicatif)
        self.assertEqual(i.uniformite_cible, "DU ≥ 85")
        # Cohérences du référentiel : débit d'équipement > débit mobilisable ; micro-irrigation sans analyse d'eau.
        i.debit_mobilisable_m3h = 20
        self.assertIn("dépasse le débit mobilisable", i.alerte_dimensionnement)
        self.assertIn("Micro-irrigation sans analyse", i.alerte_dimensionnement)
        i.write({"analyse_eau_date": "2026-03-01", "debit_mobilisable_m3h": 40, "volume_autorise_m3": 10000})
        self.assertNotIn("Micro-irrigation sans analyse", i.alerte_dimensionnement)
        self.assertIn("volume autorisé", i.alerte_dimensionnement)  # 60 j × 50 m³/ha/j × 12 ha = 36 000 m³ > 10 000

    def test_mise_en_service_point_d_arret(self):
        i = self.inst
        with self.assertRaises(UserError):  # pas d'anti-retour
            i.action_mettre_en_service()
        i.pv_antiretour = True
        with self.assertRaises(UserError):  # pas de pressions de référence
            i.action_mettre_en_service()
        i.write({"pv_pression_sortie_pompe_bar": 4.2, "pv_pression_point_defavorable_bar": 1.3, "pression_service_bar": 1.5, "pv_uniformite_pct": 88})
        i.action_mettre_en_service()
        self.assertEqual(i.etat, "en_service")
        self.assertTrue(i.pv_date)
        self.assertIn("4.2 bar", i.reglage_pressions)
        self.assertEqual(i.registre_ids.genre, "mise_en_service")
        self.assertIn("1.3 bar point défavorable", i.registre_ids.releves)

    def test_equipements_et_renouvellement(self):
        annee = fields.Date.context_today(self.inst).year
        pompe = self.env["cultiveau.equipement"].create({"installation_id": self.inst.id, "categorie": "pompe", "name": "Pompe E6S", "annee_pose": annee - 14})
        self.assertEqual(pompe.duree_vie_ans, 15)
        self.assertEqual(pompe.fin_vie_estimee, annee + 1)
        self.assertTrue(pompe.a_renouveler)
        gaine = self.env["cultiveau.equipement"].create({"installation_id": self.inst.id, "categorie": "gaine", "name": "Gaine 16 mm", "annee_pose": annee})
        self.assertEqual(gaine.duree_vie_ans, 4)
        self.assertFalse(gaine.a_renouveler)
        self.assertEqual(self.inst.nb_a_renouveler, 1)
        self.assertEqual(self.agri.cultiveau_nb_installations, 1)
        self.assertIn(self.inst, self.env["cultiveau.installation"].search([("equipement_ids.a_renouveler", "=", True)]))

    def test_dossier_et_rapport(self):
        i = self.inst
        self.assertEqual(i.dossier_completude, 0)
        i.write({"analyse_validee_le": "2026-01-15", "besoin_pointe_mm_j": 5, "pompe": "Caprari 30 m³/h à 60 m", "reglage_pressions": "1,5 bar"})
        i.registre_ids.create({"installation_id": i.id, "genre": "releve", "description": "Relevé compteur", "releves": "12 345 m³"})
        self.assertEqual(i.dossier_completude, 4)
        html = self.env["ir.actions.report"]._render_qweb_html("cultiveau_installation.report_dossier", i.ids)[0].decode()
        self.assertIn("Dossier technique", html)
        self.assertIn("Caprari 30", html)
        self.assertIn("Relevé compteur", html)
        self.assertIn("Hivernage", html)

    def test_rappels_saisonniers(self):
        i = self.inst
        i.write({"etat": "en_service", "pv_antiretour": True})
        mois = fields.Date.context_today(i).month
        n = self.env["cultiveau.installation"]._cron_saisons()
        if mois in (2, 10):
            self.assertEqual(n, 1)
            self.assertEqual(self.env["cultiveau.installation"]._cron_saisons(), 0)
        else:
            self.assertEqual(n, 0)
        resume = i.resume_pour_api()[0]
        self.assertEqual(resume["type"], "Goutte à goutte de surface")
