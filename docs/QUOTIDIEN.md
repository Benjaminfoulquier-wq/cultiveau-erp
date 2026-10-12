# Au quotidien : Aujourd'hui, rapport du lundi, budget d'heures, automatisations

Le module `cultiveau_quotidien` rassemble ce qui fait gagner du temps chaque jour.

## L'écran « Aujourd'hui »

Le premier menu de l'ERP (et la première porte de l'accueil et de l'administratif sur la map). Une tuile par chose à
traiter, de la plus pressante à la moins pressante, avec ses premières lignes (un clic ouvre le document) et « Tout voir » :

| Tuile | Ce qu'elle montre |
|---|---|
| Courriels sans réponse | au-delà du délai de réponse (trois jours ouvrés) ; les siens, ou tous pour le gérant |
| Factures échues | le reste dû et le retard, pour le gérant et la comptabilité |
| Devis à relancer | envoyés sans nouvelle depuis sept jours (réglable) |
| Interventions en retard | échéance passée, pas terminées |
| Chantiers en dépassement | au-delà de 80 % des heures prévues (rouge au-delà de 100 %) |
| Congés et notes de frais à valider | pour le gérant |
| Stock sous le minimum | d'après les règles de réassort |
| Bons signés à facturer | pour le gérant et la comptabilité |
| Rendez-vous du jour | l'agenda de la personne |

Chacun ne voit que ce qu'il peut ouvrir. « Par quoi je commence ? » pose la question à Mathis, qui lit les mêmes tuiles.

## Le rapport du lundi

Chaque lundi à 7 h, chaque gérant reçoit par courriel la semaine écoulée : facturé, encaissé, devis envoyés et signés,
interventions faites, heures de chantier, nouveaux clients, courriels reçus et délai moyen de réponse ; puis les tuiles
d'« Aujourd'hui » et les absents de la semaine. Réglages → Cultiveau → Pilotage au quotidien (« Me l'envoyer maintenant »).

## Le budget d'heures des chantiers

Le budget, ce sont les heures de pose du devis (matrice de pose) ; à défaut, la somme des heures prévues des phases. À chaque
pointage, le chantier compare :

- **50 %** : une note sur le chantier et un signal sur la map ;
- **80 %** : en plus, une activité pour le chef de chantier, un bandeau orange sur le chantier ;
- **100 %** : en plus, une activité pour le gérant, un bandeau rouge.

La fiche du chantier sur la map porte la jauge du chantier et celle de chaque poseur (ses heures, sa part du budget, ses heures
de la semaine) ; la fiche d'une personne, ses chantiers de la semaine. « Heures par poseur » ouvre le détail.

## Les automatisations « si… alors… »

Réglages → Automatisations. Dix règles du métier, inactives au départ, à activer d'un clic. Chacune a son délai, son
responsable par défaut et, quand c'est possible, l'envoi au client. Elles passent toutes les heures et n'agissent qu'une fois
par document (la trace est gardée, « Lancer » les passe tout de suite) :

| Si… | alors… |
|---|---|
| un devis envoyé reste sans réponse 7 jours | activité « Relancer » pour le commercial, ou relance envoyée au client |
| une commande d'installation est confirmée | le chantier est créé (matériel d'après la commande) et à planifier |
| un article passe sous son minimum | la commande fournisseur est préparée en brouillon |
| une facture est échue depuis 7 jours | relance envoyée au client, ou activité pour la comptabilité |
| un bon signé n'est pas facturé après 3 jours | rappel à la facturation |
| une intervention est terminée sans bon signé | rappel au technicien |
| une installation fête bientôt sa mise en service, sans contrat | le commercial propose l'entretien |
| un client n'a rien commandé depuis un an | son commercial reprend contact |
| un courriel attend depuis 5 jours ouvrés | le gérant est prévenu |
| une facture est réglée | un mot de remerciement part au client |
