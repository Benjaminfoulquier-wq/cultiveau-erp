# La flotte des camions

Le module `cultiveau_flotte` s'appuie sur le module standard des véhicules.

- **Le conducteur** : chaque véhicule est relié à une personne de l'équipe ; c'est son camion sur la map.
- **Les échéances** : prochain contrôle technique, prochain entretien (à la date ou au kilométrage), contrats (assurance,
  location) avec leur date de fin. Un mois avant (ou 1 000 km avant l'entretien), le gérant a une activité, la map un signal,
  « Aujourd'hui » une tuile ; une seule alerte par échéance.
- **L'enchaînement** : un entretien enregistré (type « Entretien ») fixe le suivant un an plus tard et à l'intervalle de
  kilomètres réglé (20 000 km par défaut) ; un contrôle technique fixe le suivant deux ans plus tard.
- **Le compteur** : le conducteur le relève depuis son téléphone (page `/moi`, « Mon camion ») ; un compteur qui recule est refusé.
- **Le carburant** : les notes de frais du conducteur se rattachent à son camion ; le carburant du mois et de l'année
  s'affichent sur le véhicule et sur la map.
- **Sur la map** : la fiche du camion porte la plaque, le kilométrage, le carburant du mois et les échéances (vert, orange, rouge).
- **Mathis** : « où en sont les camions ? », « quand est le prochain contrôle technique du Master ? ».
