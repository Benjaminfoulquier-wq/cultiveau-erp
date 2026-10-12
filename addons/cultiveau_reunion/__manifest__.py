{
    "name": "Cultiveau — Réunions, agendas et visio",
    "summary": "La salle de réunion de la map branchée sur les agendas : créneaux libres proposés, invitations, visio intégrée, Google Meet ou Teams",
    "description": """
La salle de réunion de la map vit avec l'agenda : libre ou occupée, la réunion en cours et ses participants, celles du jour,
le bouton « Rejoindre la visio ». Les personnes en réunion vont s'asseoir dans la salle (ou restent à leur poste en visio).

Planifier une réunion depuis la map, une fiche client ou Mathis : l'ERP cherche les créneaux où tout le monde est libre
(agenda, interventions planifiées, salle), puis invite les participants avec la visio choisie :
- la visio intégrée de l'ERP, sans compte à créer, ouverte aussi aux clients par un lien ;
- Google Meet, créé par Google quand l'agenda de l'organisateur est synchronisé avec Google Agenda ;
- Teams, créé par Microsoft quand l'agenda est synchronisé avec Outlook ;
- ou n'importe quel lien (Zoom, Whereby…).
Chaque personne connecte son agenda Google ou Outlook en un clic depuis la salle de réunion ; les réunions vont et viennent
dans les deux sens.
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "website": "https://cultiveau.fr",
    "license": "LGPL-3",
    "depends": ["cultiveau_mathis", "cultiveau_vue3d", "calendar", "google_calendar", "microsoft_calendar"],
    "data": ["views/reunion_views.xml", "data/identifiants.xml"],
    "installable": True,
    "auto_install": False,
}
