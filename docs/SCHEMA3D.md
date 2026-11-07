# Schéma 3D vers devis

Module `cultiveau_schema3d` (07/11/2026). L'installateur dessine son réseau dans Réseau 3D (schema3d.cultiveau.fr), exporte
l'étude au **format d'échange Cultiveau** (menu Projet › Format d'échange, fichier `.echange.json`, schéma `cultiveau-echange`),
et l'ERP en fait l'analyse des besoins, la note de dimensionnement et le devis par lots. Le plan dessiné devient le devis : plus
de ressaisie des longueurs et des pièces.

## Où

- Parc installé › une installation › bouton **Importer l'étude Schéma 3D** (le client et l'installation sont pré-remplis).
- Projets et ventes › **Importer une étude Schéma 3D** (on choisit le client ; sans installation, une est créée au nom du
  projet, à l'état « Étude et dimensionnement », le type d'installation deviné d'après la nomenclature).

Dès que le fichier est choisi, l'assistant résume ce qu'il contient : date et version de l'export, exploitant et concepteur,
objets du schéma et mètres de conduites, lignes de nomenclature par lot, non-conformités du contrôle avant émission.

## Ce que l'import fait

1. **Le fichier reste au dossier** : pièce jointe de l'installation (contenu minimal du dossier technique, § 3.10.1 : plans,
   note de dimensionnement).
2. **A1.1 et A1.2** : les champs encore vides de l'installation reçoivent les valeurs des trames `conception.analyse_des_besoins`
   et `conception.note_dimensionnement` (surface, ressource, débit mobilisable, volume autorisé, énergie et kVA, automatisme,
   hiérarchie des enjeux, besoin de pointe, DFC, temps de fonctionnement, débit d'équipement, pression de service, diamètres et
   vitesses, HMT, pompe, filtration ; les pertes de charge sont la somme des conduites). Chaque valeur est notée dans le fil avec
   son origine (déclaration, conception, calcul, constructeur) et sa source. « Écraser les valeurs déjà saisies » pour une étude
   mise à jour. Les cases « absence » du format (A8.5) ne remplissent rien.
3. **Le fil raconte** : résultats de la note de calcul (HMT, vitesse, kWh/m³, dans ou hors tolérance, estimés), non-conformités
   à lever avant la commande (§ 3.5), hypothèses, avertissements de Réseau 3D.
4. **Le devis par lots** (`cultiveau_schema3d` coché sur le devis, origine « Schéma 3D · installation ») :
   - la nomenclature vient de `nomenclature.lignes` (schéma 1.2.0 et plus : le tableau de Réseau 3D regroupé par référence et
     unité, raccords générés compris) ; un export plus ancien est reconstitué depuis `installation.objets` (conduites au mètre,
     un équipement par objet, raccords non comptés, l'assistant le dit) ;
   - **famille → lot** : Pompage, Mesure, Électricité et régulation → Lot 1 station ; Filtration → Lot 2 ; Tuyaux et raccords,
     Fixation → Lot 3 réseau (deux sous-lots : Conduites au mètre, puis Raccords, vannes et pièces) ; Goutte à goutte, Pivots,
     Enrouleurs, Aspersion → Lot 4 secteurs ; Automatisme, Traitement de l'eau → Lot 5 ; sans famille, les mots du libellé
     décident (pompe, filtre, programmateur, goutteur…), puis le type de ligne ;
   - **rapprochement du catalogue** : l'article de la société puis du réseau dont le code est la référence du fabricant, sinon
     celui dont un fournisseur porte cette référence, sinon par la fiche technique (identifiant Drive) et le DN ; trouvé, la
     ligne prend l'article et son prix (tarifs et remises de la société) ; sinon « Article à préciser » à 0 €, avec la
     désignation, le fournisseur et la référence dans le libellé ;
   - **Lot 6 pose** (optionnel) : la tranchée au mètre d'après les conduites du schéma, puis la nomenclature du réseau « Mise en
     service, réception et formation » (rinçage et essais, PV A1.3, certificat A1.4, fiche A1.5 et formation).
   Le fil du devis donne le compte des lignes reconnues et à préciser, et rappelle les non-conformités.

## Limites

- Les prix ne viennent jamais de Réseau 3D : ce sont ceux de l'ERP (catalogue, tarifs négociés, grille de remises).
- Une étude réimportée crée un nouveau devis ; l'installation garde l'identifiant Réseau 3D (`schema3d_uid`) et la date du dernier import.
- Pas encore d'envoi direct de Réseau 3D vers l'ERP : on télécharge le fichier, on l'importe. Le bouton « Envoyer à l'ERP » est la suite.
