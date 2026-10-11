# Cultiveau ERP — l'ERP de l'irrigation, sur Odoo 18 Community

Odoo (code open source, licence LGPL) fournit devis, commandes, factures, comptabilité française,
CRM, stocks, achats, e-mailing, projets, contacts et portail client. Les modules Cultiveau
(`addons/`) en font un ERP de l'irrigation, construit sur le référentiel technique Cultiveau V4 :

| Module | Ce qu'il apporte |
|---|---|
| `cultiveau_base` | Le réseau : adhérents (une société chacun), clients typés (agriculteur, collectivité, particulier, industrie, plombier, paysagiste, pisciniste — chacun son véhicule en portrait), import de clients, département, outils du réseau dans le menu, réglages |
| `cultiveau_frise` | La frise culturale (119 cultures de France et des DOM, Kc FAO-56 corrigés au climat de chaque département, frise recalée par département et par client, besoins en eau du client : pointe, débit, volumes, RFU) : cultures de chaque client, stades et besoins en eau par département, fenêtres « projet » et « achat », les quatre saisons émotionnelles (écoute, support, discret, proposition), les périodes critiques, les cours agricoles, « À contacter ce mois-ci » |
| `cultiveau_persona` | Les cinq personas de l'étude PRISM (🦁 Lion, 🐆 Jaguar, 🐈 Chat, 🐢 Tortue, 🐝 Abeille), huit questions pour les reconnaître, leur besoin sur la pyramide de Maslow, et **l'Agent** qui croise persona × frise × cours pour dire quand appeler et sur quel ton |
| `cultiveau_catalogue` | Le catalogue technique (DN, PN, matière, raccordement, fiches) ; import de la matrice Cultiveau et du catalogue 3D |
| `cultiveau_installation` | Le parc installé selon le référentiel : A1.1 analyse des besoins, A1.2 dimensionnement, A1.3 PV, A1.4 certificat, A1.5 réglage, équipements et renouvellement, A1.8 registre, rappels saisonniers, dossier technique imprimable |
| `cultiveau_ventes` | Les six phases du projet dans le CRM, devis par lots reliés à l'installation, modèles par type d'installation, simulateur d'irrigation à l'usage (€/m³, mensualité lissée) |
| `cultiveau_interventions` | Dépannage et entretien : urgence, pièces → devis, registre tenu automatiquement, kanban et calendrier |
| `cultiveau_connecteurs` | L'API pour l'assistant téléphonique (standard IA) : fiche du client qui appelle avec persona, frise du mois et conseil de l'Agent ; dépôt de l'intervention ou de l'opportunité |
| `cultiveau_marque` | L'habillage Cultiveau : couleurs, logo, menu, adresses en `/app` (le nom du logiciel n'apparaît nulle part) |
| `cultiveau_vue3d` | La vue d'ensemble : le site adhérent en 3D (WebGL), chaque poste ouvre l'écran correspondant, familles de produits cliquables, recherche « Où aller ? » |
| `cultiveau_chantier` | Les chantiers de pose : matériel prévu/posé, sortie et retour du stock, phases, pointages des équipes, rentabilité, conflits d'équipe, PV de mise en service |
| `cultiveau_comptoir` | La vente au comptoir : scan de l'article, panier, devis, commande ou encaissement immédiat avec ticket |
| `cultiveau_terrain` | Le terrain : « Ma journée » sur le téléphone, planning des techniciens, bon d'intervention signé sur place → facture, stock camion et réassort, contrats d'entretien (hivernage, remise en route, visites) avec interventions automatiques, garanties, avis du client |
| `cultiveau_api` | Les clés d'API : REST (OpenAPI) et connecteur MCP pour Claude, en lecture ou écriture, limitées aux adhérents choisis |
| `cultiveau_documents` | Devis et factures au nom de l'adhérent : mise en page à sa marque, acompte, bon pour accord, signature en ligne, CGV, mentions légales, e-mails en français, relances automatiques |
| `cultiveau_parcelles` | Les parcelles PAC de chaque agriculteur : sa déclaration Telepac (XML, shapefile ZIP ou GeoJSON) demandée par e-mail puis importée, les cultures du client remplies d'après les codes PAC, la carte des parcelles, le suivi Sentinel-2 gratuit (Copernicus Data Space : NDVI et NDWI tous les 5 jours, nuages masqués) et les alertes « ce qui cloche » (chute de vigueur, stress hydrique, parcelle hétérogène) lues selon le stade de la frise, avec un e-mail au client en un clic ; le conseil d'irrigation hebdomadaire par parcelle (météo réelle Open-Meteo, Kc du jour selon la frise du client, réserve du sol) : « apporter 25 mm avant jeudi », arrosages notés, alerte au commercial et e-mail au client |
| `cultiveau_compta` | La comptabilité courante d'un adhérent : plan comptable français et journaux en français mis en place seuls, import des relevés bancaires (CSV, OFX, CAMT.053, QIF) sans doublon, rapprochement proposé ligne par ligne (facture, paiement du comptoir, frais bancaires…) et validé en un clic, lettrage des clients et des fournisseurs, déclaration de TVA (CA3) calculée d'après les écritures avec son écriture de clôture, exports FEC, grand livre, balance et journaux, accès en lecture seule du comptable |
| `cultiveau_efacture` | La facture électronique obligatoire : inscription de chaque société sur la plateforme agréée depuis les réglages (démonstration puis réel), factures émises et reçues par la plateforme, e-reporting des ventes aux particuliers et des encaissements, double authentification exigée d'un clic |
| `cultiveau_adhesion` | Nouvel adhérent en dix minutes : société (SIRET, logo, couleur), utilisateurs invités avec leur rôle, numéro de l'assistant téléphonique, import de ses clients et de ses articles, comptabilité et comptable, inscription sur la plateforme agréée ; chaque étape se voit et se rejoue |
| `cultiveau_dimensionnement` | Du dimensionnement au devis : l'installation se découpe en secteurs (organes, maille, conduite d'amenée, dénivelé) ; débit, pluviométrie, diamètre (vitesse sous 1,5 m/s), pertes de charge (Hazen-Williams), pression en tête, HMT, puissance de pompe ; un clic génère le devis par lots avec la nomenclature (tubes, raccords, vannes, organes, filtration, automatisme, pose), articles pris au catalogue, « à préciser » sinon |
| `cultiveau_tarifs` | Tarifs fournisseurs négociés par le réseau (Excel ou CSV : chaque ligne retrouve son article, hausses et baisses visibles, prix d'achat des adhérents mis à jour, alerte au-delà d'un seuil), marge cible par adhérent et par famille (sa liste de prix de vente se construit seule), commande groupée réseau (besoins déposés par chaque adhérent, une commande d'achat par adhérent au tarif négocié, récapitulatif Excel pour le fournisseur) |
| `cultiveau_pilotage` | Le tableau de bord de l'adhérent (chiffre d'affaires et sa courbe sur deux ans, devis en cours, taux de signature, retards clients, fournisseurs à payer, trésorerie, TVA, chantiers, parcelles) et celui du réseau pour l'équipe ; bilan et compte de résultat lus dans les écritures, comparés à l'exercice précédent ; clôture d'exercice (résultat soldé en 120 ou 129, période verrouillée) ; immobilisations et amortissements passés chaque mois, créées d'un clic depuis la facture d'achat |
| `cultiveau_site` | La liaison avec cultiveau.fr : clients, interventions, chantiers et bons de l'espace adhérent récupérés chaque heure |

Pourquoi ces modules et pas d'autres : [docs/ANALYSE-ODOO-IRRIGATION.md](docs/ANALYSE-ODOO-IRRIGATION.md).
D'où viennent les frises, les personas et l'Agent (Journées Cultiveau 2025, étude PRISM 2023, pyramides de Maslow, VoxAgri) :
[docs/HISTOIRE-FRISES-PERSONAS.md](docs/HISTOIRE-FRISES-PERSONAS.md).

## Le code d'Odoo

Le code open source d'Odoo 18 (licence LGPL-3, https://github.com/odoo/odoo, branche `18.0`) est le sous-module `odoo/`
de ce dépôt : `git submodule update --init --depth 1 odoo` le récupère (environ 600 Mo). C'est exactement le code que
contient l'image Docker officielle `odoo:18` utilisée par `docker-compose.yml`. Pour construire l'ERP depuis ces sources
(lire, corriger ou figer Odoo lui-même) : `docker compose -f docker-compose.yml -f docker-compose.source.yml up -d --build`
(voir `Dockerfile`). Les modules Cultiveau ne modifient jamais le code d'Odoo : ils l'étendent depuis `addons/`.

## L'essayer sur son ordinateur (localhost)

Avec Docker Desktop installé, depuis le dossier du projet :

```sh
sh scripts/local.sh demo       # crée la base, installe Odoo et les modules Cultiveau, ajoute des données de démonstration
```

Puis http://localhost:8069, identifiant `admin`, mot de passe `admin`, menu **Cultiveau**. La première exécution prend
quelques minutes (téléchargement de l'image Odoo, installation des modules). `sh scripts/local.sh stop` arrête,
`sh scripts/local.sh reset` efface tout. Sous Windows, lancer la commande dans Git Bash ou WSL.

## Mettre en route

**Depuis GitHub, sans poste de travail** : le workflow « Déployer l'ERP » (`.github/workflows/deployer.yml`) met le serveur à
jour à chaque push. Une fois, ajouter le secret `CULTIVEAU_VPS_CLE` (la clé privée SSH du serveur, celle du poste qui déploie
l'assistant) dans Settings → Secrets → Actions, puis lancer le workflow à la main avec « premiere-installation ». Le DNS
`erp.cultiveau.fr` doit pointer sur le serveur (82.25.116.36) pour que le site HTTPS s'active.

**Depuis un poste qui a la clé SSH**, sur le serveur du réseau (même VPS et même frontal Caddy que l'assistant, le DTe, le DISC et l'Académie) :

```sh
sh deploy/deployer.sh            # copie le projet dans /srv/erp, crée .env, lance Odoo + PostgreSQL
ssh root@82.25.116.36 'cd /srv/erp/app && sh scripts/installer.sh'   # crée la base et installe tout (une fois)
sh deploy/deployer.sh domaine    # le site https://erp.cultiveau.fr quand le DNS pointe sur le serveur
```

Première connexion : `admin` / `admin`, à changer aussitôt. Puis :

1. **Cultiveau → Réglages → Importer le réseau** : le fichier JSON du réseau (groupe, équipe et comptes, adhérents et leurs
   équipes, prospects, fournisseurs référencés et contacts, adresses des outils) ; il reste hors dépôt et se redépose à chaque
   mise à jour sans doublon. Les réglages (adresses des outils, clé de l'API) se retouchent dans **Réglages Cultiveau** ;
1. **L'assistant téléphonique** se branche depuis GitHub : « Déployer l'ERP » avec « assistant : oui ». Sur le serveur, la clé
   de l'API est posée dans l'assistant (connecteur « ERP Cultiveau » et flèche pour chaque adhérent), les adhérents et leurs
   clients sont importés dans l'ERP, et l'ERP envoie ses e-mails avec le compte notification@cultiveau.fr de l'assistant ;
2. **Paramètres → Sociétés** : une société par adhérent (nom, SIRET, numéro dédié de l'assistant, dossier DTe) ; un utilisateur par personne, groupe « Adhérent » ; l'équipe Cultiveau a le groupe « Équipe Cultiveau » ;
3. **Cultiveau → Catalogue → Importer** : la matrice de référencement, puis le catalogue 3D (`python3 scripts/importer_catalogue_3d.py …`) ;
   sur le serveur, `sh scripts/donnees.sh catalogue` charge les 24 000 articles, `bibliotheque` l'inventaire des 2 300 documents du Drive
   (fiches, brochures, notices, reliés aux articles), `fiches` rapatrie les PDF eux-mêmes (3 Go) : chaque document est joint à sa fiche
   et sa première page illustre la fiche et les articles qui n'ont pas de photo ;
4. **Cultiveau → Importer mes clients** : le fichier de l'adhérent (Excel ou CSV, colonnes reconnues par leur intitulé) ; puis
   **Cultiveau → Agriculteurs** : cultures, persona, installations.
5. **Catalogue → Catalogue Cultiveau** : « Ajouter à mon catalogue » sur les articles vendus ; **Importer mes articles** pour les siens ;
   **Mon catalogue** = les deux.
6. **Cultiveau → Comptoir** : la vente au magasin, douchette ou clavier, puis « Encaisser » (ou commande à livrer, ou devis).
7. **Projets et ventes → une commande confirmée → « Lancer le chantier »** : l'équipe, les dates (Chantiers → Planning), le matériel
   sorti du magasin, les photos, puis « Mettre en service » avec le PV signé par l'exploitant.

L'API et le connecteur Claude : [docs/API.md](docs/API.md). La suite : [docs/FEUILLE-DE-ROUTE.md](docs/FEUILLE-DE-ROUTE.md).

En local, sans Docker : Python 3.10+, PostgreSQL, le code d'Odoo 18 (`git clone --depth 1 -b 18.0 https://github.com/odoo/odoo`), puis
`python odoo-bin --addons-path=odoo/addons,addons -d cultiveau -i cultiveau_connecteurs,cultiveau_catalogue,l10n_fr,mass_mailing`.

## Tests

Chaque module a ses tests (tag `cultiveau`). Sur une base de test :

```sh
python odoo-bin -d test --addons-path=odoo/addons,addons -i cultiveau_connecteurs,cultiveau_catalogue \
  --test-enable --test-tags=cultiveau --stop-after-init
```

## Les outils qui restent à côté

L'assistant téléphonique (standard IA), le DTe, le DISC et l'Académie gardent chacun leur site. L'ERP est le socle
commun des clients, du parc, des devis et des factures ; l'assistant y lit et y écrit par l'API (`cultiveau_connecteurs`).
