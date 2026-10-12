{
    "name": "Cultiveau — Flotte des camions",
    "summary": "Kilométrage, entretien, contrôle technique, assurance et carburant des camions, avec une alerte avant chaque échéance",
    "description": """
Les camions de l'équipe, sur le module standard des véhicules :

- chaque véhicule est relié à son conducteur, donc à son camion sur la map ;
- contrôle technique, entretien (à la date ou au kilométrage), assurance et contrats : une alerte un mois avant, une activité
  pour le gérant, un repère sur la map et dans « Aujourd'hui » ;
- un entretien ou un contrôle technique enregistré fixe tout seul le suivant ;
- le carburant vient des notes de frais (catégorie carburant) du conducteur ;
- le conducteur relève son compteur depuis son téléphone (/moi).
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "website": "https://cultiveau.fr",
    "license": "LGPL-3",
    "depends": ["fleet", "cultiveau_quotidien", "cultiveau_rh", "cultiveau_vue3d", "cultiveau_mathis"],
    "data": ["data/flotte_data.xml", "views/flotte_views.xml"],
    "installable": True,
    "auto_install": False,
}
