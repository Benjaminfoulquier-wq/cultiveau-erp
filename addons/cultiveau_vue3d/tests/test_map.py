from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "cultiveau")
class TestMap(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.societe = cls.env.company
        cls.tech = cls.env["res.users"].create({"name": "Léa Technicienne", "login": "lea.map", "company_id": cls.societe.id, "company_ids": [(6, 0, [cls.societe.id])],
                                                "groups_id": [(6, 0, [cls.env.ref("base.group_user").id, cls.env.ref("project.group_project_user").id])]})
        cls.agri = cls.env["res.partner"].create({"name": "Agriculteur Map", "cultiveau_type": "agriculteur", "company_id": cls.societe.id})
        cls.inst = cls.env["cultiveau.installation"].create({"name": "Pivot Map", "partner_id": cls.agri.id, "type_systeme": "pivot", "etat": "etude", "surface_ha": 30, "company_id": cls.societe.id})
        projet = cls.env["project.project"].create({"name": "Interventions map", "company_id": cls.societe.id, "cultiveau_interventions": True})
        cls.tache = cls.env["project.task"].create({"name": "Pompe en panne", "project_id": projet.id, "partner_id": cls.agri.id, "cultiveau_nature": "depannage",
                                                    "cultiveau_urgence": "immediate", "cultiveau_installation_id": cls.inst.id, "user_ids": [(6, 0, [cls.tech.id])]})

    def test_plan_genere_et_versions(self):
        Plan = self.env["cultiveau.plan"]
        plan = Plan.courant(self.societe)
        self.assertTrue(plan.publie)
        layout = plan.layout
        self.assertGreaterEqual(len(layout["contour"]), 6)
        self.assertTrue(any(z["cle"] == "atelier" for z in layout["zones"]))
        self.assertTrue(any(p["usage"] == "camion" for p in layout["places"]))
        self.assertEqual(len({o["id"] for o in layout["objets"]}), len(layout["objets"]))
        # une nouvelle version depuis l'éditeur, publiée
        layout["objets"].append({"id": "plante-test", "type": "plante", "x": 12, "z": 12, "rot": 0, "zone": "stockage", "params": {}, "entite": None})
        res = Plan.with_user(self.env.ref("base.user_admin")).with_company(self.societe).enregistrer(layout, publier=True, note="test")
        self.assertEqual(res["version"], plan.version + 1)
        self.assertEqual(Plan.courant(self.societe).version, res["version"])
        self.assertFalse(plan.publie)
        with self.assertRaises(Exception):
            Plan.enregistrer({"contour": []})

    def test_donnees_vivantes_et_evenements(self):
        d = self.env["cultiveau.map"].vivant()
        self.assertEqual(d["societe"]["id"], self.societe.id)
        lea = next(p for p in d["personnes"] if p["id"] == self.tech.id)
        self.assertEqual(lea["role"], "technicien")
        self.assertIn(lea["statut"], ("pas_arrive", "absent"))
        self.assertTrue(any(v["conducteur_id"] == self.tech.id for v in d["vehicules"]))
        self.assertTrue(any(x["id"] == self.inst.id for x in d["dossiers"]))
        self.assertEqual(len(d["kpi"]), 3)
        self.assertIn("equipe", d["onglets"])
        self.assertEqual(d["canal"], f"cultiveau_map_{self.societe.id}")
        # un pointage change le statut et produit un événement
        self.env["cultiveau.pointage"].badger("arrivee", user=self.tech, source="badgeuse")
        d = self.env["cultiveau.map"].vivant()
        lea = next(p for p in d["personnes"] if p["id"] == self.tech.id)
        self.assertEqual(lea["statut"], "au_poste")
        self.assertTrue(lea["arrivee"])
        self.env["cultiveau.pointage"].badger("depart_intervention", user=self.tech, task=self.tache)
        d = self.env["cultiveau.map"].vivant()
        lea = next(p for p in d["personnes"] if p["id"] == self.tech.id)
        self.assertEqual(lea["statut"], "en_intervention")
        self.assertTrue(any(v["parti"] for v in d["vehicules"] if v["conducteur_id"] == self.tech.id))
        genres = [e["genre"] for e in d["evenements"]]
        self.assertIn("depart_intervention", genres)
        self.assertTrue(self.env["cultiveau.evenement"].search([("genre", "=", "intervention_creee"), ("res_id", "=", self.tache.id)]))
        # les crochets du back-office
        self.tache.write({"state": "1_done"})
        self.assertEqual(self.env["cultiveau.evenement"].search([("genre", "=", "intervention_terminee"), ("res_id", "=", self.tache.id)]).modele, "project.task")
        self.inst.etat = "realisation"
        self.assertTrue(self.env["cultiveau.evenement"].search([("genre", "=", "chantier_demarre"), ("res_id", "=", self.inst.id)]))

    def test_fiches_et_focus(self):
        Map = self.env["cultiveau.map"]
        f = Map.fiche("personne", self.tech.id)
        self.assertEqual(f["nom"], "Léa Technicienne")
        self.assertIn("agenda", f)
        f = Map.fiche("dossier", self.inst.id)
        self.assertEqual(f["etapes"][1]["etat"], "en_cours")
        self.assertEqual([e["etat"] for e in f["etapes"]][0], "faite")
        f = Map.fiche("intervention", self.tache.id)
        self.assertEqual(f["client"], "Agriculteur Map")
        f = Map.fiche("client", self.agri.id)
        self.assertEqual(f["installations"][0]["id"], self.inst.id)
        self.assertEqual(Map.focus("project.task", self.tache.id)["technicien"], self.tech.id)
        self.assertEqual(Map.action_voir_sur_la_map("cultiveau.installation", self.inst.id)["params"]["focus"], f"cultiveau.installation:{self.inst.id}")
        with self.assertRaises(Exception):
            Map.fiche("inconnu", 1)

    def test_recherche_et_article(self):
        Map = self.env["cultiveau.map"]
        categ = self.env["product.category"].create({"name": "Pompes map"})
        article = self.env["product.template"].create({"name": "Pompe immergée Map 30", "default_code": "PMAP30", "categ_id": categ.id, "list_price": 1200, "company_id": self.societe.id})
        r = Map.chercher("map")
        self.assertIn("Clients", [x["groupe"] for x in r])
        self.assertTrue(any(x["genre"] == "client" and x["id"] == self.agri.id for x in r))
        self.assertTrue(any(x["genre"] == "article" and x["id"] == article.id for x in r))
        self.assertTrue(any(x["genre"] == "dossier" and x["id"] == self.inst.id for x in r))
        self.assertEqual(Map.chercher("x"), [])
        f = Map.fiche("article", article.id)
        self.assertEqual((f["code"], f["famille"], f["prix_vente"]), ("PMAP30", "Pompes map", 1200))
        d = Map.vivant()
        self.assertTrue(any(c["id"] == self.agri.id for c in d["onglets"]["clients"]))

    def test_portes(self):
        Map = self.env["cultiveau.map"]
        d = Map.vivant()
        self.assertIn("administratif", d["portes"])
        cles = [p["cle"] for p in d["portes"]["administratif"]]
        self.assertIn("factures_a_encaisser", cles)
        self.assertIn("tableau_de_bord", cles)  # le pilotage est installé sur la base de test
        f = Map.fiche("zone", 0, cle="atelier")
        self.assertTrue(any(a["cle"] == "interventions" for a in f["actions"]))
        action = self.env["cultiveau.scene"].action("tva")
        self.assertEqual(action["type"], "ir.actions.act_window")

    def test_demo(self):
        Map = self.env["cultiveau.map"]
        self.societe.cultiveau_map_demo = False
        self.assertEqual(Map.scenario_demo(), [])
        self.societe.cultiveau_map_demo = True
        etapes = Map.scenario_demo()
        self.assertGreaterEqual(len(etapes), 6)
        self.assertEqual(etapes[0]["genre"], "arrivee")
        for e in etapes:
            Map.jouer_demo(e)
        self.assertTrue(self.env["cultiveau.pointage"].search([("source", "=", "demo")]))
        self.assertTrue(self.env["cultiveau.evenement"].search([("demo", "=", True), ("genre", "=", "devis_signe")]))
        self.assertGreaterEqual(len(Map.ambiance_demo()), 5)
