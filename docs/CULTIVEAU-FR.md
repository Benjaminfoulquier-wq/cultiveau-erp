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
