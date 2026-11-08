from unittest.mock import patch

from odoo.tests import TransactionCase, tagged

PAGE = {"total": 3, "page": 1, "taille": 500, "produits": [
    {"id": 101, "reference": "RIV-D5000-16", "nom": "Gaine D5000 Ø16 1,6 l/h 0,50 m", "description": "Gaine à paroi mince.", "argumentaire": "Uniformité au top.", "unite": "m", "conditionnement": "rouleau 2 500 m",
     "poids": 0.03, "prix": 0.12, "prix_brut": 0.18, "prix_plateforme": None, "stock": None, "actif": True, "image_url": "https://logistique.cultiveau.fr/media-local/uploads/x.jpg",
     "famille": "Goutte à goutte / micro-irrigation", "sous_famille": "Gaine (paroi mince)", "fournisseur": {"id": 90001, "nom": "RIVULIS", "site": None},
     "fiches": [{"id": 7, "titre": "Fiche D5000", "url": "https://logistique.cultiveau.fr/media-local/uploads/fournisseurs/90001/fiches/d5000.pdf", "type": "pdf"}], "mis_a_jour": "2026-11-07T10:00:00.000Z", "url": "https://logistique.cultiveau.fr/produit/101"},
    {"id": 102, "reference": "ODIS-FD3", "nom": "Filtre à disques 3\"", "description": "", "argumentaire": "", "unite": "u", "conditionnement": "", "poids": 4.0, "prix": 310.0, "prix_brut": None, "prix_plateforme": None,
     "stock": 3, "actif": True, "image_url": None, "famille": "Filtration", "sous_famille": "Filtre à disques", "fournisseur": {"id": 90002, "nom": "ODIS", "site": None}, "fiches": [], "mis_a_jour": "2026-11-07T10:05:00.000Z", "url": "https://logistique.cultiveau.fr/produit/102"},
    {"id": 103, "reference": "VIEUX-1", "nom": "Produit retiré", "description": "", "argumentaire": "", "unite": "u", "conditionnement": "", "poids": None, "prix": 5.0, "prix_brut": None, "prix_plateforme": None,
     "stock": None, "actif": False, "image_url": None, "famille": "Autre", "sous_famille": None, "fournisseur": None, "fiches": [], "mis_a_jour": "2026-11-07T10:06:00.000Z", "url": None},
]}


@tagged("post_install", "-at_install", "cultiveau")
class TestSynchroLogistique(TransactionCase):
    def setUp(self):
        super().setUp()
        self.env["ir.config_parameter"].sudo().set_param("cultiveau.logistique_secret", "test")
        self.env["ir.config_parameter"].sudo().set_param("cultiveau.logistique_photos", "True")

    def test_synchro(self):
        P = self.env["product.template"]
        with patch.object(type(P), "_logistique_page", lambda self, page, depuis=None, taille=500, ids=None: PAGE if page == 1 else {"total": 3, "page": page, "taille": 500, "produits": []}), \
             patch.object(type(P), "_logistique_telecharger", lambda self, url: b"\x89PNG\r\n\x1a\n" + b"\x00" * 10 if url.endswith(".jpg") else None):
            bilan = P.cultiveau_synchro_logistique(tout=True)
        self.assertIn("2 créé(s)", bilan)
        gaine = P.search([("default_code", "=", "RIV-D5000-16")])
        self.assertEqual(len(gaine), 1)
        self.assertEqual(gaine.cultiveau_source, "logistique")
        self.assertTrue(gaine.cultiveau_reseau)
        self.assertFalse(gaine.company_id)
        self.assertEqual(gaine.categ_id.name, "Gaine (paroi mince)")
        self.assertEqual(gaine.categ_id.parent_id.name, "Goutte à goutte / micro-irrigation")
        self.assertEqual(gaine.list_price, 0.36)  # prix brut 0,18 mais jamais moins de 3 × 0,12 d'achat
        self.assertEqual(gaine.standard_price, 0.12)
        self.assertIn("Le mot de RIVULIS", gaine.description_sale)
        self.assertEqual(set(gaine.seller_ids.mapped("partner_id.name")), {"RIVULIS", "Cultiveau Logistique"})
        self.assertEqual(gaine.seller_ids.filtered(lambda s: s.partner_id.name == "Cultiveau Logistique").price, 0.12)
        self.assertTrue(gaine.cultiveau_fiche_id)
        self.assertEqual(gaine.cultiveau_fiche_id.drive_id, "logistique:7")
        self.assertIn("d5000.pdf", gaine.cultiveau_fiche_url)
        self.assertEqual(gaine.cultiveau_logistique_id, 101)
        filtre = P.search([("default_code", "=", "ODIS-FD3")])
        self.assertAlmostEqual(filtre.list_price, 310.0 * 3)  # pas de prix brut : trois fois le prix d'achat, jamais moins
        # un article déjà dans l'ERP sous la règle est relevé à la mise à jour
        filtre.with_context(active_test=False).write({"list_price": 400.0})
        self.assertEqual(self.env["product.template"].cultiveau_prix_public_minimum(), 1)
        self.assertAlmostEqual(filtre.list_price, 930.0)
        self.assertFalse(P.with_context(active_test=False).search([("default_code", "=", "VIEUX-1")]))  # retiré et inconnu : pas créé
        # deuxième passage : mise à jour, et un produit retiré s'archive
        PAGE2 = {"total": 1, "page": 1, "taille": 500, "produits": [dict(PAGE["produits"][0], actif=False, nom="Gaine D5000 retirée")]}
        with patch.object(type(P), "_logistique_page", lambda self, page, depuis=None, taille=500, ids=None: PAGE2 if page == 1 else {"total": 1, "page": page, "taille": 500, "produits": []}), \
             patch.object(type(P), "_logistique_telecharger", lambda self, url: None):
            bilan2 = P.cultiveau_synchro_logistique()
        self.assertIn("1 archivé(s)", bilan2)
        gaine = P.with_context(active_test=False).search([("default_code", "=", "RIV-D5000-16")])
        self.assertFalse(gaine.active)
        self.assertTrue(self.env["ir.config_parameter"].sudo().get_param("cultiveau.logistique_depuis"))

    def test_sans_secret(self):
        self.env["ir.config_parameter"].sudo().set_param("cultiveau.logistique_secret", "")
        with self.assertRaises(Exception):
            self.env["product.template"]._logistique_page(1)

    def test_recherche_a_la_volee_depuis_un_devis(self):
        P = self.env["product.template"]
        self.assertFalse(P.search([("default_code", "=", "ODIS-FD3")]))
        appels = []

        def recherche(self_, q, taille=20):
            appels.append(q)
            return [p for p in PAGE["produits"] if q.lower() in (p["reference"] + " " + p["nom"]).lower() and p["actif"]]
        with patch.object(type(P), "_logistique_recherche", recherche), patch.object(type(P), "_logistique_telecharger", lambda self, url: None):
            # taper la référence dans une ligne de devis : la variante est trouvée après un aller-retour logistique
            variantes = self.env["product.product"].name_search("ODIS-FD3")
            self.assertEqual(appels, ["ODIS-FD3"])
            self.assertEqual(len(variantes), 1)
            produit = P.search([("default_code", "=", "ODIS-FD3")])
            self.assertEqual((produit.cultiveau_source, produit.standard_price, produit.cultiveau_logistique_id), ("logistique", 310.0, 102))
            self.assertTrue(produit.seller_ids.filtered(lambda s: s.partner_id.name == "Cultiveau Logistique" and s.price == 310.0))
            # une deuxième frappe ne rappelle pas la logistique : l'article est déjà là
            self.env["product.product"].name_search("ODIS-FD3")
            self.assertEqual(appels, ["ODIS-FD3"])
            # trop court, ou inconnu partout : rien ne casse
            self.assertFalse(self.env["product.product"].name_search("xyz-inconnu-123"))

    def test_le_robot_ne_copie_pas_tout_sans_le_demander(self):
        P = self.env["product.template"]
        self.env["ir.config_parameter"].sudo().set_param("cultiveau.logistique_copie", "False")
        demandes = []

        def page(self_, page, depuis=None, taille=500, ids=None):
            demandes.append(ids)
            produits = [p for p in PAGE["produits"] if not ids or p["id"] in ids]
            return {"total": len(produits), "page": page, "taille": taille, "produits": produits}
        with patch.object(type(P), "_logistique_page", page), patch.object(type(P), "_logistique_telecharger", lambda self, url: None):
            bilan = P.cultiveau_synchro_logistique(tout=False)
            self.assertEqual(demandes, [])  # rien de connu : la logistique n'est même pas appelée
            self.assertIn("à la volée", bilan)
            self.assertFalse(P.search([("cultiveau_source", "=", "logistique")]))
            # un article déjà utilisé, lui, est rafraîchi
            connu = P.create({"name": "Gaine D5000", "default_code": "RIV-D5000-16", "cultiveau_logistique_id": 101, "cultiveau_source": "logistique", "standard_price": 0.05})
            P.cultiveau_synchro_logistique(tout=False)
            self.assertEqual(demandes[-1], [101])  # demandé par identifiant, pas tout le catalogue
            self.assertEqual(connu.standard_price, 0.12)
