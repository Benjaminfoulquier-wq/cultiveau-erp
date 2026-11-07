# Acompte payé en ligne à la signature

Module `cultiveau_acompte_ligne` (07/11/2026). Odoo sait déjà demander une signature puis un paiement au portail du devis ;
ce module le branche sur l'acompte Cultiveau.

- **Réglages › Cultiveau › Devis et factures › Acompte payé en ligne** : une case (cochée au départ). Le pourcentage d'acompte
  Cultiveau devient le paiement demandé au portail (`portal_confirmation_pay`, `prepayment_percent`) ; chaque devis suit son
  propre pourcentage. Décoché, le portail ne demande plus que la signature.
- **Virement bancaire** : activé pour chaque société qui a un compte bancaire (à l'installation et par le bouton « Activer le
  virement bancaire ») : le client voit le RIB et un QR code de virement ; la commande attend la réception. **Stripe, Mollie,
  PayPal…** : bouton « Fournisseurs de paiement », l'adhérent saisit ses clés dans le formulaire du fournisseur (jamais ailleurs).
- Sur le devis, sous l'acompte : « Acompte de 30 % demandé à la signature en ligne (Virement bancaire) ».
- Une fois l'acompte payé (carte) ou le virement reçu, Odoo confirme la commande, et « Le devis déclenche tout » crée le chantier,
  la facture d'acompte (qui reprend le paiement), les demandes de prix et la mise en service.

Non fait : un fournisseur de paiement par carte préconfiguré pour le réseau (les clés sont celles de chaque adhérent).
