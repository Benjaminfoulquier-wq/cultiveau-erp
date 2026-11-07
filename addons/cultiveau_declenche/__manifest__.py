{
    "name": "Cultiveau — Le devis déclenche tout",
    "summary": "Devis signé : le chantier, la facture d'acompte, les demandes de prix des manquants et la mise en service se créent seuls ; la liste de courses du devis",
    "description": """
Le devis déclenche tout
=======================

Chez les chauffagistes et les solaristes qui tournent bien sur Odoo, la confirmation du devis ne se contente pas de
réserver du stock : elle met toute la chaîne en marche. Ici, quand un devis d'installation est confirmé (signé en ligne ou
au bureau), l'ERP crée, selon les réglages de l'adhérent :

- le **chantier** de pose avec ses phases et le matériel prévu (module Chantiers) ;
- la **facture d'acompte** au pourcentage du devis, en brouillon, prête à partir ;
- les **demandes de prix** aux fournisseurs pour ce qui manque en stock (une par fournisseur, en brouillon) ;
- l'**intervention de mise en service** (PV A1.3) à planifier.

Et à tout moment, l'**approvisionnement du devis** : article par article, ce qu'il y a en stock, ce qui arrive, ce qui
manque, chez qui et à quel prix, et les demandes de prix en un clic.
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "website": "https://cultiveau.fr",
    "license": "LGPL-3",
    "depends": ["cultiveau_chantier", "cultiveau_documents", "sale_stock", "purchase_stock", "sale_purchase"],
    "data": ["security/ir.model.access.csv", "views/res_config_settings_views.xml", "views/sale_order_views.xml", "views/approvisionnement_views.xml"],
    "installable": True,
    "auto_install": False,
}
