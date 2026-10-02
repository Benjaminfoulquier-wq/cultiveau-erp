{
    "name": "Cultiveau — interventions et dépannage",
    "summary": "Les interventions sur le parc installé : urgence, installation, équipement, pièces, registre tenu automatiquement.",
    "description": """
Interventions et dépannage
==========================

En juillet, une pompe qui s'arrête coûte 15 à 20 % du rendement en quelques jours (§ 18.1) : le
dépannage est le cœur du métier, et le module « Services sur site » d'Odoo n'existe qu'en version
Enterprise. Ce module fait des tâches de projet d'Odoo Community de vraies interventions :

- **urgence** (immédiate, dans la journée, cette semaine, non urgent), **nature** (dépannage, entretien,
  remise en service, hivernage, diagnostic, modification), installation et équipement concernés,
  symptôme, origine (l'assistant téléphonique y crée directement la fiche d'intervention) ;
- **pièces utilisées** depuis le catalogue, transformées en devis ou facture d'un clic ;
- à la clôture, l'intervention s'inscrit d'elle-même au **registre de maintenance (A1.8)** de l'installation ;
- un projet « Interventions » par adhérent, avec ses étapes (à planifier, planifiée, en cours, terminée),
  en kanban, liste et calendrier par technicien.
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "license": "LGPL-3",
    "depends": ["cultiveau_installation", "cultiveau_ventes", "project"],
    "data": [
        "security/ir.model.access.csv",
        "views/project_task_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
}
