from datetime import timedelta

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "cultiveau")
class TestCommandeProjet(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write({"cultiveau_decl_chantier": True, "cultiveau_decl_acompte": False, "cultiveau_decl_achats": False, "cultiveau_decl_mise_en_service": True,
                           "cultiveau_decl_taches": True, "cultiveau_decl_financement": True, "cultiveau_financement_seuil": 1000})
        cls.agri = cls.env["res.partner"].create({"name": "SCEA des Vergers", "email": "vergers@example.test", "zip": "89140", "cultiveau_type": "agriculteur"})
        cls.inst = cls.env["cultiveau.installation"].create({"name": "Station Vergers", "partner_id": cls.agri.id, "type_systeme": "goutte_surface"})
        heure = cls.env.ref("uom.product_uom_hour")
        cls.pompe = cls.env["product.product"].create({"name": "Pompe immergée", "list_price": 19000.0, "type": "consu", "is_storable": True})
        cls.montage = cls.env["product.product"].create({"name": "Montage pompe sur site", "list_price": 60.0, "type": "service", "uom_id": heure.id, "uom_po_id": heure.id})
        cls.cablage = cls.env["product.product"].create({"name": "Montage et câblage électrique", "list_price": 60.0, "type": "service", "uom_id": heure.id, "uom_po_id": heure.id})
        cls.mes = cls.env["product.product"].create({"name": "Forfait mise en route station de pompage", "list_price": 950.0, "type": "service"})
        cls.devis = cls.env["sale.order"].create({"partner_id": cls.agri.id, "cultiveau_installation_id": cls.inst.id, "cultiveau_type_systeme": "goutte_surface", "commitment_date": "2027-05-03 08:00:00", "order_line": [
            Command.create({"display_type": "line_section", "name": "Station", "cultiveau_phase": True, "cultiveau_jours": 3, "sequence": 10}),
            Command.create({"product_id": cls.pompe.id, "product_uom_qty": 1, "sequence": 11}),
            Command.create({"product_id": cls.montage.id, "product_uom_qty": 8, "sequence": 12}),
            Command.create({"product_id": cls.cablage.id, "product_uom_qty": 6, "sequence": 13}),
            Command.create({"product_id": cls.mes.id, "product_uom_qty": 1, "sequence": 14})]})

    def test_prestations_deviennent_des_taches(self):
        self.devis.action_confirm()
        taches = self.devis.cultiveau_tache_ids
        noms = sorted(taches.mapped("name"))
        self.assertEqual(len(taches), 3)  # montage, câblage, et la mise en service déjà créée, reliée à sa ligne
        self.assertTrue(any("Montage pompe" in n for n in noms))
        montage = taches.filtered(lambda t: "Montage pompe" in t.name)
        self.assertEqual(montage.cultiveau_duree_prevue, 8)
        self.assertEqual(montage.cultiveau_debut.date(), fields.Date.to_date("2027-05-03"))
        self.assertEqual(montage.partner_id, self.agri)
        self.assertEqual(montage.cultiveau_installation_id, self.inst)
        self.assertEqual(self.devis.cultiveau_mise_en_service_id.sale_line_id.product_id, self.mes)
        self.assertEqual(self.devis.cultiveau_nb_taches, 3)
        # relancer ne duplique pas
        self.devis.action_declencher()
        self.assertEqual(len(self.devis.cultiveau_tache_ids), 3)

    def test_questionnaire_de_financement(self):
        self.devis.action_confirm()
        ui = self.devis.cultiveau_questionnaire_id
        self.assertTrue(ui)
        self.assertEqual(ui.partner_id, self.agri)
        self.assertTrue(self.devis.cultiveau_questionnaire_envoye_le)
        self.assertTrue(self.devis.activity_ids.filtered(lambda a: a.summary.startswith("Financement")))
        corps = " ".join(self.devis.message_ids.mapped("body"))
        self.assertIn("questionnaire", corps.lower())
        # la relance à J+15
        self.devis.cultiveau_questionnaire_envoye_le = fields.Date.today() - timedelta(days=16)
        n = self.env["sale.order"]._cultiveau_cron_relance_financement()
        self.assertGreaterEqual(n, 1)
        self.assertEqual(self.devis.cultiveau_questionnaire_relances, 1)
        # la réponse du client
        q = lambda x: self.env.ref(f"cultiveau_commande_projet.{x}")  # noqa: E731
        credit = q("q_mode").suggested_answer_ids.filtered(lambda a: "Crédit" in a.value)
        aide = q("q_aide").suggested_answer_ids.filtered(lambda a: "accompagn" in a.value)
        ui._save_lines(q("q_mode"), credit.id)
        ui._save_lines(q("q_aide"), aide.id)
        ui._save_lines(q("q_banque"), "Crédit Agricole")
        ui._save_lines(q("q_date"), "2027-05-10")
        ui._mark_done()
        self.assertEqual(self.devis.cultiveau_financement, "credit")
        self.assertIn("Crédit Agricole", self.devis.cultiveau_financement_detail)
        self.assertEqual(self.devis.cultiveau_date_pose_souhaitee, fields.Date.to_date("2027-05-10"))
        self.assertFalse(self.devis.activity_ids.filtered(lambda a: a.summary.startswith("Financement")))
        self.assertTrue(self.devis.activity_ids.filtered(lambda a: "conseil" in (a.summary or "").lower()))

    def test_seuil_et_sans_suite(self):
        petit = self.env["sale.order"].create({"partner_id": self.agri.id, "order_line": [Command.create({"product_id": self.mes.id, "product_uom_qty": 1})]})
        petit.action_confirm()
        self.assertFalse(petit.cultiveau_questionnaire_id)  # 950 € : sous le seuil
        d = self.env["sale.order"].create({"partner_id": self.agri.id, "order_line": [Command.create({"product_id": self.mes.id, "product_uom_qty": 1})]})
        d.cultiveau_sans_suite_raison_id = self.env.ref("cultiveau_crm_effort.perte_reporte")
        d.action_sans_suite()
        self.assertEqual(d.state, "cancel")
        self.assertIn("sans suite", " ".join(d.message_ids.mapped("body")).lower())

    def test_pro_forma_et_bloc_projet(self):
        self.assertIn(self.env.ref("sale.group_proforma_sales"), self.env.ref("base.group_user").implied_ids)
        t = self.env.ref("cultiveau_ventes.modele_goutte")
        premiere = t.sale_order_template_line_ids.sorted(lambda l: (l.sequence, l.id))[0]
        self.assertTrue(premiere.display_type == "line_note" and premiere.name.startswith("PROJET"))
