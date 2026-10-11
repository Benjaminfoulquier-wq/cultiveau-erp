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
