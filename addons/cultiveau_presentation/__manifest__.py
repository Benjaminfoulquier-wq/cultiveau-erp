{
    "name": "Cultiveau — Présentation des devis et factures",
    "summary": "Chaque adhérent détaille ses devis et ses factures comme il veut : complet, par lot, forfait, matériel et main-d'œuvre",
    "description": """
Un réglage par adhérent, modifiable document par document : le devis (et, séparément, la facture) se présente en détail complet, par lot
(un montant par lot, le détail reste interne), en forfait (une ligne), ou matériel et main-d'œuvre séparés. Une ligne peut aussi être
masquée : son montant se fond dans le reste. L'ERP garde tout ; le client voit ce que l'adhérent a décidé.
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "website": "https://cultiveau.fr",
    "license": "LGPL-3",
    "depends": ["cultiveau_documents"],
    "data": ["views/views.xml", "report/facture.xml"],
    "installable": True,
    "auto_install": False,
}
