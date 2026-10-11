{
    "name": "Cultiveau — comptoir",
    "summary": "La vente au comptoir : on scanne ou on cherche l'article, on encaisse, le ticket sort, le stock et la compta suivent.",
    "description": """
Le comptoir
===========

L'agriculteur passe au magasin pour trois raccords et un programmateur : pas le temps d'un devis en six écrans.
Le comptoir est un seul écran : la douchette (ou le clavier) pour trouver l'article, le panier, le client (ou « client de
passage »), puis « Encaisser » en espèces, carte, chèque ou virement. Derrière : la commande est confirmée, la sortie de
stock validée, la facture établie et payée, le ticket imprimé. Les boutons « Devis » et « Commande à livrer » gardent la
même saisie pour l'agriculteur qui veut réfléchir ou se faire livrer.

Si la comptabilité de l'adhérent n'est pas encore en place, le comptoir installe le plan comptable français au premier
encaissement.
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "license": "LGPL-3",
    "depends": ["cultiveau_ventes", "cultiveau_vue3d", "stock", "l10n_fr_account"],
    "data": ["views/menus.xml"],
    "assets": {"web.assets_backend": ["cultiveau_comptoir/static/src/js/comptoir.js", "cultiveau_comptoir/static/src/xml/comptoir.xml", "cultiveau_comptoir/static/src/scss/comptoir.scss"]},
    "installable": True,
}
