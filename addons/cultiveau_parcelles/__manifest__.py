{
    "name": "Cultiveau — Parcelles PAC et suivi satellite",
    "summary": "Les parcelles du client depuis sa déclaration PAC (Telepac), ses cultures en automatique, NDVI et NDWI Sentinel-2 gratuits, alertes",
    "description": """
- On demande au client son fichier Telepac (export XML de la déclaration, ou ZIP des parcelles) : ses parcelles, leur contour, leur
  surface et leur culture arrivent sur sa fiche ; ses cultures (frise, Kc, besoins en eau) se remplissent d'elles-mêmes.
- Sentinel-2, par le Copernicus Data Space (gratuit) : NDVI (vigueur) et NDWI (eau dans les feuilles) de chaque parcelle tous les 5 jours.
- Ce qui cloche (chute de vigueur, stress hydrique, parcelle hétérogène) au moment où la culture doit être verte : une alerte, une
  activité pour le commercial, et un e-mail au client en un clic (ou automatiquement).
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "website": "https://cultiveau.fr",
    "license": "LGPL-3",
    "depends": ["cultiveau_frise", "cultiveau_base", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "security/regles.xml",
        "data/codes_pac.xml",
        "data/mail.xml",
        "data/cron.xml",
        "wizard/import_telepac_views.xml",
        "views/apport_views.xml",
        "views/parcelle_views.xml",
        "views/res_partner_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "installable": True,
}
