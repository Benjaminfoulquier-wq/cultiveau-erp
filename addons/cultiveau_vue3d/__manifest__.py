{
    "name": "Cultiveau — vue d'ensemble 3D",
    "summary": "L'entreprise en un coup d'œil, en vue isométrique : magasin et stock, accueil et devis, atelier et interventions, parcelles et installations.",
    "description": """
La vue d'ensemble 3D
====================

Le jumeau de l'entreprise de l'adhérent, dessiné en isométrie à partir des données de l'ERP :

- le **magasin** : un rayon par famille d'articles, rempli selon le stock réel ;
- l'**accueil** : une personne par devis en cours ;
- l'**atelier** : un camion par intervention à faire, coloré selon l'urgence ;
- les **parcelles** : une parcelle par installation, selon son type et sa phase.

C'est la page d'accueil de l'ERP : le parcours client s'y lit station par station (accueil et comptoir, bureau
d'étude, magasin et cour, chantiers, atelier et SAV, parcelles en service, caisse) et chaque élément s'ouvre d'un clic.
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "license": "LGPL-3",
    "depends": ["cultiveau_interventions", "stock"],
    "data": ["views/menus.xml", "data/accueil.xml"],
    "assets": {
        "web.assets_backend": [
            "cultiveau_vue3d/static/src/js/modeles.js",
            "cultiveau_vue3d/static/src/js/vue3d.js",
            "cultiveau_vue3d/static/src/xml/vue3d.xml",
            "cultiveau_vue3d/static/src/scss/vue3d.scss",
        ],
    },
    "installable": True,
}
