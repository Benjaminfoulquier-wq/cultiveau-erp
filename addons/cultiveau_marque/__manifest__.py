{
    "name": "Cultiveau — la marque",
    "summary": "L'ERP aux couleurs de Cultiveau : logo, favicon, couleurs, titre, et plus aucune mention de l'éditeur du logiciel.",
    "description": """
La marque Cultiveau
===================

L'ERP du réseau se présente comme Cultiveau, pas comme le logiciel sur lequel il est bâti : logo
et favicon Cultiveau, bleu-vert sombre de la barre de menu et cyan des actions (les couleurs du
logo), titre « Cultiveau » dans l'onglet du navigateur, page de connexion sans pied de page de
l'éditeur ni lien d'inscription publique, menu utilisateur sans les liens vers l'éditeur.
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "license": "LGPL-3",
    "depends": ["web", "auth_signup", "cultiveau_base"],
    "data": [
        "data/marque.xml",
        "views/templates.xml",
    ],
    "assets": {
        "web._assets_primary_variables": [
            ("prepend", "cultiveau_marque/static/src/scss/primary_variables.scss"),
        ],
        "web.assets_backend": [
            "cultiveau_marque/static/src/js/marque.js",
            "cultiveau_marque/static/src/scss/backend.scss",
        ],
    },
    "installable": True,
    "auto_install": False,
}
