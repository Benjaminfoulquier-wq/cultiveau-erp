from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "cultiveau")
class TestChecklists(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.agri = cls.env["res.partner"].create({"name": "Earl de la Source", "zip": "30250", "cultiveau_type": "agriculteur"})
        cls.inst = cls.env["cultiveau.installation"].create({"name": "Pivot Source", "partner_id": cls.agri.id, "type_systeme": "pivot", "pv_pression_sortie_pompe_bar": 5.5})
        projet = cls.env["project.project"].cultiveau_projet_interventions(cls.env.company)
        cls.task = cls.env["project.task"].create({"name": "Remise en service pivot", "project_id": projet.id, "partner_id": cls.agri.id, "cultiveau_installation_id": cls.inst.id,
                                                   "cultiveau_nature": "remise_en_service"})

    def test_le_bon_recoit_la_checklist_de_sa_nature(self):
        bon = self.env["cultiveau.bon"].create({"task_id": self.task.id, "partner_id": self.agri.id, "installation_id": self.inst.id})
        self.assertEqual(bon.nature, "remise_en_service")
        self.assertEqual(bon.modele_checklist_id, self.env.ref("cultiveau_checklists.ck_remise_en_service"))
        self.assertGreaterEqual(len(bon.point_ids), 10)
        self.assertEqual(bon.checklist_avancement, 0)
        self.assertIn("Amorçage", bon.checklist_manques)
        # une mesure de pression remplit le relevé du bon
        p = bon.point_ids.filtered(lambda p: p.cle == "pression_pompe")
        p.write({"valeur": 5.2, "etat": "ok"})
        self.assertEqual(bon.pression_pompe_mesuree, 5.2)
        bon.action_tout_cocher()
        self.assertTrue(all(x.etat == "ok" for x in bon.point_ids.filtered(lambda x: x.genre == "case")))
        # le changement de nature recharge
        bon.nature = "hivernage"
        self.assertEqual(bon.modele_checklist_id, self.env.ref("cultiveau_checklists.ck_hivernage"))
        self.assertTrue(any("Vidange" in x.name for x in bon.point_ids))

    def test_le_modele_de_la_societe_passe_devant(self):
        reseau = self.env.ref("cultiveau_checklists.ck_hivernage")
        mien = reseau.action_copier_pour_moi()
        mien = self.env["cultiveau.checklist.modele"].browse(mien["res_id"])
        self.assertEqual(mien.company_id, self.env.company)
        mien.ligne_ids[0].name = "Mon premier point à moi"
        choisi = self.env["cultiveau.checklist.modele"].pour("hivernage", self.env.company, "pivot")
        self.assertEqual(choisi, mien)
        bon = self.env["cultiveau.bon"].create({"partner_id": self.agri.id, "installation_id": self.inst.id, "nature": "hivernage"})
        self.assertEqual(bon.point_ids[0].name, "Mon premier point à moi")

    def test_signature_avertit_sans_bloquer(self):
        bon = self.env["cultiveau.bon"].create({"partner_id": self.agri.id, "installation_id": self.inst.id, "nature": "depannage", "signe_par": "M. Source", "signature_client": b"aW1n",
                                                "ligne_ids": [(0, 0, {"genre": "piece", "product_id": self.env.ref("cultiveau_terrain.produit_main_oeuvre").id, "quantite": 1, "description": "MO"})]})
        self.assertTrue(bon.checklist_manques)
        bon.action_signer()
        self.assertEqual(bon.etat, "signe")
        self.assertTrue(any("points obligatoires non faits" in (m.body or "") for m in bon.message_ids))

    def test_toutes_les_natures_ont_leur_checklist(self):
        Modele = self.env["cultiveau.checklist.modele"]
        for nature in ("remise_en_service", "hivernage", "entretien", "mise_en_service", "depannage", "diagnostic"):
            self.assertTrue(Modele.pour(nature, self.env.company), nature)
