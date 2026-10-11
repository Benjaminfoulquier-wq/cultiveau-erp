# Étude de l'espace adhérent de cultiveau.fr

*État au 11 octobre 2026 : **visite non réalisée**. L'environnement d'exécution n'a pas pu joindre le site.*

## 1. Ce qui a bloqué

Le proxy de sortie de l'environnement cloud a refusé la connexion à `cultiveau.fr` :

```
$ curl -sS -o /dev/null -w "%{http_code}" https://cultiveau.fr/
curl: (56) CONNECT tunnel failed, response 403
000
```

Diagnostic du proxy : `connect_rejected — gateway answered 403 to CONNECT (policy denial or upstream failure)`,
hôte `cultiveau.fr:443`. Le domaine n'est pas autorisé par la politique réseau de l'environnement. Conformément à la
mission, la visite s'est arrêtée là : pas de connexion à l'espace adhérent, pas de navigation, pas de capture.

**Pour débloquer** : dans les réglages de l'environnement cloud (menu de l'environnement dans la barre de titre de la
session → *Modifier* → *Accès réseau*), ajouter `cultiveau.fr` (et `www.cultiveau.fr` s'il est utilisé) aux domaines
autorisés, ou choisir un niveau d'accès plus large. Voir
https://code.claude.com/docs/en/cloud-environments#network-access. Relancer ensuite la mission.

## 2. Règles retenues pour la prochaine visite

- Le dépôt est **public** : aucune capture d'écran n'est commitée. Les captures restent hors du dépôt, dans l'espace
  de travail de la session. `docs/espace-adherent/captures/` ne sera donc pas créé.
- Aucune donnée personnelle dans ce rapport : exemples génériques (« Nom de l'exploitation », « 06 xx xx xx xx »).
- Lecture seule sur le site : aucun formulaire envoyé, rien de créé, modifié ou supprimé.
- Les identifiants de connexion ne sont écrits nulle part.

## 3. Plan du site, écrans, modèle de données, appels réseau

*À compléter après la visite.* Pour chaque écran : rôle, données affichées, actions, liens, adresse de la page, appels
JSON/API observés, rôle requis (adhérent, équipe, administrateur), outils intégrés (DTI/DTe, diagnostic, comptes
rendus, catalogue, formation, assistant…).

## 4. Liens avec l'ERP : ce qui est déjà prêt côté ERP

Pas de correspondance écran par écran sans la visite. Voici les points d'entrée de l'ERP (voir [docs/API.md](../API.md))
que l'espace adhérent pourra utiliser :

| Ressource ERP (`/cultiveau/api/v1/…`) | Lecture | Écriture par l'API | Usage probable côté espace adhérent (à vérifier) |
|---|---|---|---|
| `adherents` | oui | non | Fiche de la société adhérente, équipe |
| `clients` | oui | création, notes | Agriculteurs de l'adhérent |
| `installations`, `registre` | oui | notes | Parc installé, registre d'entretien |
| `interventions` | oui | création, notes | Dépannages, entretien, comptes rendus |
| `chantiers` | oui | notes | Suivi des chantiers |
| `devis`, `commandes`, `factures` | oui | notes | Documents commerciaux, à encaisser |
| `opportunites` | oui | création, notes | Projets, demandes entrantes |
| `articles`, `fiches` | oui | non | Catalogue réseau, catalogue de l'adhérent, fiches techniques |
| `resume` | oui | non | Tableau de bord par adhérent |

Principes déjà posés par l'ERP, qui orientent les sens de synchronisation :

- l'ERP est la source des données du réseau ; le site lit par l'API avec une clé côté serveur (jamais dans la page) ;
- une clé peut être limitée à certains adhérents : chaque compte de l'espace adhérent ne doit voir que sa société ;
- synchronisation incrémentale possible avec `modifie_depuis` ;
- écritures autorisées du site vers l'ERP : création de clients, d'interventions, d'opportunités, et ajout de notes.

La correspondance détaillée « donnée de l'espace adhérent → ressource ERP → sens » sera rédigée après la visite.
