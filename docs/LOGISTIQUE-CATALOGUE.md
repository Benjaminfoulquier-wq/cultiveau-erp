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
