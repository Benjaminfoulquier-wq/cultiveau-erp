{
    "name": "Cultiveau — Au quotidien : Aujourd'hui, rapport du lundi, budget d'heures, automatisations",
    "summary": "L'écran « Aujourd'hui », le rapport du lundi au gérant, le budget d'heures des chantiers (alertes 50/80/100 %) et les automatisations du métier",
    "description": """
Ce qui fait gagner du temps chaque jour :

- l'écran « Aujourd'hui » : une tuile par chose à traiter (courriels sans réponse, factures échues, devis à relancer,
  interventions en retard, chantiers en dépassement, congés et notes de frais à valider, stock bas, bons à facturer, agenda) ;
- le rapport du lundi : la semaine écoulée en chiffres et ce qui attend, par courriel au gérant ;
- le budget d'heures des chantiers : alertes à 50, 80 et 100 % des heures du devis, jauge par poseur, sur la map ;
- les automatisations « si… alors… » : dix règles du métier à activer d'un clic (relance des devis, réassort, relance des
  factures, chantier préparé à la signature, entretien proposé à l'anniversaire de la mise en service…).
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "website": "https://cultiveau.fr",
    "license": "LGPL-3",
    "depends": ["cultiveau_pose", "cultiveau_terrain", "cultiveau_documents", "cultiveau_rh", "cultiveau_messagerie", "cultiveau_mathis", "cultiveau_vue3d",
                "purchase_stock"],
    "data": [
        "security/ir.model.access.csv",
        "security/regles.xml",
        "data/quotidien_data.xml",
        "views/quotidien_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "cultiveau_quotidien/static/src/js/aujourdhui.js",
            "cultiveau_quotidien/static/src/xml/aujourdhui.xml",
            "cultiveau_quotidien/static/src/scss/aujourdhui.scss",
        ],
    },
    "installable": True,
    "auto_install": False,
}
