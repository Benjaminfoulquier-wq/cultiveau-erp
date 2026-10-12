{
    "name": "Cultiveau — Équipe : congés, absences et notes de frais",
    "summary": "Congés demandés depuis le téléphone et validés en un clic, soldes, jours fériés, notes de frais lues sur la photo du ticket",
    "description": """
L'équipe dans l'ERP, sans paperasse :

- chaque personne a sa fiche salarié, le gérant valide (congés et notes de frais) ;
- congés payés (25 jours par période, réglable), RTT, sans solde, événement familial, arrêt maladie ; les jours fériés
  français sont posés tout seuls, l'année en cours et la suivante ;
- une page pour le téléphone (/moi) : badger, demander un congé, photographier un ticket, valider (pour le gérant) ;
- le ticket photographié est lu par l'IA (date, montant, TVA, fournisseur, catégorie) : il ne reste qu'à l'envoyer ;
- la map montre qui est en congés, les fiches portent les soldes et les demandes à valider ;
- les créneaux de réunion évitent les absences ; Mathis répond (« qui est absent la semaine prochaine ? ») et agit.
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "website": "https://cultiveau.fr",
    "license": "LGPL-3",
    "depends": ["hr_holidays", "hr_expense", "cultiveau_reunion", "cultiveau_mathis", "cultiveau_vue3d"],
    "data": [
        "data/rh_data.xml",
        "views/rh_views.xml",
        "views/moi_templates.xml",
    ],
    "installable": True,
    "auto_install": False,
}
