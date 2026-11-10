{
    "name": "Cultiveau — liaison avec le site cultiveau.fr",
    "summary": "L'ERP récupère, adhérent par adhérent, les clients, interventions, chantiers et bons d'intervention saisis dans l'espace adhérent de cultiveau.fr.",
    "description": """
La liaison avec l'espace adhérent
=================================

Les adhérents travaillent aussi dans l'espace adhérent de cultiveau.fr (SAV, chantiers, planning). L'ERP y va chercher
leurs données par l'API externe du site (``/api/external``, une clé par entreprise adhérente, créée dans l'administration
du site, page « Clés API ») :

- les **clients** (fiches clients du SAV) → contacts de l'adhérent, sans doublon (téléphone, e-mail, nom) ;
- les **interventions** (fiches d'intervention) → interventions de l'ERP (nature, urgence, état, date, symptômes, travaux) ;
- les **chantiers** → chantiers de l'ERP (une installation « projet » est créée pour le client si besoin) ;
- les **bons d'intervention** (réalisé, montants, signatures) → « Bons du site », rattachés au client, à l'intervention
  et au chantier, prêts pour la facturation.

Lecture seule côté site : rien n'est écrit sur cultiveau.fr. Une tâche planifiée synchronise chaque heure ; le bouton
« Synchroniser » le fait tout de suite. Les jetons de validation des pages publiques du site ne sont jamais conservés.

Les écrans dans l'ERP
---------------------

Les menus **Mon Espace** et **Logistique** affichent les vrais écrans de cultiveau.fr et de logistique.cultiveau.fr dans le
cadre de l'ERP, sans nouvelle connexion : l'ERP signe un laissez-passer d'une minute pour l'utilisateur (son e-mail doit
être celui de son compte adhérent) avec le secret ``cultiveau.erp_lien_secret`` (même valeur que « ERP_LIEN_SECRET » sur
le site). Rien n'est recopié : une évolution du site ou de la logistique se voit aussitôt dans l'ERP.
""",
    "version": "18.0.1.4.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "license": "LGPL-3",
    "depends": ["stock", "sale_management", "uom", "cultiveau_connecteurs", "cultiveau_chantier", "cultiveau_interventions", "cultiveau_installation", "cultiveau_terrain"],
    "external_dependencies": {"python": ["requests"]},
    "data": ["security/ir.model.access.csv", "views/site_views.xml", "views/ecrans.xml", "views/res_config_settings_views.xml", "views/company_views.xml", "views/chantier_views.xml", "views/terrain_views.xml", "views/articles_views.xml", "data/cron.xml", "data/erp_ouvert.xml", "data/entrepots.xml"],
    "assets": {
        "web.assets_backend": [
            "cultiveau_site/static/src/js/ecran.js",
            "cultiveau_site/static/src/xml/ecran.xml",
            "cultiveau_site/static/src/scss/ecran.scss",
        ],
    },
    "installable": True,
}
