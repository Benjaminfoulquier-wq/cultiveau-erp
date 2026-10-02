# L'API de l'ERP pour l'assistant téléphonique

Clé : en-tête `X-Cultiveau-Cle`, valeur réglée dans Cultiveau → Réglages (`cultiveau.cle_api`).

## Qui appelle ?

```
GET /cultiveau/api/client?telephone=+33612345678&numero_dedie=+33970000001
```

Réponse (client reconnu) :

```json
{"trouve": true, "adherent": "Durand Irrigation",
 "client": {"id": 42, "nom": "Jean Martin", "exploitation": "Mas Neuf", "commune": "Alès", "departement": "30",
            "persona": {"code": "fidele", "nom": "Le Fidèle", "approche": "…", "canal": "…", "moment": "…"},
            "cultures": [{"culture": "Vigne", "surface_ha": 12, "projet": "Nov–Déc", "achat": "Jan–Fév"}],
            "fenetres_du_mois": [{"culture": "Vigne", "genre": "projet", "surface_ha": 12}], "mois": "novembre",
            "installations": [{"nom": "Goutte à goutte vigne", "type": "Goutte à goutte de surface", "etat": "en_service",
                               "reference_pressions": {"sortie_pompe_bar": 4.2, "point_defavorable_bar": 1.3}, "equipements": ["Pompe E6S (2019)"]}],
            "interventions_ouvertes": [], "url": "/odoo/contacts/42"}}
```

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

Réponse : `{"ok": true, "type": "intervention", "id": 17, "client_id": 42, "client_cree": false, "url": "/odoo/action-project.action_view_all_task/17"}`.
