{
    "name": "Cultiveau — Le stock qui se recommande tout seul",
    "summary": "Une page : ce que chaque article consomme, ce qu'il reste, ce qu'il faut ; un clic pose les règles de réassort, un clic commande les manquants chez le bon fournisseur ; ensuite Odoo recommande seul",
    "description": """
Le stock qui se recommande tout seul
====================================

Un installateur n'a pas le temps de régler des règles de réassort article par article. Cette page le fait pour lui :

- pour chaque article stocké : la consommation des douze derniers mois, par mois, le stock, ce qui arrive, ce qui est réservé,
  la couverture en mois, et un **minimum et un maximum proposés** (un mois et demi, trois mois de consommation) ;
- **Poser les règles** : les règles de réassort d'Odoo se créent ou se mettent à jour, en automatique ; ensuite le planificateur
  d'Odoo prépare seul les demandes de prix dès qu'un article passe sous son minimum ;
- **Commander maintenant** : les articles sous le minimum partent en demande de prix chez leur fournisseur, une par fournisseur.
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "website": "https://cultiveau.fr",
    "license": "LGPL-3",
    "depends": ["cultiveau_base", "purchase_stock", "sale_stock"],
    "data": ["security/ir.model.access.csv", "views/views.xml"],
    "installable": True,
    "auto_install": False,
}
