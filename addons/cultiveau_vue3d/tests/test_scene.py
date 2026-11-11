from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "cultiveau")
class TestScene(TransactionCase):
    def test_donnees_de_la_scene(self):
        societe = self.env.company
        agri = self.env["res.partner"].create({"name": "Agriculteur Scène", "cultiveau_type": "agriculteur", "company_id": societe.id})
        Inst = self.env["cultiveau.installation"]
        service = Inst.create({"name": "Pivot des Grandes Terres", "partner_id": agri.id, "type_systeme": "pivot", "etat": "en_service", "surface_ha": 42, "company_id": societe.id})
        etude = Inst.create({"name": "Goutte à goutte vigne", "partner_id": agri.id, "type_systeme": "goutte_surface", "etat": "etude", "surface_ha": 6, "company_id": societe.id})
        chantier = Inst.create({"name": "Enrouleur maïs", "partner_id": agri.id, "type_systeme": "enrouleur", "etat": "realisation", "company_id": societe.id})
        produit = self.env["product.product"].create({"name": "Tube PE 63 scène", "type": "consu", "is_storable": True,
                                                      "categ_id": self.env["product.category"].create({"name": "Tuyaux scène"}).id})
        emplacement = self.env["stock.location"].search([("usage", "=", "internal"), ("company_id", "=", societe.id)], limit=1)
        self.env["stock.quant"]._update_available_quantity(produit, emplacement, 99999)
        ligne = [(0, 0, {"product_id": produit.id, "product_uom_qty": 10, "price_unit": 3})]
        comptoir = self.env["sale.order"].create({"partner_id": agri.id, "company_id": societe.id, "order_line": ligne})
        devis = self.env["sale.order"].create({"partner_id": agri.id, "company_id": societe.id, "cultiveau_installation_id": etude.id, "order_line": ligne})
        projet = self.env["project.project"].create({"name": "Interventions scène", "company_id": societe.id})
        panne = self.env["project.task"].create({"name": "Pivot arrêté", "project_id": projet.id, "partner_id": agri.id, "cultiveau_nature": "depannage",
                                                 "cultiveau_urgence": "immediate", "cultiveau_installation_id": service.id})
        mise = self.env["project.task"].create({"name": "Mise en service enrouleur", "project_id": projet.id, "partner_id": agri.id, "cultiveau_nature": "mise_en_service",
                                                "cultiveau_installation_id": chantier.id})
        d = self.env["cultiveau.scene"].donnees()
        self.assertEqual(d["societe"]["id"], societe.id)
        rayon = next(r for r in d["magasin"] if r["nom"] == "Tuyaux scène")
        self.assertEqual((rayon["quantite"], rayon["articles"]), (99999, 1))
        self.assertIn(comptoir.id, [x["id"] for x in d["accueil"]["comptoir"]])
        self.assertIn(devis.id, [x["id"] for x in d["bureau"]["devis"]])
        self.assertIn(etude.id, [x["id"] for x in d["bureau"]["etudes"]])
        self.assertIn(chantier.id, [x["id"] for x in d["chantiers"]["installations"]])
        if panne.cultiveau_intervention:
            self.assertIn(panne.id, [x["id"] for x in d["atelier"]])
            self.assertIn(mise.id, [x["id"] for x in d["chantiers"]["taches"]])
        p = next(x for x in d["parcelles"] if x["id"] == service.id)
        self.assertEqual((p["type"], p["etat"], p["surface"]), ("pivot", "en_service", 42))
        self.assertGreaterEqual(d["compteurs"]["installations"], 3)
        # La vue d'ensemble est la page d'accueil : des nouveaux comptes comme des anciens.
        nouveau = self.env["res.users"].create({"name": "Nouvel utilisateur scène", "login": "scene@exemple.fr"})
        self.assertEqual(nouveau.action_id.id, self.env.ref("cultiveau_vue3d.action_vue3d").id)
        self.env["res.users"]._cultiveau_page_accueil_pour_tous()
        self.assertEqual(self.env.user.action_id.id, self.env.ref("cultiveau_vue3d.action_vue3d").id)

    def test_les_postes_du_plan_ouvrent_tout(self):
        """Chaque porte du plan s'ouvre : actions standard filtrées, formulaires vierges, familles, lien vers Cultiveau 3D."""
        Scene = self.env["cultiveau.scene"]
        dispo = Scene._actions_disponibles()
        for cle in ("facture_nouvelle", "factures_a_encaisser", "fiches", "catalogue", "schema3d", "devis_nouveau", "livraisons", "agriculteurs", "interventions"):
            self.assertIn(cle, dispo)
        for cle in sorted(dispo):
            if cle.startswith("famille_"):
                continue
            action = Scene.action(cle, "plombier" if cle.startswith("client") else None)
            self.assertTrue(action.get("type"), cle)
        facture = Scene.action("facture_nouvelle")
        self.assertEqual((facture["res_model"], facture["view_mode"], facture["context"]["default_move_type"]), ("account.move", "form", "out_invoice"))
        self.assertEqual([v[1] for v in facture["views"]], ["form"])
        self.assertIn(("payment_state", "in", ("not_paid", "partial")), Scene.action("factures_a_encaisser")["domain"])
        self.assertEqual(Scene.action("schema3d")["type"], "ir.actions.act_url")
        # le parking : un véhicule par type de client, qui ouvre les clients de ce type
        self.env["res.partner"].create({"name": "Plomberie du plan", "cultiveau_type": "plombier", "company_id": self.env.company.id})
        self.assertGreaterEqual(Scene.donnees()["compteurs"]["clients_par_type"]["plombier"], 1)
        plombiers = Scene.action("clients_type", "plombier")
        self.assertIn(("cultiveau_type", "=", "plombier"), plombiers["domain"])
        self.assertEqual((plombiers["name"], plombiers["context"]["default_cultiveau_type"]), ("Plombiers", "plombier"))
        nouveau = Scene.action("client_type_nouveau", "paysagiste")
        self.assertEqual((nouveau["view_mode"], nouveau["context"]["default_cultiveau_type"]), ("form", "paysagiste"))
        famille = self.env["product.category"].create({"name": "Famille du plan"})
        sous = self.env["product.category"].create({"name": "Sous-famille du plan", "parent_id": famille.id})
        self.env["product.template"].create({"name": "Raccord du plan", "categ_id": sous.id, "cultiveau_reseau": True, "sale_ok": True})
        f = next(x for x in Scene.donnees()["familles"] if x["id"] == famille.id)
        self.assertEqual((f["nom"], f["reseau"]), ("Famille du plan", 1))
        for cle in ("famille_mien", "famille_stock", "famille_reseau", "famille_fiches"):
            action = Scene.action(cle, famille.id)
            self.assertIn("child_of", [c[1] for c in action["domain"] if isinstance(c, (list, tuple))], cle)
            self.assertTrue(action["name"].startswith("Famille du plan"))


@tagged("post_install", "-at_install", "cultiveau")
class TestSchemaCablage(TransactionCase):
    def test_schema_garde_son_dessin(self):
        from odoo.exceptions import ValidationError
        Schema = self.env["cultiveau.schema.cablage"]
        schema = Schema.create({"name": "Station du Mas", "donnees": '{"composants": [{"id": "c1", "type": "moteur"}, {"id": "c2", "type": "disjoncteur"}], "fils": []}'})
        self.assertEqual(schema.nb_composants, 2)
        self.assertEqual(schema.company_id, self.env.company)
        with self.assertRaises(ValidationError):
            schema.donnees = "pas du json"

    def test_schema_vers_devis(self):
        from odoo.exceptions import UserError
        client = self.env["res.partner"].create({"name": "Client Câblage"})
        article = self.env["product.product"].create({"name": "Contacteur 18 A essai", "list_price": 42.0, "sale_ok": True})
        schema = self.env["cultiveau.schema.cablage"].create({"name": "Armoire du Mas"})
        lignes = [{"designation": "Contacteur, 18 A", "quantite": 1, "unite": "u", "reperes": ["KM1"], "article_id": article.id},
                  {"designation": "Disjoncteur moteur, 11 A", "quantite": 2, "unite": "u", "reperes": ["Q3", "Q4"]},
                  {"designation": "Câble de puissance 2,5 mm²", "quantite": 62, "unite": "m"}]
        with self.assertRaises(UserError):
            schema.creer_devis(lignes)
        schema.partner_id = client
        action = schema.creer_devis(lignes)
        devis = schema.devis_id
        self.assertEqual(action["res_id"], devis.id)
        produits = devis.order_line.filtered("product_id")
        self.assertEqual(len(produits), 3)
        self.assertEqual(produits[0].product_id, article)
        self.assertEqual(produits[0].price_unit, 42.0)
        self.assertEqual(produits[1].product_id.default_code, "A-PRECISER")
        self.assertEqual(produits[1].product_uom_qty, 2)
        self.assertIn("Q3, Q4", produits[1].name)
        self.assertEqual(produits[2].product_uom_qty, 62)
        # un devis en brouillon est remis à jour, pas doublé
        schema.creer_devis(lignes[:1])
        self.assertEqual(schema.devis_id, devis)
        self.assertEqual(len(devis.order_line.filtered("product_id")), 1)
