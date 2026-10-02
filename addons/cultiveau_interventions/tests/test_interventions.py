from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "cultiveau")
class TestInterventions(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.agri = cls.env["res.partner"].create({"name": "Gaec du Vidourle", "zip": "30250", "cultiveau_type": "agriculteur", "mobile": "06 12 34 56 78"})
        cls.inst = cls.env["cultiveau.installation"].create({"name": "Pivot nord", "partner_id": cls.agri.id, "type_systeme": "pivot", "surface_ha": 40,
                                                              "etat": "en_service", "pv_antiretour": True, "pv_pression_sortie_pompe_bar": 5.5,
                                                              "pv_pression_point_defavorable_bar": 2.1})
        cls.piece = cls.env["product.product"].create({"name": "Pressostat", "list_price": 120.0, "type": "consu", "sale_ok": True})

    def test_projet_interventions_par_societe(self):
        projet = self.env["project.project"].cultiveau_projet_interventions()
        self.assertTrue(projet.cultiveau_interventions)
        self.assertEqual(projet.type_ids.mapped("name"), ["À planifier", "Planifiée", "En cours", "Terminée"])
        self.assertEqual(self.env["project.project"].cultiveau_projet_interventions(), projet, "pas de doublon")

    def test_intervention_depuis_appel_puis_registre(self):
        t = self.env["project.task"].cultiveau_creer_depuis_appel(self.env.company, self.agri, {
            "resume": "Pivot arrêté, pompe disjoncte", "urgence": "immediate", "reference": "APL-2026-0101", "transcription": "Le pivot nord ne tourne plus…"})
        self.assertTrue(t.cultiveau_intervention)
        self.assertEqual(t.cultiveau_installation_id, self.inst)
        self.assertEqual(t.priority, "1")
        self.assertEqual(t.cultiveau_origine, "assistant")
        self.assertIn("5.5 bar sortie pompe", t.cultiveau_reference_pressions)
        t.write({"cultiveau_releves": "3,8 bar sortie pompe", "state": "1_done"})
        self.assertTrue(t.cultiveau_registre_id)
        self.assertEqual(t.cultiveau_registre_id.genre, "curatif")
        self.assertEqual(t.cultiveau_registre_id.reference, "APL-2026-0101")
        self.assertIn("3,8 bar", t.cultiveau_registre_id.releves)
        self.assertEqual(len(self.inst.registre_ids), 1)

    def test_remise_en_service_date_l_installation(self):
        projet = self.env["project.project"].cultiveau_projet_interventions()
        t = self.env["project.task"].create({"name": "Remise en service", "project_id": projet.id, "partner_id": self.agri.id,
                                             "cultiveau_installation_id": self.inst.id, "cultiveau_nature": "remise_en_service"})
        t.state = "1_done"
        self.assertTrue(self.inst.remise_en_service_le)
        self.assertEqual(t.cultiveau_registre_id.genre, "remise_en_service")

    def test_pieces_vers_devis(self):
        projet = self.env["project.project"].cultiveau_projet_interventions()
        t = self.env["project.task"].create({"name": "Pressostat HS", "project_id": projet.id, "partner_id": self.agri.id, "cultiveau_installation_id": self.inst.id})
        with self.assertRaises(UserError):
            t.action_creer_devis()
        t.cultiveau_piece_ids = [(0, 0, {"product_id": self.piece.id, "quantite": 2, "note": "monté le jour même"})]
        t.action_creer_devis()
        devis = t.cultiveau_sale_order_id
        self.assertEqual(devis.partner_id, self.agri)
        self.assertEqual(devis.cultiveau_installation_id, self.inst)
        self.assertEqual(devis.order_line.product_uom_qty, 2)
        self.assertIn("monté le jour même", devis.order_line.name)
        t.cultiveau_piece_ids = [(0, 0, {"product_id": self.piece.id, "quantite": 1})]
        t.action_creer_devis()
        self.assertEqual(len(devis.order_line), 2, "la seconde pièce rejoint le même devis")
