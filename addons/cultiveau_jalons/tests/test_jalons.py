from datetime import date, timedelta

from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "cultiveau")
class TestJalons(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write({"cultiveau_decl_chantier": True, "cultiveau_decl_acompte": True, "cultiveau_decl_achats": False, "cultiveau_decl_mise_en_service": False, "cultiveau_acompte_pct": 30})
        cls.agri = cls.env["res.partner"].create({"name": "Earl du Causse", "zip": "30250", "cultiveau_type": "agriculteur"})
        cls.fourn = cls.env["res.partner"].create({"name": "Fournisseur J", "is_company": True})
        cls.tube = cls.env["product.product"].create({"name": "Tube PE Ø90", "list_price": 4.0, "type": "consu", "is_storable": True, "seller_ids": [Command.create({"partner_id": cls.fourn.id, "price": 2.5, "delay": 3})]})
        cls.pompe = cls.env["product.product"].create({"name": "Pompe 15 kW", "list_price": 6000.0, "type": "consu", "is_storable": True, "seller_ids": [Command.create({"partner_id": cls.fourn.id, "price": 4200.0, "delay": 21})]})
        cls.inst = cls.env["cultiveau.installation"].create({"name": "Goutte à goutte Causse", "partner_id": cls.agri.id, "type_systeme": "goutte_surface"})
        cls.devis = cls.env["sale.order"].create({"partner_id": cls.agri.id, "cultiveau_installation_id": cls.inst.id, "cultiveau_type_systeme": "goutte_surface", "order_line": [
            Command.create({"product_id": cls.tube.id, "product_uom_qty": 1000}), Command.create({"product_id": cls.pompe.id, "product_uom_qty": 1})]})
        cls.devis.action_confirm()
        cls.chantier = cls.devis.cultiveau_chantier_ids[:1]

    def test_jalons_par_defaut_et_materiel_rattache(self):
        c = self.chantier
        self.assertTrue(c)
        jalons = {p.name: p.jalon_pct for p in c.phase_ids}
        self.assertEqual(jalons["Tranchées et pose des réseaux"], 30)
        self.assertEqual(jalons["Station de tête et raccordements"], 30)
        self.assertEqual(c.jalons_pct_total, 60)
        lignes = {l.product_id: l for l in c.ligne_ids}
        self.assertEqual(lignes[self.tube].phase_id.name, "Tranchées et pose des réseaux")
        self.assertEqual(lignes[self.pompe].phase_id.name, "Station de tête et raccordements")
        self.assertIn("Solde à la mise en service", c.plan_facturation)
        self.assertIn("10 %", c.plan_facturation)  # 30 acompte + 30 + 30 : il reste 10

    def test_facturer_un_jalon_puis_le_solde(self):
        c = self.chantier
        phase = c.phase_ids.filtered(lambda p: p.name == "Tranchées et pose des réseaux")
        self.assertEqual(phase.jalon_etat, "a_facturer")
        n_avant = len(self.devis.invoice_ids)
        phase.action_facturer_jalon()
        self.assertEqual(phase.jalon_etat, "facture")
        self.assertEqual(len(self.devis.invoice_ids), n_avant + 1)
        self.assertAlmostEqual(phase.jalon_invoice_id.amount_total, self.devis.amount_total * 0.30, places=0)
        self.assertIn("Situation de travaux", phase.jalon_invoice_id.narration or "")
        with self.assertRaises(Exception):
            phase.action_facturer_jalon()  # pas deux fois
        c.action_facturer_solde()
        self.assertTrue(c.solde_invoice_id)
        # le solde déduit l'acompte de la commande et le jalon : il reste 40 % du TTC
        self.assertAlmostEqual(c.solde_invoice_id.amount_total, self.devis.amount_total * 0.40, places=0)

    def test_date_de_besoin_vers_les_achats(self):
        c = self.chantier
        station = c.phase_ids.filtered(lambda p: p.name == "Station de tête et raccordements")
        reseau = c.phase_ids.filtered(lambda p: p.name == "Tranchées et pose des réseaux")
        reseau.date_debut, station.date_debut = date.today() + timedelta(days=10), date.today() + timedelta(days=25)
        w = self.env["cultiveau.approvisionnement"].with_context(default_order_id=self.devis.id).create({})
        lignes = {l.product_id: l for l in w.ligne_ids}
        self.assertEqual(lignes[self.pompe].besoin_le, station.date_debut)
        self.assertEqual(lignes[self.tube].besoin_le, reseau.date_debut)
        w.action_commander()
        po = self.devis.cultiveau_purchase_ids
        self.assertEqual(len(po), 1)
        par_produit = {l.product_id: l for l in po.order_line}
        self.assertEqual(par_produit[self.pompe].date_planned.date(), station.date_debut)
        self.assertEqual(par_produit[self.tube].date_planned.date(), reseau.date_debut)
