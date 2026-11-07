{
    "name": "Cultiveau — Le devis simple : stock, phases, matériel",
    "summary": "Un devis en piochant dans son stock (disponible et manque sur chaque ligne, « Depuis mon stock »), des phases créées dans le devis avec leurs jours et leur jalon, le matériel par phase ; le chantier les reprend telles quelles",
    "description": """
Le devis simple : stock, phases, matériel
=========================================

Un adhérent doit pouvoir faire un devis vite : ouvrir son stock, poser les articles, découper en phases, chiffrer la pose, envoyer.

- sur chaque ligne du devis, le **disponible** en stock et le **manque** ; le bouton **Depuis mon stock** ouvre le catalogue filtré sur
  ce qu'il a en rayon ;
- **Ajouter une phase** sous les lignes : une section de chantier avec ses jours prévus et son jalon de facturation ; le matériel et
  la pose se mettent dessous, comme dans un lot ;
- à la confirmation, le **chantier** reprend les phases du devis (ordre, durées, jalons), y rattache le matériel de chaque phase et
  en déduit les heures prévues ; les dates de besoin et la facturation à l'avancement suivent.
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "website": "https://cultiveau.fr",
    "license": "LGPL-3",
    "depends": ["cultiveau_jalons", "sale_stock"],
    "data": ["views/views.xml"],
    "installable": True,
    "auto_install": False,
}
