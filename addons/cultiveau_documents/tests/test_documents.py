from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDocuments(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.societe = env.company
        env["res.company"].cultiveau_mise_en_page()
        cls.agri = env["res.partner"].create({"name": "Ferme des Documents", "cultiveau_type": "agriculteur", "email": "ferme.documents@exemple.fr",
                                              "company_id": cls.societe.id, "lang": "fr_FR" if env["res.lang"].search_count([("code", "=", "fr_FR")]) else env.user.lang})
        cls.pompe = env["product.product"].create({"name": "Pompe documents", "type": "consu", "list_price": 1000, "invoice_policy": "order"})
        cls.devis = env["sale.order"].create({"partner_id": cls.agri.id, "company_id": cls.societe.id,
                                              "order_line": [(0, 0, {"product_id": cls.pompe.id, "product_uom_qty": 2})]})

    def test_mise_en_page_et_devis(self):
        self.assertEqual(self.societe.external_report_layout_id, self.env.ref("cultiveau_documents.external_layout_cultiveau"))
        self.assertIn("Réserve de propriété", self.societe.cultiveau_cgv)
        self.assertEqual(self.devis.cultiveau_acompte_pct, 30)
        self.assertEqual(self.devis.cultiveau_acompte_montant, self.devis.currency_id.round(self.devis.amount_total * 0.3))
        html = self.env["ir.actions.report"]._render_qweb_html("sale.report_saleorder", self.devis.ids)[0].decode()
        for attendu in ("Bon pour accord", "Acompte à la commande", "Membre du réseau Cultiveau", "Conditions générales de vente"):
            self.assertIn(attendu, html)
        self.assertEqual(self.devis._find_mail_template(), self.env.ref("cultiveau_documents.modele_mail_devis"))

    def test_mise_en_forme_section(self):
        devis = self.env["sale.order"].create({"partner_id": self.agri.id, "company_id": self.societe.id, "order_line": [
            (0, 0, {"display_type": "line_section", "name": "Station de pompage", "cultiveau_html": "<span style='color:#c00'><strong>Station de pompage</strong></span>"}),
            (0, 0, {"product_id": self.pompe.id, "product_uom_qty": 1})]})
        html = self.env["ir.actions.report"]._render_qweb_html("sale.report_saleorder", devis.ids)[0].decode()
        self.assertIn("color:#c00", html.replace('"', "'"))
        self.assertIn("<strong>Station de pompage</strong>", html)

    def test_police_par_ligne(self):
        devis = self.env["sale.order"].create({"partner_id": self.agri.id, "company_id": self.societe.id, "order_line": [
            (0, 0, {"display_type": "line_section", "name": "Station de pompage", "cultiveau_police": "manuscrite"}),
            (0, 0, {"product_id": self.pompe.id, "product_uom_qty": 1, "cultiveau_police": "bookman"})]})
        ligne = devis.order_line.filtered(lambda l: l.product_id)
        self.assertIn("URW Bookman", ligne.cultiveau_police_css())
        html = self.env["ir.actions.report"]._render_qweb_html("sale.report_saleorder", devis.ids)[0].decode()
        self.assertIn("URW Bookman", html)   # la police de la ligne d'article
        self.assertIn("URW Chancery", html)  # la police manuscrite de la section
        # une ligne sans police choisie ne force aucune police
        autre = self.env["sale.order.line"].new({"order_id": devis.id, "product_id": self.pompe.id})
        self.assertEqual(autre.cultiveau_police_css(), "")

    def test_police_des_documents(self):
        self.assertEqual(self.societe.cultiveau_police, "sans")
        self.assertIn("Helvetica", self.societe.cultiveau_police_css())
        self.societe.write({"cultiveau_police": "serif", "cultiveau_taille": 11})
        html = self.env["ir.actions.report"]._render_qweb_html("sale.report_saleorder", self.devis.ids)[0].decode()
        self.assertIn("Georgia", html)
        self.assertIn("font-size: 11px", html)

    def test_relances_devis_puis_activite(self):
        self.devis.action_quotation_sent()
        self.assertEqual(self.devis.cultiveau_envoye_le, fields.Date.today())
        self.devis.cultiveau_envoye_le = fields.Date.today() - timedelta(days=8)
        self.env["sale.order"]._cron_relancer_devis()
        self.assertEqual(self.devis.cultiveau_relances, 1)
        self.assertTrue(self.devis.message_ids.filtered(lambda m: m.subject and "regarder le devis" in m.subject))
        self.env["sale.order"]._cron_relancer_devis()  # trop tôt pour la deuxième
        self.assertEqual(self.devis.cultiveau_relances, 1)
        self.devis.cultiveau_derniere_relance = fields.Date.today() - timedelta(days=8)
        self.env["sale.order"]._cron_relancer_devis()
        self.assertEqual(self.devis.cultiveau_relances, 2)
        self.devis.cultiveau_derniere_relance = fields.Date.today() - timedelta(days=8)
        self.env["sale.order"]._cron_relancer_devis()
        self.assertEqual(self.devis.cultiveau_relances, 2)
        self.assertTrue(self.devis.activity_ids.filtered(lambda a: a.summary.startswith("Appeler")))

    def test_acompte_facture_et_rappel(self):
        # À la confirmation, « le devis déclenche tout » prépare déjà la facture d'acompte.
        self.devis.action_confirm()
        self.assertTrue(self.devis.cultiveau_acompte_facture)
        facture = self.devis.invoice_ids
        self.assertEqual(len(facture), 1, "un seul acompte préparé à la confirmation")
        # Le bouton « Facture d'acompte » n'en crée pas un deuxième : il ouvre celui qui existe.
        action = self.devis.action_facture_acompte()
        self.assertEqual((action["res_model"], action["res_id"]), ("account.move", facture.id))
        self.assertEqual(len(self.devis.invoice_ids), 1, "pas de facture d'acompte en double")
        facture.invoice_date = fields.Date.today() - timedelta(days=40)
        facture.action_post()
        facture.invoice_date_due = fields.Date.today() - timedelta(days=10)
        self.assertEqual(facture._get_mail_template(), self.env.ref("cultiveau_documents.modele_mail_facture"))
        self.assertIn("L. 441-10", facture.cultiveau_mentions_legales())
        self.env["account.move"]._cron_relancer_factures()
        self.assertEqual((facture.cultiveau_relances, facture.cultiveau_jours_retard), (1, 10))
        self.assertTrue(facture.message_ids.filtered(lambda m: m.subject and "rappel" in m.subject))

    def test_acompte_annule_redevient_a_facturer(self):
        devis = self.env["sale.order"].create({"partner_id": self.agri.id, "company_id": self.societe.id,
                                               "order_line": [(0, 0, {"product_id": self.pompe.id, "product_uom_qty": 1})]})
        devis.action_confirm()
        facture = devis.invoice_ids
        self.assertEqual(len(facture), 1)
        self.assertTrue(devis.cultiveau_acompte_facture)
        facture.button_cancel()
        self.assertEqual(facture.state, "cancel")
        self.assertFalse(devis.cultiveau_acompte_facture, "un acompte annulé ne compte plus comme facturé")
        # Le bouton redevient disponible et crée un nouvel acompte vivant (le devis n'en a jamais deux).
        action = devis.action_facture_acompte()
        self.assertEqual(action["res_model"], "sale.advance.payment.inv")
        wizard = self.env["sale.advance.payment.inv"].with_context(action["context"]).create({})
        wizard.create_invoices()
        vivantes = devis.invoice_ids.filtered(lambda m: m.state != "cancel")
        self.assertEqual(len(vivantes), 1, "un seul acompte vivant après ré-émission")
        self.assertTrue(devis.cultiveau_acompte_facture)
