{
    "name": "Cultiveau — Rendez-vous en ligne",
    "summary": "Un lien à mettre dans les courriels ou sur le site : le client choisit un créneau libre, le rendez-vous tombe dans l'agenda",
    "description": """
La prise de rendez-vous par le client, sans échange de courriels :

- des motifs de rendez-vous (visite conseil sur l'exploitation, diagnostic, rendez-vous au dépôt…), chacun avec sa durée,
  son lieu et les personnes qui peuvent le prendre ;
- une page publique par société et par motif : les créneaux libres de l'équipe (agenda, interventions, congés), puis les
  coordonnées du client ;
- le rendez-vous tombe dans l'agenda de la personne, le client reçoit l'invitation, la map l'annonce ;
- le client est retrouvé (ou créé) dans les contacts.
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "website": "https://cultiveau.fr",
    "license": "LGPL-3",
    "depends": ["cultiveau_reunion", "cultiveau_rh", "cultiveau_vue3d", "cultiveau_mathis"],
    "data": ["security/ir.model.access.csv", "security/regles.xml", "views/rdv_views.xml", "views/rdv_templates.xml", "data/rdv_data.xml"],
    "installable": True,
    "auto_install": False,
}
