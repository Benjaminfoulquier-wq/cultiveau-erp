{
    "name": "Cultiveau — La commande fait le projet",
    "summary": "Chaque prestation du devis devient une tâche planifiée à la commande (montage, câblage, mise en route) ; le questionnaire de financement part tout seul après la signature et se relance ; pro forma en un clic ; « Sans suite » avec sa raison",
    "description": """
La commande fait le projet
==========================

Ce qu'un adhérent qui tourne bien sur Odoo (Eaux Vives Activités) a mis en place, rendu à tout le réseau sans réglage :

- chaque **prestation** du devis (montage pompe, montage mécanique, câblage, forfait mise en route…) devient à la commande une
  **tâche** du projet Interventions, avec ses heures, sa date (celle de sa phase), son client et son installation : elle apparaît
  dans Ma journée et sur les feuilles de route ; la commande compte ses tâches et ses heures pointées ;
- après la signature, le **questionnaire de financement** part au client (comptant, crédit, location, irrigation à l'usage, aide en
  cours, date de pose souhaitée) ; une tâche « Financement » suit la réponse, une relance repart à J+15, la réponse s'écrit sur la
  commande et dans le fil ;
- la **facture pro forma** s'envoie d'un clic ; un devis **sans suite** se classe avec sa raison.
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "website": "https://cultiveau.fr",
    "license": "LGPL-3",
    "depends": ["cultiveau_declenche", "cultiveau_phases_devis", "cultiveau_terrain", "cultiveau_crm_effort", "survey", "sale_project"],
    "data": ["data/survey.xml", "data/cron.xml", "views/views.xml"],
    "post_init_hook": "preparer",
    "installable": True,
    "auto_install": False,
}
