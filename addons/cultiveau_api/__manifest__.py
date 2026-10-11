{
    "name": "Cultiveau — API et connecteur Claude",
    "summary": "Les données de l'ERP ouvertes au site cultiveau.fr, aux applis et à Claude : clés d'API, API REST documentée, connecteur MCP.",
    "description": """
L'API de l'ERP
==============

Tout ce que l'ERP sait, lisible (et en partie inscriptible) par les autres outils du réseau :

- **Clés d'API** (Cultiveau → Réglages → Clés d'API) : une clé par outil (le site cultiveau.fr, l'appli, Claude…),
  en lecture seule ou en lecture et écriture, limitée ou non à certains adhérents ; la clé n'est montrée qu'une fois
  et n'est conservée que sous forme d'empreinte ;
- **API REST** ``/cultiveau/api/v1`` : clients, interventions, chantiers, installations, registre, devis, commandes,
  factures, opportunités, articles, fiches techniques, adhérents ; recherche, filtres, pagination, « modifié depuis » ;
  création de clients, d'interventions et d'opportunités, notes sur une fiche ; description OpenAPI ;
- **Connecteur Claude (MCP)** ``/cultiveau/mcp`` : la même chose en outils pour Claude, à ajouter comme connecteur
  personnalisé ; Claude lit l'ERP et y dépose des demandes.
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "license": "LGPL-3",
    "depends": ["cultiveau_connecteurs", "cultiveau_chantier", "cultiveau_catalogue", "cultiveau_installation", "stock", "account"],
    "data": ["security/ir.model.access.csv", "views/cle_api_views.xml"],
    "installable": True,
}
