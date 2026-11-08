# La marque : Cultiveau, pas l'éditeur

Module : `cultiveau_marque`. Règle : nulle part dans l'ERP le nom de l'éditeur (Odoo), ses couleurs, ses illustrations ou ses liens.

Ce que le module couvre, et comment :

- **Les écrans** (`models/vues.py`) : exemples de saisie, info-bulles, libellés et textes des vues sont réécrits à l'affichage.
- **Les phrases traduites** (`models/traductions.py`) : les traductions des fichiers .po de tous les modules, côté navigateur et côté
  serveur, sont réécrites au chargement (« Odoo enverra des notifications à ce périphérique ! » devient « Cultiveau enverra… »).
  L'empreinte des traductions change avec elles : le navigateur les recharge tout seul.
- **Les textes en base** (`models/donnees.py`, appelé à chaque mise à jour par `data/marque.xml`) : aides des écrans vides, modèles de
  courriels et de SMS, menus, actions serveur, en-têtes de rapports. Les aides des devis et commandes, qui étaient une publicité de
  l'éditeur (vidéo, exemple à télécharger), sont réécrites dans les mots du réseau.
- **Les illustrations** : visages des écrans vides redessinés (`static/src/img/*.svg`), vidéo promotionnelle masquée, icônes des
  applications redessinées, icône d'écran d'accueil iPhone, favicon, logo de connexion.
- **Les polices et couleurs** : Plus Jakarta Sans et Inter, bleu nuit `#15283a`, cyan `#1d9fbd`, fond chaud `#f5f3ee`, arrondis 10 à 16 px.
- **Les courriels** : pieds de page sans « Powered by », couleurs du réseau, expéditeur notification@cultiveau.fr (module expéditeur).

Quand un écran sent encore l'éditeur : chercher d'où vient le texte (vue, traduction, base, composant JS) et étendre la couche
correspondante plutôt que corriger l'écran seul.

## Logo et portail client (07/11/2026, nuit)

- Une société sans logo porte celui de Cultiveau, jamais celui de l'éditeur (`models/logo.py` : logo par défaut, et pose à chaque
  mise à jour sur les sociétés qui n'en ont pas). Le logo de l'adhérent le remplace dès qu'il entre depuis cultiveau.fr.
- Portail client : « Généré par Cultiveau » sous le devis ou la facture, plus de logo de l'éditeur ; « The conversation is empty »
  traduit (i18n/fr_FR.po du module).

## Polices, arrondis, couleurs (08/11/2026)

« Exactement la même chose, juste des polices différentes, des choses plus arrondies que carrées et des couleurs plus jolies. » Les polices de
cultiveau.fr (Plus Jakarta Sans pour les titres, Inter pour le texte) étaient déclarées mais jamais chargées : c'était la police système qui
s'affichait. Elles sont maintenant chargées dans `web.layout` (Google Fonts, comme sur le site). Palette alignée sur celle du site : encre
#1b2735, turquoise #2a7f8f (actions, liens), turquoise clair #6ebfcc, papier #f6f4ef, or #e2b14f (compteurs). Arrondis : 14 px par défaut,
20 px pour les cartes, boutons, onglets, étiquettes et avatars en pilule ; exemples de champs en gris plus léger.
