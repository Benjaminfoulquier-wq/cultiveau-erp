{
    "name": "Cultiveau — Facture électronique",
    "summary": "La facture électronique obligatoire (plateforme agréée, e-reporting) et la double authentification, prêtes pour chaque adhérent",
    "description": """
La réforme de la facturation électronique, dans l'ERP : chaque société s'inscrit sur la plateforme agréée depuis Réglages → Cultiveau
(en démonstration d'abord, puis en réel), émet et reçoit ses factures par la plateforme, transmet le e-reporting des ventes aux
particuliers et des encaissements ; la double authentification, exigée par la réforme, s'active d'un clic.
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "website": "https://cultiveau.fr",
    "license": "LGPL-3",
    "depends": ["cultiveau_base", "cultiveau_marque", "l10n_fr_pdp", "auth_totp_mail_enforce"],
    "data": ["views/res_config_settings_views.xml"],
    "installable": True,
    "auto_install": False,
}
