from datetime import date, timedelta

from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "cultiveau")
class TestPhasesDevis(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write({"cultiveau_decl_chantier": True, "cultiveau_decl_acompte": False, "cultiveau_decl_achats": False, "cultiveau_decl_mise_en_service": False})
        cls.agri = cls.env["res.partner"].create({"name": "Earl des Terres", "zip": "30250", "cultiveau_type": "agriculteur"})
        cls.inst = cls.env["cultiveau.installation"].create({"name": "Aspersion Terres", "partner_id": cls.agri.id, "type_systeme": "micro_aspersion"})
        cls.tube = cls.env["product.product"].create({"name": "Tube PE Ø75", "list_price": 3.0, "type": "consu", "is_storable": True})
        cls.asperseur = cls.env["product.product"].create({"name": "Asperseur", "list_price": 40.0, "type": "consu", "is_storable": True})
        heure = cls.env.ref("uom.product_uom_hour")
        cls.pose = cls.env["product.product"].create({"name": "Pose", "list_price": 48.0, "type": "service", "uom_id": heure.id, "uom_po_id": heure.id})
        wh = cls.env["stock.warehouse"].search([("company_id", "=", cls.company.id)], limit=1)
        cls.env["stock.quant"]._update_available_quantity(cls.tube, wh.lot_stock_id, 300)
        cls.devis = cls.env["sale.order"].create({"partner_id": cls.agri.id, "cultiveau_installation_id": cls.inst.id, "cultiveau_type_systeme": "micro_aspersion", "commitment_date": "2027-03-01 08:00:00", "order_line": [
            Command.create({"display_type": "line_section", "name": "Réseau enterré", "cultiveau_phase": True, "cultiveau_jours": 3, "cultiveau_jalon_pct": 40, "sequence": 10}),
            Command.create({"product_id": cls.tube.id, "product_uom_qty": 500, "sequence": 11}),
            Command.create({"product_id": cls.pose.id, "product_uom_qty": 16, "sequence": 12}),
            Command.create({"display_type": "line_section", "name": "Postes d'arrosage", "cultiveau_phase": True, "cultiveau_jours": 2, "cultiveau_jalon_pct": 30, "sequence": 20}),
            Command.create({"product_id": cls.asperseur.id, "product_uom_qty": 24, "sequence": 21}),
            Command.create({"product_id": cls.pose.id, "product_uom_qty": 8, "sequence": 22})]})

    def test_stock_sur_la_ligne(self):
        lignes = {l.product_id: l for l in self.devis.order_line if l.product_id}
        self.assertEqual(lignes[self.tube].cultiveau_dispo, 300)
        self.assertEqual(lignes[self.tube].cultiveau_manque, 200)
        self.assertEqual(lignes[self.asperseur].cultiveau_manque, 24)
        self.assertEqual(lignes[self.pose].cultiveau_manque, 0)
        a = self.devis.action_depuis_mon_stock()
        self.assertTrue(a["context"].get("search_default_real_stock_available"))

    def test_phases_du_devis(self):
        phases = self.devis.cultiveau_phases()
        self.assertEqual([p["nom"] for p in phases], ["Réseau enterré", "Postes d'arrosage"])
        self.assertEqual(phases[0]["heures"], 16)
        self.assertEqual(set(phases[1]["lignes"].mapped("product_id")), {self.asperseur, self.pose})
        self.assertEqual(self.devis.cultiveau_nb_phases, 2)
        self.assertIn("40 %", self.devis.cultiveau_phases_apercu)

    def test_le_chantier_reprend_les_phases(self):
        self.devis.action_confirm()
        c = self.devis.cultiveau_chantier_ids[:1]
        self.assertTrue(c)
        self.assertEqual(c.phase_ids.mapped("name"), ["Réseau enterré", "Postes d'arrosage"])
        p1, p2 = c.phase_ids.sorted("sequence")
        self.assertEqual(p1.jalon_pct, 40)
        self.assertEqual(p1.heures_prevues, 16)
        self.assertEqual(p1.date_debut, date(2027, 3, 1))
        self.assertEqual(p1.date_fin, date(2027, 3, 3))
        self.assertEqual(p2.date_debut, date(2027, 3, 4))
        self.assertEqual(c.date_fin, date(2027, 3, 5))
        lignes = {l.product_id: l for l in c.ligne_ids}
        self.assertEqual(lignes[self.tube].phase_id, p1)
        self.assertEqual(lignes[self.asperseur].phase_id, p2)
        self.assertEqual(lignes[self.asperseur].besoin_le, date(2027, 3, 4))
        self.assertIn("Réseau enterré", c.plan_facturation)
