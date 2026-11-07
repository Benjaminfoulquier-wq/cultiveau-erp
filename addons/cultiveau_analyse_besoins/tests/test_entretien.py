from odoo.tests import TransactionCase, tagged

from odoo.addons.cultiveau_parcelles.tests.test_parcelles import XML


@tagged("post_install", "-at_install", "cultiveau")
class TestEntretien(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.agri = cls.env["res.partner"].create({"name": "EARL de l'Entretien", "zip": "32000", "cultiveau_type": "agriculteur", "email": "entretien@exemple.fr"})
        cls.inst = cls.env["cultiveau.installation"].create({"name": "Projet pivot", "partner_id": cls.agri.id, "type_systeme": "pivot"})
        cls.mais = cls.env.ref("cultiveau_frise.culture_mais_grain")

    def test_sans_declaration_on_propose_l_import(self):
        self.assertEqual(self.inst.nb_parcelles_client, 0)
        action = self.inst.action_reprendre_parcelles()
        self.assertEqual(action["res_model"], "cultiveau.import.telepac")
        self.assertEqual(action["context"]["default_installation_id"], self.inst.id)

    def test_import_depuis_le_projet_remplit_le_parcellaire(self):
        import base64
        w = self.env["cultiveau.import.telepac"].create({"partner_id": self.agri.id, "installation_id": self.inst.id, "campagne": 2026,
                                                        "nom_fichier": "declaration.xml", "fichier": base64.b64encode(XML if isinstance(XML, bytes) else XML.encode())})
        w.action_importer()
        self.inst.invalidate_recordset()
        self.assertEqual(self.inst.nb_parcelles_client, 2)
        # seule la parcelle avec une culture reliée (le maïs) est reprise ; le code ZZZ inconnu attend d'être relié
        self.assertEqual(len(self.inst.parcelle_ids), 1)
        self.assertAlmostEqual(self.inst.surface_ha, 12.0, delta=0.05)
        self.assertIn(self.mais, self.inst.culture_ids)
        self.assertEqual(self.inst.culture_pointe_id, self.mais)
        self.assertTrue(self.inst.parcelle.startswith("îlot 1 p. 1"), self.inst.parcelle)
        self.assertTrue(self.inst.commune.startswith("INSEE "), self.inst.commune)
        self.assertIn("Campagne PAC 2026", self.inst.assolement)
        self.assertIn("Maïs", self.inst.assolement)
        self.assertTrue(self.inst.etape_parcellaire_ok)
        self.assertTrue(self.inst.etape_cultures_ok)  # cultures et culture de pointe suffisent ; l'assolement prévisible reste à demander
        # un deuxième passage par le choix des parcelles : tout est proposé, on en garde la totalité
        action = self.inst.action_reprendre_parcelles()
        self.assertEqual(action["res_model"], "cultiveau.installation.parcelles")
        choix = self.env["cultiveau.installation.parcelles"].with_context(default_installation_id=self.inst.id).create({})
        self.assertEqual(choix.parcelle_ids, self.inst.parcelle_ids)
        self.assertAlmostEqual(choix.surface_ha, self.inst.surface_ha, places=2)

    def test_ce_qu_il_a_ecrit_n_est_pas_ecrase(self):
        self.env["cultiveau.parcelle"].importer(self.agri, "declaration.xml", XML, 2026)
        self.inst.write({"commune": "Auch", "assolement": "Il passe en semence.", "parcelle": "Les Grandes Terres"})
        self.inst.appliquer_parcelles(self.agri.cultiveau_parcelle_ids)
        self.assertEqual((self.inst.commune, self.inst.assolement, self.inst.parcelle), ("Auch", "Il passe en semence.", "Les Grandes Terres"))
        self.assertEqual(len(self.inst.parcelle_ids), 2)

    def test_avancement(self):
        self.assertIn("0 / 8", self.inst.entretien_html)
        self.inst.write({"hierarchie": "eau", "titre_prelevement": "autorisation", "energie": "thermique"})
        self.assertTrue(self.inst.etape_priorite_ok and self.inst.etape_titre_ok and self.inst.etape_energie_ok)
        self.assertIn("3 / 8", self.inst.entretien_html)
        self.assertIn("Reste à voir", self.inst.entretien_html)
