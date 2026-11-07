{
    "name": "Cultiveau — L'expéditeur des courriels",
    "summary": "Tout ce que l'ERP envoie (devis, commandes, factures, réponses du fil) part de notification@cultiveau.fr au nom de l'adhérent, ou de la boîte de l'adhérent ; chaque envoi reste écrit dans le fil de la fiche",
    "description": """
L'expéditeur des courriels
==========================

Un client qui reçoit un devis doit voir le nom de son installateur, pas celui d'un serveur. Deux réglages par adhérent :

- **Par le réseau** : l'e-mail part de notification@cultiveau.fr avec le nom de l'adhérent comme expéditeur, et les réponses
  reviennent à l'adresse de l'adhérent (Répondre à). Rien à configurer chez lui.
- **Par sa boîte** : l'adhérent a branché sa boîte (Courriels › Boîtes mail : Gmail, Outlook ou SMTP) ; tout part de là, en son nom,
  et ses envois apparaissent dans ses « Envoyés ».

Dans les deux cas, chaque courriel sorti par l'ERP est écrit dans le fil de la fiche concernée (devis, commande, facture, client,
intervention) : le fil reste la base de tout.
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "website": "https://cultiveau.fr",
    "license": "LGPL-3",
    "depends": ["cultiveau_base", "cultiveau_messagerie", "mail"],
    "data": ["views/views.xml"],
    "installable": True,
    "auto_install": False,
}
