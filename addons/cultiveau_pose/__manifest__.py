{
    "name": "Cultiveau — Matrice de pose",
    "summary": "Le temps de pose par geste, construit avec les techniciens ; la main-d'œuvre calculée au devis et corrigée par les chantiers réels",
    "description": """
Une table des gestes de pose (asperseur sur PE, tranchée au mètre, raccord électrosoudable, programmation d'un secteur…) avec le temps
standard, le nombre de personnes et les coefficients de terrain (caillouteux, pente, accès, hiver). Au devis, la main-d'œuvre se calcule
depuis la nomenclature au lieu d'un forfait au doigt mouillé. À la fin de chaque chantier, les heures pointées sont comparées au prévu et
chaque geste apprend son temps constaté, que l'adhérent adopte en un clic. Le réseau propose une matrice de départ.
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "website": "https://cultiveau.fr",
    "license": "LGPL-3",
    "depends": ["cultiveau_chantier"],
    "data": ["security/ir.model.access.csv", "security/regles.xml", "data/gestes.xml", "views/pose_views.xml"],
    "installable": True,
    "auto_install": False,
}
