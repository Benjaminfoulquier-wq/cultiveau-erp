{
    "name": "Cultiveau — Tableaux de bord demandés en français",
    "summary": "« Montre-moi les interventions par technicien ce mois » : Mathis ouvre le graphique, on l'enregistre dans Mes tableaux ; sans Mathis, un formulaire en trois choix fait pareil",
    "description": """
Tableaux de bord demandés en français
=====================================

Les outils d'IA qui fabriquent des tableaux de bord à la demande font envie ; ici c'est dans l'ERP, sur les données de
l'adhérent, avec ses droits, sans rien de plus à payer.

- un sujet (interventions, bons, devis, commandes, factures, opportunités, effort commercial, clients, installations,
  chantiers, achats), une mesure (nombre, montant, heures…), un regroupement (technicien, client, mois, nature, étape, type…),
  une période, un type de graphique : l'ERP ouvre la vue graphique et le tableau croisé correspondants ;
- **Mathis** comprend la demande en français (« les devis par commercial sur le trimestre, en camembert ») et ouvre le tableau ;
  « enregistre-le » le garde dans **Mes tableaux** ;
- sans Mathis, le formulaire Mes tableaux fait la même chose en trois listes déroulantes.
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "website": "https://cultiveau.fr",
    "license": "LGPL-3",
    "depends": ["cultiveau_mathis", "cultiveau_terrain", "cultiveau_chantier", "cultiveau_crm_effort", "purchase"],
    "data": ["security/ir.model.access.csv", "security/regles.xml", "views/views.xml"],
    "installable": True,
    "auto_install": False,
}
