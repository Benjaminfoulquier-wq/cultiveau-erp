from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "cultiveau")
class TestAcompteLigne(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write({"cultiveau_acompte_en_ligne": True, "cultiveau_acompte_pct": 30})
        cls.agri = cls.env["res.partner"].create({"name": "Earl des Lavandes", "zip": "30250", "cultiveau_type": "agriculteur"})
        cls.produit = cls.env["product.product"].create({"name": "Filtre", "list_price": 1000.0, "type": "consu"})

    def test_reglages_portail_suivent_l_acompte(self):
        self.assertTrue(self.company.portal_confirmation_pay)
        self.assertTrue(self.company.portal_confirmation_sign)
        self.assertAlmostEqual(self.company.prepayment_percent, 0.30)
        self.company.cultiveau_acompte_pct = 40
        self.assertAlmostEqual(self.company.prepayment_percent, 0.40)
        self.company.cultiveau_acompte_en_ligne = False
        self.assertFalse(self.company.portal_confirmation_pay)
        self.company.write({"cultiveau_acompte_en_ligne": True, "cultiveau_acompte_pct": 30})

    def test_le_devis_demande_l_acompte_en_ligne(self):
        devis = self.env["sale.order"].create({"partner_id": self.agri.id, "order_line": [Command.create({"product_id": self.produit.id, "product_uom_qty": 2})]})
        self.assertTrue(devis.require_payment)
        self.assertAlmostEqual(devis.prepayment_percent, 0.30)
        self.assertIn("30 %", devis.cultiveau_acompte_en_ligne_texte)
        devis.cultiveau_acompte_pct = 50
        self.assertAlmostEqual(devis.prepayment_percent, 0.50)
        # le montant demandé au portail est bien l'acompte
        self.assertAlmostEqual(devis._get_prepayment_required_amount(), devis.amount_total * 0.5, places=2)

    def test_virement_active_quand_il_y_a_un_compte(self):
        banque = self.env["res.bank"].create({"name": "Crédit Test", "bic": "TESTFRPP"})
        self.env["res.partner.bank"].create({"acc_number": "FR7612345678901234567890123", "partner_id": self.company.partner_id.id, "bank_id": banque.id, "company_id": self.company.id})
        self.company.cultiveau_activer_paiement_en_ligne()
        self.assertTrue(self.company.cultiveau_virement_actif)
        self.assertIn("Virement", self.company.cultiveau_fournisseurs_actifs)
