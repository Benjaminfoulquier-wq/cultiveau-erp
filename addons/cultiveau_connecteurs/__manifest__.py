{
    "name": "Cultiveau — connecteurs (standard IA, outils du réseau)",
    "summary": "L'assistant téléphonique lit la fiche du client qui appelle et dépose dans l'ERP l'intervention ou l'opportunité.",
    "description": """
Que tout communique
===================

Deux points d'entrée HTTP, protégés par la clé réglée dans Cultiveau → Réglages :

- ``GET /cultiveau/api/client?telephone=…&numero_dedie=…`` : qui appelle ? Nom, exploitation, commune,
  persona (comment lui parler), cultures et fenêtre commerciale du mois, installations et pressions de
  référence : de quoi décrocher en connaissant le client ;
- ``POST /cultiveau/api/appel`` : à la fin de l'appel, l'assistant dépose une **intervention** (panne,
  avec son urgence) ou une **opportunité** (demande de prix, projet), rattachée au client (créé s'il est
  inconnu) et à l'adhérent reconnu par son numéro dédié ; sinon une activité sur la fiche du client.

Côté assistant téléphonique (dépôt cultiveau-assistant), le connecteur « odoo » appelle ces adresses.
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "license": "LGPL-3",
    "depends": ["cultiveau_base", "cultiveau_frise", "cultiveau_persona", "cultiveau_installation", "cultiveau_ventes", "cultiveau_interventions"],
    "data": [],
    "installable": True,
}
