{
    "name": "Cultiveau — Fiches techniques lues et comparateur",
    "summary": "Les fiches techniques lues par l'IA : des caractéristiques structurées par famille, un comparateur côte à côte, une recherche par caractéristique",
    "description": """
Les fiches techniques PDF sont déjà jointes aux articles. Ce module les lit (texte du PDF, ou OCR Mistral pour les fiches scannées), en
tire les caractéristiques propres à chaque famille (pompe : débit, HMT, puissance… ; asperseur : portée, débit, pression… ; tube : DN, PN,
matière…) avec la page source, et les range sur les articles. Ensuite : on coche deux à cinq articles et on les compare côte à côte,
différences surlignées, prix d'achat et de vente en regard ; et on cherche un article par ses caractéristiques.
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "website": "https://cultiveau.fr",
    "license": "LGPL-3",
    "depends": ["cultiveau_catalogue", "cultiveau_tarifs"],
    "data": ["security/ir.model.access.csv", "data/familles.xml", "data/cron.xml", "views/fiches_views.xml"],
    "installable": True,
    "auto_install": False,
}
