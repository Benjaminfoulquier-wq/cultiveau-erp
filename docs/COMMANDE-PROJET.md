# La commande fait le projet (ce que fait Eaux Vives, pour tout le réseau)

Module `cultiveau_commande_projet` (07/11/2026). Benjamin, devant l'Odoo de Pierre Anglard (Eaux Vives Activités) : « je veux ça ».
Ce qu'il y avait sur son écran, et ce qui y répond chez nous, sans réglage :

| Chez Eaux Vives | Dans l'ERP Cultiveau |
|---|---|
| Des articles de service qui « génèrent une tâche à la commande » (montage pompe, montage mécanique, câblage, forfait mise en route) | Chaque prestation du devis devient une tâche du projet Interventions à la confirmation : heures (si l'unité est l'heure), date de sa phase, client, installation ; la mise en service déjà créée se relie à sa ligne au lieu d'être doublée. Bouton « Tâches » sur la commande. |
| « Enregistré 0 heures » | Bouton « Heures pointées » sur la commande : les pointages de ses chantiers. |
| Projet, livraison, achats, fabrication | Chantier, sorties de stock, demandes de prix : « Le devis déclenche tout ». La fabrication (station assemblée à l'atelier) n'est pas faite : à voir avec une tâche d'atelier. |
| « Calculateur de devis, dimensionnement pompage » | Le dimensionnement de l'installation (secteurs, HMT, pompe), l'import Schéma 3D, Ma pompe. |
| E-mail automatique « Demande de choix de financement », questionnaire, tâche Financement, relances 05/10 et 20/10 | Après la signature (au-dessus d'un seuil, 3 000 € HT par défaut), le questionnaire « Votre financement et votre date de pose » part au client (comptant, crédit, location, irrigation à l'usage, à conseiller ; aide demandée ; banque ; date de pose ; commentaire), une tâche « Financement » s'ouvre, une relance repart à J+15 (deux au plus), la réponse s'écrit sur la commande et dans le fil, la tâche se ferme, un appel se planifie si le client veut être accompagné, la date de pose souhaitée date le chantier. |
| Première ligne « PROJET … » avec les hypothèses et ce qui est inclus | Le bloc « PROJET » en tête des modèles de devis du réseau (à compléter). |
| « Envoyer la facture pro forma » | Activé pour tous. |
| « Sans suite ? », « Relancé le », « Clôturé » | Relances automatiques (module Documents), bouton « Sans suite » avec la raison (celles du CRM), qui perd aussi l'opportunité. |
| Thème sombre, Enterprise | Non : Odoo communautaire, à part. |

Réglages › Cultiveau › Le devis déclenche tout : les deux nouvelles cases (tâches, questionnaire) et le seuil.
