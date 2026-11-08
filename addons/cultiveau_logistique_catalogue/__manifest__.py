{
    "name": "Cultiveau — Le catalogue de la logistique dans l'ERP",
    "summary": "Chaque produit mis en ligne sur logistique.cultiveau.fr arrive tout seul dans l'ERP : nom, famille, fournisseur, prix, photo, fiches techniques ; retiré là-bas, archivé ici",
    "description": """
Le catalogue de la logistique dans l'ERP
========================================

Un produit publié sur logistique.cultiveau.fr n'a pas à être ressaisi : toutes les heures, l'ERP lit les produits modifiés
depuis la dernière fois et les crée ou les met à jour dans le catalogue du réseau, avec la famille, le fournisseur, le prix
net Cultiveau (prix d'achat et fournisseur « Cultiveau Logistique »), le prix brut, la photo, les fiches techniques (dans la
bibliothèque des fiches, reliées à l'article). Un produit retiré de la logistique est archivé dans l'ERP.
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "website": "https://cultiveau.fr",
    "license": "LGPL-3",
    "depends": ["cultiveau_catalogue"],
    "data": ["data/cron.xml", "views/views.xml", "data/prix_public.xml"],
    "installable": True,
    "auto_install": False,
}
