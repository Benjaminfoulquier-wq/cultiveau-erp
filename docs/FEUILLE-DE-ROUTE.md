# Feuille de route — ce qui rendra l'ERP plus puissant

État au 4 octobre 2026. Ce qui est en place, puis ce qui manque, dans l'ordre où le faire.

## En place

- **Le catalogue Cultiveau** : 24 755 articles (référencement + catalogue 3D), cotes DN/PN/matière/raccordement, 2 264 fiches techniques
  jointes avec leur première page en image. Commun à tout le réseau.
- **Mon catalogue** : chaque adhérent pioche dans le catalogue Cultiveau (« Ajouter à mon catalogue », à l'unité ou en masse) et importe
  ses propres articles depuis n'importe quel fichier Excel ou CSV (colonnes reconnues par leur intitulé). Ses articles restent les siens.
- **Mes clients** : import depuis n'importe quel fichier (ancien logiciel, comptable, assistant téléphonique, téléphone) ; un client connu
  est complété, jamais dupliqué ; les clients d'un adhérent ne sont pas visibles des autres.
- **Agriculteurs** : cultures et frise culturale (postures du mois, périodes critiques, cours), persona PRISM (Lion, Jaguar, Chat, Tortue,
  Abeille) et l'Agent qui dit comment aborder le client ce mois-ci.
- **Installations, devis, interventions** : le dossier de chaque site (analyse des besoins, dimensionnement, équipements), devis liés à
  l'installation, simulateur « irrigation à l'usage », interventions planifiées et registre.
- **Assistant téléphonique** : l'API donne à l'assistant la fiche du client qui appelle (frise, persona, conseil) et reçoit les appels.
- **Marque** : l'ERP est aux couleurs de Cultiveau, sans mention de l'éditeur ; déploiement en un push sur erp.cultiveau.fr.

## À faire, dans l'ordre

1. **Mise en route d'un adhérent en dix minutes.** Un assistant « Nouvel adhérent » : raison sociale, SIRET, logo, utilisateurs,
   numéro dédié de l'assistant, puis import de ses clients et de ses articles dans la foulée. Aujourd'hui ces étapes existent mais
   séparément, dans les réglages.
2. **Devis et factures au nom de l'adhérent.** Modèle PDF propre (logo et couleurs de l'adhérent, mention « membre du réseau
   Cultiveau »), conditions générales, acompte, signature en ligne du devis, relances automatiques des devis sans réponse.
3. **Tarifs et marges.** Les prix négociés par Cultiveau chez chaque fournisseur (import du tarif fournisseur Excel/PDF, mise à jour
   annuelle), la marge cible par adhérent, le prix de vente proposé automatiquement ; alerte quand un fournisseur change ses prix.
4. **Stock et achats.** Inventaire initial depuis le fichier d'articles (la colonne « stock » est lue, pas encore importée), stock
   camion par technicien, réassort automatique, et la **commande groupée réseau** : les besoins de plusieurs adhérents regroupés
   vers un fournisseur référencé.
5. **Du dimensionnement au devis.** Dans l'installation : calcul des pertes de charge, débit et pression par secteur, puis génération
   automatique de la nomenclature du devis depuis le catalogue (tubes, raccords, vannes, pompe). C'est le cœur métier.
6. **Terrain.** Planning des interventions sur calendrier, appli mobile (l'application Odoo fonctionne déjà), feuille d'intervention
   signée sur place avec photos, temps passé qui part en facturation, entretien préventif programmé depuis la frise (hivernage, remise
   en route).
7. **Campagnes au bon moment.** Segmentation par culture, persona et département ; e-mails et SMS déclenchés par la frise (« le maïs
   entre en floraison dans le Gard : proposer la vérification des pivots ») ; portail client où l'agriculteur voit ses devis, factures
   et installations.
8. **Pilotage.** Tableau de bord de l'adhérent (chiffre d'affaires, devis en cours, taux de signature, saisonnalité) et tableau de bord
   réseau pour l'équipe Cultiveau (volumes par fournisseur, adhérents actifs, catalogue réellement vendu) ; export vers le comptable.
9. **Les outils connectés dans les deux sens.** Depuis l'assistant téléphonique : créer un rendez-vous ou un devis à la fin de l'appel ;
   synchronisation automatique des clients entre l'assistant et l'ERP (plus besoin de fichier) ; DTe et DISC lisibles depuis la fiche
   de l'adhérent.
10. **Photos et visuels.** Il n'y a pas de photos produits dans le Drive : il faut une source (sites fournisseurs, dossier photos) ; en
    attendant, la première page de la fiche technique sert d'image. Catalogue 3D visuel à terme.
11. **Comptabilité.** Le plan comptable français est installé ; reste par société : journaux, TVA, import des relevés bancaires,
    rapprochement, FEC, accès du comptable externe.
12. **Exploitation et sécurité.** Sauvegarde quotidienne hors serveur, double authentification, changement des mots de passe d'origine,
    journal des accès, RGPD (export et suppression d'un client).

## Ce que ça demande à Cultiveau

- Les **tarifs négociés** par fournisseur (étape 3) et la **marge cible** conseillée.
- Un **modèle de devis** de référence (étape 2) : mentions, CGV, acompte.
- Les **règles de dimensionnement** retenues par le réseau (étape 5) : pertes de charge admissibles, vitesses, coefficients.
- Une **source de photos** (étape 10).
