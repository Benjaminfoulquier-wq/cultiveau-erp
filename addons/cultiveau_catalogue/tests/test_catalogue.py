import base64
import io

from odoo.tests import TransactionCase, tagged


def classeur(lignes, entete=None):
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["MATRICE D'IMPORTATION DES PRODUITS — CULTIVEAU"])
    ws.append(["Remplissez ce fichier puis importez-le."])
    ws.append(["🔴 Obligatoire", "", "", "🟢 Optionnel"])
    ws.append(entete or ["Référence ", "Nom du produit ", "Fournisseur ", "Catégorie", "Description", "Prix HT (€) ", "Unité ",
                         "Conditionnement", "Poids (kg)", "URL Image"])
    ws.append(["Code unique du produit (ex: REF-001)", "Nom complet du produit", "Nom exact du fournisseur", "Nom exact de la catégorie",
               "Description détaillée", "", "Unité de vente", "Détail", "Poids", "Lien"])
    for l in lignes:
        ws.append(l)
    sortie = io.BytesIO()
    wb.save(sortie)
    return sortie.getvalue()


@tagged("post_install", "-at_install", "cultiveau")
class TestCatalogue(TransactionCase):
    def test_import_matrice(self):
        contenu = classeur([
            ["9000002", "AQUA4D H-A 00", "AQUA 4D", "Agricole-Irrigation", "Unité de traitement physique de l'eau", 1250.5, "unité", "Carton", 3.2, ""],
            ["TUB-PE-32", "Tube PE 32 PN10", "ATUSA", "Tuyaux", "", "1,45", "mètre", "Rouleau 100 m", 0.21, ""],
            ["", "Sans référence", "ATUSA", "", "", "", "", "", "", ""],
        ])
        bilan = self.env["product.template"].cultiveau_importer_matrice(contenu)
        self.assertEqual((bilan["crees"], bilan["maj"], bilan["ignores"]), (2, 0, 0))
        self.assertEqual(len(bilan["erreurs"]), 1)
        p = self.env["product.template"].search([("default_code", "=", "9000002")])
        self.assertEqual(p.name, "AQUA4D H-A 00")
        self.assertEqual(p.list_price, 1250.5)
        self.assertEqual(p.categ_id.name, "Agricole-Irrigation")
        self.assertEqual(p.seller_ids.partner_id.name, "AQUA 4D")
        self.assertEqual(p.seller_ids.price, 1250.5)
        self.assertEqual(p.cultiveau_source, "matrice")
        tube = self.env["product.template"].search([("default_code", "=", "TUB-PE-32")])
        self.assertEqual(tube.uom_id, self.env.ref("uom.product_uom_meter"))
        self.assertEqual(tube.list_price, 1.45)
        self.assertEqual(tube.cultiveau_conditionnement, "Rouleau 100 m")
        # Réimporter met à jour, sans doublon.
        bilan = self.env["product.template"].cultiveau_importer_matrice(classeur([["9000002", "AQUA4D H-A 00 (v2)", "AQUA 4D", "", "", 1300, "", "", "", ""]]))
        self.assertEqual((bilan["crees"], bilan["maj"]), (0, 1))
        self.assertEqual(p.name, "AQUA4D H-A 00 (v2)")
        self.assertEqual(len(p.seller_ids), 1)
        self.assertEqual(p.seller_ids.price, 1300)

    def test_wizard_matrice(self):
        w = self.env["cultiveau.catalogue.import.matrice"].create({"fichier": base64.b64encode(classeur([["R1", "Vanne", "SIME", "Vannes", "", 10, "", "", "", ""]]))})
        w.action_importer()
        self.assertIn("créés : 1", w.resultat)

    def test_import_catalogue_3d(self):
        dicts = {"four": ["ATUSA", "SIME"], "fam": ["Tuyaux et raccords (réseau)", "Pompage"], "sub": ["Coude", "Autre", "Bride"],
                 "rac": ["bout à bout", "à brides"], "mat": ["inox 304", "acier galvanisé"], "fiche": ["FICHE1"],
                 "xk": ["rayon_R_mm", "type"]}
        fiches = {"FICHE1": {"t": "FT COUDE.pdf", "n": "1.4307 (AISI 304L) EN 10253-4"}}
        produits = [
            {"id": "lot2_atusa_1-1", "f": 0, "F": 0, "S": 0, "t": 0, "m": 0, "k": 0, "ref": "IC341018",
             "designation": "Coude 90° 3D à souder bout à bout inox 304L EN 10253-4 d18", "dn": 15.0, "pouces": "1/2\"", "d_ext": 18.0,
             "H": 32.0, "ep": 1.5, "poids": 0.026, "x": [[0, "23"], [1, "3D"]]},
            {"id": "lot2_sime_7", "f": 1, "F": 1, "S": 1, "t": 1, "m": 1, "k": 99, "designation": "Bride tournante zinguée DN250", "pn": 10.0, "dn": 250.0},
            {"id": "doublon", "f": 0, "F": 0, "S": 2, "t": 0, "m": 0, "k": 0, "ref": "IC341018", "designation": "Doublon de référence"},
        ]
        bilan = self.env["product.template"].cultiveau_importer_3d(dicts, fiches, produits)
        self.assertEqual((bilan["crees"], bilan["maj"]), (2, 0))
        coude = self.env["product.template"].search([("default_code", "=", "IC341018")])
        self.assertEqual(coude.cultiveau_dn, 15.0)
        self.assertEqual(coude.cultiveau_matiere, "inox 304")
        self.assertEqual(coude.cultiveau_raccordement, "bout à bout")
        self.assertEqual(coude.categ_id.complete_name, "Tuyaux et raccords (réseau) / Coude")
        self.assertEqual(coude.cultiveau_caracteristiques["rayon_R_mm"], "23")
        self.assertIn("FICHE1", coude.cultiveau_fiche_url)
        self.assertEqual(coude.seller_ids.partner_id.name, "ATUSA")
        self.assertIn("rayon R mm", coude.cultiveau_caracteristiques_html)
        bride = self.env["product.template"].search([("default_code", "=", "lot2_sime_7")])
        self.assertEqual(bride.categ_id.name, "Pompage")  # sous-famille « Autre » : on reste sur la famille
        self.assertEqual(bride.cultiveau_pn, 10.0)
        bilan = self.env["product.template"].cultiveau_importer_3d(dicts, fiches, produits[:1])
        self.assertEqual((bilan["crees"], bilan["maj"]), (0, 1))
        # La recherche par cotes, telle que le menu Catalogue la propose.
        self.assertIn(coude, self.env["product.template"].search([("cultiveau_dn", "=", 15), ("cultiveau_matiere", "ilike", "inox")]))

    def test_bibliotheque_et_lien_fiche(self):
        Fiche = self.env["cultiveau.fiche"]
        inventaire = ("source;fournisseur;famille;sous_famille;type_doc;titre;chemin;mime;taille_octets;id;viewUrl\n"
                      "fiches_techniques;Nelson_Irrigation_Fiches_techniques;Aspersion;Canons;Fiche technique;Big Gun 100;FICHES/NELSON;application/pdf;1234;ABC123;https://drive.google.com/file/d/ABC123/view\n"
                      "adherents;(racine);Hors bibliothèque;;Brochure;Plaquette;FOURNISSEURS;application/pdf;10;DEF456;https://drive.google.com/file/d/DEF456/view\n")
        bilan = Fiche.cultiveau_importer_inventaire(inventaire)
        self.assertEqual((bilan["crees"], bilan["maj"]), (2, 0))
        bilan = Fiche.cultiveau_importer_inventaire(inventaire)
        self.assertEqual((bilan["crees"], bilan["maj"]), (0, 2), "relançable sans doublon")
        fiche = Fiche.search([("drive_id", "=", "ABC123")])
        self.assertEqual((fiche.type_doc, fiche.famille, fiche.fournisseur_nom), ("fiche", "Aspersion", "Nelson_Irrigation_Fiches_techniques"))
        self.assertEqual(Fiche.search([("drive_id", "=", "DEF456")]).type_doc, "brochure")
        # Le catalogue 3D relie l'article à sa fiche, créée a minima si l'inventaire ne la connaît pas encore.
        dicts = {"four": ["Nelson"], "fam": ["Aspersion"], "sub": ["Canons"], "rac": ["fileté"], "mat": ["laiton"], "fiche": ["ABC123", "XYZ789"], "xk": []}
        fiches = {"ABC123": {"t": "Big Gun 100", "n": "canon"}, "XYZ789": {"t": "Nouvelle fiche", "n": "inconnue"}}
        produits = [{"id": "n1", "F": 0, "f": 0, "S": 0, "t": 0, "m": 0, "k": 0, "ref": "BG100", "designation": "Big Gun 100", "poids": 5},
                    {"id": "n2", "F": 0, "f": 0, "S": 0, "t": 0, "m": 0, "k": 1, "ref": "BG150", "designation": "Big Gun 150", "poids": 7}]
        self.env["product.template"].cultiveau_importer_3d(dicts, fiches, produits)
        p1 = self.env["product.template"].search([("default_code", "=", "BG100")])
        self.assertEqual(p1.cultiveau_fiche_id, fiche)
        self.assertEqual(fiche.nb_produits, 1)
        p2 = self.env["product.template"].search([("default_code", "=", "BG150")])
        self.assertEqual(p2.cultiveau_fiche_id.name, "Nouvelle fiche")
        self.assertEqual(p2.cultiveau_fiche_id.url, "https://drive.google.com/file/d/XYZ789/view")
        self.assertEqual(fiche.action_ouvrir()["url"], fiche.url)
