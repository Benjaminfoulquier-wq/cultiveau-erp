# Feuille de route — ce qui rendra l'ERP plus puissant

État au 4 octobre 2026. Ce qui est en place, puis ce qui manque, dans l'ordre où le faire.

## En place

- **Le catalogue Cultiveau** : 24 755 articles (référencement + catalogue 3D), cotes DN/PN/matière/raccordement, 2 264 fiches techniques
  jointes avec leur première page en image. Commun à tout le réseau.
- **Mon catalogue** : chaque adhérent pioche dans le catalogue Cultiveau (« Ajouter à mon catalogue », à l'unité ou en masse) et importe
  ses propres articles depuis n'importe quel fichier Excel ou CSV (colonnes reconnues par leur intitulé). Ses articles restent les siens.
- **Mes clients** : import depuis n'importe quel fichier (ancien logiciel, comptable, assistant téléphonique, téléphone) ; un client connu
  est complété, jamais dupliqué ; les clients d'un adhérent ne sont pas visibles des autres.
- **Agriculteurs** : cultures et frise culturale (postures du mois, périodes critiques, cours), persona PRISM (Lion, Jaguar, Chat, Tortue,
  Abeille) et l'Agent qui dit comment aborder le client ce mois-ci.
- **Installations, devis, interventions** : le dossier de chaque site (analyse des besoins, dimensionnement, équipements), devis liés à
  l'installation, simulateur « irrigation à l'usage », interventions planifiées et registre.
- **Matrice de pose** : le temps de chaque geste, les coefficients de terrain, la main-d'œuvre calculée au devis depuis la
  nomenclature, et les chantiers terminés qui corrigent les temps constatés geste par geste.
- **Fiches techniques lues par l'IA** : les caractéristiques de chaque article tirées de sa fiche PDF (page à l'appui), un
  comparateur côte à côte, la recherche par caractéristique. Clé Mistral à renseigner dans les réglages ; un lot de fiches par nuit.
- **Présentation des devis et factures** : détail complet, par lot, forfait, ou matériel et main-d'œuvre, au choix de l'adhérent et
  document par document ; lignes masquables ; l'ERP garde tout.
- **Grille de remises** : typologie de client × famille / sous-famille, exceptions par client, article ou quantité ; la remise se pose
  seule sur chaque ligne de devis, la marge est sous les yeux ; grille du réseau copiable.
- **Pilotage** : le tableau de bord de l'adhérent et celui du réseau ; bilan et compte de résultat ; clôture d'exercice ;
  immobilisations amorties chaque mois.
- **Tarifs, marges, commande groupée** : le tarif négocié chez chaque fournisseur s'importe et met à jour le prix d'achat de tous les
  adhérents ; chacun règle sa marge (par famille s'il veut) et sa liste de prix de vente suit ; la commande groupée regroupe les
  besoins et crée une commande d'achat par adhérent.
- **Du dimensionnement au devis** : l'installation se découpe en secteurs ; l'ERP calcule débits, diamètres, pertes de charge, pression
  en tête, HMT et pompe, puis génère le devis par lots avec la nomenclature prise au catalogue.
- **Conseil d'irrigation** : chaque matin, la météo réelle de chaque parcelle (ETo et pluie des trois dernières semaines, prévision à
  sept jours, Open-Meteo, gratuit) croisée avec le Kc du jour de la frise du client et la réserve de son sol donne le déficit et le
  conseil (« apporter 25 mm, soit 9 h à votre débit, avant jeudi ») ; les arrosages se notent, l'alerte prévient le commercial, le
  client reçoit l'e-mail en un clic.
- **Nouvel adhérent** : un seul écran, sept étapes dans l'ordre (société, utilisateurs, assistant téléphonique, clients, articles,
  comptabilité, facture électronique), chacune rejouable ; l'adhérent travaille le soir même.
- **Facture électronique** : chaque société s'inscrit sur la plateforme agréée depuis Réglages → Cultiveau (démonstration, puis
  réel), reçoit ses factures fournisseurs par la plateforme et y émettra les siennes à l'échéance de 2027 ; e-reporting du comptoir ;
  double authentification exigée d'un clic ; sauvegarde nocturne vérifiée, copiée hors serveur si un espace de stockage est fourni.
- **Comptabilité** : chaque société a son plan comptable français et ses journaux ; le relevé de la banque s'importe (CSV, OFX,
  CAMT.053, QIF) et chaque ligne est proposée en face d'une facture, d'un paiement du comptoir ou d'un compte (frais bancaires,
  emprunt, TVA…), le sûr se rapproche seul, le reste se valide en un clic ; les clients et fournisseurs se lettrent d'eux-mêmes ;
  la déclaration de TVA se calcule d'après les écritures et passe son écriture ; le comptable a son accès et ses exports (FEC,
  grand livre, balance, journaux).
- **Parcelles et satellite** : on demande à l'agriculteur son fichier Telepac (un e-mail en un clic) ; à l'import, ses parcelles
  (contours, surfaces, îlots) et ses cultures se remplissent d'après les codes PAC. Chaque parcelle suivie reçoit les images
  Sentinel-2 gratuites (Copernicus) : NDVI et NDWI, courbe de la saison, et une alerte quand la vigueur chute, que l'eau des
  feuilles baisse ou que la parcelle devient hétérogène, en pleine saison seulement (d'après la frise du client) ; le commercial a
  une activité « appeler », le client un e-mail en un clic (ou automatiquement si on le choisit).
- **Assistant téléphonique** : l'API donne à l'assistant la fiche du client qui appelle (frise, persona, conseil) et reçoit les appels ;
  le branchement se fait depuis GitHub (« assistant : oui ») : clé, connecteurs, numéros dédiés, clients de l'assistant importés chez
  chaque adhérent, messagerie sortante.
- **Le réseau** : Cultiveau, Agrifusion Holding et Solution Magnus, l'équipe, les 16 adhérents et leurs équipes, les prospects, les 39
  fournisseurs référencés et leurs contacts, importés d'un fichier (Réglages → Importer le réseau).
- **Marque** : l'ERP est aux couleurs de Cultiveau, sans mention de l'éditeur ; déploiement en un push sur erp.cultiveau.fr.
- **L'équipe** : congés et notes de frais depuis le téléphone (`/moi`), validés en un clic par le gérant ; jours fériés et congés
  payés posés tout seuls ; le ticket photographié est lu par l'IA ; les absences sur la map, dans les réunions et chez Mathis.
- **Réunions et agendas** : la salle de réunion de la map suit les agendas ; créneaux libres proposés, invitations, visio intégrée,
  Google Meet ou Teams selon l'agenda connecté.
- **Mathis dans l'ERP** : l'assistant du standard IA est aussi dans l'ERP et sur la map : questions sur les données dans les droits de
  chacun, actions confirmées d'un clic, appels téléphoniques en direct sur la map.
- **La Map vivante** : la page d'accueil est le site de l'adhérent en 3D, relié aux données en temps réel (équipe, camions, clients,
  chantiers, parcelles, stock), avec fiches, suivi d'installation, visite guidée, mode démonstration et éditeur de plan.
- **La vue d'ensemble** (remplacée par la map) : le magasin en 3D (accueil et comptoir, bureau d'étude, magasin et cour, chantiers,
  atelier et SAV, parcelles en service, caisse) ; chaque objet s'ouvre sur ce qu'il représente.
- **Le comptoir** : un écran pour la vente au magasin ; la douchette ou le clavier trouve l'article (code-barres, référence, nom),
  le panier, le client ou « client de passage », puis « Encaisser » (espèces, carte, chèque, virement) : commande confirmée, sortie de
  stock validée, facture payée, ticket ; ou « Commande à livrer », ou « Devis à envoyer ». Le plan comptable français se met en place
  tout seul au premier encaissement d'un adhérent.
- **L'API** : une clé par outil (Réglages → Clés d'API), l'API REST `/cultiveau/api/v1` (clients, interventions, chantiers,
  installations, devis, factures, articles…) et le connecteur Claude ; voir [API.md](API.md).
- **Les chantiers** : lancés depuis la commande, avec l'équipe de pose, les dates (planning par chef de chantier), le matériel prévu
  d'après la commande et sorti du magasin (bon de sortie), les photos, puis la mise en service : PV A1.3 signé par l'exploitant sur
  place, l'installation passe « en service » et le registre est tenu.

## À faire, dans l'ordre

1. **Mise en route d'un adhérent en dix minutes.** Fait : Réglages → Nouvel adhérent enchaîne la société (SIRET, logo, couleur),
   les utilisateurs invités avec leur rôle, le numéro de l'assistant, l'import des clients et des articles, la comptabilité et le
   comptable, l'inscription sur la plateforme agréée ; l'avancement se voit, chaque étape se rejoue.
2. **Devis et factures au nom de l'adhérent.** Fait : mise en page « Cultiveau » (logo et couleur de l'adhérent, « membre du
   réseau Cultiveau » en pied), devis avec le projet, l'acompte, le bon pour accord et les CGV en dernière page, signature en ligne,
   facture d'acompte en un clic, mentions légales des factures, e-mails en français, relances automatiques des devis sans réponse et
   des factures en retard puis activité « appeler le client ». Reste : le paiement en ligne (fournisseur de paiement à choisir).
3. **Tarifs et marges.** Fait : tarifs fournisseurs importés (Excel, CSV ; chaque ligne retrouve son article, hausses et baisses,
   alerte au-delà d'un seuil, prix d'achat des adhérents mis à jour), marge cible par adhérent et par famille, liste de prix de
   vente construite seule, commande groupée réseau. Reste : les tarifs en PDF (lecture par l'IA, sur le modèle des fiches techniques).
4. **Stock et achats.** Fait : la commande groupée réseau (les besoins de plusieurs adhérents regroupés vers un fournisseur
   référencé, une commande d'achat par adhérent). Reste : inventaire initial depuis le fichier d'articles, réassort automatique.
5. **Du dimensionnement au devis.** Fait : secteurs (organes, maille, conduite d'amenée, dénivelé), débit et pluviométrie par secteur,
   diamètres pour une vitesse sous 1,5 m/s, pertes de charge, pression en tête, HMT, pompe et puissance, note de calcul ; devis par
   lots généré avec la nomenclature, articles pris au catalogue (DN, matière) ou « à préciser ». Reste : les abaques des fabricants
   (courbes de pompes, portées d'asperseurs) : les caractéristiques lues sur les fiches sont là, reste à les brancher sur le calcul.
6. **Terrain.** Fait : le planning des techniciens sur calendrier, « Ma journée » sur le téléphone, le bon d'intervention signé sur
   place (pièces sorties du camion, temps et déplacement chiffrés, écart au PV signalé), la facture en un clic, le stock camion et son
   réassort, les phases et pointages de chantier avec la rentabilité, les contrats d'entretien (hivernage, remise en route, visites)
   qui créent leurs interventions un mois avant, les garanties par équipement, la demande d'avis au client à la signature. Reste :
   le Gantt multi-semaines des chantiers et l'avis par SMS.
7. **Campagnes au bon moment.** Segmentation par culture, persona et département ; e-mails et SMS déclenchés par la frise (« le maïs
   entre en floraison dans le Gard : proposer la vérification des pivots ») ; portail client où l'agriculteur voit ses devis, factures
   et installations.
8. **Pilotage.** Fait : tableau de bord de l'adhérent (CA et courbe sur deux ans, devis, taux de signature, retards, fournisseurs,
   trésorerie, TVA, chantiers, parcelles) et vue réseau (CA, devis, retards, trésorerie, dernière connexion par adhérent) ; bilan et
   compte de résultat ; export vers le comptable. Reste : volumes par fournisseur et catalogue réellement vendu dans la vue réseau.
9. **Les outils connectés dans les deux sens.** Depuis l'assistant téléphonique : créer un rendez-vous ou un devis à la fin de l'appel ;
   synchronisation automatique des clients entre l'assistant et l'ERP (plus besoin de fichier) ; DTe et DISC lisibles depuis la fiche
   de l'adhérent.
10. **Photos et visuels.** Il n'y a pas de photos produits dans le Drive : il faut une source (sites fournisseurs, dossier photos) ; en
    attendant, la première page de la fiche technique sert d'image. Catalogue 3D visuel à terme.
11. **Comptabilité.** Fait : plan et journaux français par société, import des relevés (CSV, OFX, CAMT, QIF), rapprochement proposé
    et validé en un clic, lettrage automatique des tiers, déclaration de TVA calculée et son écriture, exports FEC / grand livre /
    balance, accès du comptable, bilan et compte de résultat, clôture d'exercice, immobilisations. Reste : le paiement en ligne,
    les virements SEPA fournisseurs en lot.
12. **Exploitation et sécurité.** Fait : sauvegarde quotidienne vérifiée (30 jours, hebdomadaires 90 jours) et copie hors serveur dès
    qu'un espace de stockage est renseigné (secret `CULTIVEAU_RCLONE_CONF`), double authentification. Reste : changement des mots de
    passe d'origine, journal des accès, RGPD (export et suppression d'un client), dépôt GitHub privé.

## Ce que ça demande à Cultiveau

- Les **tarifs négociés** par fournisseur (étape 3) et la **marge cible** conseillée.
- Un **modèle de devis** de référence (étape 2) : mentions, CGV, acompte.
- Les **règles de dimensionnement** retenues par le réseau (étape 5) : pertes de charge admissibles, vitesses, coefficients.
- Une **source de photos** (étape 10).
