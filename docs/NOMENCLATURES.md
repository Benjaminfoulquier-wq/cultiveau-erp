# Nomenclatures, sous-lots et sous-totaux du devis

Module `cultiveau_ventes` (07/11/2026), avec le PDF dans `cultiveau_documents` et la présentation « par lot » dans
`cultiveau_presentation`. Demande de Benjamin : « il faut aussi pouvoir créer des nomenclatures, des sous-totaux, etc. ».

## Les nomenclatures

Une nomenclature est un ensemble d'articles prêt à poser dans un devis : une tête de secteur, la protection d'une station, un
point haut, la mise en service et la réception. Projets et ventes › Nomenclatures (ensembles).

- **Fiche** : nom, lot du devis où elle prend place, type d'installation (ou tous), ce que vaut une quantité de 1 (« par
  secteur », « par station »), description, sections du référentiel, articles. Chaque article a sa quantité, son unité, un
  libellé au devis, une note sous la ligne (une consigne du référentiel), et deux cases : **× la quantité insérée** (3 têtes =
  3 vannes ; décochée, la quantité est fixe : un compteur pour la station) et **en option** (proposé, pas posé d'office).
- **Insérer dans un devis** (bouton du devis ou de la nomenclature) : on choisit la nomenclature, la quantité d'ensembles, le
  placement (en sous-lot à la suite du devis, en nouveau lot, ou lignes seules), avec ou sans les options ; l'aperçu montre les
  quantités obtenues. Les prix viennent des tarifs et remises de la société, jamais de la nomenclature. Les lignes gardent la
  trace de leur nomenclature (compteur « Devis » sur la fiche).
- **Enregistrer en nomenclature** (bouton du devis) : un lot ou un sous-lot du devis devient une nomenclature ; « ces lignes
  valent N ensembles » divise les quantités pour revenir à l'unité. Un lot emporte ses sous-lots, un sous-lot seulement ses
  lignes. L'équipe Cultiveau peut la proposer à tout le réseau.
- **Celles du réseau** (société vide) : Protection de la station de pompage (§ 8.3, § 15.3.1), Tête de secteur (§ 6.4.2,
  § 6.4.3), Point haut et point bas du réseau, Mise en service, réception et formation (A1.3, A1.4, A1.5). Elles portent des
  articles génériques à 0 € (codes `NOM-*`) à remplacer par l'article du catalogue au devis. Chaque adhérent voit les siennes et
  celles du réseau, ne modifie que les siennes.

## Les sous-lots et les sous-totaux

- Une section ordinaire est un **lot** ; « Ajouter un sous-lot » (sous les lignes) crée une section de second niveau dans le
  lot qui la précède, en italique à l'écran. Le dimensionnement crée un sous-lot par secteur dans le lot 4.
- L'onglet **Lots et sous-totaux** du devis : par lot, le matériel, la main-d'œuvre et prestations (articles de type service),
  le sous-total HT et la part du total ; les sous-lots en dessous de leur lot ; le total.
- Le **PDF** imprime, après chaque lot ou sous-lot, « Sous-total · nom » ; quand un lot contient des sous-lots, « Total · nom
  du lot » après le dernier. La présentation « par lot » ne compte pas les sous-lots comme des lots : un seul montant par lot.
