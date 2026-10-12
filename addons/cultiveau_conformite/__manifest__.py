{
    "name": "Cultiveau — Conformité : journal d'audit, RGPD, démo",
    "summary": "Qui a modifié quoi (avant, après), l'export et l'effacement des données d'un client (RGPD), la remise à zéro de la démonstration",
    "description": """
- Le journal d'audit : chaque création, modification et suppression des documents du métier (clients, devis, factures,
  paiements, articles, installations, chantiers, interventions, achats, congés, notes de frais), avec la personne, l'heure,
  et pour chaque champ la valeur avant et après. « Historique des modifications » sur chaque document.
- Le RGPD : l'export de toutes les données d'un client (un fichier lisible), et l'effacement : anonymisation complète s'il n'a
  aucune pièce comptable, sinon limitation (coordonnées, échanges et courriels supprimés, les factures restent, comme la loi
  l'impose).
- La démonstration : un bouton remet la map à zéro (pointages et événements joués effacés).
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "website": "https://cultiveau.fr",
    "license": "LGPL-3",
    "depends": ["cultiveau_quotidien", "cultiveau_messagerie", "cultiveau_rh", "cultiveau_vue3d", "purchase"],
    "data": ["security/ir.model.access.csv", "security/regles.xml", "data/conformite_data.xml", "views/conformite_views.xml"],
    "installable": True,
    "auto_install": False,
}
