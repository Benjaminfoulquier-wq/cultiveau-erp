# L'API de l'ERP Cultiveau

L'ERP (erp.cultiveau.fr) est la source des données du réseau : clients, interventions, chantiers, installations, devis,
factures, articles… Le site cultiveau.fr, l'appli et Claude les lisent par cette API, chacun avec sa clé.

## 1. Créer une clé

Dans l'ERP : **Cultiveau → Réglages → Clés d'API → Nouveau**.

| Réglage | Choix |
|---|---|
| Outil | « Site cultiveau.fr », « Claude », « Appli des techniciens »… |
| Droits | *Lecture seule*, ou *Lecture et écriture* (créer clients, interventions, opportunités, ajouter des notes) |
| Adhérents | Vide = tout le réseau ; sinon la clé ne voit que ces sociétés |
| Expire le | Facultatif |

La clé (`cv_…`) n'est montrée qu'une fois : copiez-la, puis « J'ai copié la clé ». L'ERP n'en garde qu'une empreinte.
« Nouvelle clé » remplace la clé (l'ancienne cesse aussitôt de marcher) ; décocher « Actif » la coupe.

## 2. Appeler l'API (site, appli, scripts)

Base : `https://erp.cultiveau.fr/cultiveau/api/v1` — en-tête `Authorization: Bearer cv_…` à chaque requête.

```
GET  /                         les ressources et les droits de la clé
GET  /resume                   le tableau de bord, adhérent par adhérent
GET  /<ressource>              la liste (recherche, filtres, pagination)
GET  /<ressource>/<id>         la fiche complète
POST /<ressource>              créer (clients, interventions, opportunites)
POST /<ressource>/<id>/notes   ajouter une note sur la fiche {"texte": "...", "auteur": "..."}
GET  /openapi.json             la description OpenAPI 3.1 (sans clé)
```

Ressources : `clients`, `interventions`, `chantiers`, `installations`, `registre`, `devis`, `commandes`, `factures`,
`opportunites`, `articles`, `fiches`, `adherents`.

Paramètres de liste : `q` (texte), `limite` (1 à 200, 50 par défaut), `decalage` ou `page`, `modifie_depuis`
(AAAA-MM-JJ, pour synchroniser), `client_id`, `installation_id`, `adherent_id`, `etat`, `ouvertes=1` (interventions),
`a_encaisser=1` (factures), `catalogue=mien|reseau` et `en_stock=1` (articles).

Réponse d'une liste :

```json
{"ressource": "interventions", "total": 42, "limite": 50, "decalage": 0, "suivant": null,
 "resultats": [{"id": 17, "titre": "Pivot arrêté", "urgence": {"code": "immediate", "libelle": "Immédiate…"},
                "client": {"id": 8, "nom": "EARL des Oliviers"}, "installation": {"id": 3, "nom": "Pivot des Grandes Terres"},
                "etape": "À faire", "modifie_le": "2026-10-11 14:02:11", "url": "https://erp.cultiveau.fr/app/project.task/17"}]}
```

Créer une intervention (clé en écriture) :

```
curl -X POST https://erp.cultiveau.fr/cultiveau/api/v1/interventions \
  -H "Authorization: Bearer cv_…" -H "Content-Type: application/json" \
  -d '{"titre": "Enrouleur qui ne rembobine plus", "urgence": "journee",
       "client": {"nom": "Jean Martin", "telephone": "06 12 34 56 78", "commune": "Alès"}, "origine": "telephone"}'
```

Un client inconnu est créé ; un client connu (même téléphone ou même e-mail) est retrouvé, pas dupliqué.

Erreurs : `401` clé absente ou invalide, `403` clé en lecture seule ou adhérent hors de la clé, `404` introuvable,
`400` paramètre invalide — toujours `{"erreur": "…"}`.

### Côté site cultiveau.fr (Django)

```python
# settings.py : ERP_URL = "https://erp.cultiveau.fr/cultiveau/api/v1" ; ERP_CLE = os.environ["ERP_CLE"]
import requests
from django.conf import settings

def erp(chemin, **params):
    r = requests.get(f"{settings.ERP_URL}/{chemin}", params=params, headers={"Authorization": f"Bearer {settings.ERP_CLE}"}, timeout=15)
    r.raise_for_status()
    return r.json()

def erp_post(chemin, donnees):
    r = requests.post(f"{settings.ERP_URL}/{chemin}", json=donnees, headers={"Authorization": f"Bearer {settings.ERP_CLE}"}, timeout=15)
    r.raise_for_status()
    return r.json()

# erp("clients", q="Martin") ; erp("installations", client_id=8) ; erp("interventions", ouvertes=1, modifie_depuis="2026-10-01")
```

La clé reste côté serveur (variable d'environnement), jamais dans une page.

## 3. Brancher Claude (connecteur)

1. Créer une clé avec l'usage **Claude (connecteur)** ; l'ERP affiche l'**adresse du connecteur**
   `https://erp.cultiveau.fr/cultiveau/mcp/cv_…` (la clé est dans l'adresse : à garder pour soi).
2. Dans Claude : **Réglages → Connecteurs → Ajouter un connecteur personnalisé**, nom « ERP Cultiveau », coller l'adresse.
3. Claude dispose alors des outils `resume`, `chercher`, `lister`, `lire` et, si la clé est en écriture, `creer_client`,
   `creer_intervention`, `creer_opportunite`, `ajouter_note`.

Exemples : « Quelles interventions urgentes chez Eaux Vives ? », « Résume le dossier de l'EARL des Oliviers »,
« Dépose un dépannage pour Jean Martin, enrouleur bloqué ».

Le connecteur parle le protocole MCP (HTTP, réponses JSON, versions 2024-11-05 à 2025-06-18) ; il accepte aussi
la clé en en-tête `Authorization: Bearer` à l'adresse `/cultiveau/mcp`.
