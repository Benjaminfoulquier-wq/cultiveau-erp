# Le catalogue de la logistique dans l'ERP

Module `cultiveau_logistique_catalogue` (07/11/2026). Demande de Benjamin : « à chaque fois qu'un produit est mis en ligne sur
logistique.cultiveau.fr, il doit l'être aussi sur erp.cultiveau.fr avec les fiches techniques ».

- **Côté logistique** (`server/erpExport.ts`) : `GET /api/erp/produits?depuis=<ISO>&page=&taille=` avec l'en-tête `X-Erp-Secret`
  (variable `ERP_SYNC_SECRET` du conteneur). Renvoie les produits modifiés depuis la date, actifs et retirés, avec famille,
  sous-famille, fournisseur, prix net, prix brut, prix plateforme, stock plateforme, photo et fiches techniques en adresses absolues.
- **Côté ERP** : toutes les heures (cron), et « Tout synchroniser maintenant » dans Réglages › Cultiveau › Le catalogue de la logistique.
  Chaque produit devient un article du **catalogue du réseau** (société vide, source « Logistique Cultiveau ») : nom, référence, famille
  et sous-famille, description + « Le mot du fabricant », conditionnement, poids, prix de vente (prix brut, sinon prix net + 30 %),
  coût (prix net), deux lignes fournisseur (le fabricant avec sa référence ; « Cultiveau Logistique » avec le prix net, c'est le canal
  d'achat), la photo (rapatriée une fois par adresse), les fiches techniques dans la bibliothèque des fiches (identifiant
  `logistique:<id>`, lien vers le PDF de la logistique) reliées à l'article. Un produit retiré de la logistique est archivé. Chaque page
  de 500 est acquise avant la suivante ; la date de reprise est gardée (`cultiveau.logistique_depuis`).
- **Secret** : `cultiveau.logistique_secret` dans l'ERP, `ERP_SYNC_SECRET` dans `/srv/logistique/.env` et le `docker-compose.yml`
  de la logistique ; posé par l'équipe Cultiveau sur le serveur, jamais affiché.

Non fait : les fichiers des fiches ne sont pas copiés dans l'ERP (lien vers la logistique) ; les caractéristiques techniques
(DN, PN…) de la logistique ne sont pas encore reprises dans les cotes de l'article.

## La logistique est la base (07/11/2026, soir)

« On ne doit pas avoir besoin de copier » : le catalogue n'est plus copié en masse dans l'ERP. Quand on tape une référence ou un nom
(quatre caractères au moins) dans une ligne de devis, de commande d'achat ou d'inventaire et que l'ERP ne trouve rien, il interroge
`GET /api/erp/recherche?q=…` sur la logistique, les articles trouvés entrent dans le catalogue (prix d'achat en fournisseur
« Cultiveau Logistique », prix de vente, fiches, photo) et la recherche reprend : l'article apparaît comme s'il avait toujours
été là. Le robot horaire ne crée plus rien : il rafraîchit les articles déjà utilisés (prix, fiches, retraits). La copie complète
reste possible par le réglage « Copier tout le catalogue dans l'ERP » ou le bouton « Tout synchroniser maintenant ».

## Prix public : jamais moins de trois fois le prix d'achat (08/11/2026)

« Mets un minimum de ×3 sur les prix du catalogue Cultiveau pour le prix public. » `_prix_public(prix_achat, prix_brut)` = max(prix brut du
fabricant, 3 × prix d'achat), arrondi au centime (`COEF_PUBLIC_MINI`). Appliqué à chaque article lu sur la logistique (synchronisation,
recherche à la volée depuis un devis) et rejoué sur les articles déjà dans l'ERP à chaque mise à jour (`cultiveau_prix_public_minimum`,
`data/prix_public.xml`). Les articles des adhérents (leur base cultiveau.fr) ne sont pas concernés : leurs prix sont les leurs.
