{
    "name": "Cultiveau — Grille de remises",
    "summary": "Des remises par typologie de client et par famille d'articles, appliquées seules au devis, la marge sous les yeux",
    "description": """
La base tarifaire de l'adhérent : une grille de remises croisant la typologie du client (agriculteur, collectivité, paysagiste, plombier,
pisciniste, industrie, particulier) et la famille ou sous-famille d'articles, avec des exceptions pour un client, un article ou une
quantité. Au devis, chaque ligne trouve sa remise d'elle-même (modifiable) et la marge s'affiche. Le réseau propose une grille que
chaque adhérent copie puis ajuste.
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "website": "https://cultiveau.fr",
    "license": "LGPL-3",
    "depends": ["cultiveau_tarifs", "sale_margin"],
    "data": ["security/ir.model.access.csv", "security/regles.xml", "views/grille_views.xml", "views/res_config_settings_views.xml"],
    "installable": True,
    "auto_install": False,
}
