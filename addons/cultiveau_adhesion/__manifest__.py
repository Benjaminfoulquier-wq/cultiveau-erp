{
    "name": "Cultiveau — Nouvel adhérent",
    "summary": "Un adhérent prêt à travailler en dix minutes : société, utilisateurs, assistant téléphonique, clients, articles, comptabilité, facture électronique",
    "description": """
L'assistant « Nouvel adhérent », dans Réglages : la raison sociale, le SIRET, le logo et la couleur ; les utilisateurs et leur rôle,
invités par e-mail ; le numéro dédié de l'assistant téléphonique ; l'import de ses clients et de ses articles ; la comptabilité mise
en place et le comptable invité ; l'inscription sur la plateforme agréée. Chaque étape se voit, se rejoue, et rien n'est oublié.
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "website": "https://cultiveau.fr",
    "license": "LGPL-3",
    "depends": ["cultiveau_base", "cultiveau_catalogue", "cultiveau_compta", "cultiveau_efacture", "sales_team", "stock", "purchase", "project"],
    "data": ["security/ir.model.access.csv", "views/adhesion_views.xml"],
    "installable": True,
    "auto_install": False,
}
