import json

from odoo.tests import HttpCase, TransactionCase, tagged


@tagged("post_install", "-at_install", "cultiveau")
class TestApiV1(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.societe = env.company
        cls.autre = env["res.company"].create({"name": "Adhérent étanche API"})
        cls.agri = env["res.partner"].create({"name": "Agriculteur API", "cultiveau_type": "agriculteur", "company_id": cls.societe.id,
                                              "mobile": "+33698765401", "city": "Uzès", "exploitation": "Mas de l'API"})
        cls.cache = env["res.partner"].create({"name": "Client d'un autre adhérent", "cultiveau_type": "agriculteur", "company_id": cls.autre.id})
        cls.inst = env["cultiveau.installation"].create({"name": "Pivot API", "partner_id": cls.agri.id, "type_systeme": "pivot", "etat": "en_service",
                                                         "company_id": cls.societe.id, "surface_ha": 30})
        Cle = env["cultiveau.cle.api"]
        cls.lecture = Cle.create({"name": "Site (lecture)", "usage": "site", "droits": "lecture", "company_ids": [(6, 0, cls.societe.ids)]})
        cls.cle_lecture = cls.lecture.cle_a_copier
        cls.ecriture = Cle.create({"name": "Claude", "usage": "claude", "droits": "ecriture", "company_ids": [(6, 0, cls.societe.ids)]})
        cls.cle_ecriture = cls.ecriture.cle_a_copier

    def appel(self, chemin, cle=None, corps=None, methode="GET"):
        entetes = {"Authorization": f"Bearer {cle}"} if cle else {}
        if methode == "GET":
            r = self.url_open(chemin, headers=entetes)
        else:
            entetes["Content-Type"] = "application/json"
            r = self.url_open(chemin, data=json.dumps(corps), headers=entetes)
        return r.status_code, (r.json() if r.content else None)

    def test_cles(self):
        """La clé n'est gardée qu'en empreinte, s'efface une fois copiée, et se régénère."""
        self.assertTrue(self.cle_lecture.startswith("cv_"))
        self.assertNotEqual(self.lecture.empreinte, self.cle_lecture)
        self.lecture.action_cle_copiee()
        self.assertFalse(self.lecture.cle_a_copier)
        Cle = self.env["cultiveau.cle.api"]
        self.assertEqual(Cle.authentifier(self.cle_lecture), self.lecture)
        self.assertFalse(Cle.authentifier("cv_nimporte"))
        self.lecture.action_regenerer()
        self.assertFalse(Cle.authentifier(self.cle_lecture))
        self.assertEqual(Cle.authentifier(self.lecture.cle_a_copier), self.lecture)

    def test_rest_lecture(self):
        statut, _ = self.appel("/cultiveau/api/v1/clients")
        self.assertEqual(statut, 401)
        statut, index = self.appel("/cultiveau/api/v1", self.cle_lecture)
        self.assertEqual(statut, 200)
        self.assertIn("interventions", [r["nom"] for r in index["ressources"]])
        statut, liste = self.appel("/cultiveau/api/v1/clients?q=API", self.cle_lecture)
        self.assertEqual(statut, 200)
        ids = [c["id"] for c in liste["resultats"]]
        self.assertIn(self.agri.id, ids)
        self.assertNotIn(self.cache.id, ids, "les clients d'un autre adhérent ne sortent pas")
        statut, fiche = self.appel(f"/cultiveau/api/v1/clients/{self.agri.id}", self.cle_lecture)
        self.assertEqual((fiche["nom"], fiche["exploitation"], fiche["adresse"]["commune"]), ("Agriculteur API", "Mas de l'API", "Uzès"))
        self.assertIn(self.inst.id, [i["id"] for i in fiche["installations"]])
        statut, _ = self.appel(f"/cultiveau/api/v1/clients/{self.cache.id}", self.cle_lecture)
        self.assertEqual(statut, 404)
        statut, inst = self.appel(f"/cultiveau/api/v1/installations?client_id={self.agri.id}", self.cle_lecture)
        self.assertEqual([i["nom"] for i in inst["resultats"]], ["Pivot API"])
        statut, resume = self.appel("/cultiveau/api/v1/resume", self.cle_lecture)
        self.assertEqual([a["adherent"]["id"] for a in resume["adherents"]], [self.societe.id])
        statut, _ = self.appel("/cultiveau/api/v1/inconnue", self.cle_lecture)
        self.assertEqual(statut, 400)
        statut, doc = self.appel("/cultiveau/api/v1/openapi.json")
        self.assertEqual(statut, 200)
        self.assertIn("/chantiers/{id}", doc["paths"])

    def test_rest_ecriture(self):
        statut, rep = self.appel("/cultiveau/api/v1/interventions", self.cle_lecture, {"titre": "Pivot bloqué", "client_id": self.agri.id}, "POST")
        self.assertEqual(statut, 403)
        statut, inter = self.appel("/cultiveau/api/v1/interventions", self.cle_ecriture,
                                   {"titre": "Pivot bloqué en bout de parcelle", "urgence": "immediate", "client_id": self.agri.id, "installation_id": self.inst.id,
                                    "origine": "telephone"}, "POST")
        self.assertEqual(statut, 200, inter)
        self.assertEqual((inter["urgence"]["code"], inter["client"]["id"], inter["installation"]["id"]), ("immediate", self.agri.id, self.inst.id))
        statut, opp = self.appel("/cultiveau/api/v1/opportunites", self.cle_ecriture,
                                 {"titre": "Goutte à goutte vigne 4 ha", "client": {"nom": "Nouveau viticulteur API", "telephone": "06 98 76 54 99"}}, "POST")
        self.assertEqual(statut, 200, opp)
        nouveau = self.env["res.partner"].browse(opp["client"]["id"])
        self.assertEqual((nouveau.name, nouveau.company_id), ("Nouveau viticulteur API", self.societe))
        statut, note = self.appel(f"/cultiveau/api/v1/interventions/{inter['id']}/notes", self.cle_ecriture, {"texte": "Rappeler avant 18 h."}, "POST")
        self.assertTrue(note["ok"])
        self.assertIn("Rappeler avant 18 h.", self.env["mail.message"].browse(note["message_id"]).body)

    def test_mcp(self):
        """Le connecteur Claude : initialisation, outils, appels."""
        url = f"/cultiveau/mcp/{self.cle_ecriture}"
        statut, init = self.appel(url, corps={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}}}, methode="POST")
        self.assertEqual((statut, init["result"]["protocolVersion"], init["result"]["serverInfo"]["name"]), (200, "2025-06-18", "erp-cultiveau"))
        statut, _ = self.appel(url, corps={"jsonrpc": "2.0", "method": "notifications/initialized"}, methode="POST")
        self.assertEqual(statut, 202)
        statut, outils = self.appel(url, corps={"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, methode="POST")
        noms = [o["name"] for o in outils["result"]["tools"]]
        self.assertTrue({"resume", "lister", "lire", "chercher", "creer_intervention", "ajouter_note"} <= set(noms))
        statut, rep = self.appel(url, corps={"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "chercher", "arguments": {"texte": "API"}}}, methode="POST")
        self.assertFalse(rep["result"]["isError"])
        self.assertIn(self.agri.id, [c["id"] for c in rep["result"]["structuredContent"]["clients"]])
        statut, rep = self.appel(url, corps={"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "lire", "arguments": {"ressource": "clients", "id": self.cache.id}}},
                                 methode="POST")
        self.assertTrue(rep["result"]["isError"])
        # lecture seule : pas d'outils d'écriture
        statut, outils = self.appel(f"/cultiveau/mcp/{self.cle_lecture}", corps={"jsonrpc": "2.0", "id": 5, "method": "tools/list"}, methode="POST")
        self.assertNotIn("creer_intervention", [o["name"] for o in outils["result"]["tools"]])
        statut, _ = self.appel("/cultiveau/mcp/cv_fausse", corps={"jsonrpc": "2.0", "id": 6, "method": "tools/list"}, methode="POST")
        self.assertEqual(statut, 401)

    def test_toutes_les_ressources(self):
        """Chaque ressource se liste et chaque fiche se lit, sans clé restreinte (tout le réseau)."""
        moteur = self.env["cultiveau.api.moteur"]
        chantier = self.env["cultiveau.chantier"].create({"titre": "Pose API", "installation_id": self.inst.id, "company_id": self.societe.id})
        self.assertTrue(chantier)
        for ressource in moteur._ressources():
            liste = moteur.lister(ressource, {"limite": 3})
            self.assertEqual(liste["ressource"], ressource)
            self.assertLessEqual(len(liste["resultats"]), 3)
            if liste["resultats"]:
                fiche = moteur.lire(ressource, liste["resultats"][0]["id"])
                self.assertEqual(fiche["id"], liste["resultats"][0]["id"], ressource)
        self.assertEqual(moteur.lire("chantiers", chantier.id)["titre"], "Pose API")
        self.assertIn("pv", moteur.lire("chantiers", chantier.id))


@tagged("post_install", "-at_install")
class TestMoteurDepuisLErp(TransactionCase):
    def test_sans_cle_un_utilisateur_garde_ses_droits(self):
        """Appelé depuis l'ERP (et non par l'API), le moteur ne passe pas en super-utilisateur."""
        autre = self.env["res.company"].create({"name": "Adhérent voisin du moteur"})
        self.env["res.partner"].create({"name": "Client caché du voisin", "company_id": autre.id, "cultiveau_type": "agriculteur"})
        vendeur = self.env["res.users"].create({"name": "Vendeur du moteur", "login": "vendeur.moteur@exemple.fr", "company_id": self.env.company.id,
                                                "company_ids": [(6, 0, self.env.company.ids)], "groups_id": [(6, 0, [self.env.ref("base.group_user").id])]})
        moteur = self.env["cultiveau.api.moteur"].with_user(vendeur)
        noms = [r["nom"] for r in moteur.lister("clients", {"q": "Client caché du voisin"})["resultats"]]
        self.assertNotIn("Client caché du voisin", noms)
