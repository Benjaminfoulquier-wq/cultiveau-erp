# L'équipe : congés, absences et notes de frais

Le module `cultiveau_rh` s'appuie sur les congés et les notes de frais standards de l'ERP Cultiveau, réglés pour une petite
entreprise : une seule validation, par le gérant, en un clic.

## La mise en place (automatique)

À l'installation, puis chaque nuit :

- chaque personne de l'équipe reçoit sa **fiche salarié** dans sa société (y compris les nouvelles personnes, dès leur création) ;
- le **gérant** (le rôle « gérant » de la map) devient le valideur des congés et des notes de frais de toute l'équipe ;
- les **jours fériés français** (onze jours, Pâques, Ascension et Pentecôte calculés) sont posés pour l'année en cours et la
  suivante : ils ne sont jamais décomptés d'un congé ;
- les **congés payés** de la période (du 1er juin au 31 mai) sont attribués : 25 jours par défaut (Réglages → Cultiveau → Équipe).
  Les soldes de départ se corrigent dans Congés → Attributions ; le report des jours non pris est conservé.

Types de congés : congés payés, RTT et récupération (jours attribués par le gérant), congé sans solde, événement familial,
arrêt maladie. Un arrêt maladie n'est jamais nommé devant les collègues : ils lisent « Absent ».

## Sur le téléphone : `/moi`

Une page à ouvrir dans le navigateur du téléphone (et à ajouter à l'écran d'accueil), sans application à installer :

- **badger** : arrivée, pause, reprise, départ en intervention, retour, départ (la map bouge) ;
- **demander un congé** : type, dates, demi-journée, motif ; les soldes restants sont affichés ;
- **photographier un ticket** : l'IA lit la date, le fournisseur, le montant TTC, la TVA et la catégorie ; sans ticket, un
  montant ou des kilomètres (indemnités kilométriques au taux réglé) ; puis **Envoyer au gérant** ;
- pour le gérant, **À valider** : chaque demande avec ✓ / ✗.

## La lecture des tickets

La photo (ou le PDF) passe par l'OCR de Mistral, puis par une lecture structurée — la même clé que les fiches techniques
(Réglages → Cultiveau → Fiches techniques et IA). La catégorie donne le compte de charge et la TVA habituelle :

| Catégorie | Compte | TVA |
|---|---|---|
| Repas | 625600 | 10 % |
| Carburant | 606100 | 20 % |
| Péage et parking | 625100 | 20 % |
| Hôtel | 625100 | non récupérable |
| Petites fournitures et outillage | 606300 | 20 % |
| Indemnités kilométriques | 625100 | — |
| Autre dépense | 625100 | 20 % |

Le taux lu sur le ticket l'emporte ; un ticket à plusieurs taux garde le détail dans la note. Une lecture incertaine est
signalée sur la dépense. Les tickets déposés depuis l'ERP (liste des dépenses, bouton « Lire le ticket ») sont lus aussi ;
ceux qui restent sont lus toutes les quinze minutes. Une dépense qui ressemble à une dépense déjà validée bloque la validation.

En option, la note validée passe directement en comptabilité (à rembourser au salarié).

## Sur la map

- Les personnes en congé quittent la map : leur statut devient « En congés · retour lundi 19 octobre ».
- La fiche d'une personne porte ses congés à venir, ses soldes (pour elle et le gérant) et ses notes de frais ; « Demander un
  congé » et « Mon espace sur le téléphone » pour soi.
- La zone administrative porte **À valider** (congés et notes de frais, ✓ / ✗) et les absents des sept prochains jours ; ses portes
  ouvrent les congés à valider, les notes de frais et le planning des congés.
- Le fil d'activité annonce les demandes, les validations et les notes envoyées.

## Réunions et Mathis

Les créneaux de réunion proposés évitent les congés (validés ou demandés) des participants.

Mathis répond (« qui est absent la semaine prochaine ? », « combien me reste-t-il de congés ? », « mes notes de frais ») et agit
après confirmation : demander un congé, créer une dépense (montant ou kilomètres), envoyer ses dépenses, et pour le gérant
valider ou refuser.
