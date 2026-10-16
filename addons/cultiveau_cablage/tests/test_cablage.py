from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from ..models import regles


@tagged("post_install", "-at_install")
class TestCablage(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.s = cls.env.company
        cls.client = cls.env["res.partner"].create({"name": "GAEC du Câblage", "email": "gaec@cablage-test.fr"})
        cls.inst = cls.env["cultiveau.installation"].create({"name": "Aspersion des Essais", "partner_id": cls.client.id, "type_systeme": "couverture_integrale", "company_id": cls.s.id,
                                                             "puissance_kw": 13.2, "longueur_principale_m": 400, "simultaneite": 1, "niveau_automatisme": "programmateur",
                                                             "secteur_ids": [Command.create({"name": f"Secteur {k}", "surface_ha": 2, "organe": "asperseur", "longueur_m": 150 * k}) for k in range(1, 5)]})

    def test_regles(self):
        i = regles.courant_moteur(7.5)
        self.assertAlmostEqual(i, 15.0, delta=0.5)
        self.assertEqual(regles.disjoncteur_moteur(i), (13, 18))
        self.assertEqual(regles.contacteur(7.5, i), (7.5, 18))
        self.assertEqual(regles.demarrage_conseille(4), "direct")
        self.assertEqual(regles.demarrage_conseille(11), "etoile_triangle")
        self.assertEqual(regles.demarrage_conseille(4, regulation=True), "variateur")
        s, chute = regles.section_cable(i, 200)
        self.assertGreaterEqual(s, 6, "200 m : la chute de tension impose une section plus grosse que le courant")
        self.assertLessEqual(chute, 5)
        self.assertEqual(regles.section_electrovanne(100)[0], 0.75)
        self.assertEqual(regles.section_electrovanne(500)[0], 4.0)
        self.assertEqual(regles.calibre_general(45), 50)
        self.assertEqual(regles.programmateur_voies(5), 6)

    def test_depuis_etude_et_compilation(self):
        Armoire = self.env["cultiveau.armoire"]
        a = Armoire.depuis_installation(self.inst)
        self.assertEqual(a.reseau, "tri")
        pompe = a.depart_ids.filtered(lambda d: d.genre == "pompe")
        self.assertEqual(pompe.puissance_kw, 15, "la puissance moteur standard au-dessus de 13,2 kW")
        self.assertEqual(len(a.sortie_ids), 4)
        self.assertEqual(a.sortie_ids[-1].longueur_m, 400 + 600 + 20)
        self.assertEqual(Armoire.depuis_installation(self.inst), a, "un seul dossier par installation")
        a.action_compiler()
        self.assertEqual(a.etat, "compile")
        self.assertEqual(a.indice, "A")
        self.assertAlmostEqual(pompe.courant_a, 30.0, delta=1)
        self.assertEqual(pompe.demarrage_retenu, "etoile_triangle")
        self.assertEqual((pompe.repere_q, pompe.repere_km, pompe.repere, pompe.repere_f), ("Q1", "KM1", "M1", "F1"))
        self.assertIn("24–32 A", pompe.disjoncteur)
        self.assertGreaterEqual(a.calibre_general_a, 40)
        self.assertEqual(a.ddr_type, "300 mA type A")
        self.assertEqual(a.voies, 6, "4 secteurs + vanne maître → programmateur 6 voies")
        self.assertEqual(a.transfo_va, 50)
        y = a.sortie_ids.sorted("sequence")
        self.assertEqual([s.repere for s in y], ["Y1", "Y2", "Y3", "Y4"])
        self.assertTrue(y[-1].section_mm2 >= 2.5, "1 020 m de câble 24 V")
        self.assertTrue(a.borne_ids.filtered(lambda b: b.bornier == "XA" and b.destination.endswith("PE")))
        self.assertTrue(a.borne_ids.filtered(lambda b: b.bornier == "XB" and b.repere == "Y0"), "la vanne maître a sa borne")
        self.assertTrue(a.borne_ids.filtered(lambda b: b.bornier == "XC" and b.repere == "B1"))
        reperes = a.ligne_ids.mapped("repere")
        for r in ("Q0", "Q0.1", "F0", "Q1", "KM1", "T1", "A1", "Y1", "Y0", "S0"):
            self.assertIn(r, reperes)
        self.assertTrue(any("étoile-triangle" in l.designation for l in a.ligne_ids))
        for svg in (a.folio_puissance, a.folio_commande, a.folio_borniers, a.folio_nomenclature):
            self.assertTrue(svg.startswith("<svg"))
            self.assertIn("INDICE A", svg)
        self.assertIn("KM1", a.folio_puissance)
        self.assertIn("Y4", a.folio_commande)
        self.assertIn("Pré-dimensionnement", a.folio_nomenclature)
        self.assertEqual(a.nb_folios, 4)
        # une modification recompile en indice B
        pompe.longueur_cable_m = 250
        self.assertEqual(a.etat, "brouillon")
        a.action_compiler()
        self.assertEqual(a.indice, "B")
        self.assertIn("INDICE B", a.folio_puissance)
        self.assertGreaterEqual(pompe.section_mm2, 16)

    def test_variateur_mono_et_alertes(self):
        a = self.env["cultiveau.armoire"].create({"installation_id": self.inst.id, "reseau": "mono", "regulation_pression": True, "pilotage": "automate", "simultaneite": 2,
                                                  "depart_ids": [Command.create({"genre": "pompe", "name": "Pompe", "puissance_kw": 2.2, "longueur_cable_m": 60})],
                                                  "sortie_ids": [Command.create({"name": "Goutte à goutte", "longueur_m": 900})]})
        a.action_compiler()
        pompe = a.depart_ids[0]
        self.assertEqual(pompe.demarrage_retenu, "variateur")
        self.assertEqual(pompe.repere_km, "U1")
        self.assertEqual(pompe.variateur_kw, 2.2)
        self.assertEqual(a.ddr_type, "300 mA type A", "un variateur monophasé ne force pas le type B")
        self.assertIn("B2", a.borne_ids.filtered(lambda b: b.bornier == "XC").mapped("repere"), "capteur de pression avec la régulation")
        self.assertTrue(any("chute" in x for x in a.alertes.split("\n")), "900 m de 24 V : signalé")
        self.assertIn("Automate", a.folio_commande)
        with self.assertRaises(UserError):
            self.env["cultiveau.armoire"].create({"installation_id": self.inst.id}).action_compiler()

    def test_devis_rapport_map_mathis(self):
        a = self.env["cultiveau.armoire"].depuis_installation(self.inst)
        a.action_compiler()
        # le devis
        with self.assertRaises(UserError):
            a.action_ajouter_au_devis()
        produit = self.env["product.product"].create({"name": "Tube test", "list_price": 1})
        devis = self.env["sale.order"].create({"partner_id": self.client.id, "cultiveau_installation_id": self.inst.id, "order_line": [Command.create({"product_id": produit.id})]})
        a.action_ajouter_au_devis()
        lot = devis.order_line.filtered(lambda l: l.cultiveau_armoire_id == a)
        self.assertTrue(lot.filtered(lambda l: l.display_type == "line_section" and "Lot 7" in l.name))
        self.assertGreater(len(lot), 10)
        n = len(devis.order_line)
        a.action_ajouter_au_devis()
        self.assertEqual(len(devis.order_line), n, "réajouter remplace le lot, sans doublon")
        # le rapport (HTML : le PDF demande wkhtmltopdf)
        html = self.env["ir.actions.report"]._render_qweb_html("cultiveau_cablage.action_report_armoire", a.ids)[0].decode()
        self.assertEqual(html.count("<svg"), 4)
        # la map
        fiche = self.env["cultiveau.map"].fiche("dossier", self.inst.id)
        self.assertTrue(any(b["titre"] == "Câblage" for b in fiche["blocs"]))
        self.assertIn("cablage_dossier", [x["cle"] for x in fiche["actions"]])
        self.assertIn("cablage", [p["cle"] for p in self.env["cultiveau.map"]._portes()["bureau"]])
        # Mathis
        M = self.env["cultiveau.mathis"]
        self.assertTrue({"cablage", "compiler_cablage"} <= {o["function"]["name"] for o in M._outils()})
        res, _a = M._executer("cablage", {"installation_id": self.inst.id})
        self.assertEqual(res["indice"], "A")
        self.assertEqual(res["electrovannes"], 4)
        self.assertIn("compiler_cablage", M._ecritures())
        self.assertEqual(self.inst.nb_armoires, 1)
        self.assertEqual(self.inst.action_cablage()["res_id"], a.id)
