{
    "name": "Cultiveau — Acompte payé en ligne à la signature",
    "summary": "Le client signe le devis en ligne et règle l'acompte dans la foulée (virement avec QR code, ou carte via Stripe ou Mollie) ; le pourcentage est celui du devis ; la commande se confirme et déclenche tout",
    "description": """
Acompte payé en ligne à la signature
====================================

Le flux des entreprises de services qui tournent sur Odoo : rendez-vous ou devis, paiement, et la suite démarre toute seule.
Ici, le portail du devis demande déjà la signature ; ce module y ajoute le paiement de l'acompte :

- le **pourcentage d'acompte** du devis (celui de Réglages › Devis et factures, modifiable devis par devis) devient le
  paiement demandé au portail ;
- le fournisseur **Virement bancaire** est activé pour chaque société qui a un compte bancaire : le client voit le RIB et un
  QR code de virement ; Stripe ou Mollie s'activent dans Fournisseurs de paiement avec les clés de l'adhérent ;
- une fois l'acompte reçu, la commande est confirmée et « Le devis déclenche tout » fait le reste.
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "website": "https://cultiveau.fr",
    "license": "LGPL-3",
    "depends": ["cultiveau_documents", "payment_custom", "sale_management"],
    "data": ["views/views.xml"],
    "post_init_hook": "activer_virement",
    "installable": True,
    "auto_install": False,
}
