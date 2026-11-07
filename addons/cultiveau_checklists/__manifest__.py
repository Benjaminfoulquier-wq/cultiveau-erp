{
    "name": "Cultiveau — Fiches d'intervention à checklist",
    "summary": "Une checklist par nature d'intervention, tirée du référentiel (remise en service § 18.3, hivernage § 18.5, saison § 18.4, mise en service A1.3, dépannage § 18.9, diagnostic A1.7), cochée sur le bon et imprimée",
    "description": """
Fiches d'intervention à checklist
=================================

Les feuilles de travail des logiciels de service et les ordres de travail des garages ont une chose en commun : une
checklist par type de travail, pour que rien ne soit oublié et que le client voie ce qui a été vérifié. Ici la checklist
vient du référentiel technique : les fiches de vérification saisonnières (A1.6) renvoient aux check-lists du chapitre 18.

- un **modèle de checklist par nature** d'intervention (et par type d'installation si besoin), proposé par le réseau,
  copiable et adaptable par l'adhérent ; chaque point a sa section du référentiel, un type (case, mesure, texte), peut être
  obligatoire ;
- le **bon d'intervention** reçoit la checklist de sa nature à la création ; le technicien coche, mesure, note ; les mesures
  de pression remplissent les relevés du bon ; la signature avertit si un point obligatoire manque (sans bloquer) ;
- la checklist s'**imprime** sur le bon remis au client, avec ce qui a été vérifié, mesuré et remarqué.
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "website": "https://cultiveau.fr",
    "license": "LGPL-3",
    "depends": ["cultiveau_terrain"],
    "data": ["security/ir.model.access.csv", "security/regles.xml", "data/modeles.xml", "views/checklist_views.xml", "views/bon_views.xml", "report/bon_report.xml"],
    "installable": True,
    "auto_install": False,
}
