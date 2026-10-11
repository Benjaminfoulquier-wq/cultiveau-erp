{
    "name": "Cultiveau — Pilotage, bilan et clôture",
    "summary": "Tableau de bord de l'adhérent et du réseau, bilan et compte de résultat, clôture d'exercice, immobilisations et amortissements",
    "description": """
Ce qu'il faut pour piloter, pas seulement pour déclarer : le tableau de bord de l'adhérent (chiffre d'affaires et sa courbe, devis en cours,
taux de signature, retards clients, fournisseurs à payer, trésorerie, TVA) et celui du réseau pour l'équipe Cultiveau ; le bilan et le
compte de résultat lus dans les écritures, comparés à l'exercice précédent ; la clôture d'exercice (résultat soldé en 120 ou 129, période
verrouillée) ; les immobilisations et leurs amortissements passés chaque mois.
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "website": "https://cultiveau.fr",
    "license": "LGPL-3",
    "depends": ["cultiveau_compta", "sale_management"],
    "data": ["security/ir.model.access.csv", "security/regles.xml", "data/cron.xml", "views/etats_views.xml", "views/cloture_views.xml", "views/immobilisation_views.xml",
             "views/tableau_views.xml", "views/menus.xml"],
    "installable": True,
    "auto_install": False,
}
