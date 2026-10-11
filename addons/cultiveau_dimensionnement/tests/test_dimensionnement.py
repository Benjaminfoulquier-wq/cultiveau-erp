from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from ..models import hydraulique as hy


@tagged("post_install", "-at_install")
class TestDimensionnement(TransactionCase):
    def test_formules(self):
        self.assertEqual(hy.diametre_conseille(106.7, "pe")[0], 200)  # 0,0296 m³/s : Ø 200 PE tient 1,41 m/s, Ø 180 dépasse 1,5
        self.assertAlmostEqual(hy.vitesse(106.7, 163.6), 1.41, places=2)
        self.assertAlmostEqual(hy.pertes_de_charge(106.7, 163.6, 400), 4.3, delta=0.5)  # ≈ 3,9 m linéaires + 10 %
        self.assertAlmostEqual(hy.puissance_kw(100, 40, 0.65), 16.8, delta=0.2)

    def test_secteurs_et_devis(self):
        client = self.env["res.partner"].create({"name": "GAEC Dimensionnement", "cultiveau_type": "agriculteur", "zip": "32000"})
        inst = self.env["cultiveau.installation"].create({
            "name": "Goutte à goutte maïs", "partner_id": client.id, "type_systeme": "goutte_surface", "surface_ha": 10, "besoin_pointe_mm_j": 6,
            "energie": "reseau", "puissance_souscrite_kva": 36, "niveau_automatisme": "programmateur", "longueur_principale_m": 400, "denivele_station_m": 4, "hauteur_aspiration_m": 3,
            "secteur_ids": [Command.create({"name": "Secteur nord", "surface_ha": 5, "organe": "goutteur", "debit_unitaire": 1.6, "pression_organe_bar": 1.0,
                                            "espacement_m": 0.5, "ecartement_m": 1.5, "longueur_m": 150, "denivele_m": 2}),
                            Command.create({"name": "Secteur sud", "surface_ha": 5, "organe": "goutteur", "debit_unitaire": 1.6, "pression_organe_bar": 1.0,
                                            "espacement_m": 0.5, "ecartement_m": 1.5, "longueur_m": 300, "denivele_m": -1})]})
        nord = inst.secteur_ids[0]
        self.assertEqual(nord.nb_organes, 66666)
        self.assertAlmostEqual(nord.debit_m3h, 106.7, delta=0.1)
        self.assertAlmostEqual(nord.pluviometrie_mm_h, 2.13, places=2)
        self.assertEqual(nord.diametre_calc, 200)
        self.assertGreater(nord.pression_tete_bar, 1.2)
        self.assertAlmostEqual(nord.longueur_rampes_m, 33333, delta=1)
        inst.action_dimensionner()
        self.assertEqual((inst.secteurs, inst.diametre_principal_mm), (2, 200))
        self.assertAlmostEqual(inst.debit_equipement_m3_h, 106.7, delta=0.1)
        self.assertTrue(20 < inst.hmt_m < 45, inst.hmt_m)
        self.assertTrue(8 < inst.puissance_kw < 20, inst.puissance_kw)
        self.assertIn("HMT", inst.dimensionnement_html)
        self.assertIn("m³/h", inst.pompe)
        # un tube PE 200 au catalogue de la société : il est pris pour la principale
        tube = self.env["product.template"].create({"name": "Tube PE 100 PN10 Ø 200", "cultiveau_dn": 200, "cultiveau_matiere": "PE", "list_price": 18.5, "sale_ok": True,
                                                    "uom_id": self.env.ref("uom.product_uom_meter").id, "uom_po_id": self.env.ref("uom.product_uom_meter").id})
        action = inst.action_generer_devis()
        devis = self.env["sale.order"].browse(action["res_id"])
        self.assertEqual((devis.partner_id, devis.cultiveau_installation_id), (client, inst))
        sections = devis.order_line.filtered(lambda l: l.display_type == "line_section").mapped("name")
        self.assertEqual(len(sections), 6)
        self.assertTrue(any(s.startswith("Lot 3") for s in sections))
        du_tube = devis.order_line.filtered(lambda l: l.product_id.product_tmpl_id == tube)
        self.assertEqual(len(du_tube), 3, "la principale et les deux conduites d'amenée sont en Ø 200")
        principale = du_tube.filtered(lambda l: "principale" in l.name)
        self.assertEqual((len(principale), principale.product_uom_qty), (1, 400))
        self.assertAlmostEqual(principale.price_unit, 18.5)
        a_preciser = devis.order_line.filtered(lambda l: l.product_id.default_code == "A-PRECISER")
        self.assertGreater(len(a_preciser), 5, "le reste attend son article")
        gaine = devis.order_line.filtered(lambda l: "goutte à goutte" in (l.name or "") and "nord" in (l.name or ""))
        self.assertEqual(gaine.product_uom_qty, 33333)
        self.assertEqual(len(devis.order_line.filtered(lambda l: "Électrovannes" in (l.name or ""))), 1)
        with self.assertRaises(UserError):
            self.env["cultiveau.installation"].create({"name": "Vide", "partner_id": client.id, "type_systeme": "pivot"}).action_generer_devis()
