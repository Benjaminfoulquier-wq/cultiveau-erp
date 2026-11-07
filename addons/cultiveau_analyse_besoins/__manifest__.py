{
    "name": "Cultiveau — analyse des besoins en entretien",
    "summary": "L'A1.1 comme on la fait à la ferme : huit questions dans l'ordre de la visite, les parcelles Telepac du client reprises en un clic, ce qu'il manque dit en clair.",
    "description": """
L'analyse des besoins, en entretien
===================================

Le référentiel V4 fait de l'analyse des besoins la phase fondatrice (§ 3.2, p. 22) : huit données d'entrée
(check-list p. 23), restituées dans la trame A1.1 (p. 129) et validées avec l'exploitant avant tout
dimensionnement. Ce module remplace l'onglet A1.1 de la fiche installation, qui était une grille de champs,
par **l'entretien** : huit cartes, une question par carte, dans l'ordre où elles viennent à la ferme, avec
ce qu'il faut demander, pourquoi (la section du référentiel), et ce qui manque encore.

Les **parcelles déclarées à la PAC** du client (module Parcelles, fichier Telepac) se reprennent en un clic :
surfaces, cultures, culture la plus exigeante en pointe, lieux-dits, commune, assolement de la campagne.
Sans déclaration importée, on l'importe ou on la demande au client depuis la même carte.
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "license": "LGPL-3",
    "depends": ["cultiveau_installation", "cultiveau_parcelles"],
    "data": [
        "security/ir.model.access.csv",
        "wizard/choisir_parcelles_views.xml",
        "views/installation_views.xml",
    ],
    "assets": {"web.assets_backend": ["cultiveau_analyse_besoins/static/src/scss/entretien.scss"]},
    "installable": True,
    "auto_install": False,
}
