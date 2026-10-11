from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "cultiveau")
class TestChantier(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.societe = cls.env.company
        cls.agri = cls.env["res.partner"].create({"name": "Agriculteur Chantier", "cultiveau_type": "agriculteur", "company_id": cls.societe.id})
        cls.tube = cls.env["product.product"].create({"name": "Tube PE 75 chantier", "type": "consu", "is_storable": True, "list_price": 4})
        cls.etude = cls.env["product.product"].create({"name": "Étude chantier", "type": "service", "list_price": 300})
        emplacement = cls.env["stock.location"].search([("usage", "=", "internal"), ("company_id", "=", cls.societe.id)], limit=1)
        cls.env["stock.quant"]._update_available_quantity(cls.tube, emplacement, 500)
        cls.commande = cls.env["sale.order"].create({
            "partner_id": cls.agri.id, "company_id": cls.societe.id, "cultiveau_type_systeme": "pivot",
            "order_line": [(0, 0, {"product_id": cls.tube.id, "product_uom_qty": 120}), (0, 0, {"product_id": cls.etude.id, "product_uom_qty": 1})],
        })
        cls.commande.action_confirm()
        cls.poseur = cls.env["res.users"].create({"name": "Poseur Chantier", "login": "poseur.chantier", "email": "poseur@example.com",
                                                  "groups_id": [(4, cls.env.ref("cultiveau_base.group_adherent").id)]})

    def test_lancer_le_chantier_depuis_la_commande(self):
        """La commande sans installation en crée une, puis le chantier reprend le matériel stockable de la commande."""
        action = self.commande.action_lancer_chantier()
        chantier = self.env["cultiveau.chantier"].browse(action["res_id"])
        self.assertTrue(self.commande.cultiveau_installation_id)
        self.assertEqual(chantier.installation_id, self.commande.cultiveau_installation_id)
        self.assertEqual(chantier.partner_id, self.agri)
        self.assertTrue(chantier.name.startswith("CH/"))
        self.assertEqual(chantier.ligne_ids.mapped("product_id"), self.tube)
        self.assertEqual(chantier.ligne_ids.quantite_prevue, 120)
        self.assertEqual(chantier.ligne_ids.manque, 0)
        self.assertEqual(self.commande.cultiveau_nb_chantiers, 1)
        self.assertEqual(self.commande.cultiveau_installation_id.nb_chantiers, 1)

    def test_deroule_complet(self):
        """Planifier → démarrer → sortir le matériel → PV → mise en service → terminer ; l'installation suit et le registre est tenu."""
        chantier = self.env["cultiveau.chantier"].browse(self.commande.action_lancer_chantier()["res_id"])
        with self.assertRaises(UserError):
            chantier.action_planifier()
        chantier.write({"date_debut": "2026-10-20", "date_fin": "2026-10-24", "equipe_ids": [(4, self.poseur.id)]})
        chantier.action_planifier()
        self.assertEqual((chantier.etat, chantier.jours, chantier.avancement), ("planifie", 5, 5))
        chantier.action_demarrer()
        self.assertEqual(chantier.etat, "en_cours")
        self.assertEqual(chantier.installation_id.etat, "realisation")
        self.assertTrue(chantier.date_debut_reel)
        chantier.action_sortir_materiel()
        picking = chantier.picking_id
        self.assertTrue(picking)
        self.assertEqual(picking.picking_type_code, "outgoing")
        self.assertEqual(picking.move_ids.product_id, self.tube)
        self.assertEqual(picking.move_ids.product_uom_qty, 120)
        self.assertEqual(picking.state, "assigned")
        # Le PV incomplet bloque la mise en service (anti-retour et pressions de référence obligatoires).
        with self.assertRaises(UserError):
            chantier.action_mise_en_service()
        chantier.write({"pv_antiretour": True, "pv_pression_sortie_pompe_bar": 6.2, "pv_pression_point_defavorable_bar": 3.1, "pv_rincage": True,
                        "pv_securites_testees": True, "pv_signe_par": "L'exploitant"})
        chantier.action_mise_en_service()
        self.assertEqual(chantier.installation_id.etat, "en_service")
        self.assertTrue(chantier.mise_en_service_le)
        self.assertEqual(chantier.installation_id.pv_intervenant, self.env.user.name)
        self.assertEqual(chantier.ligne_ids.quantite_posee, 120)
        self.assertTrue(self.env["cultiveau.registre"].search([("installation_id", "=", chantier.installation_id.id), ("genre", "=", "mise_en_service")]))
        chantier.action_terminer()
        self.assertEqual((chantier.etat, chantier.avancement), ("termine", 100))
        self.assertTrue(chantier.date_fin_reel)

    def test_terminer_sans_pv_exige_des_reserves(self):
        chantier = self.env["cultiveau.chantier"].browse(self.commande.action_lancer_chantier()["res_id"])
        chantier.write({"date_debut": "2026-10-20", "date_fin": "2026-10-21"})
        chantier.action_planifier()
        chantier.action_demarrer()
        with self.assertRaises(UserError):
            chantier.action_terminer()
        chantier.reserves = "Compteur d'eau non posé, en attente du syndicat."
        chantier.action_terminer()
        self.assertEqual(chantier.etat, "termine")

    def test_vue_d_ensemble(self):
        """La scène montre le chantier planifié avec son équipe, et ne compte plus l'installation en double."""
        chantier = self.env["cultiveau.chantier"].browse(self.commande.action_lancer_chantier()["res_id"])
        chantier.write({"date_debut": "2026-10-20", "date_fin": "2026-10-24", "equipe_ids": [(4, self.poseur.id)]})
        chantier.action_planifier()
        chantier.action_demarrer()
        d = self.env["cultiveau.scene"].donnees()
        mien = next(c for c in d["chantiers"]["chantiers"] if c["id"] == chantier.id)
        self.assertEqual((mien["etat"], mien["equipe"], mien["chef"]), ("en_cours", 1, self.env.user.name))
        self.assertNotIn(chantier.installation_id.id, [i["id"] for i in d["chantiers"]["installations"]])
        self.assertGreaterEqual(d["compteurs"]["chantiers"], 1)
