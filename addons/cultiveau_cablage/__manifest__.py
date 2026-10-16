{
    "name": "Cultiveau — Câblage : de l'étude à l'armoire, sans dessin",
    "summary": "L'armoire de pompage et le câblage des électrovannes compilés depuis l'étude : puissance, commande, borniers, nomenclature, cartouche et indice",
    "description": """
Vous décrivez l'armoire (ou l'ERP la reprend de l'étude : la pompe du dimensionnement, un secteur = une électrovanne), vous cliquez
« Compiler ». Le dossier d'exécution sort :

- folio puissance (unifilaire) : arrivée, interrupteur-sectionneur, différentiel, parafoudre, départs moteurs avec disjoncteur,
  contacteur, étoile-triangle ou variateur, câbles et chutes de tension ;
- folio commande : l'échelle 230 V (arrêt d'urgence, Auto/Manu, thermique, manque d'eau, ordre du programmateur), le 24 V
  (transformateur, programmateur ou automate, une sortie par secteur, vanne maître, entrées) ;
- borniers XA / XB / XC, nomenclature repérée (IEC 81346) avec les articles du catalogue, cartouche et indice de révision.

Les courants, calibres, sections et chutes de tension suivent les règles usuelles (NF C 15-100) : un pré-dimensionnement que
l'électricien qui réalise l'armoire vérifie et valide. La nomenclature s'ajoute au devis en un lot ; le PDF se joint au dossier
technique de l'installation ; Mathis répond et compile.
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "website": "https://cultiveau.fr",
    "license": "LGPL-3",
    "depends": ["cultiveau_dimensionnement", "cultiveau_vue3d", "cultiveau_mathis", "sale_management"],
    "data": ["security/ir.model.access.csv", "security/regles.xml", "data/cablage_data.xml", "report/armoire_report.xml", "views/armoire_views.xml"],
    "installable": True,
    "auto_install": False,
}
