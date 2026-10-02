{
    "name": "Cultiveau — réseau",
    "summary": "Le socle Cultiveau dans Odoo : adhérents, agriculteurs, départements, liens vers les outils du réseau.",
    "description": """
Le réseau Cultiveau dans Odoo
=============================

- chaque **adhérent** (entreprise d'irrigation) est une société Odoo : ses devis, factures, stocks
et comptabilité sont les siens ; l'équipe Cultiveau voit toutes les sociétés ;
- chaque **agriculteur** est un contact de la société de l'adhérent qui le suit ;
- le **département** est déduit du code postal (frise culturale, statistiques) ;
- les **outils du réseau** (assistant téléphonique, DTe, DISC, Académie) sont à un clic depuis le menu Cultiveau.
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "website": "https://cultiveau.fr",
    "license": "LGPL-3",
    "depends": ["base", "contacts", "mail", "base_setup"],
    "data": [
        "security/cultiveau_security.xml",
        "views/res_partner_views.xml",
        "views/res_company_views.xml",
        "views/res_config_settings_views.xml",
        "views/menus.xml",
    ],
    "application": True,
    "installable": True,
}
