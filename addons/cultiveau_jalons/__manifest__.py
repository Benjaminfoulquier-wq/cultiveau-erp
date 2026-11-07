{
    "name": "Cultiveau — Facturation à l'avancement et besoins datés",
    "summary": "Chaque phase du chantier porte son jalon de facturation (% du devis) et sa date de besoin matière : la facture part à la fin de la phase, les achats arrivent pour la phase",
    "description": """
Facturation à l'avancement et besoins datés
===========================================

Sur un pivot ou une station, on ne facture pas tout à la mise en service : un acompte à la commande, une situation à la fin
des tranchées, une autre à la station posée, le solde après les essais. Et le matériel de chaque phase doit arriver pour la
phase, pas tout le premier jour (idée vue dans l'industrie construction d'Odoo 20).

- chaque **phase** du chantier a son **jalon** (% du devis facturé à la fin de la phase) ; « Facturer ce jalon » crée la facture
  d'acompte correspondante, « Facturer le solde » la facture finale qui déduit tout ;
- le **matériel** du chantier se rattache à une phase ; sa **date de besoin** est le début de la phase ; l'approvisionnement du
  devis la reprend pour la date de livraison demandée aux fournisseurs ;
- le chantier montre le **plan de facturation** : acompte, jalons, solde, ce qui est facturé et encaissé.
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "website": "https://cultiveau.fr",
    "license": "LGPL-3",
    "depends": ["cultiveau_chantier", "cultiveau_declenche", "cultiveau_documents"],
    "data": ["views/views.xml"],
    "installable": True,
    "auto_install": False,
}
