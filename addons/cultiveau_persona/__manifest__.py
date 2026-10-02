{
    "name": "Cultiveau — persona client",
    "summary": "Qui est l'agriculteur en face, et comment lui parler : un questionnaire de huit questions, quatre personas.",
    "description": """
Le persona client
=================

Le Bâtisseur investit pour dix ans et veut un dossier ; le Pragmatique veut que ça marche vite au
juste prix ; le Pilote veut des sondes et des données ; le Fidèle achète une relation. Le même devis
ne se présente pas de la même façon à chacun.

Depuis la fiche d'un agriculteur, le commercial répond à huit questions ; le persona est calculé,
affiché sur la fiche avec l'approche, les arguments, le canal, le moment et les pièges à éviter.
Les personas et leurs conseils suivent le référentiel technique Cultiveau (conseil d'abord, analyse
des besoins avant tout dimensionnement, suivi et maintenance).
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "license": "LGPL-3",
    "depends": ["cultiveau_base"],
    "data": [
        "security/ir.model.access.csv",
        "data/personas.xml",
        "views/persona_views.xml",
        "wizard/persona_wizard_views.xml",
        "views/res_partner_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
}
