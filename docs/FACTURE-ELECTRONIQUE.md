# Facture électronique et sauvegardes

## Ce que la réforme demande

- Depuis le 1er septembre 2026 : toute entreprise doit pouvoir **recevoir** ses factures par une plateforme agréée.
- Depuis le 1er septembre 2026 pour les grandes entreprises et les ETI, à partir du **1er septembre 2027** pour les PME, TPE et
  micro-entreprises (les adhérents) : **émettre** par une plateforme agréée, et transmettre le **e-reporting** (ventes aux
  particuliers, encaissements).

## Dans l'ERP

Réglages → Cultiveau → **Facture électronique**, société par société :

1. Renseigner le **SIRET** (il identifie la société sur l'annuaire national).
2. **Exiger la double authentification** (la plateforme l'impose à celui qui inscrit la société). Il faut que l'envoi d'e-mails
   soit configuré : le code de connexion arrive par e-mail.
3. **Inscrire la société** : l'assistant propose le mode *démonstration* (rien ne part, pour s'entraîner), *test* ou *réel*.
   L'inscription en réel est validée par l'annuaire sous un jour ; une migration depuis une autre plateforme peut prendre deux
   semaines.
4. Cocher **E-reporting** et sa date de début quand l'obligation s'applique (2027 pour les adhérents).

Ensuite : les factures fournisseurs arrivent dans Achats ; les factures clients partent par le bouton « Envoyer » habituel
(la plateforme est choisie d'elle-même pour un client inscrit sur l'annuaire) ; chaque facture porte son statut de cycle de vie
(déposée, rejetée, acceptée, encaissée).

## Sauvegardes

Chaque nuit à 1 h 45, `deploy/sauvegarde.sh` sur le serveur :

- exporte la base (`pg_dump`) et vérifie que l'export se relit, puis archive les fichiers (filestore) ;
- garde 30 jours sur le serveur, et les sauvegardes du dimanche 90 jours ;
- si le secret GitHub `CULTIVEAU_RCLONE_CONF` contient une configuration rclone nommée `sauvegardes` (un espace de stockage chez
  un autre hébergeur : Storage Box, Object Storage, Backblaze…), la sauvegarde du jour y est copiée et les copies de plus de
  90 jours effacées.

Pour poser l'espace hors serveur : créer le stockage chez l'hébergeur, écrire le fichier rclone correspondant (section
`[sauvegardes]`), le coller dans le secret, puis relancer un déploiement.
