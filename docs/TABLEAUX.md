# Tableaux de bord demandés en français

Module `cultiveau_tableaux` (07/11/2026). Les outils d'IA qui fabriquent des tableaux de bord à la demande (vus sur YouTube)
font ici partie de l'ERP, sur les données de l'adhérent, avec ses droits, sans abonnement de plus.

- **Trois choix** : un sujet (interventions, bons, devis, commandes, factures, opportunités, effort commercial, clients,
  installations, chantiers, achats), une mesure (nombre, montant, heures, kilomètres, surface…), un regroupement (technicien,
  client, nature, étape, type, commune, mois, semaine…), éventuellement un second, une période, un type de graphique. L'ERP ouvre
  la vue graphique et le tableau croisé d'Odoo avec le bon domaine et les bons regroupements. Une mesure ou un regroupement qui
  n'existe pas pour le sujet retombe sur le premier valide.
- **Mathis** a l'outil `tableau` : « montre-moi les interventions par technicien ce mois », « répartition des devis par type
  d'installation en camembert », « évolution des commandes sur douze mois en courbe, enregistre-le ». Il ouvre l'écran et, si on
  le demande, le range dans Mes tableaux.
- **Mes tableaux** (menu Cultiveau) : la liste des tableaux enregistrés, à ouvrir d'un clic, à partager avec la société ou non ;
  le formulaire fait la même chose que Mathis en trois listes déroulantes, avec l'aide des mesures et regroupements possibles.

Les sujets, mesures et regroupements sont dans `SUJETS` de `models/tableau.py` : en ajouter un, c'est une ligne.
