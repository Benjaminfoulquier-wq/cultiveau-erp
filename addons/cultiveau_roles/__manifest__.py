{
    "name": "Cultiveau — Rôles prêts à l'emploi et aide par écran",
    "summary": "Cinq rôles (gérant, administratif, technicien, magasinier, commercial) qui règlent les droits d'un coup ; un salarié reçoit son accès depuis sa fiche ; le « ? » de chaque écran dit à quoi il sert",
    "description": """
Rôles prêts à l'emploi et aide par écran
========================================

Première cause d'échec d'un ERP dans toutes les vidéos d'implémentation : des droits trop larges ou trop étroits, et personne
formé. Ici :

- un **rôle** sur l'utilisateur (gérant, administratif, technicien, magasinier, commercial) pose les droits d'un coup, dans les
  bonnes applications, ni plus ni moins ; on peut toujours affiner ensuite ;
- depuis la fiche d'un **salarié sans accès**, « Lui donner un accès » crée son utilisateur avec son rôle et lui envoie son
  invitation ;
- le bouton **?** en haut de chaque écran explique à quoi sert l'écran, par où commencer, et renvoie à la documentation ou à
  un tutoriel quand il existe. Les textes se modifient dans Réglages › Cultiveau › Aides des écrans.
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "website": "https://cultiveau.fr",
    "license": "LGPL-3",
    "depends": ["cultiveau_base", "cultiveau_rh", "cultiveau_terrain", "cultiveau_chantier", "sales_team", "crm", "account", "purchase", "stock", "project"],
    "data": ["security/ir.model.access.csv", "data/aides.xml", "views/views.xml"],
    "assets": {"web.assets_backend": ["cultiveau_roles/static/src/js/aide.js", "cultiveau_roles/static/src/xml/aide.xml"]},
    "installable": True,
    "auto_install": False,
}
