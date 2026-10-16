# Câblage : de l'étude à l'armoire, sans dessin

Le module `cultiveau_cablage` compile l'armoire de pompage et le câblage des électrovannes en un dossier d'exécution, comme
un compilateur de schémas : on décrit, on clique, le dossier sort.

## D'où ça part

Sur une installation : bouton **Câblage** (ou menu Action → « Câblage de l'armoire », ou la fiche de l'installation sur la map).
L'ERP crée le dossier depuis l'étude :

- la **pompe** du dimensionnement, arrondie à la puissance moteur normalisée au-dessus (13,2 kW calculés → moteur 15 kW) ;
- une **électrovanne par secteur**, avec une longueur de câble 24 V estimée (principale + conduite d'amenée + 20 m) ;
- une prise 16 A et l'éclairage du local ; le pilotage (programmateur, ou automate si l'étude est « pilotée ») ; la vanne maître.

On ajuste : réseau (triphasé 400 V ou monophasé 230 V), régime de neutre, source, parafoudre, autres départs (surpresseur,
pompe doseuse, filtration à contre-lavage, agitateur), longueurs de câble, démarrage imposé ou conseillé, régulation de
pression, entrées (manque d'eau, pluviomètre, compteur à impulsions). « Reprendre l'étude » recharge pompe et secteurs.

## Ce que la compilation calcule

| Quoi | Règle |
|---|---|
| Courant d'un moteur | P / (√3 · 400 · cos φ 0,85 · η 0,85) en tri, P / (230 · 0,85 · 0,85) en mono |
| Démarrage conseillé | direct ≤ 5,5 kW · étoile-triangle ≤ 30 kW · variateur au-delà, ou dès qu'on régule la pression |
| Disjoncteur moteur | la plage magnétothermique qui contient le courant, réglé au nominal |
| Contacteur / variateur | AC-3 à la puissance du moteur · variateur à la puissance normalisée au-dessus |
| Relais thermique | réglé au nominal (au nominal / √3 en étoile-triangle) |
| Section du câble | la plus petite qui tient le courant **et** la chute de tension ≤ 5 % (cuivre, PVC, conduit ou enterré) |
| Protection générale | interrupteur-sectionneur + différentiel 300 mA au calibre normalisé ≥ 1,1 × le courant total ; type B dès qu'un variateur triphasé est présent, type A sinon |
| Prise, éclairage | disjoncteur courbe C + différentiel 30 mA |
| Transformateur 24 V | les électrovannes ouvertes en même temps (+ la vanne maître) à l'appel (0,4 A chacune) + le pilotage, marge 25 %, puissance normalisée |
| Câble des électrovannes | section 0,75 à 4 mm² pour une chute ≤ 3 V à l'appel (aller + retour) |
| Programmateur | le nombre de voies normalisé ≥ secteurs + vanne maître ; au-delà de 24 ou avec des secteurs simultanés : automate |

Les **repères** suivent l'IEC 81346 : Q disjoncteurs, F protections, KM contacteurs, U variateurs, T transformateur, M moteurs,
Y électrovannes, B capteurs, S commandes, H voyants, A programmateur ou automate, X borniers.

Ce qui dépasse une règle est listé en **Points à vérifier** : chute de tension trop forte, démarrage direct d'un gros moteur,
programmateur avec des secteurs simultanés, trop de secteurs pour un programmateur.

## Ce qui sort

Quatre folios A3 paysage, avec cadre, cartouche (adhérent, client et installation, titre, dossier, indice, date, auteur) et la
mention « pré-dimensionnement à vérifier et valider par l'électricien qui réalise l'armoire » :

1. **Puissance — schéma unifilaire** : arrivée, Q0, différentiel, parafoudre, jeu de barres, chaque départ (disjoncteur, contacteur,
   étoile-triangle ou variateur, bornes, câble et chute, moteur), le transformateur de commande.
2. **Commande** : l'échelle 230 V (S0 arrêt d'urgence, S1 Auto/0/Manu, thermique, B1 manque d'eau, KA1 ordre du programmateur,
   bobine KM ou RUN du variateur ; marche manuelle ; voyants marche et défaut ; un échelon par moteur supplémentaire) et le 24 V
   (T1, A1 programmateur ou automate, une sortie par secteur, vanne maître sur MV, entrées B1 à B4, commun).
3. **Borniers** XA (puissance : L1 L2 L3 PE par départ), XB (24 V : une borne par électrovanne, la vanne maître, le commun),
   XC (entrées et capteurs).
4. **Nomenclature** repérée, avec quantités, folio et l'article du catalogue quand il existe (le nom le plus court qui porte les
   bons mots, jamais un lot).

Les folios se lisent dans l'onglet **Folios** du dossier et s'impriment en PDF (« Folios PDF »). « Joindre au dossier technique »
range le PDF dans les pièces de l'installation. Une modification (départ, électrovanne, réglage) repasse le dossier « à compiler » ;
recompiler passe l'indice à B, C… « Validé par l'électricien » fige l'indice.

## Le devis et le reste

- **Ajouter au devis** : la nomenclature devient le lot 7 « Armoire électrique et câblage » du dernier devis ouvert de l'installation
  (articles du catalogue, sinon « article à préciser ») ; réajouter remplace le lot.
- **Map** : la fiche de l'installation porte le dossier (indice, départs, électrovannes, calibre) et « Câblage de l'armoire » ;
  le bureau d'étude a la porte « Câblage des armoires ».
- **Mathis** : « où en est le câblage de l'installation du Bousquet ? », « compile le câblage » (après confirmation).

## Limites

Les règles sont celles d'une armoire de pompage classique en basse tension. Elles ne remplacent ni la note de calcul de
l'électricien, ni les exigences du distributeur (courant d'appel, puissance souscrite), ni les cas particuliers (groupe
électrogène, solaire, moteurs immergés spéciaux, très longues distances en aluminium). Le dossier le dit sur chaque folio.
