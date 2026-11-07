# Feuille de route des salariés (avec ou sans accès)

Module `cultiveau_feuille_route` (07/11/2026). Vu dans le webinaire Odoo « entreprise de panneaux solaires » : on planifie des
personnes qui n'ont pas de compte, elles reçoivent leur planning. Un installateur n'achète pas un accès par poseur.

- **Salariés sans accès** : une fiche Employé sans utilisateur. Champ « Salariés sans accès » sur l'intervention (avec la
  consigne pour l'équipe) et sur le chantier, à côté de l'équipe.
- **La page du jour** : Employé › onglet Feuille de route, un lien personnel `/journee/<jeton>` sans mot de passe, à envoyer
  une fois par SMS. Sur le téléphone : la journée (demain après 17 h, aujourd'hui avant), flèches veille et lendemain ; par
  ligne : heure, nature, titre, client et téléphone cliquable, installation, adresse et itinéraire Google Maps, produits à
  embarquer (pièces prévues de l'intervention), consigne, machines et accès du chantier, avec qui. « Nouveau lien » révoque
  l'ancien. Aucune autre donnée n'est visible.
- **L'e-mail de la veille** : chaque jour à 17 h 30 (heure du serveur), à chaque salarié qui a coché « Recevoir sa journée »
  et qui a quelque chose de planifié le prochain jour ouvré (le vendredi, le lundi). « Envoyer sa journée de demain » à la main.
- Menu Interventions › Feuilles de route : la liste des employés, filtre « Sans accès à l'ERP ».

Les salariés avec accès ont la même page et le même e-mail (leurs interventions par `user_ids`, leurs chantiers par équipe ou chef).
