{
    "name": "Cultiveau — Mathis, l'assistant",
    "summary": "Mathis, l'assistant IA du réseau, dans l'ERP et sur la map : il répond sur vos données, agit avec votre accord, et ses appels vivent sur la map",
    "description": """
Mathis répond déjà au téléphone pour les adhérents (le standard IA). Ici il entre dans l'ERP :

- un panneau Mathis sur tous les écrans (icône en haut à droite) et sur la map (le personnage à l'accueil, le bouton Mathis) ;
- il répond aux questions sur les données de l'adhérent, dans les droits de la personne connectée : « qui est en intervention ? »,
  « quels devis relancer ? », « il reste combien de PE 63 ? », « où en est le chantier Durand ? » ;
- il agit avec votre accord : créer un client, une intervention, une opportunité, une note, un brouillon de courriel, un pointage ;
  chaque action est proposée puis confirmée d'un clic ;
- ses appels téléphoniques arrivent sur la map en direct : notification, Mathis décroche à l'accueil, la fiche de l'appel.
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "website": "https://cultiveau.fr",
    "license": "LGPL-3",
    "depends": ["cultiveau_api", "cultiveau_vue3d", "cultiveau_fiches"],
    "data": ["security/ir.model.access.csv", "security/regles.xml", "views/mathis_views.xml"],
    "assets": {
        "web.assets_backend": [
            "cultiveau_mathis/static/src/js/mathis.js",
            "cultiveau_mathis/static/src/xml/mathis.xml",
            "cultiveau_mathis/static/src/scss/mathis.scss",
        ],
    },
    "installable": True,
    "auto_install": False,
}
