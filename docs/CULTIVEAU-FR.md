# cultiveau.fr et l'ERP : un seul compte, les deux sens

Module : `cultiveau_site` (contrôleurs `ecran.py` et `entree.py`, modèle `entree.py`). Côté site : `server/erpLien.ts`.

## De cultiveau.fr vers l'ERP (07/11/2026)

Dans l'espace adhérent, une famille de tuiles « Gestion » (Mon ERP, Devis & commandes, Clients, Chantiers, Stock, Achats,
Factures) ouvre l'ERP dans le même onglet, sur le compte de la personne connectée. cultiveau.fr signe un laissez-passer
(HMAC, deux minutes, usage unique) qui dit qui entre, son entreprise et son rôle dans l'équipe ; l'ERP (`/cultiveau/entree`)
le vérifie, retrouve ou crée l'entreprise (`res.company.cultiveau_site_id`) et l'utilisateur (login = e-mail, rôle Cultiveau :
manager → gérant, gestionnaire → administratif, salarié → technicien), puis ouvre la session par une vérification d'identité
« cultiveau_site » (pas de mot de passe ERP). Le laissez-passer consommé est gardé (`cultiveau.site.laissez_passer`) pour
interdire le rejeu.

À la première entrée d'une entreprise, l'ERP demande à cultiveau.fr sa clé d'accès aux données (`POST /api/erp/lier`, signé) et
crée la connexion `cultiveau.site.connexion` : clients, interventions, chantiers et bons saisis sur cultiveau.fr arrivent dans
l'ERP à la synchronisation horaire, sans rien régler à la main.

## De l'ERP vers cultiveau.fr

Les menus « Mon Espace » et « Logistique » de l'ERP (`/cultiveau/ecran?vers=…`) renvoient sur cultiveau.fr avec le même genre de
laissez-passer ; le site (`GET /api/erp/entree`) ouvre la session adhérent et affiche l'écran demandé dans le cadre de l'ERP.

## Réglages

Secret partagé : paramètre système `cultiveau.erp_lien_secret` dans l'ERP = `ERP_LIEN_SECRET` dans Admin › Clés et services de
cultiveau.fr. Adresse du site : `cultiveau.url_site`. Côté site, `ERP_ORIGIN` (défaut https://erp.cultiveau.fr).

## Ce qui reste séparé

L'annuaire des collègues du réseau (module « Collègues » de cultiveau.fr) n'est pas recopié dans l'ERP : l'ERP connaît les
entreprises et les personnes au fur et à mesure qu'elles entrent, et le réseau par l'import réseau (`cultiveau_base`).

## Tout le monde n'a pas l'ERP (07/11/2026, soir)

Les tuiles « Gestion » n'apparaissent sur cultiveau.fr que si l'ERP ouvre sa porte à la personne : cultiveau.fr le lui demande
(`GET /cultiveau/entree/eligible`, signé). La porte est ouverte quand son compte ERP existe déjà, ou quand sa société a la case
« Accès à l'ERP ouvert » (fiche Société, onglet Cultiveau ; les sociétés déjà équipées l'ont d'office à la mise à jour). Sinon,
l'entrée répond « Votre entreprise n'a pas encore accès à l'ERP Cultiveau : demandez-le à Cultiveau », et rien n'est créé.

## Les chantiers de l'ERP dans l'appli Mon Chantier

Un chantier né dans l'ERP (commande confirmée, « Lancer le chantier ») est envoyé à cultiveau.fr une fois la transaction acquise
(`POST /api/external/chantiers` avec la clé de l'entreprise) : client, objet, dates, état, phases et heures. Le site rend son
identifiant, gardé dans `cultiveau_site_ref` : la synchronisation horaire reconnaît le même chantier. Une clé remise avant le
07/11 (lecture seule) est remplacée d'elle-même au premier refus ou à la prochaine entrée depuis cultiveau.fr. Bouton « Envoyer
dans Mon Chantier » sur le chantier, filet de sécurité toutes les 15 minutes. Le retour (modifications faites dans l'appli) passe
toujours par la synchronisation horaire site → ERP.

## Tout ce que l'adhérent a sur cultiveau.fr arrive dans l'ERP (07/11/2026, nuit)

- Le premier passage de la synchronisation envoyait « updatedSince=False » au site, qui répondait 422 : rien n'arrivait. Corrigé.
- La première synchronisation part dans la minute qui suit la liaison (entrée depuis cultiveau.fr), plus seulement à l'heure.
- Les **articles** de « Clients & Articles » deviennent des articles de la société dans l'ERP (référence, désignation, prix HT,
  code-barres, unité, famille sous « Articles cultiveau.fr », marque), source « Clients & Articles de cultiveau.fr », reconnus
  par `cultiveau_site_ref`. Si la clé de l'entreprise n'a pas encore le droit « articles », la synchronisation le dit et continue.
- Les chantiers du site sont dans l'application **Chantiers** de l'ERP (menu Cultiveau), pas dans « Projet » d'Odoo ; la tuile
  Chantiers de cultiveau.fr y mène directement.
- **Le logo de l'entreprise** est celui de son espace cultiveau.fr : le laissez-passer porte son adresse, l'ERP le reprend à
  l'entrée et le remplace quand il change là-bas (`res.company.cultiveau_site_logo_url`). Il sert alors sur les devis, factures et
  courriels de l'ERP.

## Une seule appli chantier : celle de cultiveau.fr (08/11/2026)

« J'aimerais que ça crée directement dans la partie chantier de cultiveau.fr et que la vue des chantiers soit celle de cultiveau.fr sur l'ERP. »

- Le menu **Chantiers › Mes chantiers** de l'ERP ouvre l'appli Mon Chantier de cultiveau.fr dans le cadre de l'ERP (écran `cultiveau_site.ecran`, destination `/adherent/chantier`). La tuile Gestion › Chantiers de cultiveau.fr y mène aussi. La liste propre à l'ERP reste sous **Suivi ERP (matériel, heures, PV)** : c'est elle qui tient le matériel sorti du magasin, les heures, le PV et la facturation.
- **Lancer le chantier** depuis une commande : le chantier est envoyé tout de suite dans Mon Chantier et c'est la fiche du site qui s'ouvre (`/adherent/chantier?id=<id du site>`). Sans liaison au site (entreprise pas reliée, site injoignable), la fiche de l'ERP s'ouvre comme avant et l'envoi se fera au passage suivant.
- Le chantier créé à la confirmation de la commande (module déclenchements) part dans Mon Chantier après l'enregistrement ; le bouton **Chantiers** de la commande ouvre alors la fiche du site. Sur la fiche ERP d'un chantier présent sur le site : bouton **Ouvrir dans Mon Chantier**.
- Le logo de l'entreprise suit son espace cultiveau.fr à chaque synchronisation (`GET /api/external/entreprise`), plus seulement à l'entrée.

## Le stock : un entrepôt par société, et l'inventaire validé devient le stock (08/11/2026)

« Le stock n'est toujours pas disponible. » Deux causes : les sociétés venues de cultiveau.fr n'avaient **pas d'entrepôt** dans l'ERP (seule
la première en avait un), donc aucune quantité n'était possible ; et **aucune quantité n'existe sur cultiveau.fr** (la base Articles n'a pas de
colonne stock ; le stock réel de l'adhérent est dans sa gestion commerciale, Sage chez Modern Irrigation 81).

- `res.company.cultiveau_entrepot()` crée l'entrepôt manquant au nom de la société (rejoué à chaque mise à jour par `data/entrepots.xml`, et à la
  création d'une société depuis cultiveau.fr).
- Nouvelle étape de la synchronisation, **Inventaires** : les inventaires **validés** dans Mon Inventaire (`GET /api/external/inventaires`,
  avec leurs lignes) fixent la quantité en stock des articles comptés dans l'entrepôt de la société (mode inventaire d'Odoo). Les lignes d'un
  même article s'additionnent (plusieurs zones) ; ce qui n'a pas été compté ne bouge pas ; une référence inconnue de l'ERP est signalée dans
  le résultat, jamais inventée. Article reconnu par son identifiant du site, sinon sa référence, sinon son code-barres.
- Tant qu'aucun inventaire n'est validé, le stock reste à zéro. L'autre chemin reste l'import Excel du stock Sage dans l'ERP (Inventaire ›
  Ajustements, import standard).

## La base articles dans les deux sens, et un écran pour les prix (08/11/2026)

« Le stock ne se fera que par l'ERP ; en revanche il faut que les articles créés soient disponibles dans la base, et qu'on puisse facilement
accéder à la base articles pour mettre à jour les prix de vente et les prix d'achat. »

- **ERP → cultiveau.fr** (`models/article_site.py`) : pour une société reliée, un article créé dans l'ERP est créé dans la base Clients & Articles
  du site (`POST /api/external/articles`, droit `articles:write`) ; un changement de désignation, référence, prix de vente, unité, TVA, famille,
  code-barres ou archivage y est répercuté (`PATCH /api/external/articles/<id>`). Le prix d'achat et le stock ne partent pas. L'article créé par
  un utilisateur d'une société reliée appartient à sa société. Envoi après l'enregistrement, filet toutes les 15 minutes, action « Envoyer sur
  cultiveau.fr » dans la liste. Ce que la synchronisation site → ERP écrit ne repart jamais (contexte `cultiveau_depuis_site`).
- **Écran Base articles** (menu Cultiveau › Base articles, tuile Gestion › Base articles sur cultiveau.fr) : liste modifiable ligne par ligne,
  référence, désignation, famille, prix d'achat, prix de vente HT, TVA, stock ; filtres « sans prix d'achat », « sans prix de vente »,
  « venus de cultiveau.fr », « à envoyer » ; modification en masse.
- Le stock se gère dans l'ERP seul ; l'étape « Inventaires » (Mon Inventaire validé → stock) reste disponible et peut se décocher par société.

## C'est cultiveau.fr qui décide qui a l'ERP (08/11/2026)

« Pour le moment j'aimerais pouvoir être seul à décider qui a accès à l'ERP ou pas, depuis Admin › Adhérents de cultiveau.fr : on fait un
setup et feu. » Côté ERP (`controllers/entree.py`, `models/entree.py`) :

- `POST /cultiveau/entree/ouvrir`, corps `{"t": <jeton signé>}` (charge `action: "ouvrir"`, `entreprise` avec `erp_acces: true`, `gerant`) :
  société retrouvée ou créée (avec son entrepôt), marquée ouverte, gérant créé sans invitation (il entre par les tuiles), clé demandée au
  site (`POST /api/erp/lier`), première synchronisation déclenchée. Réponse `{ok, societe_id, utilisateurs, cle, synchro}`. Nonce à usage
  unique, 409 s'il resservait, 400 si l'action ne correspond pas à l'adresse.
- `POST /cultiveau/entree/fermer` (`action: "fermer"`) : société fermée, comptes internes qui n'ont que cette société désactivés, liaison
  mise en sommeil (plus de synchronisation). Réponse `{ok, societe_id, utilisateurs_desactives}`.
- À l'entrée et à la question d'éligibilité, `entreprise.erp_acces: true` dans le laissez-passer ouvre la société si elle ne l'était pas :
  la décision vient du site. Sans ce champ, comportement inchangé (comptes existants, sociétés cochées dans l'ERP).
