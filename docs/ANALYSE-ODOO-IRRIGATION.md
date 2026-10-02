# Ce qui ne va pas dans Odoo pour l'irrigation, et ce qu'on y change

Odoo Community est un excellent socle : devis, commandes, factures, comptabilité française, CRM,
stocks, achats, e-mailing, projets, contacts, portail client. On ne réécrit rien de tout cela.
Mais Odoo est un ERP générique, pensé pour vendre des articles à des clients. Un installateur
d'irrigation vend des **projets** à des **agriculteurs**, vit de son **parc installé**, travaille au
rythme des **cultures** et dépanne en **urgence** l'été. Voici, point par point, ce qui manque ou
gêne, et le module Cultiveau qui y répond. Les références (§) renvoient au référentiel technique
Cultiveau V4.

| # | Ce qui ne va pas dans Odoo | Ce que ça coûte à l'adhérent | Ce qu'on y change | Module |
|---|---|---|---|---|
| 1 | **Pas de parc installé.** Odoo connaît des clients et des articles vendus, pas « le pivot nord de Durand, posé en 2019, pompe Caprari, PV à 5,5 bar ». | On dépanne sans référence (« on tâtonne », § 18.9), on ne sait pas quoi renouveler, on oublie l'hivernage. | L'**installation** (site d'irrigation) avec ses équipements, leur durée de vie (§ 3.9) et l'alerte de renouvellement, son registre (A1.8), ses rappels de remise en service et d'hivernage (§ 18.3, 18.5). | `cultiveau_installation` |
| 2 | **Pas de méthode de projet.** Le CRM d'Odoo va de « Nouveau » à « Gagné » ; rien n'oblige à analyser le besoin avant de chiffrer. | Des devis faits avant d'avoir compris la ressource, la puissance souscrite ou la culture de pointe : sous-dimensionnement, litiges. | Les **six phases** du référentiel comme étapes du pipeline ; l'**analyse des besoins A1.1** (huit données d'entrée, validée avec l'exploitant) et la **note de dimensionnement A1.2** (douze lignes, DFC et débit d'équipement calculés, cohérences vérifiées) tenues sur l'installation ; avertissement à la confirmation d'un devis sans A1.1 validée. | `cultiveau_installation`, `cultiveau_ventes` |
| 3 | **Le devis est une liste plate.** Un projet d'irrigation se lit par lots : station, filtration, réseau, secteurs, automatisme, pose. | Devis illisibles pour l'agriculteur et sa banque ; oublis (anti-retour, PV, formation). | **Modèles de devis par type d'installation** (goutte à goutte, aspersion, enrouleur, pivot) avec les lots et les lignes de mise en service, réception, formation ; le devis est relié à l'installation. | `cultiveau_ventes` |
| 4 | **La saison n'existe pas.** Odoo ne sait pas qu'on vend en hiver et qu'on dépanne en juillet. | On prospecte au mauvais moment, on rate la fenêtre d'achat. | La **frise culturale** : cultures de chaque client, stades et besoins en eau par département, et les deux **fenêtres commerciales** (projet, achat) ; liste « À contacter ce mois-ci » et activités créées chaque mois. | `cultiveau_frise` |
| 5 | **Les interventions sur site sont en Enterprise.** Le module Field Service n'existe pas en Community. | Les dépannages vivent sur un carnet, les pièces ne sont pas facturées, le registre n'est pas tenu. | Les tâches de projet deviennent des **interventions** : urgence, nature, installation, équipement, pièces → devis d'un clic, inscription automatique au **registre A1.8** à la clôture ; un projet « Interventions » par adhérent avec kanban et calendrier. | `cultiveau_interventions` |
| 6 | **Le catalogue se cherche par nom.** Un raccord se cherche par DN, PN, matière, raccordement ; Odoo n'a ni ces champs ni ces filtres. | 27 000 références inutilisables ; on ressaisit les devis depuis les catalogues papier. | Caractéristiques techniques et filtres sur chaque article, fiche technique liée, fournisseur avec prix et délai ; **import de la matrice** Cultiveau et du **catalogue 3D** (27 756 références). | `cultiveau_catalogue` |
| 7 | **L'agriculteur est un contact comme un autre.** Pas de département, pas de « qui est-il, comment lui parler ». | Le même discours au Bâtisseur et au Pragmatique ; relances inefficaces. | Type Cultiveau, exploitation, **département** déduit du code postal ; le **persona** (huit questions, quatre profils) avec l'approche, les arguments, le canal et le moment. | `cultiveau_base`, `cultiveau_persona` |
| 8 | **Personne ne décroche.** Odoo n'a pas de téléphonie ; l'appel de l'agriculteur se perd. | Appels manqués en saison, demandes jamais saisies. | Le **connecteur du standard IA** : l'assistant lit la fiche du client qui appelle (persona, cultures, installations, pressions de référence) et dépose l'intervention ou l'opportunité dans l'ERP, sans double saisie. | `cultiveau_connecteurs` |
| 9 | **Un réseau, pas une entreprise.** Odoo multi-sociétés demande des dizaines de réglages par société. | Chaque adhérent se configure à la main ; l'équipe Cultiveau n'a pas de vue d'ensemble. | Chaque adhérent est une société (ses devis, factures, stocks, comptabilité), l'équipe Cultiveau voit tout ; les outils du réseau (assistant, DTe, DISC, Académie) sont dans le menu ; `scripts/installer.sh` pose les modules et les réglages français d'un coup. | `cultiveau_base`, projet |
| 10 | **Trop de menus.** Un installateur de huit personnes n'a que faire de 40 applications. | Les gens n'utilisent pas l'outil. | Un seul menu **Cultiveau** : Agriculteurs, Parc installé, Interventions, Projets et ventes, Catalogue, Frise, Personas, Outils du réseau, Réglages. Le reste d'Odoo reste accessible, mais n'est pas devant. | tous |

## Ce qu'Odoo fait très bien et qu'on garde tel quel

- devis, commandes, livraisons, factures, avoirs, relances, paiements, comptabilité française (`l10n_fr`) ;
- stocks, achats et demandes de prix aux fournisseurs, réassort ;
- e-mailing (`mass_mailing`) : les newsletters, avec les filtres de la frise (« à contacter ce mois-ci », par culture, par département) comme cibles ;
- portail client : l'agriculteur signe son devis en ligne et retrouve ses factures ;
- utilisateurs, droits, multi-sociétés, sauvegardes, API XML-RPC.

## Ce qui reste à côté, volontairement

- l'**assistant téléphonique** (standard IA, temps réel) reste une application à part, reliée par le connecteur ;
- le **DTe**, le **DISC** et l'**Académie** gardent leur site : ce sont des outils d'animation du réseau, pas de gestion de l'entreprise ; leurs adresses sont dans le menu Cultiveau.

## Et ensuite

- importer dans l'ERP les clients et le parc tenus aujourd'hui dans l'assistant (export CSV → contacts, installations) ;
- enrichir la frise de référence pour les autres départements du réseau (le Gard est fourni) ;
- un rapport « A1.3 PV de mise en service » à faire signer sur tablette, et l'uniformité au champ (A1.10) saisie en 16 points.
