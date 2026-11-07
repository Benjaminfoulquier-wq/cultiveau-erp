# Le chantier en un clic

Module `cultiveau_chantier_flux` (07/11/2026). Règle de Benjamin : simple, jamais deux fois, un clic.

- **Démarrer la phase** (bouton sur la phase) : le chantier démarre s'il ne l'était pas, et le matériel de la phase sort du
  stock **sur la livraison créée par la commande** : les lignes de la phase sont validées, le reste part en reliquat pour les
  phases suivantes. Un article ajouté au chantier mais absent de la commande sort par un bon propre. Sans commande, un bon de
  sortie propre, comme avant. Avant ce module, « Sortir le matériel » créait un second bon à côté de la livraison : le stock
  sortait deux fois ; « Sortir le matériel » passe désormais par le même chemin.
- **Terminer la phase** : le posé se remplit (égal au prévu si rien n'a été saisi), la facture du jalon se prépare si la phase en
  porte un, le fil annonce la phase suivante.
- **Mise en service** (PV rempli, anti-retour coché, pressions de référence) : en plus de l'installation en service et du registre,
  la facture de solde se prépare, l'intervention de mise en service créée à la confirmation se clôt, le matériel non posé repart
  au dépôt (retour préparé), les phases restantes se ferment, et le commercial reçoit « Proposer le contrat d'entretien » dans un mois.
