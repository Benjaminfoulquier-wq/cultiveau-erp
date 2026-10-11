# L'API de l'ERP pour l'assistant téléphonique

Clé : en-tête `X-Cultiveau-Cle`. Deux possibilités :
- **la clé de l'adhérent** (recommandé) : Réglages → Clés d'API, usage « Assistant », droits « lecture et écriture », limitée à sa
  société. Tout ce qu'elle dépose reste chez cet adhérent, quel que soit le `numero_dedie` envoyé ;
- la clé commune du réseau, réglée dans Cultiveau → Réglages (`cultiveau.cle_api`) : l'adhérent est alors reconnu par son numéro dédié.

## Qui appelle ?

```
GET /cultiveau/api/client?telephone=+33612345678&numero_dedie=+33970000001
```

Réponse (client reconnu) :

```json
{"trouve": true, "adherent": "Durand Irrigation",
 "client": {"id": 42, "nom": "Jean Martin", "exploitation": "Mas Neuf", "commune": "Alès", "departement": "30",
            "persona": {"code": "tortue", "nom": "La Tortue", "animal": "🐢", "surnom": "Le fidèle", "maslow": "2", "approche": "…", "canal": "…", "moment": "…"},
            "frise": {"mois": "novembre", "posture": "ecoute", "posture_libelle": "Écoute", "consigne": "Il a le temps et il réfléchit : écouter…",
                      "periode_critique": false, "critiques": [], "stades": [{"culture": "Vigne", "stade": "hors cycle", "posture": "ecoute"}],
                      "cours": "baisse", "ton": "Cours en baisse : parler sécurité et retour sur investissement…"},
            "agent": {"resume": "Novembre · La Tortue · posture ecoute · cours baisse", "quand": "Le bon moment pour écouter : …",
                      "ton": "Cours en baisse : … Il a besoin d'être accompagné : expliquer, étaler, garantir…", "approche": "…",
                      "eviter": ["Parler prix d'achat avant d'avoir parlé sécurité et rentabilité.", "…"],
                      "posture": "ecoute", "periode_critique": false, "cours": "baisse"},
            "cultures": [{"culture": "Vigne", "surface_ha": 12, "projet": "Nov–Déc", "achat": "Jan–Fév"}],
            "fenetres_du_mois": [{"culture": "Vigne", "genre": "projet", "surface_ha": 12}], "mois": "novembre",
            "installations": [{"nom": "Goutte à goutte vigne", "type": "Goutte à goutte de surface", "etat": "en_service",
                               "reference_pressions": {"sortie_pompe_bar": 4.2, "point_defavorable_bar": 1.3}, "equipements": ["Pompe E6S (2019)"]}],
            "interventions_ouvertes": [], "url": "/app/contacts/42"}}
```

`persona` : l'un des cinq profils de l'étude PRISM (lion, jaguar, chat, tortue, abeille) et son besoin dominant sur la pyramide
de Maslow de l'agriculteur (1 viabilité → 5 accomplissement). `frise` : la posture du mois d'après les stades de ses cultures
(écoute, support, discret, proposition), les cultures en période critique (on ne dérange pas), la tendance des cours.
`agent` : la recommandation qui croise les trois, à lire à l'assistant avant qu'il parle : quand, sur quel ton, quoi éviter.
Un client sans persona ni culture a `persona` et `frise` à `null` ; `agent` reste présent avec la posture par défaut (écoute).

## Déposer l'appel

```
POST /cultiveau/api/appel
{"numero_dedie": "+33970000001", "reference": "APL-2026-0042", "categorie": "panne",
 "urgence": "immediate", "client": {"nom": "Jean Martin", "telephone": "+33612345678", "commune": "Alès"},
 "resume": "Pompe arrêtée, vigne en véraison", "transcription": "…", "surface_ha": 0}
```

- `categorie` : `panne` → intervention (projet « Interventions » de l'adhérent) ; `devis` ou `projet` → opportunité
  (étape « Demande ») ; autre → activité « appeler » sur la fiche du client ;
- `urgence` : `immediate`, `journee`, `semaine`, `non_urgent` ;
- le client est créé s'il est inconnu (marqué « à vérifier ») ; un appel déjà déposé (même `reference`) n'est pas dupliqué.

Réponse : `{"ok": true, "type": "intervention", "id": 17, "client_id": 42, "client_cree": false, "url": "/app/action-project.action_view_all_task/17"}`.

**L'appel lui-même** est rangé dans l'ERP (menu Appels, bouton « Appels » de la fiche client) : dans le fil du client, une ligne avec
le sujet en une ou deux phrases et le lien « Voir la conversation et écouter » ; sur la fiche de l'appel, tout ce qui a été dit
(transcription complète, sans coupure), le résumé de l'assistant et le lecteur audio. Champs facultatifs :

- `sujet` : une ou deux phrases (sinon les deux premières phrases du `resume`) ;
- `duree_s`, `date` (ISO), `sens` (`entrant` ou `sortant` ; un appel passé par l'assistant ne crée pas d'activité « rappeler ») ;
- `lien_appel` : la page de l'appel dans l'assistant ;
- `audio_url` : un lien **https** signé par l'assistant vers l'enregistrement (l'audio n'est pas copié dans l'ERP : il est lu chez
  l'assistant, qui respecte la durée de conservation de l'adhérent), `audio_jusqu_au` : la date où il sera effacé ; après, le lecteur
  disparaît et la transcription reste.

## Le CRM de l'assistant dans l'ERP

```
POST /cultiveau/api/synchro
{"numero_dedie": "+33970000001", "elements": [
  {"type": "client", "reference": "CLI-12", "nom": "Jean Martin", "exploitation": "Mas Neuf", "telephone": "+33612345678",
   "telephone2": "", "email": "", "adresse": "", "commune": "Alès", "code_postal": "30100", "genre": "client", "notes": ""},
  {"type": "note", "reference": "NOTE-40", "client": "CLI-12", "texte": "Veut un second pivot.", "auteur": "Paul", "source": "dictee", "date": "2026-10-11"},
  {"type": "tache", "reference": "TAC-7", "client": "CLI-12", "titre": "Rappeler pour le devis", "detail": "", "echeance": "2026-10-20",
   "heure": "10:30", "pour_email": "paul@adherent.fr", "etat": "a_faire"},
  {"type": "equipement", "reference": "EQ-3", "client": "CLI-12", "famille": "station_pompage", "marque": "Caprari", "modele": "E6S",
   "numero_serie": "", "site": "Grandes Terres", "pose_le": "2019", "notes": "", "actif": true}]}
```

Jusqu'à 500 éléments par envoi, les clients avant ce qui s'y rattache. Chaque élément réussit ou échoue seul :
`{"ok": true, "adherent": "…", "resultats": [{"reference": "CLI-12", "ok": true, "id": 42, "cree": false, "url": "/app/contacts/42"}, …]}`.

- **client** : retrouvé par sa référence, sinon par téléphone ou e-mail chez l'adhérent (pas de doublon avec un client déjà dans
  l'ERP, qui est seulement complété), sinon créé. `genre` : client, prospect, fournisseur, partenaire, administration (→ collectivité), autre ;
- **note** : une note datée et signée dans le fil du client (une seule fois par référence) ;
- **tache** : une activité sur la fiche du client (« rendez-vous » si une heure est donnée), pour la personne dont l'e-mail est donné ;
  renvoyée avec `etat` = `fait`, elle est marquée faite dans l'ERP ; `annule` la retire ;
- **equipement** : rangé dans l'installation « Matériel connu de l'assistant » du client (parc installé), mis à jour s'il revient.

## Relier les adhérents d'un coup

```
POST /cultiveau/api/relier          (clé commune du réseau uniquement)
{"adherents": [{"numero_dedie": "+33970000001"}, …]}
```

Pour chaque numéro dédié qui correspond à un adhérent de l'ERP, une clé propre à cet adhérent (usage « Assistant », lecture et
écriture, limitée à sa société) est créée et renvoyée **une seule fois** : `{"resultats": [{"numero_dedie": "…", "trouve": true,
"adherent": "…", "cle": "cv_…"}, {"numero_dedie": "…", "trouve": false}]}`. Redemander retire l'ancienne clé « Assistant
téléphonique » de cet adhérent. L'assistant le fait chaque jour (secret `ERP_CLE_RESEAU`) : un adhérent qui passe à l'ERP y est
relié de lui-même, et tout son CRM y part.
