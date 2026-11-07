# Le devis qui en dit plus

Module : `cultiveau_devis_plus` (dépend de `cultiveau_documents`, `cultiveau_ventes`, `cultiveau_catalogue`, `sale_margin`).

## Les marges

Pour celui qui fait le devis, jamais pour le client : colonnes Achat, Marge et Taux sur chaque ligne, tableau « Marge par lot »
et avis du référentiel dans l'onglet « Marges et référentiel », marge totale sous les totaux, alerte quand la marge passe sous le
minimum de l'entreprise (Réglages › Cultiveau › Le devis qui en dit plus, 20 % par défaut). Visible des gérants, administratifs et
commerciaux (groupe « tous les documents » des ventes) ; les techniciens et magasiniers ne la voient pas. Le PDF et le portail
n'en portent aucune trace. Le prix d'achat vient du coût de l'article : pour les articles de la logistique Cultiveau, il n'est à
jour que si la synchronisation de la logistique tourne (docs/LOGISTIQUE-CATALOGUE.md).

## Les fiches techniques

À l'envoi du devis (bouton Envoyer par e-mail), les fiches techniques des matériels du devis (`cultiveau.fiche` reliée à l'article,
qu'elle vienne du Drive, de la logistique ou d'un fournisseur) partent en pièces jointes. Une fiche connue seulement par son lien
est rapatriée une fois, puis conservée. Le PDF du devis les liste ; le courriel le dit. Réglage : « Joindre les fiches techniques ».

## Le référentiel sur le devis

Des règles (`cultiveau.referentiel.avis`) : des mots cherchés dans les lignes (désignation, référence, famille), un type
d'installation, et une note qui cite la section, la page et le niveau de prescription (§ 1.4.3 du référentiel). Trois genres :

- **présence** : le matériel appelle une prescription (gaine → finesse de filtration § 14.2 ; injecteur → anti-retour § 15.3.1 ;
  pompe → marche à sec § 10.5.1 ; tube → PN et vitesses § 13.1.3 et 13.1.5 ; enrouleur, pivot, ventouses, régulateurs,
  programmateur, vannes, clapets, réseau enterré) ;
- **absence** : ce qui manque (pas de filtre en micro-irrigation § 14.3, injection sans anti-retour § 15.3.1, pas de compteur
  § 8.3, pompe sans sécurité § 10.5.1, réseau sans ventouse § 13.3.2) ;
- **toujours** : rinçage avant mise en service et hivernage (§ 13.5.2, § 18.5).

Le bouton « Relire avec le référentiel » écrit une section « Notes techniques (référentiel Cultiveau V4) » en fin de devis, une
note par avis ; un second passage remplace les notes, « Retirer les notes » les enlève. Les notes s'impriment sur le devis
et sur le portail. Les règles se complètent par entreprise ou pour le réseau (Réglages › Cultiveau › Les règles du référentiel).

Hors référentiel : le choix des mots déclencheurs est une pratique Cultiveau ; le référentiel fixe les prescriptions citées,
pas la manière de les repérer dans un devis. Un avis mal placé se corrige dans la règle, jamais en modifiant la citation.
