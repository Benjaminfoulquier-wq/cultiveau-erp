{
    "name": "Cultiveau — le devis qui en dit plus",
    "summary": "Les marges visibles (ligne, lot, total), les fiches techniques jointes à l'envoi, et les commentaires techniques du référentiel V4 sur le devis.",
    "description": """
Le devis qui en dit plus
========================

- **Les marges** : prix d'achat, marge et taux sur chaque ligne, marge par lot, marge totale avec un repère par rapport au minimum
  de l'entreprise. Visibles des gérants, administratifs et commerciaux, jamais du client.
- **Les fiches techniques** : à l'envoi du devis, les fiches des matériels proposés (bibliothèque du réseau, logistique Cultiveau,
  fournisseurs) partent en pièces jointes ; le PDF du devis les liste.
- **Le référentiel sur le devis** : un bouton relit le devis avec le référentiel technique de l'irrigation agricole V4 et ajoute
  des notes techniques (section, page, niveau de prescription § 1.4.3) : ce que le matériel proposé impose (filtration, anti-retour,
  ventouses, PN, vitesses…) et ce qui manque (compteur, sécurité de pompe, filtre en micro-irrigation…). Les règles se complètent
  dans Réglages › Cultiveau › Avis du référentiel.
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "license": "LGPL-3",
    "depends": ["cultiveau_documents", "cultiveau_ventes", "cultiveau_catalogue", "sale_margin"],
    "data": [
        "security/ir.model.access.csv",
        "data/avis.xml",
        "views/avis_views.xml",
        "views/sale_order_views.xml",
        "views/product_views.xml",
        "views/res_config_settings_views.xml",
        "report/devis.xml",
    ],
    "installable": True,
    "auto_install": False,
}
