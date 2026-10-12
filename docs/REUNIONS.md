# Réunions, agendas et visio

Module `cultiveau_reunion`. La salle de réunion de la map est branchée sur les agendas : on y voit qui est en réunion, on y planifie
les réunions avec les créneaux où tout le monde est libre, et on rejoint la visio d'un clic.

## Sur la map

- **La salle de réunion** du dépôt (table de huit, écran mural) porte une étiquette en direct : « libre » avec la prochaine réunion,
  ou « occupée » avec la réunion en cours et son heure de fin. L'écran passe en visio quand une réunion s'y tient.
- **Les personnes suivent leur agenda** : une réunion dans la salle, elles vont s'y asseoir ; une visio, elles restent à leur poste
  (écran en visio, statut « En visio ») ; un rendez-vous dehors, elles quittent la map (statut « En rendez-vous »). Les interventions,
  chantiers et pauses passent avant.
- **La fiche de la salle** : la réunion en cours (participants, « Rejoindre la visio »), celles du jour, mes réunions, l'état de mes
  agendas Google et Outlook, et les boutons Planifier une réunion, Mon agenda, Connecter mon agenda Google / Outlook.
- **« Proposer une réunion »** depuis la fiche d'une personne, d'un client ou d'une installation ouvre le planificateur déjà rempli.

## Planifier une réunion

Objet, participants de l'équipe, un client éventuel, durée, lieu (la salle, en visio, chez le client), visio. « Proposer des
créneaux » cherche les premiers créneaux libres pour l'organisateur et chaque participant, sur deux semaines, du lundi au
vendredi dans les heures des réglages, deux au plus par jour : il tient compte de leurs agendas (y compris Google et Outlook une fois
connectés), des interventions planifiées et de la salle. Un clic sur le créneau, « Planifier et inviter » : l'événement est créé
dans l'agenda, les participants (et le client) reçoivent l'invitation, la map se met à jour.

## La visio

- **Visio intégrée** (par défaut) : la visio de l'ERP, sans compte à créer, ouverte aussi aux clients par le lien de l'invitation.
- **Google Meet** : quand l'organisateur a connecté son agenda Google, la réunion part chez Google qui crée le lien Meet et le renvoie
  dans l'agenda et l'invitation.
- **Teams** : même chose avec un agenda Outlook connecté (Microsoft crée le lien Teams).
- **Mon lien** : n'importe quelle adresse (Zoom, Whereby…).
- Sans agenda connecté, Meet ou Teams basculent sur la visio intégrée, et le planificateur le dit.

## Connecter les agendas

Une fois pour toutes, l'administrateur (Réglages → Cultiveau → **Réunions et agendas**) :
- **Google** : dans la console Google Cloud, activer l'API Google Calendar, créer un identifiant OAuth « Application Web » avec
  l'adresse de retour affichée dans les réglages (`…/google_account/authentication`), puis coller l'identifiant et le secret.
- **Outlook** : dans le portail Microsoft Entra, inscrire une application (Calendars.ReadWrite, OnlineMeetings.ReadWrite) avec
  l'adresse de retour affichée (`…/microsoft_account/authentication`), puis coller l'identifiant et le secret.

Ensuite chacun clique « Connecter mon agenda Google » (ou Outlook) dans la fiche de la salle : la page de connexion de Google ou
Microsoft s'ouvre, on accepte, et les réunions vont et viennent dans les deux sens.

## Avec Mathis

« Trouve un créneau d'une heure avec Sophie et Marc cette semaine », « planifie un point chantier demain matin en visio avec le client
Durand », « mes réunions du jour » : Mathis cherche les créneaux, propose la réunion, et la crée après votre confirmation.

## Réglages

Nom de la salle, heures des réunions (`8:30-12:00,13:30-18:00` par défaut), visio par défaut.

## Connecter Google et Outlook d'un clic, pour tout le réseau

Pour que chacun connecte son agenda (et sa messagerie) en cliquant sur « Connecter mon agenda Google » ou « Connecter mon
agenda Outlook », sans aucun réglage chez l'adhérent, le réseau Cultiveau inscrit **une fois** une application chez Google et
une chez Microsoft, et en donne les identifiants au serveur.

### 1. L'application Google (Google Cloud Console)

1. https://console.cloud.google.com → créer un projet « Cultiveau ERP ».
2. API et services → Bibliothèque : activer **Google Calendar API** (et **Gmail API** pour la messagerie).
3. Écran de consentement OAuth : type **Externe**, nom « Cultiveau ERP », logo, domaine `cultiveau.fr`, adresse de contact ;
   portées : `…/auth/calendar` (et `https://mail.google.com/` pour la messagerie).
4. Identifiants → Créer → **ID client OAuth**, type **Application Web**, URI de redirection autorisés :
   - `https://erp.cultiveau.fr/google_account/authentication` (agenda)
   - `https://erp.cultiveau.fr/google_gmail/confirm` (messagerie)
5. Noter l'**ID client** et le **code secret**.
6. Publier l'application (« En production ») et demander la **validation Google** : sans elle, Google affiche « application
   non validée » et limite à 100 comptes. La portée agenda est « sensible » (validation en quelques jours à quelques semaines) ;
   la portée Gmail complète est « restreinte » et demande en plus un audit de sécurité payant : tant qu'il n'est pas fait, les
   boîtes Gmail se branchent en IMAP avec un mot de passe d'application.

### 2. L'application Microsoft (portail Entra)

1. https://entra.microsoft.com → Applications → Inscriptions d'applications → Nouvelle inscription « Cultiveau ERP ».
2. Types de comptes : **comptes de tout annuaire organisationnel et comptes Microsoft personnels**.
3. URI de redirection (Web) :
   - `https://erp.cultiveau.fr/microsoft_account/authentication` (agenda)
   - `https://erp.cultiveau.fr/microsoft_outlook/confirm` (messagerie)
4. Autorisations d'API (déléguées) : `offline_access`, `openid`, `Calendars.ReadWrite`, `OnlineMeetings.ReadWrite`, et pour la
   messagerie `IMAP.AccessAsUser.All`, `SMTP.Send` (Office 365 Exchange Online).
5. Certificats et secrets → Nouveau secret client (24 mois). Noter l'**ID d'application (client)** et la **valeur** du secret.
6. Recommandé : la vérification de l'éditeur (Microsoft Partner Network), pour que l'écran d'accord affiche « éditeur vérifié ».
   Certaines entreprises imposent l'accord de leur administrateur Microsoft 365 avant le premier branchement.

### 3. Les donner au serveur (une fois)

Dans le dépôt GitHub de l'ERP : Settings → Secrets and variables → Actions → New repository secret :

| Secret | Valeur |
|---|---|
| `CULTIVEAU_GOOGLE_CLIENT_ID` | l'ID client Google |
| `CULTIVEAU_GOOGLE_CLIENT_SECRET` | le code secret Google |
| `CULTIVEAU_MICROSOFT_CLIENT_ID` | l'ID d'application Microsoft |
| `CULTIVEAU_MICROSOFT_CLIENT_SECRET` | la valeur du secret Microsoft |

Puis Actions → « Déployer l'ERP » → Run workflow (ou le prochain push). Les identifiants vont dans `/srv/erp/.env` du serveur
(jamais dans le dépôt ni dans le journal), l'ERP les reprend au démarrage et à chaque mise à jour, pour l'agenda **et** pour la
messagerie (Gmail, Outlook). Ils l'emportent sur une saisie locale dans les réglages.

Ensuite, pour chacun : la salle de réunion de la map → « Connecter mon agenda Google » (ou Outlook) → l'écran d'accord de
Google ou Microsoft → retour dans l'ERP, agenda synchronisé dans les deux sens.
