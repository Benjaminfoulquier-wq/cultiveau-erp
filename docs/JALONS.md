# Facturation à l'avancement et besoins datés

Module `cultiveau_jalons` (07/11/2026), sur les chantiers et l'approvisionnement du devis. Idée vue dans l'industrie
construction d'Odoo 20 : les lots planifiés portent leur facturation et leurs dates de besoin matière.

- **Jalons** : chaque phase du chantier a un « Jalon (% du devis) ». Par défaut : préparation 0 %, tranchées et réseaux 30 %,
  station 30 %, essais 0 % ; avec l'acompte de 30 % à la commande il reste 10 % au solde. Le gérant règle les pourcentages dans
  Phases et heures. « Facturer » sur la phase crée la facture d'acompte du jalon (narration « Situation de travaux : phase, % »).
  Onglet Facturation à l'avancement : le plan complet (acompte, jalons, solde) avec facturé et encaissé ; « Facturer le solde »
  crée la facture finale qui déduit tous les acomptes. Au-delà de 100 %, le plan prévient.
- **Besoins datés** : le matériel du chantier se rattache à une phase (rattachement automatique à la création : pompe, filtre,
  armoire, compteur vers la station ; le reste vers les réseaux). « Besoin le » = début de la phase. L'approvisionnement du devis
  reprend cette date par article et la demande au fournisseur (date prévue de la ligne d'achat) au lieu d'aujourd'hui plus le
  délai.
