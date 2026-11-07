from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "cultiveau")
class TestDeclenche(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write({"cultiveau_decl_chantier": True, "cultiveau_decl_acompte": True, "cultiveau_decl_achats": True, "cultiveau_decl_mise_en_service": True, "cultiveau_acompte_pct": 30})
        cls.agri = cls.env["res.partner"].create({"name": "Earl du Pech", "zip": "30250", "cultiveau_type": "agriculteur"})
        cls.fourn_a = cls.env["res.partner"].create({"name": "Fournisseur A", "is_company": True})
        cls.fourn_b = cls.env["res.partner"].create({"name": "Fournisseur B", "is_company": True})
        cls.tube = cls.env["product.product"].create({"name": "Tube PE Ø110", "list_price": 5.0, "standard_price": 3.0, "type": "consu", "is_storable": True,
                                                      "seller_ids": [Command.create({"partner_id": cls.fourn_a.id, "price": 3.2, "delay": 5, "product_code": "A-110"})]})
        cls.vanne = cls.env["product.product"].create({"name": "Vanne 4\"", "list_price": 120.0, "standard_price": 70.0, "type": "consu", "is_storable": True,
                                                       "seller_ids": [Command.create({"partner_id": cls.fourn_b.id, "price": 68.0, "delay": 10})]})
        cls.pompe = cls.env["product.product"].create({"name": "Pompe sans fournisseur", "list_price": 4000.0, "type": "consu", "is_storable": True})
        cls.pose = cls.env["product.product"].create({"name": "Pose", "list_price": 50.0, "type": "service"})
        cls.inst = cls.env["cultiveau.installation"].create({"name": "Goutte à goutte Pech", "partner_id": cls.agri.id, "type_systeme": "goutte_surface", "surface_ha": 5})
        # 40 tubes en stock : il en manquera 160 sur 200
        wh = cls.env["stock.warehouse"].search([("company_id", "=", cls.company.id)], limit=1)
        cls.env["stock.quant"]._update_available_quantity(cls.tube, wh.lot_stock_id, 40)
        cls.devis = cls.env["sale.order"].create({"partner_id": cls.agri.id, "cultiveau_installation_id": cls.inst.id, "cultiveau_type_systeme": "goutte_surface", "order_line": [
            Command.create({"display_type": "line_section", "name": "Lot 3 — Réseau", "sequence": 10}),
            Command.create({"product_id": cls.tube.id, "product_uom_qty": 200, "sequence": 11}),
            Command.create({"product_id": cls.vanne.id, "product_uom_qty": 3, "sequence": 12}),
            Command.create({"product_id": cls.pompe.id, "product_uom_qty": 1, "sequence": 13}),
            Command.create({"product_id": cls.pose.id, "product_uom_qty": 10, "sequence": 20})]})

    def test_besoins_avant_confirmation(self):
        b = {x["product"]: x for x in self.devis.cultiveau_besoins()}
        self.assertEqual(b[self.tube]["qte"], 200)
        self.assertEqual(b[self.tube]["couvert_stock"], 40)
        self.assertEqual(b[self.tube]["manque"], 160)
        self.assertEqual(b[self.vanne]["manque"], 3)
        self.assertNotIn(self.pose, b)  # un service ne s'approvisionne pas
        self.assertEqual(self.devis.cultiveau_nb_manquants, 3)
        w = self.env["cultiveau.approvisionnement"].with_context(default_order_id=self.devis.id).create({})
        lignes = {l.product_id: l for l in w.ligne_ids}
        self.assertEqual(lignes[self.tube].fournisseur_id, self.fourn_a)
        self.assertEqual(lignes[self.tube].prix, 3.2)
        self.assertEqual(lignes[self.tube].a_commander, 160)
        self.assertFalse(lignes[self.pompe].fournisseur_id)
        self.assertIn("Pompe sans fournisseur", w.sans_fournisseur)
        self.assertAlmostEqual(w.total_a_commander, 160 * 3.2 + 3 * 68.0)

    def test_confirmation_declenche_tout(self):
        self.devis.action_confirm()
        d = self.devis
        self.assertEqual(d.state, "sale")
        self.assertTrue(d.cultiveau_declenche_le)
        # chantier, avec le matériel du devis
        self.assertEqual(len(d.cultiveau_chantier_ids), 1)
        self.assertEqual(set(d.cultiveau_chantier_ids.ligne_ids.mapped("product_id")), {self.tube, self.vanne, self.pompe})
        self.assertTrue(d.cultiveau_chantier_ids.phase_ids)
        # mise en service à planifier
        self.assertTrue(d.cultiveau_mise_en_service_id)
        self.assertEqual(d.cultiveau_mise_en_service_id.cultiveau_nature, "mise_en_service")
        self.assertEqual(d.cultiveau_mise_en_service_id.cultiveau_installation_id, self.inst)
        # facture d'acompte brouillon à 30 %
        self.assertTrue(d.cultiveau_acompte_facture)
        fa = d.invoice_ids.filtered(lambda f: f.state == "draft")
        self.assertEqual(len(fa), 1)
        self.assertAlmostEqual(fa.amount_total, d.cultiveau_acompte_montant, places=0)
        # une demande de prix par fournisseur, seulement les manquants ; la pompe sans fournisseur est signalée
        po = d.cultiveau_purchase_ids
        self.assertEqual(set(po.mapped("partner_id")), {self.fourn_a, self.fourn_b})
        self.assertTrue(all(p.state == "draft" for p in po))
        la = po.filtered(lambda p: p.partner_id == self.fourn_a).order_line
        self.assertEqual(la.product_qty, 160)
        self.assertEqual(la.price_unit, 3.2)
        self.assertEqual(d.cultiveau_nb_achats, 2)
        corps = " ".join(d.message_ids.mapped("body"))
        self.assertIn("la chaîne est lancée", corps)
        self.assertIn("Pompe sans fournisseur", corps)
        # le panneau
        self.assertIn("Chantier", d.cultiveau_declenchements)
        self.assertIn("Acompte", d.cultiveau_declenchements)
        # relancer ne duplique rien
        d.action_declencher()
        self.assertEqual(len(d.cultiveau_chantier_ids), 1)
        self.assertEqual(len(d.cultiveau_purchase_ids), 2)
        self.assertEqual(len(d.invoice_ids), 1)

    def test_reglages_eteints(self):
        self.company.write({"cultiveau_decl_chantier": False, "cultiveau_decl_acompte": False, "cultiveau_decl_achats": False, "cultiveau_decl_mise_en_service": False})
        self.devis.action_confirm()
        self.assertFalse(self.devis.cultiveau_chantier_ids)
        self.assertFalse(self.devis.cultiveau_purchase_ids)
        self.assertFalse(self.devis.invoice_ids)
        self.assertFalse(self.devis.cultiveau_mise_en_service_id)

    def test_comptoir_ne_declenche_pas(self):
        vente = self.env["sale.order"].create({"partner_id": self.agri.id, "origin": "Comptoir", "order_line": [Command.create({"product_id": self.vanne.id, "product_uom_qty": 1})]})
        vente.action_confirm()
        self.assertFalse(vente.cultiveau_purchase_ids)
        self.assertFalse(vente.cultiveau_declenche_le)

    def test_commander_tout_le_devis(self):
        w = self.env["cultiveau.approvisionnement"].with_context(default_order_id=self.devis.id).create({"tout": True})
        w._onchange_tout()
        lignes = {l.product_id: l for l in w.ligne_ids}
        self.assertEqual(lignes[self.tube].a_commander, 200)
        lignes[self.pompe].fournisseur_id = self.fourn_b
        lignes[self.pompe].prix = 3500
        w.action_commander()
        po = self.devis.cultiveau_purchase_ids
        self.assertEqual(len(po), 2)
        pb = po.filtered(lambda p: p.partner_id == self.fourn_b)
        self.assertEqual(set(pb.order_line.mapped("product_id")), {self.vanne, self.pompe})
        self.assertEqual(pb.order_line.filtered(lambda l: l.product_id == self.pompe).price_unit, 3500)
