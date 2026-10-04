{
    "name": "Cultiveau — catalogue fournisseurs",
    "summary": "Le catalogue technique de l'irrigation : DN, PN, matière, raccordement, fiches techniques ; import de la matrice Cultiveau et du catalogue 3D.",
    "description": """
Le catalogue de l'irrigation
============================

Un catalogue d'irrigation se cherche par cotes : DN, PN, diamètre, matière, raccordement. Odoo
range les produits par nom et par catégorie ; ce module ajoute les caractéristiques techniques
sur chaque article, les filtres qui vont avec, le lien vers la fiche technique, le conditionnement
et le fournisseur avec son prix et son délai.

Le **catalogue Cultiveau** (référencement, catalogue 3D) est commun à tout le réseau ; chaque adhérent y pioche
ce qu'il vend (« Ajouter à mon catalogue ») et importe ses propres articles depuis n'importe quel fichier
(Catalogue → Importer mes articles) : ceux-là sont à lui seul. « Mon catalogue » = les deux.

Deux imports réseau :

- la **matrice d'import** Excel du référencement Cultiveau (Référence, Nom, Fournisseur, Catégorie,

Description, Prix HT, Unité, Conditionnement, Poids, URL image) ;
- le **catalogue 3D** (27 000 références de raccords, vannes, pompes, filtration… avec familles,

sous-familles, matières, cotes et fiches techniques), par le menu ou par le script
``scripts/importer_catalogue_3d.py``.
""",
    "version": "18.0.3.0.1",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "license": "LGPL-3",
    "depends": ["cultiveau_base", "product", "stock", "purchase"],
    "external_dependencies": {"python": ["openpyxl"]},
    "data": [
        "security/ir.model.access.csv",
        "views/fiche_views.xml",
        "views/product_views.xml",
        "wizard/import_views.xml",
        "wizard/import_articles_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
}
