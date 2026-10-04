{
    "name": "Cultiveau — réseau",
    "summary": "Le socle Cultiveau dans Odoo : adhérents, agriculteurs, départements, liens vers les outils du réseau.",
    "description": """
Le réseau Cultiveau dans Odoo
=============================

- chaque **adhérent** (entreprise d'irrigation) est une société Odoo : ses devis, factures, stocks

et comptabilité sont les siens ; l'équipe Cultiveau voit toutes les sociétés ;
- chaque **agriculteur** est un contact de la société de l'adhérent qui le suit ; l'adhérent importe ses clients
  depuis n'importe quel fichier (Excel, CSV) : les colonnes sont reconnues par leur intitulé ;
- le **département** est déduit du code postal (frise culturale, statistiques) ;
- les **outils du réseau** (assistant téléphonique, DTe, DISC, Académie) sont à un clic depuis le menu Cultiveau.

""",
    "version": "18.0.1.2.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "website": "https://cultiveau.fr",
    "license": "LGPL-3",
    "depends": ["base", "contacts", "mail", "base_setup"],
    "data": [
        "security/cultiveau_security.xml",
        "security/ir.model.access.csv",
        "wizard/import_clients_views.xml",
        "wizard/import_reseau_views.xml",
        "views/res_partner_views.xml",
        "views/res_company_views.xml",
        "views/res_config_settings_views.xml",
        "views/menus.xml",
    ],
    "application": True,
    "installable": True,
}
