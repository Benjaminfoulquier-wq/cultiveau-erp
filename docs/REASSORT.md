# Le stock qui se recommande tout seul

Module `cultiveau_reassort` (07/11/2026). Menu Cultiveau › Réassort du stock.

- **La page** : pour chaque article stocké et achetable de la société (ceux qui bougent, ou tout le stock en décochant), la
  consommation des douze derniers mois (sorties vers les clients et la production), par mois, le stock, ce qui arrive, ce qui est
  réservé, la couverture en mois, le **mini proposé** (1,5 mois) et le **maxi proposé** (3 mois), le fournisseur, son prix, son délai,
  et « à commander » quand le disponible (stock + arrive − réservé) est sous le minimum de la règle (la règle existante si elle est
  posée, sinon la proposition).
- **Poser les règles de réassort** : crée ou met à jour les règles d'Odoo (minimum, maximum, déclenchement automatique) pour les lignes
  cochées. Ensuite plus rien à faire : le planificateur d'Odoo (chaque nuit) prépare les demandes de prix dès qu'un article passe sous
  son minimum, chez le fournisseur de la fiche.
- **Commander les manquants** : tout de suite, une demande de prix par fournisseur pour ce qui est sous le minimum ; les articles sans
  fournisseur sont laissés de côté et signalés.

Ajuster les coefficients : `MOIS_MIN` et `MOIS_MAX` dans `models/reassort.py`.
