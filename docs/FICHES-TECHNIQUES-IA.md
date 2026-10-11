# Fiches techniques lues par l'IA et comparateur d'articles

Module `cultiveau_fiches`. Les 2 264 fiches techniques du catalogue sont des PDF : utiles à ouvrir, impossibles à comparer. Ce module
les lit une fois pour toutes et range ce qu'elles disent sur les articles.

## Ce que ça fait

1. **Le texte de la fiche.** Le PDF est lu tel quel (PyPDF2). S'il ne contient pas de texte (fiche scannée), l'OCR de Mistral prend
   le relais, page par page. Le texte est gardé sur la fiche (« Texte lu »).
2. **Les caractéristiques de la famille.** Chaque famille d'articles a sa liste de caractéristiques attendues, avec son unité
   (Catalogue → Familles de caractéristiques, réservé à l'équipe Cultiveau). Neuf familles sont livrées : pompes, asperseurs et
   turbines, goutte à goutte, tubes, vannes, filtration, programmateurs, enrouleurs et pivots, raccords. La famille d'une fiche se
   devine d'après son nom, sa famille catalogue et ses articles ; on peut la fixer à la main sur la fiche.
3. **La lecture.** L'IA (Mistral, réponse en JSON strict, température zéro) reçoit le texte page par page et la liste des
   caractéristiques attendues. Elle rend une entrée par référence de la gamme, chaque valeur convertie dans l'unité demandée et
   accompagnée de sa **page source**. Ce qui n'est pas dans la fiche reste vide ; une clé hors liste est ignorée.
4. **Le rangement.** Chaque article relié à la fiche reçoit les caractéristiques de sa référence (reconnue dans son nom ou son code) ;
   une fiche qui ne décrit qu'un produit sert tous ses articles. Sur l'article, l'onglet Cultiveau affiche le tableau (libellé,
   valeur, page).
5. **Le comparateur.** Dans la liste des articles, cocher deux à six articles → Action → « Comparer les articles cochés » (ou
   Catalogue → Comparer des articles). Un tableau côte à côte : les caractéristiques lues, puis DN, PN, matière, raccordement,
   fournisseur, prix d'achat net et prix de vente. Ce qui diffère est en gras sur fond jaune ; chaque valeur porte sa page ; la fiche
   s'ouvre d'un clic.
6. **La recherche.** Dans la liste des articles, le champ « Caractéristique » cherche `debit_m3h=30`, `pn_bar=10`, `matiere=PE`… et
   « Famille de caractéristiques » filtre par famille.

## Mise en route

- Réglages → Cultiveau → **Fiches techniques et IA** : coller la clé Mistral (console.mistral.ai). Sans clé, rien n'est envoyé.
- « Lire un lot maintenant » lit vingt fiches ; ensuite une tâche planifiée en lit quarante chaque nuit, en commençant par les fiches
  qui ont des articles. Le compteur des réglages suit l'avancement.
- Sur une fiche : bouton « Lire par l'IA » ; sur des articles cochés : Action → « Lire la fiche technique par l'IA ».

## Coût et limites

- Une fiche de dix pages coûte quelques centimes (texte) ; l'OCR, un peu plus. Chaque fiche n'est lue qu'une fois ; relire est un choix.
- Le texte envoyé est tronqué à 40 000 caractères (une dizaine de pages de catalogue dense) ; les tarifs de cent pages sont pour la suite.
- La lecture est aussi bonne que la fiche : un tableau de courbes de pompe sans valeurs chiffrées ne donne rien ; une valeur douteuse
  se vérifie à la page indiquée.
- L'extraction sert la comparaison, pas encore le dimensionnement : les débits et HMT lus pourront à terme guider le choix de pompe.
- Rien de personnel ne part vers Mistral : seulement le texte des fiches des fabricants.
