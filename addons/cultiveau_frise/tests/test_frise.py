from odoo import fields
from odoo.tests import TransactionCase, tagged

from ..models.culture import libelle_mois, mois_couverts


@tagged("post_install", "-at_install", "cultiveau")
class TestFrise(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vigne = cls.env.ref("cultiveau_frise.culture_vigne")
        cls.agri = cls.env["res.partner"].create({"name": "Durand Jean", "zip": "30100", "cultiveau_type": "agriculteur"})

    def test_mois_couverts_passe_l_hiver(self):
        self.assertEqual(mois_couverts(11, 2), [11, 12, 1, 2])
        self.assertEqual(mois_couverts(3, 4), [3, 4])
        self.assertEqual(libelle_mois([11, 12, 1, 2]), "Nov–Fév")

    def test_departement_deduit_du_code_postal(self):
        self.assertEqual(self.agri.departement, "30")
        corse = self.env["res.partner"].create({"name": "Corse", "zip": "20167"})
        self.assertEqual(corse.departement, "2A")

    def test_donnees_du_gard(self):
        stades = self.vigne.stades_pour("30")
        self.assertEqual(len(stades), 4)
        self.assertEqual(stades[0].name, "Débourrement")
        ligne = self.vigne.ligne_frise("30")
        self.assertEqual(ligne["projet"], [11, 12])
        self.assertEqual(ligne["achat"], [1, 2])
        self.assertEqual(ligne["cases"][6]["stade"].name, "Véraison")  # juillet
        self.assertGreater(ligne["cases"][6]["intensite"], ligne["cases"][2]["intensite"])

    def test_repli_sur_les_valeurs_generales(self):
        # Un département sans données : on prend celles valables partout (la frise France) ; sans rien, la ligne est vide.
        self.assertEqual(self.vigne.stades_pour("64")[0].name, "Repos hivernal")
        self.assertEqual(self.vigne.stades_pour("30")[0].name, "Débourrement")
        nouvelle = self.env["cultiveau.culture"].create({"name": "Culture sans frise"})
        self.assertFalse(nouvelle.stades_pour("64"))
        self.env["cultiveau.culture.stade"].create({"culture_id": nouvelle.id, "name": "Général", "mois_debut": "4", "mois_fin": "9", "kc_max": 0.7})
        self.assertEqual(nouvelle.stades_pour("64").name, "Général")

    def test_toutes_les_cultures_avec_frise_et_kc(self):
        cultures = self.env["cultiveau.culture"].search([])
        self.assertGreaterEqual(len(cultures), 110)
        familles = set(cultures.mapped("categorie"))
        for f in ("grandes_cultures", "maraichage", "arbo", "petits_fruits", "vigne", "prairies", "sous_abri", "espaces_verts", "ppam", "tropicales"):
            self.assertIn(f, familles)
        for c in cultures.filtered(lambda c: c.kc_mi):
            self.assertTrue(0.1 <= c.kc_ini <= 1.3 and 0.25 <= c.kc_mi <= 1.3 and 0.2 <= c.kc_fin <= 1.3, c.name)
            self.assertGreaterEqual(len(c.stades_pour("")), 2, c.name)
            self.assertEqual(len(c.fenetres_pour("")), 2, c.name)
            self.assertIn("<svg", c.courbe_kc, c.name)
        self.assertEqual(len(cultures.filtered(lambda c: not c.kc_mi)), 0, "chaque culture du catalogue a ses Kc")

    def test_kc_au_jour_suit_la_courbe_fao(self):
        mais = self.env.ref("cultiveau_frise.culture_mais_grain")
        self.assertEqual((mais.kc_ini, mais.kc_mi, mais.kc_fin, mais.duree_cycle), (0.3, 1.2, 0.35, 150))
        self.assertEqual(mais.kc_au_jour(10), 0.3)  # phase initiale
        self.assertAlmostEqual(mais.kc_au_jour(50), 0.75, places=2)  # mi-chemin de la montée (30 → 70 j)
        self.assertEqual(mais.kc_au_jour(90), 1.2)  # mi-saison
        self.assertAlmostEqual(mais.kc_au_jour(150), 0.35, places=2)
        self.assertEqual(mais.besoin_mm_jour(5.0, 90), 6.0)
        juillet = mais.ligne_frise("64")["cases"][6]
        self.assertEqual(juillet["stade"].name, "Floraison (sortie des soies)")
        self.assertTrue(juillet["critique"])

    def test_frise_du_client_et_fenetres(self):
        cc = self.env["cultiveau.culture.client"].create({"partner_id": self.agri.id, "culture_id": self.vigne.id, "surface_ha": 12.5})
        self.assertEqual(cc.departement, "30")
        self.assertEqual(cc.projet_mois, "Nov–Déc")
        self.assertEqual(self.agri.cultiveau_surface_ha, 12.5)
        self.assertIn("Vigne", self.agri.cultiveau_frise_html)
        self.assertIn("Véraison", self.agri.cultiveau_frise_html)
        self.assertIn("projet Nov–Déc", self.agri.cultiveau_fenetres)
        self.assertEqual(cc.fenetres_du_mois(11), {"projet"})
        self.assertEqual(cc.fenetres_du_mois(1), {"achat"})
        self.assertEqual(cc.fenetres_du_mois(6), set())

    def test_a_contacter_ce_mois(self):
        toute_l_annee = self.env["cultiveau.culture"].create({"name": "Test toute l'année", "fenetre_ids": [
            (0, 0, {"genre": "achat", "mois_debut": "1", "mois_fin": "12"})]})
        jamais = self.env["cultiveau.culture"].create({"name": "Test jamais"})
        a = self.env["res.partner"].create({"name": "Toujours", "cultiveau_culture_ids": [(0, 0, {"culture_id": toute_l_annee.id})]})
        b = self.env["res.partner"].create({"name": "Jamais", "cultiveau_culture_ids": [(0, 0, {"culture_id": jamais.id})]})
        self.assertTrue(a.cultiveau_a_contacter)
        self.assertFalse(b.cultiveau_a_contacter)
        trouves = self.env["res.partner"].search([("cultiveau_a_contacter", "=", True)])
        self.assertIn(a, trouves)
        self.assertNotIn(b, trouves)
        n = self.env["cultiveau.culture.client"]._cron_fenetres()
        self.assertGreaterEqual(n, 1)
        self.assertTrue(a.activity_ids.filtered(lambda x: x.summary.startswith("Fenêtre ")))
        self.assertEqual(self.env["cultiveau.culture.client"]._cron_fenetres(), 0, "pas de doublon le même mois")
        self.assertEqual(fields.Date.context_today(a.activity_ids[0]).month, a.activity_ids[0].date_deadline.month)

    def test_postures_des_stades_du_gard(self):
        # Les quatre saisons émotionnelles : floraison = critique (discret), été = discret, après récolte = proposition, printemps = support.
        stades = {s.name: s for s in self.vigne.stades_pour("30")}
        self.assertTrue(stades["Floraison"].critique)
        self.assertEqual(stades["Floraison"].posture, "discret")
        self.assertEqual(stades["Véraison"].posture, "discret")
        self.assertEqual(stades["Maturation"].posture, "proposition")
        self.assertEqual(stades["Débourrement"].posture, "support")
        ligne = self.vigne.ligne_frise("30")
        self.assertEqual(ligne["cases"][11]["posture"], "ecoute", "décembre, hors cycle : le calendrier (hiver = écoute)")
        self.assertTrue(ligne["cases"][4]["critique"], "mai : floraison")
        # La posture reste modifiable à la main.
        stades["Maturation"].posture = "discret"
        self.assertEqual(self.vigne.ligne_frise("30")["cases"][8]["posture"], "discret")

    def test_posture_du_client_et_cours(self):
        melon = self.env.ref("cultiveau_frise.culture_melon")
        (self.vigne | melon).write({"cours_tendance": "stable"})  # indépendant des cours saisis dans la base
        self.env["cultiveau.culture.client"].create({"partner_id": self.agri.id, "culture_id": self.vigne.id, "surface_ha": 12})
        s = self.agri.cultiveau_situation(10)
        self.assertEqual(s["posture"], "proposition", "octobre, vigne en maturation : le moment de proposer")
        self.assertFalse(s["critique"])
        self.assertEqual(s["cours"], "stable")
        self.env["cultiveau.culture.client"].create({"partner_id": self.agri.id, "culture_id": melon.id, "surface_ha": 3})
        s = self.agri.cultiveau_situation(9)
        self.assertEqual(s["posture"], "discret", "septembre : le melon est en récolte, on ne dérange pas")
        self.assertTrue(s["critique"])
        self.assertIn("Melon (récolte)", s["critiques"])
        self.assertEqual(self.agri.cultiveau_situation(12)["posture"], "ecoute")
        self.vigne.cours_tendance = "baisse"
        self.agri.invalidate_recordset()
        self.assertEqual(self.agri.cultiveau_cours, "baisse", "une culture en baisse suffit : la prudence l'emporte")
        self.assertIn("sécurité", self.agri.cultiveau_cours_ton)
        self.assertIn("Posture", self.agri.cultiveau_frise_html)
        self.assertIn("✖", self.agri.cultiveau_frise_html)
        api = self.agri.cultiveau_frise_pour_api(9)
        self.assertEqual(api["posture"], "discret")
        self.assertTrue(api["periode_critique"])
        self.assertEqual(api["cours"], "baisse")
        self.assertFalse(self.env["res.partner"].create({"name": "Sans culture"}).cultiveau_frise_pour_api())

    def test_cron_previent_des_periodes_critiques(self):
        culture = self.env["cultiveau.culture"].create({"name": "Test critique", "stade_ids": [
            (0, 0, {"name": "Récolte", "mois_debut": "1", "mois_fin": "12", "kc_max": 0.9})],
            "fenetre_ids": [(0, 0, {"genre": "achat", "mois_debut": "1", "mois_fin": "12"})]})
        p = self.env["res.partner"].create({"name": "Récolte permanente", "cultiveau_culture_ids": [(0, 0, {"culture_id": culture.id})]})
        self.env["cultiveau.culture.client"]._cron_fenetres()
        activite = p.activity_ids.filtered(lambda a: a.summary.startswith("Fenêtre "))
        self.assertTrue(activite)
        self.assertIn("période critique", activite.note)


@tagged("post_install", "-at_install")
class TestFriseDepartementale(TransactionCase):
    """La frise et les Kc s'adaptent au département, puis au client (date de semis, variété, sol, système)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mais = cls.env.ref("cultiveau_frise.culture_mais_grain")

    def test_kc_corrige_par_le_climat(self):
        # FAO-56 éq. 62 : Hérault (vent 3 m/s, air à 40 %) → Kc de pointe 1,20 + 0,053 ; Finistère (2,8 m/s, 55 %) → 1,20 − 0,007
        self.assertEqual(self.mais.kc_ajustes("34"), (0.3, 1.25, 0.35))  # Kc fin < 0,45 : pas de correction
        self.assertEqual(self.mais.kc_ajustes("29")[1], 1.19)
        self.assertEqual(self.mais.kc_ajustes(""), (0.3, 1.2, 0.35))
        tomate = self.env.ref("cultiveau_frise.culture_tomate")
        self.assertGreater(tomate.kc_ajustes("13")[2], tomate.kc_fin, "Kc fin ≥ 0,45 : corrigé aussi")

    def test_frise_recalee_sur_le_departement(self):
        floraison = lambda dep: self.mais.stades_pour(dep).filtered(lambda s: "Floraison" in s.name)  # noqa: E731
        self.assertEqual(floraison("").mois_debut, "7")
        self.assertEqual(floraison("34").mois_debut, "7", "15 jours d'avance : la floraison reste en juillet")
        self.assertEqual(floraison("05").mois_debut, "8", "20 jours de retard en montagne : elle passe en août")
        self.assertGreater(floraison("34").etp_max, floraison("29").etp_max, "l'ETo du département remplace celle de la France")
        self.assertEqual(floraison("34").kc_max, 1.25, "le Kc du stade est celui du département")
        # le Gard garde sa frise locale (vigne) ; une culture sans frise locale y prend la frise France recalée
        vigne = self.env.ref("cultiveau_frise.culture_vigne")
        self.assertEqual(vigne.stades_pour("30")[0].name, "Débourrement")
        self.assertEqual(floraison("30").kc_max, 1.25)

    def test_analyse_du_client(self):
        agri = self.env["res.partner"].create({"name": "Maïsiculteur du Gers", "zip": "32000", "cultiveau_type": "agriculteur"})
        cc = self.env["cultiveau.culture.client"].create({"partner_id": agri.id, "culture_id": self.mais.id, "surface_ha": 40,
                                                         "sol_texture": "limoneux", "systeme": "pivot"})
        self.assertEqual((cc.departement, cc.efficience, cc.ru_mm_m), ("32", 0.85, 170))
        self.assertEqual(cc.decalage_jours, -10)
        self.assertTrue(6.0 <= cc.besoin_pointe_mm <= 7.0, cc.besoin_pointe_mm)  # ETo 5,4 × Kc ≈ 1,2
        self.assertAlmostEqual(cc.debit_m3h, round(cc.besoin_pointe_mm / 0.85 * 10 * 40 / 20), delta=2)
        self.assertTrue(200 <= cc.irrigation_mm <= 400, cc.irrigation_mm)  # année sèche, pour dimensionner
        self.assertTrue(150 <= cc.irrigation_moyenne_mm < cc.irrigation_mm, cc.irrigation_moyenne_mm)
        self.assertEqual(cc.volume_m3, round(cc.irrigation_mm / 0.85 * 10 * 40), "volume à la pompe : besoin ÷ efficience")
        self.assertTrue(cc.tour_eau_j > 10)
        self.assertIn("Gers", cc.analyse)
        # semé tard (20 mai) : sa frise se décale, la floraison passe après celle du département
        floraison = lambda c: next(case["mois"] for case in c.ligne_frise()["cases"] if case["stade"] and "Floraison" in case["stade"].name)  # noqa: E731
        avant = floraison(cc)
        cc.date_semis = "2026-05-20"
        self.assertGreater(cc.decalage_jours, 20)
        self.assertGreater(floraison(cc), avant)
        # le goutte à goutte demande moins d'eau à la pompe que l'enrouleur pour le même besoin
        cc.systeme = "enrouleur"
        enrouleur = cc.volume_m3
        cc.systeme = "goutte"
        self.assertLess(cc.volume_m3, enrouleur)

    def test_vigne_conduite_en_restriction(self):
        agri = self.env["res.partner"].create({"name": "Vigneron du Vaucluse", "zip": "84100", "cultiveau_type": "agriculteur"})
        vigne = self.env.ref("cultiveau_frise.culture_vigne")
        cc = self.env["cultiveau.culture.client"].create({"partner_id": agri.id, "culture_id": vigne.id, "surface_ha": 10, "systeme": "goutte"})
        self.assertEqual(vigne.satisfaction, 0.4)
        self.assertTrue(60 <= cc.irrigation_moyenne_mm <= 160, cc.irrigation_moyenne_mm)
