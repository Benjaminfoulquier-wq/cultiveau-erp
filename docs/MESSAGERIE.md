# La messagerie : Gmail et Outlook rangés par client

Le module `cultiveau_messagerie` branche la boîte mail de l'entreprise (contact@, devis@…) ou celle de chacun sur l'ERP.
Chaque courriel arrive rangé sur son client et son dossier, trié, résumé, et suivi jusqu'à la réponse.

## Brancher une boîte (Courriels → Boîtes mail)

| Messagerie | Branchement |
|---|---|
| Gmail / Google Workspace | « Connecter » → page d'autorisation Google (une fois, par l'administrateur de l'ERP) |
| Outlook / Microsoft 365 | « Connecter » → page d'autorisation Microsoft |
| Toute autre (OVH, Orange, Free…) | serveurs IMAP et SMTP, identifiant et mot de passe ; « Connecter » essaie la connexion |

Pour Gmail et Outlook, il faut une fois pour toutes l'identifiant de l'application (Réglages → Cultiveau → Messagerie) ;
à défaut, celui déjà saisi pour les agendas est repris :

- **Google Cloud** : le même projet que l'agenda ; activer l'API Gmail ; ajouter l'adresse de retour `…/google_gmail/confirm`.
- **Microsoft Entra** : la même application que l'agenda ; autorisations `IMAP.AccessAsUser.All` et `SMTP.Send` ; adresse de
  retour `…/microsoft_outlook/confirm`.

Une boîte **partagée** est vue par toute l'équipe ; une boîte **personnelle**, par son responsable et le gérant seulement.

## La relève ne touche pas la boîte

Toutes les cinq minutes, l'ERP lit la boîte de réception **en lecture seule** : rien n'est marqué comme lu, déplacé ou
supprimé. On continue d'utiliser Gmail ou Outlook comme avant, sur l'ordinateur comme sur le téléphone. La première relève
reprend les courriels des quatorze derniers jours.

Le dossier « Envoyés » est lu aussi : une réponse faite directement depuis Gmail ou Outlook marque le courriel « répondu ».

## Le rangement

1. **Le client** : l'adresse de l'expéditeur, sinon le domaine de son entreprise (`compta@earl-dupont.fr` → l'EARL Dupont),
   jamais un domaine de messagerie grand public (gmail.com, orange.fr…).
2. **Le dossier** : la référence citée (S00042, FAC/2026/0012…), sinon le dossier ouvert du client qui correspond au sujet :
   la facture impayée pour un règlement, le devis pour une demande, l'intervention en cours pour une panne.
3. **Le tri** (avec la clé Mistral) : catégorie (devis, panne, facture, commande, fournisseur, administratif, publicité),
   urgence, résumé d'une phrase, et s'il attend une réponse. Sans clé, des mots-clés font le tri.
4. Une **note** signale le courriel sur la fiche du dossier (ou du client) ; la **map** l'annonce.

Un courriel qui répond à un envoi de l'ERP (un devis, une facture envoyés depuis l'ERP) retrouve tout seul son document.
Les lettres d'information et les notifications automatiques sont classées d'office.

## Répondre

- **Préparer la réponse avec Mathis** : Mathis rédige la réponse avec le contexte (client, dossier, échanges) ; elle s'ouvre
  pour être relue, corrigée puis envoyée. Il n'invente ni prix, ni date, ni délai.
- **Répondre** : la réponse part **de la boîte qui a reçu le courriel**, et la réponse du client y revient (le courriel
  repasse « à traiter »).
- **Classer** : rien à répondre.

## Sans réponse

Au-delà de trois jours ouvrés (réglable), le courriel est signalé **sans réponse** : une activité pour son responsable (le
commercial du client, sinon le responsable de la boîte), un repère rouge sur la map, une ligne dans le fil d'activité.

## Sur la map et avec Mathis

- L'accueil, le bureau d'étude et l'administratif portent **Courriels à traiter** : les plus en retard d'abord, avec
  « Préparer la réponse » et « Classer » ; la fiche d'un client porte ses derniers courriels, celle d'une personne ses
  courriels à traiter.
- Mathis : « quels courriels attendent une réponse ? », « que dit le dernier courriel de l'EARL Dupont ? », « prépare la
  réponse en disant qu'on passe jeudi », « classe-le ».
