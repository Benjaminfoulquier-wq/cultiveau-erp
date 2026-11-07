# La Map vivante

Module `cultiveau_vue3d`. La page d'accueil de l'ERP est le site de l'adhérent en 3D, vivant : l'équipe, les camions, les
clients au parking, les chantiers et les parcelles bougent avec les données. Tout objet visible est cliquable et ouvre une fiche,
avec un bouton vers l'écran du back-office. La map n'est pas une maquette : c'est une vue sur les mêmes tables que le reste de
l'ERP, et un changement dans l'un se voit dans l'autre en moins d'une seconde.

## Ce qu'on voit

- **Le dépôt**, bâtiment en L vu en coupe (les murs côté caméra sont bas) : accueil et comptoir, magasin, stockage par famille,
  atelier et SAV, bureau d'étude, salle de réunion, administratif, salle de pause. Dehors : parking clients, cour poids lourds,
  dépôt extérieur, route avec circulation, et de l'autre côté les champs des agriculteurs.
- **L'équipe** : une personne par utilisateur de la société, à son poste selon son rôle (comptoir, bureau d'étude, administratif,
  atelier), en réunion, en pause (café, baby-foot), sur un chantier ou en intervention. Le statut vient des pointages du jour,
  sinon des interventions et chantiers en cours, sinon de la connexion à l'ERP.
- **Les camions** : un par technicien, avec son stock à bord (module Terrain) ; il sort de la cour quand le technicien part et
  rentre à son retour.
- **Les clients au parking** (07/11/2026) : chaque type a son véhicule, pick-up de l'agriculteur, benne à gyrophare et bande
  tricolore de la collectivité, plateau chargé de végétaux du paysagiste, fourgon à tuyaux du plombier, fourgon à échelle du
  pisciniste, benne orange des travaux publics, utilitaire gris de l'industrie, voiture du particulier. D'abord ceux « sur place »
  (devis, vente ou commande du jour, avec la personne à l'accueil), puis, sur les places qui restent, les derniers clients
  touchés, un par type. Un clic ouvre le client : type, persona (animal, surnom, comment lui parler), CA, impayés, devis,
  installations, et les boutons « Voir les paysagistes » (le premier filtre : tous les clients du même type), « Persona » (sa
  fiche, pour l'évaluer ou lire l'Agent), « Fiche complète », « Nouveau devis », « Appeler ».
- **Les champs** : les chantiers en cours (pelle, tubes, tranchée, équipe), les installations en réalisation, les parcelles en
  service avec leur matériel (pivot qui tourne, enrouleur et canon, goutte à goutte, aspersion) et leur arrosage en saison ; une
  épingle rouge quand l'état d'eau est en déficit (module Parcelles).
- **Le stock** : six rayonnages, un par famille, remplis selon le stock réel ; une épingle orange quand une règle de réassort est
  en négatif.
- **L'atelier** : une pompe sur un établi par intervention d'atelier ; des étincelles quand un technicien y est.
- **Les livraisons** : un camion fournisseur dans la cour pour une réception du jour.

## Le décor (07/11/2026)

`static/src/js/decor.js`, posé une fois à la construction, sans données : le ciel et ses nuages qui dérivent, l'horizon
(collines, bois, village et clocher, éoliennes qui tournent, château d'eau), la route avec son trottoir, ses lignes de rive, son
passage piéton, son accotement et son fossé, les portails coulissants ouverts, l'auvent de l'entrée au nom de la société, le tapis
« Bienvenue », les massifs fleuris, les mâts et leurs drapeaux qui flottent, le range-vélos, les poubelles de tri, les flèches et la
place PMR du parking, le fardeau de tubes PVC, les piles de palettes, les cônes, les traces de pneus et les taches des camions, le
transpalette et les caisses devant la porte de la cour. Dedans : les suspensions du hall et les dalles LED des bureaux (elles
s'allument davantage le soir), les poteaux de charpente, les extincteurs, le tableau blanc du bureau d'étude, le planning à post-it
de l'atelier, l'horloge de l'accueil à l'heure, le marquage piétons du stockage ; les murs ont un couronnement à la couleur, un
soubassement et des fenêtres côté bureaux et accueil. Chez les agriculteurs : le chemin, une borne d'irrigation par parcelle, des
haies, le bassin de stockage avec sa station de pompage, des balles de paille ; les parcelles sans dossier restent cultivées (blé,
prairie, tournesol, labour). Des touffes d'herbe, des fleurs, des buissons et deux vols d'oiseaux. La lumière suit l'heure
(`_ambiance`) : jour, crépuscule, soir, avec le dégradé du ciel de la page assorti.

## L'écran autour de la map

- **Trois KPI** : interventions du jour, devis en attente, chantiers en cours. Ils clignotent quand ils changent.
- **La fiche détaillée** d'un objet : personne (statut, heure d'arrivée, présence, agenda du jour, pointages), installation
  (étape, devis, historique, équipements, PV), chantier (avancement, équipe, matériel posé), intervention (client, technicien,
  pièces, bons), client (CA, impayés, devis, installations), camion (tournée, stock à bord), rayon (stock, manquants), zone
  (qui est là), badgeuse (journal), livraison, poste de travail. Boutons : suivre, fiche complète, ouvrir dans le back-office.
- **Le suivi de l'installation** : Demande → Étude → Devis → Pose → Mise en service → Entretien, avec l'avancement.
- **Le tableau à onglets** : Équipe, Camions (les interventions du jour), Dossiers, Clients (les derniers touchés), Stock ; chaque ligne vole vers l'objet.
- **La recherche** (`/`) : ce qui est sur la map, puis tous les clients, articles, installations et interventions de l'adhérent
  (un article ouvre sa fiche et vole vers le rayon de sa famille) ; le sélecteur de zone avec le nombre de présents, le badge Live, la cloche et le fil d'activité, les
  notifications volantes, la visite guidée (`T`), la vue d'ensemble (`H`), `Échap` pour fermer.
- **Les gestes** : clic gauche glissé déplace la carte, clic droit pivote, molette zoome.

## Le temps réel

Chaque action métier écrit un événement (`cultiveau.evenement`) poussé sur le canal de la société : intervention créée ou
terminée, arrivée sur place, bon signé, devis envoyé ou signé, facture payée, livraison reçue, sortie de stock, chantier démarré,
mise en service, étape d'installation, pointage. La map s'y abonne : notification, animation (la personne entre et badge, le
camion sort, le fournisseur se présente), KPI, tableau et fiches mis à jour. Un rafraîchissement toutes les trente secondes
couvre le reste.

Les pointages (`cultiveau.pointage`) : arrivée, pause, départ en intervention, retour, départ. Depuis la badgeuse de la map,
depuis une fiche (« Badger sa pause »), ou automatiquement : « Arrivé sur place » sur une intervention, bon signé qui clôture.

## Le plan

Le plan 3D est un JSON par société (`cultiveau.plan`), versionné et publié : contour, murs, portes, cloisons vitrées, zones et
leur sol, objets du kit, places (postes, attente, réunion, pause, rayons, établis, camions, parking, livraison, champs). Un
générateur produit le premier plan ; le gérant l'affine dans la map (bouton Plan) : glisser un objet (grille de 0,5 m), `R` pour
tourner de 15°, `Suppr`, palette d'objets, lien d'un objet à une entité, annuler et rétablir, brouillon ou publication.
Réglages → Cultiveau → Map vivante : régénérer le plan initial, les plans du site, le fil d'activité, les pointages.

## Le mode démonstration

Réglages → Cultiveau → Map vivante → Mode démonstration. Dans les 75 premières secondes, la map rejoue un scénario sur les
données de la société : arrivée d'un technicien qui badge, départ en dépannage (le camion sort), livraison fournisseur, pause,
bon signé sur place, devis signé ; puis des notifications d'ambiance toutes les 14 à 20 secondes. Tout passe par les tables
(pointages et événements marqués « démonstration »). Pour présenter l'ERP à un adhérent ou filmer une démo avec la visite
guidée (`T`).

## Depuis le back-office

« Voir sur la map » sur une installation, un chantier, une intervention, un client, un utilisateur (bouton ou menu Action) :
la map s'ouvre, vole vers l'objet et ouvre sa fiche. Au retour, la map garde la caméra et la sélection pendant vingt minutes.

## Limites et suite

- Tout est procédural (aucun modèle téléchargé) : la map pèse quelques centaines de kilo-octets et tourne sur un portable récent.
  Sur un appareil sans WebGL, les listes et les fiches restent accessibles par le menu.
- Le temps réel passe par le canal de l'ERP (`/websocket`), déjà proxyé en production.
- À venir : la conduite des camions vers une vraie carte des parcelles (GPS), le portail client sur la même map, le pointage
  par badge NFC à l'accueil.
