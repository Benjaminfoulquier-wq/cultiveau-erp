# Mathis, l'assistant du réseau

Mathis répond déjà au téléphone pour les adhérents : c'est le standard IA (l'assistant téléphonique), qui dépose ses appels,
interventions et opportunités dans l'ERP par l'API. Le module `cultiveau_mathis` lui donne sa place dans l'ERP.

## Dedans : Mathis sur tous les écrans

- **L'icône Mathis** en haut à droite ouvre le panneau, sur n'importe quel écran. Sur la map : le bouton « Mathis » et le personnage à
  l'accueil (sa fiche montre ses derniers appels).
- **Il répond sur vos données**, avec les droits de la personne connectée (un technicien ne voit pas plus que ce qu'il voit dans l'ERP) :
  « qui est en intervention ? », « quels devis relancer ? », « il reste combien de PE 63 ? », « où en est le chantier Durand ? ».
  Ses outils sont ceux de l'API de l'ERP (résumé, lister, lire, chercher) plus ceux de la map (l'équipe en direct, le stock d'un article,
  ouvrir un écran). Il ne devine jamais un chiffre : il appelle l'outil, et dit quand il ne trouve rien.
- **Il agit avec votre accord** : créer un client, une intervention, une opportunité, ajouter une note, préparer un courriel à un client,
  enregistrer un pointage. Chaque action est d'abord une proposition dans le panneau ; rien n'est écrit avant le clic « Confirmer ».
- **Il fait tout ce que vous pouvez faire** : au-delà de ces gestes, Mathis sait trouver n'importe quel type de fiche (devis, facture,
  commande fournisseur, livraison, rendez-vous, article, congé…), lire ses champs et ses boutons, chercher, compter, puis créer, modifier
  ou appuyer sur un bouton (confirmer un devis, valider une facture, annuler). Exemple : « fais un devis de 3 vannes pour le GAEC Durand
  et confirme-le » : il propose le devis, vous confirmez, il propose de le confirmer, vous confirmez. Les garde-fous :
  - vos droits, pas plus : ce que l'ERP vous refuse dans les écrans, il le refuse à Mathis, avec le même message ;
  - rien sans votre clic : chaque écriture est une proposition lisible (le client par son nom, les lignes, le bouton par son libellé) ;
  - rien n'est supprimé : pour retirer une fiche, il l'archive ;
  - seuls les boutons de la fiche sont permis : Mathis appuie là où vous pourriez cliquer, rien d'autre ;
  - un bouton qui ouvre un écran (un courriel à relire, un assistant) l'ouvre devant vous : c'est vous qui terminez et qui envoyez ;
  - hors de portée, même pour un administrateur : les comptes d'utilisateur, les droits, les réglages techniques, les clés et mots de
    passe, les modèles de courriel, le site.
- **Il planifie les réunions** (module Réunions) : il cherche les créneaux libres de chacun et crée la réunion avec sa visio après
  confirmation.
- **Ses réponses sont cliquables** : une fiche citée ouvre l'écran correspondant. Une action peut ouvrir un écran (le tableau de bord,
  les écritures à lettrer) ou un brouillon de courriel à relire.
- Les conversations sont les vôtres (Réglages → Map vivante → Conversations avec Mathis) ; une conversation repart à zéro au-delà
  d'une soixantaine de messages, ou avec le bouton +.

## Dehors : ses appels sur la map

Quand Mathis prend un appel au téléphone, l'ERP le reçoit (API) et la map le montre en direct : notification « Appel pris par Mathis »,
le personnage décroche à l'accueil, et la fiche de l'appel (client, sujet, urgence, résumé, intervention ou opportunité créée) s'ouvre
d'un clic. Le fil d'activité le garde.

## Réglages

- Réglages → Cultiveau → **Fiches techniques et IA** : la clé Mistral. Sans elle, Mathis n'a pas de voix dans l'ERP (le panneau le dit).
- Réglages → Cultiveau → **Mathis, l'assistant** : son prénom (celui du standard, « Mathis »), le modèle (`mistral-small-latest` par
  défaut ; `mistral-medium-latest` pour des réponses plus fines, un peu plus chères).
- Coût : une question coûte une fraction de centime à quelques centimes selon les outils appelés.

## Limites

- Pour les demandes en plusieurs étapes (créer puis confirmer, chercher dans un type de fiche peu courant), le modèle
  `mistral-medium-latest` est plus sûr que `mistral-small-latest` ; dix allers-retours avec ses outils au plus par message.
- Mathis parle de ce que l'ERP sait ; pas d'accès à Internet ni à des documents extérieurs.
- Les écritures passent par les mêmes règles que l'ERP : une personne sans droit d'écriture obtient un refus clair.
- La voix (dictée, lecture) reste au téléphone ; dans l'ERP, il écrit.

## La dictée

Le bouton micro du panneau de Mathis enregistre la question (une minute au plus) ; elle est transcrite par Voxtral, le modèle
de transcription de Mistral déjà utilisé par l'assistant téléphonique (même clé), puis envoyée à Mathis. Un second appui
arrête l'enregistrement. Le navigateur demande l'autorisation du micro la première fois.
