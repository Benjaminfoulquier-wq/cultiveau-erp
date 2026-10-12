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

- Mathis parle de ce que l'ERP sait ; pas d'accès à Internet ni à des documents extérieurs.
- Les écritures passent par les mêmes règles que l'ERP : une personne sans droit d'écriture obtient un refus clair.
- La voix (dictée, lecture) reste au téléphone ; dans l'ERP, il écrit.
