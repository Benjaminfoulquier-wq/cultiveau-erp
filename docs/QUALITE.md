# Qualité des données

Module `cultiveau_qualite` (07/11/2026). Menu Cultiveau › Qualité des données : un score sur 100 et, par groupe, ce qui
manque ou doublonne, pourquoi ça compte, et « Voir et corriger » qui ouvre la liste filtrée (modification en masse en vue
liste ; Action › Fusionner pour les doublons de contacts).

Contrôles (`controles()` dans `models/qualite.py`) :

- **Clients** : sans type de contact ; tous du même type (à partir de 20 clients) ; sans téléphone ni e-mail ; sans e-mail ;
  sans commune ; doublons probables (même téléphone à 9 chiffres, même e-mail, ou même nom et même commune).
- **Articles** (ceux de la société, vendables) : sans prix ; sans référence ; stockables sans fournisseur.
- **Parc installé** : en service sans pressions de référence (PV A1.3) ; sans surface ; études de plus de 60 jours sans analyse
  des besoins validée.
- **Interventions** : ouvertes sans technicien ni salarié depuis plus de 7 jours ; ouvertes sans date ; bons en brouillon depuis
  plus de 14 jours.
- **Devis** : expirés sans décision ; devis d'installation sans installation reliée.
- **Société** : compte bancaire, e-mail, logo, pourcentage d'acompte, CGV.

Ajouter un contrôle : une ligne dans `controles()` (groupe, libellé, nombre, pourquoi, modèle, domaine, contexte).
