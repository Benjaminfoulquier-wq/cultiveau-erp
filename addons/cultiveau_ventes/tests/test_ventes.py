from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "cultiveau")
class TestVentes(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.agri = cls.env["res.partner"].create({"name": "Earl des Oliviers", "zip": "30250", "cultiveau_type": "agriculteur"})
        cls.produit = cls.env["product.product"].create({"name": "Filtre à disques 3\"", "list_price": 850.0, "type": "consu"})

    def test_six_phases_du_pipeline(self):
        noms = self.env["crm.stage"].search([]).mapped("name")
        for attendu in ("Analyse des besoins (A1.1)", "Étude et dimensionnement (A1.2)", "Mise en service (A1.3) et réception", "Suivi et maintenance"):
            self.assertIn(attendu, noms)
        self.assertTrue(self.env.ref("cultiveau_ventes.stage_suivi").is_won)

    def test_opportunite_vers_installation(self):
        lead = self.env["crm.lead"].create({"name": "Goutte à goutte oliviers", "partner_id": self.agri.id, "type": "opportunity",
                                            "cultiveau_type_systeme": "goutte_surface", "cultiveau_surface_ha": 8, "cultiveau_origine": "assistant",
                                            "cultiveau_reference_appel": "APL-2026-0042"})
        lead.action_creer_installation()
        inst = lead.cultiveau_installation_id
        self.assertEqual(inst.partner_id, self.agri)
        self.assertEqual(inst.type_systeme, "goutte_surface")
        self.assertEqual(inst.surface_ha, 8)
        self.assertEqual(lead.stage_id, self.env.ref("cultiveau_ventes.stage_analyse"))
        self.assertEqual(inst.nb_opportunites, 1)

    def test_devis_par_lots_relie_a_l_installation(self):
        inst = self.env["cultiveau.installation"].create({"name": "GàG oliviers", "partner_id": self.agri.id, "type_systeme": "goutte_surface", "surface_ha": 8})
        action = inst.action_nouveau_devis()
        ctx = action["context"]
        self.assertEqual(ctx["default_sale_order_template_id"], self.env.ref("cultiveau_ventes.modele_goutte").id)
        devis = self.env["sale.order"].with_context(ctx).create({"partner_id": self.agri.id})
        devis._onchange_sale_order_template_id()
        sections = devis.order_line.filtered(lambda l: l.display_type == "line_section").mapped("name")
        self.assertEqual(len(sections), 6)
        self.assertIn("Lot 1 — Station de pompage et énergie", sections)
        self.assertEqual(devis.cultiveau_installation_id, inst)
        self.assertEqual(devis.cultiveau_type_systeme, "goutte_surface")
        self.assertFalse(devis.cultiveau_analyse_validee)
        devis.order_line.create({"order_id": devis.id, "product_id": self.produit.id, "product_uom_qty": 2})
        devis.action_confirm()
        self.assertEqual(devis.state, "sale")
        self.assertTrue(any("A1.1" in (m.body or "") for m in devis.message_ids), "l'avertissement du référentiel est consigné")
        self.assertEqual(inst.nb_devis, 1)
        inst.besoin_pointe_mm_j, inst.debit_equipement_m3_h, inst.hmt_m = 5, 30, 55
        self.assertIn("30 m³/h", devis.cultiveau_dimensionnement)

    def test_devis_sans_installation_en_cree_une(self):
        devis = self.env["sale.order"].create({"partner_id": self.agri.id, "cultiveau_type_systeme": "pivot"})
        devis.action_creer_installation()
        self.assertEqual(devis.cultiveau_installation_id.type_systeme, "pivot")
        self.assertEqual(devis.cultiveau_installation_id.partner_id, self.agri)

    def test_irrigation_a_l_usage_exemple_des_journees(self):
        """Maïs 30 ha, 50 000 €, 3,25 %, 5 000 € de maintenance, 900 000 m³ sur dix ans → ≈ 0,073 €/m³, ≈ 0,081 avec marge, ≈ 600 €/mois."""
        u = self.env["cultiveau.usage"].create({"partner_id": self.agri.id, "surface_ha": 30, "investissement": 50000, "taux_pct": 3.25,
                                                "duree_ans": 10, "entretien_an": 500, "marge_pct": 10, "volume_m3_an": 90000})
        self.assertAlmostEqual(u.volume_total, 900000)
        self.assertGreater(u.interets, 8000)
        self.assertLess(u.interets, 10500)
        self.assertAlmostEqual(u.prix_m3, 0.072, delta=0.003)
        self.assertAlmostEqual(u.prix_m3_marge, 0.080, delta=0.003)
        self.assertAlmostEqual(u.mensualite, 600, delta=15)
        self.assertLess(u.mensualite_capex, u.mensualite, "le crédit seul coûte moins par mois, mais sans la maintenance ni le SAV")
        self.assertAlmostEqual(u.volume_min, 81000)
        self.assertAlmostEqual(u.volume_max, 99000)
        self.assertIn("CAPEX", u.comparatif_html)
        self.assertIn("90–110", u.comparatif_html)
        u.action_pitch()
        self.assertTrue(self.agri.message_ids.filtered(lambda m: "financez votre récolte" in (m.body or "")))
        with self.assertRaises(Exception):
            u.write({"duree_ans": 0})

    def test_usage_depuis_l_installation(self):
        vigne = self.env.ref("cultiveau_frise.culture_vigne")
        inst = self.env["cultiveau.installation"].create({"name": "GàG vigne", "partner_id": self.agri.id, "type_systeme": "goutte_surface", "surface_ha": 12,
                                                          "culture_pointe_id": vigne.id, "besoin_pointe_mm_j": 4.5, "volume_autorise_m3": 25000})
        ctx = inst.action_simuler_usage()["context"]
        self.assertEqual(ctx["default_culture_id"], vigne.id)
        self.assertEqual(ctx["default_volume_m3_an"], 25000, "4,5 mm × 60 j × 12 ha = 32 400 m³, borné par le volume autorisé")
        self.assertIn("volume autorisé", ctx["default_volume_source"])
        u = self.env["cultiveau.usage"].with_context(ctx).create({"investissement": 30000})
        self.assertEqual(u.installation_id, inst)
        self.assertEqual(inst.nb_usages, 1)
        self.assertIn("vigne", u.name)
        sans_pointe = self.env["cultiveau.installation"].create({"name": "Sans pointe", "partner_id": self.agri.id, "type_systeme": "enrouleur", "surface_ha": 10})
        self.assertEqual(sans_pointe.action_simuler_usage()["context"]["default_volume_m3_an"], 30000, "3 000 m³/ha par défaut")
