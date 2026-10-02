from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from ..models.agent import recommander
from ..models.questionnaire import ORDRE, QUESTIONS, scorer

LION = {"probleme": "sait", "achat": "pointe", "relation": "efficace", "strategie": "productivite", "moral": "optimiste",
        "engagement": "societaire", "techno": "avance", "info": "presse"}
JAGUAR = {"probleme": "recherche", "achat": "meilleur", "relation": "rythme", "strategie": "autonomie", "moral": "optimiste",
          "engagement": "diversifiee", "techno": "roi", "info": "internet"}
CHAT = {"probleme": "seul", "achat": "memes", "relation": "rythme", "strategie": "charges", "moral": "inquiet",
        "engagement": "base", "techno": "maitrise", "info": "internet"}
TORTUE = {"probleme": "dialogue", "achat": "liste", "relation": "suivi", "strategie": "transmettre", "moral": "prudent",
          "engagement": "base", "techno": "prouve", "info": "technicien"}
ABEILLE = {"probleme": "dialogue", "achat": "liste", "relation": "partenaire", "strategie": "autonomie", "moral": "entoure",
           "engagement": "label", "techno": "prouve", "info": "pairs"}


@tagged("post_install", "-at_install", "cultiveau")
class TestPersona(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.agri = cls.env["res.partner"].create({"name": "Martin Paul", "zip": "30100", "cultiveau_type": "agriculteur"})
        cls.vigne = cls.env.ref("cultiveau_frise.culture_vigne")

    def test_cinq_personas_prism(self):
        personas = self.env["cultiveau.persona"].search([])
        self.assertEqual(set(personas.mapped("code")), {"lion", "jaguar", "chat", "tortue", "abeille"})
        self.assertEqual(set(personas.mapped("maslow")), {"1", "2", "3", "4", "5"}, "chaque persona sur un niveau de la pyramide")
        chat = self.env.ref("cultiveau_persona.persona_chat")
        self.assertEqual(chat.animal, "🐈")
        self.assertIn("fiabilité", chat.approche)
        self.assertEqual(len(chat.pour_agent()["pieges_texte"]), 3)
        self.assertEqual(len(QUESTIONS), 8)
        self.assertEqual(ORDRE[0], "chat", "en cas d'égalité, la prudence")

    def test_scoring(self):
        for attendu, reponses in (("lion", LION), ("jaguar", JAGUAR), ("chat", CHAT), ("tortue", TORTUE), ("abeille", ABEILLE)):
            code, scores = scorer(reponses)
            self.assertEqual(code, attendu, scores)
            self.assertGreaterEqual(scores[attendu] - max(v for c, v in scores.items() if c != attendu), 5, f"{attendu} doit se détacher : {scores}")
        self.assertEqual(scorer({})[0], "chat", "sans réponse, l'ordre de priorité tranche")

    def test_wizard_enregistre_le_persona(self):
        W = self.env["cultiveau.persona.wizard"]
        w = W.with_context(default_partner_id=self.agri.id).create({"probleme": "dialogue"})
        self.assertFalse(w.persona_id)
        with self.assertRaises(UserError):
            w.action_valider()
        w.write(TORTUE)
        self.assertEqual(w.persona_id.code, "tortue")
        w.action_valider()
        self.assertEqual(self.agri.cultiveau_persona_id.code, "tortue")
        self.assertEqual(len(self.agri.cultiveau_persona_evaluation_ids), 1)
        self.assertIn("La Tortue", self.agri.cultiveau_persona_evaluation_ids.repartition)
        # Les réponses précédentes sont proposées au départ d'une nouvelle évaluation.
        w2 = W.with_context(default_partner_id=self.agri.id).create({})
        self.assertEqual(w2.relation, "suivi")
        api = self.agri.cultiveau_persona_pour_api()
        self.assertEqual(api["code"], "tortue")
        self.assertEqual(api["animal"], "🐢")
        self.assertEqual(api["maslow"], "2")
        self.assertTrue(api["approche"])

    def test_agent_exemple_des_journees(self):
        """Viticulteur Chat, après vendanges, cours du vin en baisse : attendre la fin du stress, rassurer, pas de prix."""
        chat = self.env.ref("cultiveau_persona.persona_chat")
        self.env["cultiveau.persona.evaluation"].create({"partner_id": self.agri.id, "persona_id": chat.id, "reponses": CHAT, "scores": scorer(CHAT)[1]})
        self.env["cultiveau.culture.client"].create({"partner_id": self.agri.id, "culture_id": self.vigne.id, "surface_ha": 12})
        self.vigne.cours_tendance = "baisse"
        # Septembre : les vendanges sont une période critique.
        self.vigne.stades_pour("30").filtered(lambda s: s.name == "Maturation").write({"name": "Vendanges"})
        self.assertTrue(self.vigne.stades_pour("30").filtered(lambda s: s.name == "Vendanges").critique)
        r = self.agri.cultiveau_recommandation(9)
        self.assertTrue(r["critique"])
        self.assertIn("Attendre", r["timing"])
        self.assertIn("Vigne (vendanges)", r["timing"])
        self.assertIn("sécurité", r["ton"])
        self.assertIn("témoignages", r["ton"])
        self.assertIn("fiabilité", r["approche"].lower())
        self.assertTrue(any("prix" in e for e in r["eviter"]))
        self.assertIn("Le Chat", r["resume"])
        # Décembre : hiver, écoute ; le persona et le ton restent.
        r = self.agri.cultiveau_recommandation(12)
        self.assertFalse(r["critique"])
        self.assertEqual(r["posture"], "ecoute")
        self.assertIn("écouter", r["timing"])
        html = self.agri.cultiveau_agent_html
        self.assertIn("Quand", html)
        self.assertIn("Éviter", html)
        api = self.agri.cultiveau_agent_pour_api()
        self.assertEqual(api["cours"], "baisse")
        self.assertIn(api["posture"], ("ecoute", "support", "discret", "proposition"))

    def test_agent_sans_persona_ni_culture(self):
        sans_rien = self.env["res.partner"].create({"name": "Inconnu"})
        r = sans_rien.cultiveau_recommandation(7)
        self.assertIn("Persona inconnu", r["approche"])
        self.assertEqual(r["posture"], "ecoute", "sans culture, la posture par défaut est l'écoute")
        self.assertIn("rien à dire", sans_rien.cultiveau_agent_html)
        lion = {"code": "lion", "name": "Le Lion", "approche": "Résultats.", "pieges_texte": ["Attendre."]}
        r = recommander(lion, {"posture": "discret", "critique": False, "critiques": [], "cours": "hausse", "ton": "Cours en hausse.", "mois": "juillet"})
        self.assertIn("discret", r["timing"].lower())
        self.assertIn("premium", r["ton"])
        self.assertIn("Attendre.", r["eviter"])
        self.assertTrue(any("pleine saison" in e for e in r["eviter"]))
