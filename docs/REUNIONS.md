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
