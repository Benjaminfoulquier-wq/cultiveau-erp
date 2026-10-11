{
    "name": "Cultiveau — Tarifs, marges et commande groupée",
    "summary": "Les tarifs négociés par le réseau chez chaque fournisseur, la marge de chaque adhérent, le prix de vente proposé seul, la commande groupée",
    "description": """
L'argument économique du réseau, dans l'ERP : les tarifs fournisseurs négociés (Excel ou CSV, mise à jour annuelle, hausses et baisses
visibles, prix d'achat de chaque adhérent mis à jour), la marge cible par adhérent affinée par famille (sa liste de prix de vente se
construit seule), et la commande groupée réseau (les besoins de plusieurs adhérents chez un fournisseur référencé, une commande d'achat
par adhérent au tarif négocié, le récapitulatif pour le fournisseur).
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "website": "https://cultiveau.fr",
    "license": "LGPL-3",
    "depends": ["cultiveau_catalogue", "cultiveau_compta", "purchase", "sale"],
    "data": ["security/ir.model.access.csv", "security/regles.xml", "views/tarif_views.xml", "views/groupee_views.xml", "views/res_config_settings_views.xml", "views/menus.xml"],
    "installable": True,
    "auto_install": False,
}
