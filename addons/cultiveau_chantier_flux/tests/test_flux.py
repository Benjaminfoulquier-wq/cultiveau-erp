from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "cultiveau")
class TestFlux(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write({"cultiveau_decl_chantier": True, "cultiveau_decl_acompte": True, "cultiveau_decl_achats": False, "cultiveau_decl_mise_en_service": True, "cultiveau_acompte_pct": 30})
        cls.agri = cls.env["res.partner"].create({"name": "Earl des Prés", "zip": "30250", "cultiveau_type": "agriculteur"})
        cls.inst = cls.env["cultiveau.installation"].create({"name": "Goutte à goutte Prés", "partner_id": cls.agri.id, "type_systeme": "goutte_surface"})
        cls.tube = cls.env["product.product"].create({"name": "Tube PE Ø63", "list_price": 2.0, "type": "consu", "is_storable": True})
        cls.vanne = cls.env["product.product"].create({"name": "Vanne 2\"", "list_price": 50.0, "type": "consu", "is_storable": True})
        cls.wh = cls.env["stock.warehouse"].search([("company_id", "=", cls.company.id)], limit=1)
        cls.env["stock.quant"]._update_available_quantity(cls.tube, cls.wh.lot_stock_id, 1000)
        cls.env["stock.quant"]._update_available_quantity(cls.vanne, cls.wh.lot_stock_id, 20)
        cls.devis = cls.env["sale.order"].create({"partner_id": cls.agri.id, "cultiveau_installation_id": cls.inst.id, "cultiveau_type_systeme": "goutte_surface", "order_line": [
            Command.create({"display_type": "line_section", "name": "Réseau", "cultiveau_phase": True, "cultiveau_jours": 2, "cultiveau_jalon_pct": 40, "sequence": 10}),
            Command.create({"product_id": cls.tube.id, "product_uom_qty": 400, "sequence": 11}),
            Command.create({"display_type": "line_section", "name": "Têtes de secteur", "cultiveau_phase": True, "cultiveau_jours": 1, "cultiveau_jalon_pct": 20, "sequence": 20}),
            Command.create({"product_id": cls.vanne.id, "product_uom_qty": 6, "sequence": 21})]})
        cls.devis.action_confirm()
        cls.chantier = cls.devis.cultiveau_chantier_ids[:1]

    def _stock(self, p):
        return p.with_context(warehouse_id=self.wh.id).qty_available

    def test_phase_sort_le_stock_une_seule_fois(self):
        c = self.chantier
        p1, p2 = c.phase_ids.sorted("sequence")
        livraisons_avant = self.devis.picking_ids
        self.assertEqual(len(livraisons_avant), 1)
        p1.action_demarrer_phase()
        self.assertEqual(p1.etat, "en_cours")
        self.assertEqual(c.etat, "en_cours")
        self.assertEqual(self._stock(self.tube), 600)   # 400 sortis, une seule fois
        self.assertEqual(self._stock(self.vanne), 20)   # la phase 2 n'a pas bougé
        self.assertTrue(p1.picking_id.state == "done")
        # pas de bon de sortie à côté : la livraison de la commande a servi, le reste est en reliquat
        self.assertEqual(len(self.devis.picking_ids), 2)
        reliquat = self.devis.picking_ids.filtered(lambda p: p.state != "done")
        self.assertEqual(reliquat.move_ids.product_id, self.vanne)
        self.assertEqual(len(self.env["stock.picking"].search([("partner_id", "=", self.agri.id), ("picking_type_code", "=", "outgoing")])), 2)
        p2.action_demarrer_phase()
        self.assertEqual(self._stock(self.vanne), 14)
        self.assertTrue(all(p.state == "done" for p in self.devis.picking_ids))

    def test_terminer_facture_le_jalon(self):
        c = self.chantier
        p1 = c.phase_ids.sorted("sequence")[0]
        p1.action_demarrer_phase()
        n = len(self.devis.invoice_ids)
        p1.action_terminer_phase()
        self.assertEqual(p1.etat, "termine")
        self.assertEqual(p1.jalon_etat, "facture")
        self.assertEqual(len(self.devis.invoice_ids), n + 1)
        self.assertTrue(all(l.quantite_posee == l.quantite_prevue for l in p1.ligne_ids))

    def test_mise_en_service_lance_la_suite(self):
        c = self.chantier
        for p in c.phase_ids.sorted("sequence"):
            p.action_demarrer_phase()
        c.phase_ids.sorted("sequence")[0].action_terminer_phase()
        c.write({"pv_date": "2027-04-10", "pv_pression_sortie_pompe_bar": 4.2, "pv_pression_point_defavorable_bar": 1.4, "pv_antiretour": True, "pv_securites_testees": True})
        c.action_mise_en_service()
        self.assertTrue(c.solde_invoice_id)
        self.assertEqual(self.devis.cultiveau_mise_en_service_id.state, "1_done")
        self.assertTrue(c.activity_ids.filtered(lambda a: "entretien" in (a.summary or "").lower()))
        self.assertTrue(all(p.etat == "termine" for p in c.phase_ids))
        self.assertEqual(c.installation_id.etat, "en_service")
