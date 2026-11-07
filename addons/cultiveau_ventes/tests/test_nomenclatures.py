from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "cultiveau")
class TestNomenclatures(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.agri = cls.env["res.partner"].create({"name": "Earl du Mas Neuf", "zip": "30250", "cultiveau_type": "agriculteur"})
        cls.vanne = cls.env["product.product"].create({"name": "Vanne 2\"", "list_price": 40.0, "type": "consu"})
        cls.regul = cls.env["product.product"].create({"name": "Régulateur 2 bar", "list_price": 25.0, "type": "consu"})
        cls.compteur = cls.env["product.product"].create({"name": "Compteur", "list_price": 300.0, "type": "consu"})
        cls.pose = cls.env["product.product"].create({"name": "Pose", "list_price": 50.0, "type": "service"})
        cls.tete = cls.env["cultiveau.nomenclature"].create({
            "name": "Tête de secteur test", "lot": "secteurs", "unite": "par secteur",
            "ligne_ids": [Command.create({"product_id": cls.vanne.id, "quantite": 1}), Command.create({"product_id": cls.regul.id, "quantite": 1, "note": "Selon § 6.4.2"}),
                          Command.create({"product_id": cls.compteur.id, "quantite": 1, "proportionnel": False}),
                          Command.create({"product_id": cls.pose.id, "quantite": 0.5, "optionnel": True})]})
        cls.devis = cls.env["sale.order"].create({"partner_id": cls.agri.id, "order_line": [
            Command.create({"display_type": "line_section", "name": "Lot 4 — Secteurs", "sequence": 10})]})

    def test_insertion_multipliee(self):
        w = self.env["cultiveau.nomenclature.inserer"].create({"order_id": self.devis.id, "nomenclature_id": self.tete.id, "quantite": 3, "placement": "sous_lot"})
        self.assertEqual(w.titre, "Tête de secteur test × 3")
        w.action_inserer()
        lignes = self.devis.order_line.sorted(lambda l: (l.sequence, l.id))
        sections = lignes.filtered(lambda l: l.display_type == "line_section")
        self.assertEqual(len(sections), 2)
        self.assertTrue(sections[1].cultiveau_sous_lot)
        par_produit = {l.product_id: l for l in lignes if l.product_id}
        self.assertEqual(par_produit[self.vanne].product_uom_qty, 3)       # × la quantité insérée
        self.assertEqual(par_produit[self.compteur].product_uom_qty, 1)    # fixe
        self.assertNotIn(self.pose, par_produit)                           # option non prise
        self.assertEqual(par_produit[self.vanne].price_unit, 40.0)         # le prix vient de la liste de prix, pas de la nomenclature
        self.assertTrue(lignes.filtered(lambda l: l.display_type == "line_note" and "6.4.2" in l.name))
        self.assertEqual(par_produit[self.vanne].cultiveau_nomenclature_id, self.tete)
        self.assertEqual(self.tete.nb_usages, 1)

    def test_recap_lots_et_sous_lots(self):
        self.devis.write({"order_line": [
            Command.create({"product_id": self.compteur.id, "product_uom_qty": 1, "sequence": 11}),
            Command.create({"display_type": "line_section", "name": "Secteur A", "cultiveau_sous_lot": True, "sequence": 12}),
            Command.create({"product_id": self.vanne.id, "product_uom_qty": 2, "sequence": 13}),
            Command.create({"display_type": "line_section", "name": "Secteur B", "cultiveau_sous_lot": True, "sequence": 14}),
            Command.create({"product_id": self.vanne.id, "product_uom_qty": 1, "sequence": 15}),
            Command.create({"product_id": self.pose.id, "product_uom_qty": 2, "sequence": 16}),
            Command.create({"display_type": "line_section", "name": "Lot 6 — Pose", "sequence": 20}),
            Command.create({"product_id": self.pose.id, "product_uom_qty": 1, "sequence": 21})]})
        lots = self.devis.cultiveau_lots()
        self.assertEqual([x["nom"] for x in lots], ["Lot 4 — Secteurs", "Lot 6 — Pose"])
        self.assertEqual(lots[0]["montant"], 300 + 80 + 40 + 100)
        self.assertEqual(lots[0]["mo"], 100)
        self.assertEqual([(s["nom"], s["montant"]) for s in lots[0]["sous"]], [("Secteur A", 80), ("Secteur B", 140)])
        self.assertEqual(self.devis.cultiveau_nb_lots, 2)
        self.assertIn("Secteur B", self.devis.cultiveau_recap_lots)
        # la présentation « par lot » (module cultiveau_presentation) ne compte pas les sous-lots comme des lots
        if "cultiveau_detail" in self.devis._fields:
            self.devis.cultiveau_detail = "lots"
            presentees = self.devis._get_order_lines_to_report()
            self.assertEqual([l.name for l in presentees if not l.display_type], ["Lot 4 — Secteurs", "Lot 6 — Pose"])

    def test_enregistrer_un_lot(self):
        self.devis.write({"order_line": [
            Command.create({"product_id": self.vanne.id, "product_uom_qty": 6, "sequence": 11}),
            Command.create({"display_type": "line_section", "name": "Tête", "cultiveau_sous_lot": True, "sequence": 12}),
            Command.create({"product_id": self.regul.id, "product_uom_qty": 3, "sequence": 13}),
            Command.create({"display_type": "line_section", "name": "Lot 6", "sequence": 20}),
            Command.create({"product_id": self.pose.id, "product_uom_qty": 1, "sequence": 21})]})
        lot4 = self.devis.order_line.filtered(lambda l: l.name == "Lot 4 — Secteurs")
        w = self.env["cultiveau.nomenclature.enregistrer"].create({"order_id": self.devis.id, "section_id": lot4.id, "lot": "secteurs", "quantite_reference": 3})
        self.assertEqual(w.name, "Lot 4 — Secteurs")
        self.assertEqual(w.nb_lignes, 2)  # le lot emporte son sous-lot, pas le lot suivant
        action = w.action_enregistrer()
        n = self.env["cultiveau.nomenclature"].browse(action["res_id"])
        self.assertEqual(n.company_id, self.env.company)
        self.assertEqual({(l.product_id, l.quantite) for l in n.ligne_ids}, {(self.vanne, 2.0), (self.regul, 1.0)})
        self.assertEqual(n.origine_order_id, self.devis)

    def test_nomenclatures_du_reseau_visibles(self):
        reseau = self.env.ref("cultiveau_ventes.nom_protection_station")
        self.assertFalse(reseau.company_id)
        self.assertIn(reseau, self.env["cultiveau.nomenclature"].search([]))
        self.assertGreaterEqual(len(reseau.ligne_ids), 5)
