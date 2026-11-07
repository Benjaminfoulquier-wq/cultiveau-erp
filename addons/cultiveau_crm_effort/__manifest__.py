{
    "name": "Cultiveau — Le CRM qui mesure l'effort commercial",
    "summary": "Types d'activités comptés (appel, R1, R2, relance, visite), relances automatiques par étape, affaires oubliées reprises, raison de perte obligatoire, pistes et revenus récurrents activés, le tableau de l'effort commercial",
    "description": """
Le CRM qui mesure l'effort commercial
=====================================

Un pipeline en six phases ne suffit pas si l'on ne mesure pas ce qu'on fait pour avancer. Ce module :

- donne des **types d'activités** nommés comme sur le terrain : appel de prospection, visite R1 (découverte), visite R2 (remise du
  devis), relance du devis, visite de chantier ou d'après-vente ;
- **enchaîne** : passage en Analyse des besoins, une visite R1 est planifiée ; devis envoyé, une relance à J+7 ; une affaire sans
  activité ni mouvement depuis 14 jours reçoit « Reprendre contact » ;
- rend la **raison de perte obligatoire** et en propose les vraies : prix, concurrent, reporté, pas de financement, pas d'eau ou
  d'autorisation, sans réponse ;
- active les **pistes** (la prospection pure, à part des opportunités) et les **revenus récurrents** (le contrat d'entretien
  annuel chiffré avec le projet) ;
- offre le tableau **Effort commercial** : activités faites par personne, par type et par mois, à croiser avec les affaires gagnées.
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "website": "https://cultiveau.fr",
    "license": "LGPL-3",
    "depends": ["cultiveau_ventes", "crm"],
    "data": ["security/ir.model.access.csv", "data/donnees.xml", "data/cron.xml", "views/views.xml"],
    "post_init_hook": "activer_groupes",
    "installable": True,
    "auto_install": False,
}
