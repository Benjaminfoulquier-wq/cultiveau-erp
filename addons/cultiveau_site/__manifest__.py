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
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "license": "LGPL-3",
    "depends": ["cultiveau_chantier", "cultiveau_interventions", "cultiveau_installation"],
    "external_dependencies": {"python": ["requests"]},
    "data": ["security/ir.model.access.csv", "views/site_views.xml", "data/cron.xml"],
    "installable": True,
}
