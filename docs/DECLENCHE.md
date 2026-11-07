# Le devis déclenche tout

Module `cultiveau_declenche` (07/11/2026). Idée prise chez les chauffagistes et les solaristes qui tournent bien sur Odoo : la
confirmation du devis ne réserve pas seulement du stock, elle met toute la chaîne en marche. Réglages › Cultiveau › « Le devis
déclenche tout » : quatre cases par adhérent, toutes cochées au départ. Tout se crée en brouillon, rien ne part sans lui.

## À la confirmation (signée en ligne ou au bureau)

Pour un devis d'installation (relié à une installation ou avec un type d'installation ; jamais une vente au comptoir) :

1. **Le chantier** de pose, avec ses quatre phases type et le matériel prévu d'après les lignes ; la date de début prend la date
   d'engagement du devis si elle est saisie.
2. **L'intervention de mise en service** (nature « Mise en service (A1.3) ») dans le projet Interventions, à planifier, reliée à
   l'installation : rinçage, essais de pression, pressions et débits de référence, fiche de réglage A1.5, formation.
3. **La facture d'acompte** au pourcentage du devis (Réglages › Devis et factures), en brouillon.
4. **Les demandes de prix** aux fournisseurs pour ce qui manque : une par fournisseur (celui de la fiche article, au prix et au
   délai de la fiche), en brouillon, reliées au devis (`cultiveau_sale_order_id`). Les articles sans fournisseur connu sont
   nommés dans le fil.

Le fil du devis raconte ce qui a été créé, avec les liens ; « Relancer les déclenchements » (commande confirmée avant le
module, ou réglage corrigé) crée ce qui manque sans rien dupliquer. Un déclenchement qui échoue (compte d'acompte non
configuré, par exemple) n'empêche jamais la confirmation : il est noté dans le fil.

## L'approvisionnement du devis (la liste de courses)

Bouton « Approvisionnement » sur tout devis : article stockable par article stockable, la quantité au devis, le disponible
(stock moins ce que d'autres commandes attendent déjà), ce qui arrive (déjà commandé, pas reçu), le manque, le fournisseur,
sa référence, son prix, son délai, le montant. On ajuste les quantités, on choisit un fournisseur pour les articles qui n'en ont
pas, « Commander tout le devis » pour un chantier livré directement du fournisseur, puis « Créer les demandes de prix ». Le
bouton statistique « Achats » du devis ouvre les commandes fournisseurs qui en découlent.

## L'onglet « Après la signature »

Sur la commande confirmée : chantier (état, avancement), sorties de stock (les livraisons créées par Odoo), acompte (facturé,
payé), achats (demandes de prix et ce qui reste non couvert), mise en service (étape). Chaque ligne a sa coche ou « à faire »,
et la date des déclenchements.

## Ce qui n'est pas fait

- Les commandes passées à la logistique Cultiveau plutôt qu'au fournisseur : les demandes de prix restent des achats Odoo.
- La facturation à l'avancement par phase de chantier (jalons) : la facture d'acompte puis le solde, comme avant.
