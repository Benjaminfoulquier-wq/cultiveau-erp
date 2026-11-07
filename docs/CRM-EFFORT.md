# Le CRM qui mesure l'effort commercial

Module `cultiveau_crm_effort` (07/11/2026). Le pipeline en six phases (§ 3.1) dit où en sont les affaires ; ce module dit ce
qu'on fait pour les faire avancer, et ne laisse plus une affaire s'endormir.

- **Types d'activités** comme sur le terrain : appel de prospection, visite R1 (découverte, A1.1), visite R2 (remise du devis et de
  la note A1.2), relance du devis, visite de chantier ou d'après-vente, reprendre contact.
- **Enchaînements** à chaque étape franchie : Analyse des besoins planifie la R1 à J+3 ; Étude planifie la R2 à J+7 ; Devis envoyé
  planifie la relance à J+7 (elle tombe dès que l'affaire avance) ; Mise en service planifie la visite d'après-vente à J+30 (proposer
  le contrat d'entretien). Jamais de doublon : une activité du même type déjà ouverte suffit.
- **Affaires oubliées** : chaque jour, les opportunités ouvertes avant la commande, sans activité planifiée et sans action depuis
  14 jours reçoivent « Reprendre contact ». Un bandeau sur la fiche compte les jours sans action.
- **Raison de perte obligatoire**, avec les vraies raisons d'un projet d'irrigation : prix, concurrent, reporté, pas de
  financement ou d'aide, pas de ressource en eau ou d'autorisation, sans réponse, l'agriculteur fait lui-même.
- **Pistes et revenus récurrents** activés pour tous à l'installation : la prospection pure (mairies, paysagistes, salons) vit dans
  les pistes, à part des opportunités ; le contrat d'entretien annuel se chiffre avec le projet (plan « Contrat d'entretien annuel »).
- **Effort commercial** (Projets et ventes › Effort commercial) : chaque activité marquée faite sur une affaire, par personne, par
  type, par mois, avec l'étape et l'issue ; pivot, graphique, liste. Vue SQL sur les messages d'activité du fil.
