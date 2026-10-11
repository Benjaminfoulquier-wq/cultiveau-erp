import base64

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

SIGNATURE = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)


@tagged("post_install", "-at_install", "cultiveau")
class TestTerrain(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.societe = env.company
        cls.agri = env["res.partner"].create({"name": "Agriculteur Terrain", "cultiveau_type": "agriculteur", "company_id": cls.societe.id,
                                              "street": "1 chemin des Pivots", "zip": "30100", "city": "Alès"})
        cls.inst = env["cultiveau.installation"].create({"name": "Pivot Terrain", "partner_id": cls.agri.id, "type_systeme": "pivot", "etat": "en_service",
                                                         "company_id": cls.societe.id, "pv_pression_sortie_pompe_bar": 6.0, "pv_pression_point_defavorable_bar": 3.0})
        cls.joint = env["product.product"].create({"name": "Joint de pivot terrain", "type": "consu", "is_storable": True, "list_price": 12.5})
        cls.tech = env["res.users"].create({"name": "Technicien Terrain", "login": "tech.terrain@exemple.fr", "company_id": cls.societe.id,
                                            "company_ids": [(6, 0, cls.societe.ids)], "groups_id": [(4, env.ref("cultiveau_base.group_adherent").id),
                                                                                                     (4, env.ref("project.group_project_user").id)]})
        projet = env["project.project"].cultiveau_projet_interventions(cls.societe)
        cls.panne = env["project.task"].create({"name": "Pivot arrêté en bout", "project_id": projet.id, "partner_id": cls.agri.id, "cultiveau_nature": "depannage",
                                                "cultiveau_urgence": "journee", "cultiveau_installation_id": cls.inst.id, "user_ids": [(6, 0, cls.tech.ids)],
                                                "cultiveau_piece_ids": [(0, 0, {"product_id": cls.joint.id, "quantite": 2})]})
        stock = env["stock.warehouse"].search([("company_id", "=", cls.societe.id)], limit=1).lot_stock_id
        env["stock.quant"]._update_available_quantity(cls.joint, stock, 50)

    def test_planning(self):
        self.panne.write({"cultiveau_debut": "2026-10-20 08:00:00", "cultiveau_duree_prevue": 3})
        self.assertEqual(str(self.panne.cultiveau_fin), "2026-10-20 11:00:00")
        self.assertEqual(self.panne.stage_id.name, "Planifiée")
        self.assertIn("Alès", self.panne.cultiveau_adresse)

    def test_du_bon_a_la_facture(self):
        # le camion du technicien, chargé de joints
        self.tech.action_creer_camion()
        camion = self.tech.cultiveau_camion_id
        self.assertTrue(camion)
        self.env["cultiveau.camion.dotation"].create({"user_id": self.tech.id, "product_id": self.joint.id, "quantite": 10})
        reassort = self.env["stock.picking"].browse(self.tech.action_reassort_camion()["res_id"])
        for m in reassort.move_ids:
            m.quantity = m.product_uom_qty
            m.picked = True
        reassort.button_validate()
        self.assertEqual(self.joint.with_context(location=camion.id).qty_available, 10)
        # sur place : le bon s'ouvre avec les pièces prévues, l'intervention passe « En cours »
        bon = self.env["cultiveau.bon"].browse(self.panne.action_arrive_sur_place()["res_id"])
        self.assertEqual((bon.partner_id, bon.installation_id, bon.user_ids), (self.agri, self.inst, self.tech))
        self.assertEqual(bon.ligne_ids.product_id, self.joint)
        self.assertEqual(self.panne.stage_id.name, "En cours")
        self.assertEqual(self.panne.action_arrive_sur_place()["res_id"], bon.id, "un seul bon en cours par intervention")
        bon.write({"heure_arrivee": 8.5, "heure_depart": 10.0, "trajet_km": 40, "pression_pompe_mesuree": 5.0, "pression_defavorable_mesuree": 2.4,
                   "travaux": "Joints changés, essai en pression."})
        self.assertEqual(bon.duree_heures, 1.5)
        self.assertEqual(round(bon.ecart_pct), -20)
        self.assertTrue(bon.alerte_ecart)
        bon.action_chiffrer_temps()
        bon.action_chiffrer_temps()  # recalculé, pas doublé
        self.assertEqual(sorted(bon.ligne_ids.mapped("genre")), ["deplacement", "mo", "piece"])
        self.assertEqual(bon.montant_ht, 2 * 12.5 + 1.5 * 60 + 40 * 0.65)
        with self.assertRaises(UserError):
            bon.action_signer()
        bon.write({"signe_par": "L'exploitant", "signature_client": SIGNATURE})
        bon.action_signer()
        self.assertEqual(bon.etat, "signe")
        # les joints sont sortis du camion, l'intervention est close et inscrite au registre, l'écart est signalé
        self.assertEqual(bon.picking_id.state, "done")
        self.assertEqual(bon.picking_id.location_id, camion)
        self.assertEqual(self.joint.with_context(location=camion.id).qty_available, 8)
        self.assertEqual((self.panne.state, self.panne.stage_id.name), ("1_done", "Terminée"))
        self.assertIn("5 bar sortie pompe", self.panne.cultiveau_releves)
        self.assertTrue(self.panne.cultiveau_registre_id)
        self.assertTrue(bon.activity_ids)
        # la facture, puis plus rien à facturer
        facture = self.env["account.move"].browse(bon.action_facturer()["res_id"])
        self.assertEqual((facture.move_type, facture.partner_id, facture.amount_untaxed), ("out_invoice", self.agri, bon.montant_ht))
        self.assertEqual((bon.etat, bon.invoice_id), ("facture", facture))
        with self.assertRaises(UserError):
            bon.action_facturer()
        # le PDF du bon
        html = self.env["ir.actions.report"]._render_qweb_html("cultiveau_terrain.report_bon", bon.ids)[0].decode()
        self.assertIn(bon.name, html)
        self.assertIn("Joints changés", html)

    def test_facture_groupee(self):
        bons = self.env["cultiveau.bon"]
        for jour in ("2026-10-02", "2026-10-09"):
            b = self.env["cultiveau.bon"].create({"partner_id": self.agri.id, "date": jour, "company_id": self.societe.id, "signe_par": "Client",
                                                  "signature_client": SIGNATURE, "heure_arrivee": 8, "heure_depart": 9})
            b.action_chiffrer_temps()
            b.action_signer()
            bons |= b
        action = bons.action_facturer()
        facture = self.env["account.move"].browse(action["res_id"])
        self.assertEqual(set(bons.mapped("invoice_id")), {facture})
        self.assertEqual(len(facture.invoice_line_ids.filtered(lambda l: l.display_type == "line_section")), 2)
        self.assertEqual(facture.amount_untaxed, 120)

    def test_contrat_entretien_et_garantie(self):
        from datetime import date
        env = self.env
        contrat = env["cultiveau.contrat"].create({"partner_id": self.agri.id, "installation_ids": [(6, 0, self.inst.ids)], "prix_annuel": 450,
                                                   "date_debut": date(2026, 1, 1), "date_fin": date(2026, 12, 31), "visites": 2, "depannage_prioritaire": True})
        self.assertTrue(contrat.name.startswith("CE/"))
        natures = sorted(n for _, n, _ in contrat._echeancier())
        self.assertEqual(natures, ["entretien", "entretien", "hivernage", "remise_en_service"])
        contrat.action_activer()
        self.assertEqual(contrat.etat, "actif")
        # début février : la remise en route se crée, une seule fois même si le cron repasse
        contrat._generer(date(2026, 1, 15))
        contrat._generer(date(2026, 2, 3))
        taches = contrat.task_ids.filtered(lambda t: t.cultiveau_nature == "remise_en_service")
        self.assertEqual(len(taches), 1)
        self.assertEqual((taches.partner_id, taches.cultiveau_installation_id), (self.agri, self.inst))
        contrat._generer(date(2026, 9, 20))
        self.assertEqual(contrat.task_ids.filtered(lambda t: t.cultiveau_nature == "hivernage").mapped(lambda t: t.date_deadline.date()), [date(2026, 10, 31)])
        # un dépannage chez ce client passe en priorité et la fiche le dit
        depannage = env["project.task"].create({"name": "Pompe en panne", "project_id": taches[0].project_id.id, "partner_id": self.agri.id,
                                                "cultiveau_nature": "depannage", "cultiveau_installation_id": self.inst.id})
        self.assertEqual(depannage.priority, "1")
        self.assertTrue(depannage.cultiveau_sous_contrat)
        # garantie sur l'équipement
        equipement = env["cultiveau.equipement"].create({"installation_id": self.inst.id, "name": "Pompe", "garantie_fin": fields.Date.today().replace(year=2099)})
        depannage.cultiveau_equipement_id = equipement
        self.assertTrue(depannage.cultiveau_sous_garantie)
        # facture annuelle
        contrat.action_facturer()
        self.assertEqual(contrat.invoice_ids.amount_untaxed, 450)
        renouvele = env["cultiveau.contrat"].browse(contrat.action_renouveler()["res_id"])
        self.assertEqual((renouvele.date_debut, renouvele.etat), (date(2027, 1, 1), "brouillon"))
