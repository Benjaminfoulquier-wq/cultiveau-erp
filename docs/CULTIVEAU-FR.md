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
