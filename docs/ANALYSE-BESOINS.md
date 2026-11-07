# L'analyse des besoins en entretien (A1.1)

Module : `cultiveau_analyse_besoins` (dépend de `cultiveau_installation` et `cultiveau_parcelles`).

## Ce que dit le référentiel

L'analyse des besoins est la phase fondatrice (§ 3.2, p. 22). Elle porte sur cinq domaines (§ 3.2.1 à 3.2.5, p. 22 et 23)
et se restitue dans la trame A1.1 (p. 129), validée avec l'exploitant avant tout dimensionnement. La check-list des
données d'entrée (p. 23) en compte huit : parcellaire, assolement et culture de pointe, sol, ressource, titre de
prélèvement, énergie, contraintes humaines, hiérarchie eau / énergie / rendement.

## Ce que fait le module

L'onglet A1.1 de la fiche installation n'est plus une grille de champs mais **l'entretien** : huit cartes, dans l'ordre
de la visite, chacune avec la question à poser (en mots de ferme), les champs qui la rangent et le « pourquoi » avec la
section du référentiel. En tête : l'avancement (n / 8), ce qui reste à voir, et « Ses mots, en vrac » pour noter
pendant la visite et ranger après. La validation reste le bouton d'en-tête de la fiche (module installation).

**Les parcelles du client** (déclaration PAC importée par le module Parcelles) se reprennent depuis la carte 1 :

- le client a une déclaration : « Reprendre ses parcelles » ouvre le choix (les parcelles irriguées de la dernière
  campagne sont cochées) ; le projet reçoit les parcelles, la surface, les cultures, la culture la plus exigeante en
  pointe (besoin de pointe calculé pour ce client, sinon Kc de mi-saison), les lieux-dits (îlot et numéro), la commune
  (code INSEE) et l'assolement de la campagne ;
- pas de déclaration : « Importer son fichier Telepac » (l'import pose ensuite les parcelles irriguées dans le projet) ou
  « Lui demander par e-mail » (modèle du module Parcelles).

Ce que l'installateur a déjà écrit lui-même (commune, lieux-dits, assolement, culture de pointe) n'est jamais écrasé.

## Hors référentiel

L'ordre des huit questions et leur formulation sont une pratique Cultiveau, pas une prescription : le référentiel fixe
les données d'entrée et la validation avec l'exploitant, pas la manière de les recueillir.
