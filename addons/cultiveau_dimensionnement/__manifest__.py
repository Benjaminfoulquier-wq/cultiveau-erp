{
    "name": "Cultiveau — Du dimensionnement au devis",
    "summary": "Secteurs, débits, diamètres, pertes de charge, HMT et pompe calculés ; la nomenclature du devis générée depuis le catalogue",
    "description": """
Le cœur du métier : l'installation se découpe en secteurs (organes, espacements, surface, conduite d'amenée, dénivelé), l'ERP calcule
le débit de chaque secteur, sa pluviométrie, le diamètre qui tient la vitesse sous 1,5 m/s, les pertes de charge (Hazen-Williams),
la pression en tête, puis le débit d'équipement, la HMT, la puissance de la pompe. Un clic génère le devis par lots avec la
nomenclature : tubes, raccords, vannes, organes, filtration, automatisme, pose — pris dans le catalogue quand il les a, à préciser sinon.
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "website": "https://cultiveau.fr",
    "license": "LGPL-3",
    "depends": ["cultiveau_installation", "cultiveau_ventes", "cultiveau_catalogue"],
    "data": ["security/ir.model.access.csv", "security/regles.xml", "views/secteur_views.xml"],
    "installable": True,
    "auto_install": False,
}
