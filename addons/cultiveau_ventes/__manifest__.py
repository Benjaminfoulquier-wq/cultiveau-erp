{
    "name": "Cultiveau — devis et projets d'irrigation",
    "summary": "Le pipeline en six phases du référentiel, des devis par lots (station, filtration, réseau, secteurs, automatisme, pose) reliés à l'installation.",
    "description": """
Devis et projets d'irrigation
=============================

Un devis d'irrigation n'est pas une liste de lignes : c'est un projet par lots (station de pompage,
filtration, réseau principal, secteurs, automatisme, pose et mise en service), relié à l'analyse des
besoins et au dimensionnement de l'installation. Ce module :

- relie chaque **opportunité** et chaque **devis** à l'installation (parc installé) et rappelle, au
  moment de confirmer, si l'analyse des besoins (A1.1) n'a pas été validée avec l'exploitant ;
- donne au CRM les **six phases** du référentiel (§ 3.1) : demande → analyse des besoins → étude et
  dimensionnement → devis → commande et réalisation → mise en service → suivi ;
- fournit des **modèles de devis par type d'installation** (goutte à goutte, aspersion, enrouleur,
  pivot) avec les lots et les lignes de mise en service, réception et formation (PV A1.3, A1.5) ;
- met devis, commandes, factures et opportunités dans le menu Cultiveau.
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "license": "LGPL-3",
    "depends": ["cultiveau_installation", "sale_management", "crm", "account"],
    "data": [
        "data/crm_stages.xml",
        "data/modeles_devis.xml",
        "views/sale_order_views.xml",
        "views/crm_lead_views.xml",
        "views/installation_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
}
