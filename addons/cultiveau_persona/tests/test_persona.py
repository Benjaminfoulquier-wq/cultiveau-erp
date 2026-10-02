from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from ..models.questionnaire import QUESTIONS, scorer


@tagged("post_install", "-at_install", "cultiveau")
class TestPersona(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.agri = cls.env["res.partner"].create({"name": "Martin Paul", "cultiveau_type": "agriculteur"})

    def test_quatre_personas_charges(self):
        codes = set(self.env["cultiveau.persona"].search([]).mapped("code"))
        self.assertEqual(codes, {"batisseur", "pragmatique", "pilote", "fidele"})

    def test_scoring(self):
        batisseur = {"surface": "tres_grande", "relation": "nouveau", "priorite": "conseil", "materiel": "ancien",
                     "horizon": "structurant", "decision": "devis", "canal": "mail", "pilotage": "curieux"}
        self.assertEqual(scorer(batisseur)[0], "batisseur")
        pragmatique = {"surface": "moyenne", "relation": "occasionnel", "priorite": "prix", "materiel": "entretenu",
                       "horizon": "saison", "decision": "seul_vite", "canal": "sms", "pilotage": "non"}
        self.assertEqual(scorer(pragmatique)[0], "pragmatique")
        pilote = {"surface": "grande", "relation": "regulier", "priorite": "technique", "materiel": "automatise",
                  "horizon": "veille", "decision": "demo", "canal": "mail", "pilotage": "connecte"}
        self.assertEqual(scorer(pilote)[0], "pilote")
        self.assertEqual(scorer({})[0], "batisseur", "sans réponse, l'ordre de priorité tranche")

    def test_wizard_enregistre_le_persona(self):
        W = self.env["cultiveau.persona.wizard"]
        w = W.with_context(default_partner_id=self.agri.id).create({"surface": "petite"})
        self.assertFalse(w.persona_id)
        with self.assertRaises(UserError):
            w.action_valider()
        reponses = {"surface": "petite", "relation": "historique", "priorite": "conseil", "materiel": "entretenu",
                    "horizon": "renouveler", "decision": "conseiller", "canal": "visite", "pilotage": "non"}
        w.write(reponses)
        self.assertEqual(w.persona_id.code, "fidele")
        w.action_valider()
        self.assertEqual(self.agri.cultiveau_persona_id.code, "fidele")
        self.assertEqual(len(self.agri.cultiveau_persona_evaluation_ids), 1)
        self.assertIn("Le Fidèle", self.agri.cultiveau_persona_evaluation_ids.repartition)
        # Les réponses précédentes sont proposées au départ d'une nouvelle évaluation.
        w2 = W.with_context(default_partner_id=self.agri.id).create({})
        self.assertEqual(w2.relation, "historique")
        self.assertEqual(len(QUESTIONS), 8)
        api = self.agri.cultiveau_persona_pour_api()
        self.assertEqual(api["code"], "fidele")
        self.assertTrue(api["approche"])
