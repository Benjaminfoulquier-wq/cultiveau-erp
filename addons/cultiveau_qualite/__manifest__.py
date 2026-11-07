{
    "name": "Cultiveau — Qualité des données",
    "summary": "Une page qui compte ce qui manque ou doublonne (clients sans type ni téléphone, doublons, articles sans prix ni fournisseur, installations sans PV, devis expirés, réglages absents) et ouvre la liste à corriger en masse",
    "description": """
Qualité des données
===================

Deuxième cause d'échec d'un ERP : des données sales qu'on a migrées sans les regarder. Cette page compte, par société, ce qui
manque ou doublonne, dit pourquoi ça compte (le véhicule au parking, la newsletter, la liste de courses, le dépannage sans
référence) et ouvre la liste à corriger, en masse quand c'est possible.
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "website": "https://cultiveau.fr",
    "license": "LGPL-3",
    "depends": ["cultiveau_base", "cultiveau_installation", "cultiveau_terrain", "cultiveau_documents", "contacts"],
    "data": ["security/ir.model.access.csv", "views/views.xml"],
    "assets": {"web.assets_backend": ["cultiveau_qualite/static/src/js/qualite.js", "cultiveau_qualite/static/src/xml/qualite.xml"]},
    "installable": True,
    "auto_install": False,
}
