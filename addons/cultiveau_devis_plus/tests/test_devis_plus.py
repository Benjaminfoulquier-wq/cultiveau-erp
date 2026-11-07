import base64

from odoo import Command
from odoo.tests import TransactionCase, tagged

PDF = b"%PDF-1.4\n%fiche de test\n%%EOF\n"


@tagged("post_install", "-at_install", "cultiveau")
class TestDevisPlus(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = cls.env["res.partner"].create({"name": "EARL du Devis", "email": "devis@exemple.fr", "cultiveau_type": "agriculteur"})
        cls.fiche = cls.env["cultiveau.fiche"].create({"name": "Filtre à disques 3 pouces", "fichier": base64.b64encode(PDF), "fichier_nom": "filtre.pdf", "fournisseur_nom": "Filtromatic"})
        Produit = cls.env["product.template"]
        cls.filtre = Produit.create({"name": "Filtre à disques 3\" 130 µm", "list_price": 900, "standard_price": 600, "cultiveau_fiche_id": cls.fiche.id})
        cls.gaine = Produit.create({"name": "Gaine goutte à goutte 16 mm 1,6 l/h", "list_price": 0.25, "standard_price": 0.15})
        cls.pompe = Produit.create({"name": "Électropompe immergée 4 pouces", "list_price": 2500, "standard_price": 1900})
        cls.injecteur = Produit.create({"name": "Injecteur venturi 1 pouce", "list_price": 300, "standard_price": 180})
        cls.compteur = Produit.create({"name": "Compteur Woltmann DN80", "list_price": 400, "standard_price": 280})

    def _devis(self, produits, type_systeme="goutte_surface"):
        lignes = [Command.create({"display_type": "line_section", "name": "Lot 1 · Station"})]
        for p in produits:
            lignes.append(Command.create({"product_id": p.product_variant_id.id, "product_uom_qty": 1}))
        return self.env["sale.order"].create({"partner_id": self.client.id, "cultiveau_type_systeme": type_systeme, "order_line": lignes})

    def test_marges_visibles_et_alerte(self):
        devis = self._devis([self.filtre, self.pompe])
        attendu = sum(l.price_subtotal - (l.purchase_price or 0) * l.product_uom_qty for l in devis.order_line.filtered('product_id'))
        self.assertAlmostEqual(devis.margin, attendu, places=2)
        self.assertGreater(devis.margin, 0)
        devis.company_id.cultiveau_marge_mini_pct = 40
        devis.invalidate_recordset()
        self.assertIn("sous le minimum", devis.cultiveau_marge_alerte or "")
        devis.company_id.cultiveau_marge_mini_pct = 10
        devis.invalidate_recordset()
        self.assertFalse(devis.cultiveau_marge_alerte)

    def test_fiches_jointes_a_l_envoi(self):
        devis = self._devis([self.filtre, self.gaine])
        self.assertEqual(devis.cultiveau_fiche_ids, self.fiche)
        action = devis.action_quotation_send()
        pieces = self.env["ir.attachment"].browse(action["context"]["default_attachment_ids"][0][2])
        self.assertEqual(pieces.mapped("name"), ["filtre.pdf"])
        self.assertEqual(base64.b64decode(pieces.datas), PDF)
        # un deuxième envoi ne crée pas de doublon
        action2 = devis.action_quotation_send()
        self.assertEqual(action2["context"]["default_attachment_ids"], action["context"]["default_attachment_ids"])

    def test_referentiel_ce_qui_manque_et_ce_qui_est_la(self):
        # injection sans anti-retour, goutte à goutte sans filtre, pompe sans sécurité, pas de compteur
        devis = self._devis([self.gaine, self.pompe, self.injecteur])
        noms = [a.name for a, _lots in self.env["cultiveau.referentiel.avis"].pour_devis(devis)]
        self.assertIn("Injection prévue sans anti-retour au devis", noms)
        self.assertIn("Pas de filtration dans un devis de micro-irrigation", noms)
        self.assertIn("Pompe sans sécurité au devis", noms)
        self.assertIn("Pas de compteur volumétrique", noms)
        self.assertIn("Finesse et type de filtration", noms)
        self.assertIn("Rinçage avant mise en service et hivernage", noms)
        # on ajoute le filtre et le compteur : les deux manques disparaissent
        devis.write({"order_line": [Command.create({"product_id": self.filtre.product_variant_id.id}), Command.create({"product_id": self.compteur.product_variant_id.id})]})
        noms = [a.name for a, _lots in self.env["cultiveau.referentiel.avis"].pour_devis(devis)]
        self.assertNotIn("Pas de filtration dans un devis de micro-irrigation", noms)
        self.assertNotIn("Pas de compteur volumétrique", noms)
        self.assertIn("Compteur : implantation et usage", noms)

    def test_notes_ecrites_puis_remplacees(self):
        devis = self._devis([self.gaine, self.injecteur])
        devis.action_relire_referentiel()
        notes = devis.order_line.filtered("cultiveau_avis_id")
        self.assertTrue(notes)
        self.assertTrue(all(n.display_type == "line_note" for n in notes))
        self.assertIn("§ 15.3.1", "".join(notes.mapped("name")))
        self.assertIn("exigence réglementaire", "".join(notes.mapped("name")))
        n1 = len(devis.order_line)
        devis.action_relire_referentiel()
        self.assertEqual(len(devis.order_line), n1)  # remplacées, pas ajoutées
        devis.action_retirer_notes_referentiel()
        self.assertFalse(devis.order_line.filtered("cultiveau_avis_id"))
        self.assertFalse(devis.order_line.filtered(lambda l: l.display_type == "line_section" and "Notes techniques" in (l.name or "")))
        # les notes ne comptent pas dans le corpus : pas d'auto-déclenchement par les mots des notes
        devis.action_relire_referentiel()
        noms = [a.name for a, _l in self.env["cultiveau.referentiel.avis"].pour_devis(devis)]
        self.assertNotIn("Compteur : implantation et usage", noms)
