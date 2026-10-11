{
    "name": "Cultiveau — Devis et factures",
    "summary": "Devis et factures au nom de l'adhérent : mise en page à sa marque, acompte, signature en ligne, CGV, relances automatiques",
    "description": """
Les documents qu'un adhérent envoie à ses clients, propres et à sa marque :
- une mise en page « Cultiveau » : logo et couleur de l'adhérent, ses coordonnées, « membre du réseau Cultiveau » en pied ;
- le devis : le projet (installation, surface), l'acompte à la commande, le bloc « bon pour accord », la signature en ligne, les CGV en dernière page ;
- la facture : mentions légales françaises (pénalités, indemnité de recouvrement) ;
- les e-mails en français : envoi du devis avec le bouton « voir et signer », envoi de la facture ;
- les relances automatiques : devis sans réponse, factures en retard, puis une activité pour le commercial.
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "website": "https://cultiveau.fr",
    "license": "LGPL-3",
    "depends": ["cultiveau_ventes", "cultiveau_marque", "sale_management", "account"],
    "data": [
        "report/layout.xml",
        "report/devis.xml",
        "report/facture.xml",
        "data/mail.xml",
        "data/cron.xml",
        "views/res_config_settings_views.xml",
        "views/sale_order_views.xml",
        "views/account_move_views.xml",
        "data/defauts.xml",
    ],
    "installable": True,
    "auto_install": False,
}
