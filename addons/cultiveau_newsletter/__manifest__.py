{
    "name": "Cultiveau — Newsletters de l'adhérent",
    "summary": "Les newsletters de l'adhérent à ses agriculteurs : à sa marque, pied « Membre du réseau Cultiveau », générateur par culture et par saison, et l'adhérent ajoute les siennes (Canva compris)",
    "description": """
La newsletter est celle de l'adhérent, pas celle du réseau : son logo et sa couleur en haut, « Membre du réseau
Cultiveau » discrètement en pied. Un générateur monte des numéros prêts à envoyer, ancrés dans le référentiel V4 :
- par culture ou par famille et par moment : les besoins en eau (besoin de pointe, besoin de saison, stade sensible,
  réserve du sol), le bon réflexe de pilotage, le Kc de la culture (déjà dans la base) ;
- par saison : hivernage, remise en route de printemps, contrat d'entretien, les aides du moment ;
- la sienne : un modèle vierge à sa marque où il colle son visuel fait sur Canva (ou son texte) et l'envoie.
Chaque newsletter cible les bons agriculteurs (par culture, par famille) grâce à la frise culturale. Tout est créé en
brouillon : l'adhérent relit, ajuste et envoie lui-même.
""",
    "version": "18.0.1.5.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "website": "https://cultiveau.fr",
    "license": "LGPL-3",
    "depends": ["mass_mailing", "mass_mailing_themes", "cultiveau_frise", "cultiveau_documents", "cultiveau_expediteur"],
    "data": [
        "security/groupes.xml",
        "security/ir.model.access.csv",
        "views/newsletter_views.xml", "views/galerie.xml",
    ],
    "post_init_hook": "_post_init_acces_newsletters",
    "installable": True,
    "auto_install": False,
}
