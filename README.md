# Cultiveau ERP — l'ERP de l'irrigation, sur Odoo 18 Community

Odoo (code open source, licence LGPL) fournit devis, commandes, factures, comptabilité française,
CRM, stocks, achats, e-mailing, projets, contacts et portail client. Les modules Cultiveau
(`addons/`) en font un ERP de l'irrigation, construit sur le référentiel technique Cultiveau V4 :

| Module | Ce qu'il apporte |
|---|---|
| `cultiveau_base` | Le réseau : adhérents (une société Odoo chacun), agriculteurs, département, outils du réseau dans le menu, réglages |
| `cultiveau_frise` | La frise culturale : cultures de chaque client, stades et besoins en eau par département, fenêtres « projet » et « achat », les quatre saisons émotionnelles (écoute, support, discret, proposition), les périodes critiques, les cours agricoles, « À contacter ce mois-ci » |
| `cultiveau_persona` | Les cinq personas de l'étude PRISM (🦁 Lion, 🐆 Jaguar, 🐈 Chat, 🐢 Tortue, 🐝 Abeille), huit questions pour les reconnaître, leur besoin sur la pyramide de Maslow, et **l'Agent** qui croise persona × frise × cours pour dire quand appeler et sur quel ton |
| `cultiveau_catalogue` | Le catalogue technique (DN, PN, matière, raccordement, fiches) ; import de la matrice Cultiveau et du catalogue 3D |
| `cultiveau_installation` | Le parc installé selon le référentiel : A1.1 analyse des besoins, A1.2 dimensionnement, A1.3 PV, A1.4 certificat, A1.5 réglage, équipements et renouvellement, A1.8 registre, rappels saisonniers, dossier technique imprimable |
| `cultiveau_ventes` | Les six phases du projet dans le CRM, devis par lots reliés à l'installation, modèles par type d'installation, simulateur d'irrigation à l'usage (€/m³, mensualité lissée) |
| `cultiveau_interventions` | Dépannage et entretien : urgence, pièces → devis, registre tenu automatiquement, kanban et calendrier |
| `cultiveau_connecteurs` | L'API pour l'assistant téléphonique (standard IA) : fiche du client qui appelle avec persona, frise du mois et conseil de l'Agent ; dépôt de l'intervention ou de l'opportunité |

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

1. **Cultiveau → Réglages** : adresses des outils du réseau, clé de l'API (à reporter dans la page « Clés » de l'assistant) ;
2. **Paramètres → Sociétés** : une société par adhérent (nom, SIRET, numéro dédié de l'assistant, dossier DTe) ; un utilisateur par personne, groupe « Adhérent » ; l'équipe Cultiveau a le groupe « Équipe Cultiveau » ;
3. **Cultiveau → Catalogue → Importer** : la matrice de référencement, puis le catalogue 3D (`python3 scripts/importer_catalogue_3d.py …`) ;
   sur le serveur, `sh scripts/donnees.sh catalogue` charge les 24 000 articles, `bibliotheque` l'inventaire des 2 300 documents du Drive
   (fiches, brochures, notices, reliés aux articles), `fiches` rapatrie les PDF eux-mêmes (3 Go) : chaque document est joint à sa fiche
   et sa première page illustre la fiche et les articles qui n'ont pas de photo ;
4. **Cultiveau → Agriculteurs** : les clients (import CSV depuis l'assistant ou le CRM), leurs cultures, leur persona, leurs installations.

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
