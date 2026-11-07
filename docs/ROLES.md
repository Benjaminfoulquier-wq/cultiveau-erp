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
