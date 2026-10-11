{
    "name": "Cultiveau — chantiers",
    "summary": "Le chantier de pose : planning de l'équipe, matériel sorti du magasin, journal et photos, PV de mise en service signé.",
    "description": """
Les chantiers
=============

Entre le devis signé et l'installation en service, il y a le chantier : une équipe de pose, des dates, du matériel
réservé au magasin et sorti pour le chantier, un journal avec les photos, puis la mise en service avec son PV
(pressions de référence, essais, sécurités) signé par l'exploitant sur place.

- un chantier se lance depuis la commande (« Lancer le chantier ») ou depuis l'installation ;
- le matériel prévu vient des lignes de la commande ; « Sortir le matériel » crée le bon de sortie du magasin ;
- le planning (calendrier, par chef de chantier) et le tableau (à planifier, planifié, en cours, terminé) ;
- la mise en service remplit le PV de l'installation, la passe « en service » et l'inscrit au registre ;
- la vue d'ensemble montre les chantiers en cours avec leur équipe.
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "license": "LGPL-3",
    "depends": ["cultiveau_interventions", "cultiveau_vue3d", "stock"],
    "data": [
        "security/ir.model.access.csv",
        "data/sequence.xml",
        "views/chantier_views.xml",
        "views/sale_order_views.xml",
        "views/installation_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
}
