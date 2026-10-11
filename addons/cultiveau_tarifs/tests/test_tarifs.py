import base64

from odoo import Command
from odoo.tests import TransactionCase, tagged

from ..models.marges import remise_pour_marge


@tagged("post_install", "-at_install")
class TestTarifs(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.fournisseur = cls.env["res.partner"].create({"name": "Tuyaux du Sud", "is_company": True, "supplier_rank": 1})
        cls.a = cls.env["res.company"].with_context(chart_template_load=True).create({"name": "Adhérent A", "cultiveau_adherent": True})
        cls.b = cls.env["res.company"].with_context(chart_template_load=True).create({"name": "Adhérent B", "cultiveau_adherent": True})
        cls.env.user.company_ids |= cls.a | cls.b
        cls.tuyaux = cls.env["product.category"].create({"name": "Tuyaux"})
        cls.tube = cls.env["product.template"].create({"name": "Tube PE 63 PN10", "default_code": "TUB63", "company_id": False, "cultiveau_reseau": True, "categ_id": cls.tuyaux.id,
                                                       "list_price": 3.0, "purchase_ok": True, "seller_ids": [Command.create({"partner_id": cls.fournisseur.id, "product_code": "F-TUB-63", "price": 2.0})]})
        cls.vanne = cls.env["product.template"].create({"name": "Vanne 2 pouces", "default_code": "VAN2", "company_id": False, "cultiveau_reseau": True, "list_price": 40.0, "purchase_ok": True})

    def test_tarif_fournisseur(self):
        csv = "Réf fournisseur;Désignation;Prix brut;Remise\nF-TUB-63;Tube PE 63;3,00;20\nVAN2;Vanne 2 pouces;40,00;25\nNEW-1;Raccord inconnu;5,00;0\n".encode("cp1252")
        tarif = self.env["cultiveau.tarif.fournisseur"].create({"fournisseur_id": self.fournisseur.id, "fichier": base64.b64encode(csv), "nom_fichier": "tarif.csv", "creer_inconnus": True})
        tarif.action_analyser()
        etats = {l.ref_fournisseur: (l.etat, l.prix_net, l.product_id) for l in tarif.ligne_ids}
        self.assertEqual(etats["F-TUB-63"], ("hausse", 2.4, self.tube))
        self.assertEqual(etats["VAN2"][:2], ("inchange", 30.0))  # pas d'ancien prix chez ce fournisseur
        self.assertEqual(etats["NEW-1"][0], "nouveau")
        self.assertEqual(tarif.nb_hausses, 1)
        tarif.action_appliquer()
        self.assertEqual(tarif.etat, "applique")
        self.assertAlmostEqual(self.tube.seller_ids.filtered(lambda s: s.partner_id == self.fournisseur).price, 2.4)
        self.assertAlmostEqual(self.vanne.seller_ids.filtered(lambda s: s.partner_id == self.fournisseur).price, 30.0)
        self.assertAlmostEqual(self.tube.with_company(self.a).standard_price, 2.4)
        self.assertAlmostEqual(self.tube.with_company(self.b).standard_price, 2.4)
        cree = tarif.ligne_ids.filtered(lambda l: l.ref_fournisseur == "NEW-1").product_id
        self.assertTrue(cree and cree.cultiveau_reseau and cree.seller_ids.price == 5.0)
        self.assertTrue(tarif.activity_ids, "une hausse de 20 % : on prévient")

    def test_marges(self):
        self.assertAlmostEqual(remise_pour_marge(30), -42.857, places=2)
        a = self.a
        a.cultiveau_marge_pct = 30
        self.env["cultiveau.marge"].create({"company_id": a.id, "categ_id": self.tuyaux.id, "marge_pct": 40})
        a.cultiveau_appliquer_marges()
        liste = a.cultiveau_tarif_vente_id
        self.assertTrue(liste and liste.company_id == a and len(liste.item_ids) == 2)
        self.assertEqual(self.env["ir.config_parameter"].sudo().get_param(f"res.partner.property_product_pricelist_{a.id}"), str(liste.id))
        self.tube.with_company(a).standard_price = 2.4
        self.vanne.with_company(a).standard_price = 30.0
        propre = self.env["product.template"].with_company(a).create({"name": "Mon article", "company_id": a.id, "list_price": 50.0})
        prix = lambda p: liste._get_product_price(p.product_variant_id.with_company(a), 1.0)  # noqa: E731
        self.assertAlmostEqual(prix(self.tube), 4.0, places=2)    # 2,40 / 0,6 (marge 40 % des tuyaux)
        self.assertAlmostEqual(prix(self.vanne), 42.86, places=2)  # 30 / 0,7
        self.assertAlmostEqual(prix(propre), 50.0, places=2)      # pas de prix d'achat : prix catalogue
        client = self.env["res.partner"].with_company(a).create({"name": "Client de A", "company_id": a.id})
        self.assertEqual(client.with_company(a).property_product_pricelist, liste)

    def test_commande_groupee(self):
        g = self.env["cultiveau.commande.groupee"].create({"name": "Tubes printemps", "fournisseur_id": self.fournisseur.id, "date_limite": "2027-03-01",
                                                           "ligne_ids": [Command.create({"company_id": self.a.id, "product_id": self.tube.product_variant_id.id, "qty": 500}),
                                                                         Command.create({"company_id": self.b.id, "product_id": self.tube.product_variant_id.id, "qty": 300}),
                                                                         Command.create({"company_id": self.b.id, "product_id": self.vanne.product_variant_id.id, "qty": 4, "prix": 28})]})
        self.assertAlmostEqual(g.ligne_ids[0].prix, 2.0)
        self.assertEqual(g.nb_adherents, 2)
        self.assertAlmostEqual(g.total_ht, 500 * 2 + 300 * 2 + 4 * 28)
        g.action_cloturer()
        g.action_commander()
        self.assertEqual((g.etat, len(g.purchase_ids)), ("commandee", 2))
        de_b = g.purchase_ids.filtered(lambda p: p.company_id == self.b)
        self.assertEqual((de_b.partner_id, len(de_b.order_line), de_b.amount_untaxed), (self.fournisseur, 2, 300 * 2 + 4 * 28))
        self.assertTrue(all(g.ligne_ids.mapped("purchase_line_id")))
        self.assertIn("/web/content/", g.action_recapitulatif()["url"])
