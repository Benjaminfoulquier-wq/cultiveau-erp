# Conformité : journal d'audit, RGPD, démonstration

Le module `cultiveau_conformite`.

## Le journal d'audit

Chaque création, modification et suppression des documents du métier est notée : clients et contacts, devis et commandes,
factures et paiements, articles, achats, installations, chantiers, interventions, congés, notes de frais. Pour une
modification : la personne, l'heure, et pour chaque champ la valeur avant et après (seuls les champs qui changent vraiment).

- Réglages → Journal d'audit (gérant), avec filtres par personne, type de document, jour.
- Sur chaque document, menu Action → « Historique des modifications ».
- Rien n'est noté pendant l'installation des modules ; les mots de passe, images et la mécanique interne ne sont pas suivis.
- Conservation : trois ans (réglable), purge mensuelle.

## Le RGPD

Sur la fiche d'un client, menu Action (gérant) :

- **RGPD : exporter ses données** : un fichier JSON lisible avec la fiche et ses contacts, devis, factures, installations,
  interventions, chantiers, rendez-vous, courriels et échanges (droit d'accès, article 15).
- **RGPD : effacer ses données** (taper EFFACER pour confirmer) :
  - sans pièce comptable : la fiche et ses contacts sont anonymisés, leurs échanges, courriels et appels supprimés ;
  - avec des factures, que la loi impose de garder dix ans : on limite ; courriel, téléphones, notes, échanges, courriels
    et appels sont supprimés, le nom et l'adresse de facturation restent, la fiche est archivée.
  - Refusé tant qu'une commande est à facturer ou une facture impayée.

Chaque export et chaque effacement est noté au journal d'audit.

## La démonstration

Réglages → Map vivante → « Remettre la démonstration à zéro » : les pointages et événements joués par le mode démonstration
sont effacés (la map retrouve l'état réel de l'équipe).
