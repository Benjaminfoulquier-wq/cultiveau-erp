# Rôles prêts à l'emploi et aide par écran

Module `cultiveau_roles` (07/11/2026). Les deux premières causes d'échec d'un ERP dans toutes les vidéos d'implémentation :
des droits mal posés et personne formé.

## Les rôles

Sur l'utilisateur (onglet Droits d'accès), un « Rôle Cultiveau » : gérant, administratif, technicien / poseur, magasinier,
commercial, ou réglage à la main. Le rôle pose les groupes des applications d'un coup (`GROUPES` dans `models/roles.py`) :

- gérant : ventes responsable, comptabilité responsable, achats responsable, stock responsable, projets responsable, RH, congés et
  notes de frais responsable, contacts ;
- administratif : ventes (toutes les affaires), facturation, achats, stock, projets, RH, contacts ;
- technicien : ses propres documents de vente, stock, projets (ses interventions), notes de frais ;
- magasinier : stock responsable, achats, ventes (comptoir), projets ;
- commercial : ventes (toutes les affaires), projets, stock en lecture, contacts.

Un changement de rôle remplace seulement les groupes que les rôles connaissent ; un groupe réglé à la main en dehors reste.

Depuis la fiche d'un salarié sans accès (Employés), « Lui donner un accès » crée l'utilisateur (identifiant = e-mail
professionnel) avec le rôle proposé, le relie à la fiche, et envoie l'invitation.

## L'aide par écran

Le « ? » en haut à droite ouvre l'aide de l'écran courant : en une phrase, par où commencer, un lien vers la documentation. Les
textes sont dans Réglages › Cultiveau › Aides des écrans (équipe Cultiveau), par identifiant d'action ou par modèle : map vivante,
devis, interventions, bons, chantiers, installations, clients, nomenclatures, Mes tableaux, feuilles de route, checklists,
opportunités, utilisateurs. Sans aide pour l'écran, une notification renvoie au menu Cultiveau et à Mathis.

## Un tuto par page (08/11/2026)

« Je veux un petit ? sur chaque page, on clique et on a le tuto. » Le « ? » devient un bouton visible en haut à droite (rond turquoise, « Tuto »
sur grand écran). Il reconnaît la page par l'identifiant de son action, ou par son numéro résolu côté serveur (`_xmlid_de_l_action`), sinon
par le modèle affiché, sinon il montre les gestes qui servent partout (et le dit). Le tuto a cinq parties : en une phrase, pas à pas
(numéroté), par où commencer, à ne pas faire, liens (vidéo, documentation). Cent tutos sont livrés dans `data/tutos.xml` (noupdate : vos
modifications dans Réglages › Aides des écrans sont gardées), un par page du menu Cultiveau et pour les écrans standards utiles (devis,
commandes, factures, produits, achats, inventaire, contacts, calendrier). L'ancien texte de la Map, qui pointait sur un identifiant
inexistant, est retiré à la mise à jour.
