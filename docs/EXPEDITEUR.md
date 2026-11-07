# L'expéditeur des courriels

Module `cultiveau_expediteur` (07/11/2026). Demande de Benjamin : tout ce que l'ERP envoie (devis, commandes, factures,
conversations) part de notification@cultiveau.fr au nom de l'adhérent, ou de la boîte de l'adhérent, et tout reste écrit dans
le fil de la fiche, qui est la base de tout.

- **Réglages › Cultiveau › L'expéditeur des courriels**, par société :
  - *Par le réseau* (défaut) : `De : Durand Irrigation <notification@cultiveau.fr>`, `Répondre à : Durand Irrigation <contact@durand.fr>`
    (l'e-mail de la société ; s'il manque, l'aperçu le dit). Rien à configurer chez l'adhérent ; le serveur SMTP du réseau envoie.
  - *Par sa boîte* : la boîte partagée branchée dans Courriels › Boîtes mail (Gmail, Outlook ou SMTP) ; `De : Durand Irrigation
    <devis@durand.fr>` par son propre serveur d'envoi ; les envois sont dans ses « Envoyés ». Boîte pas connectée : le réseau prend le relais.
  - L'adresse du réseau est un paramètre (`cultiveau.expediteur_reseau`), visible de l'équipe Cultiveau.
- **Comment** : chaque `mail.mail` créé par l'ERP (envoi d'un devis, d'une facture, réponse ou message du fil, relance automatique,
  feuille de route…) reçoit à la création l'expéditeur de sa société (celle de la fiche, sinon de l'auteur, sinon la courante),
  l'adresse de réponse et le serveur d'envoi.
- **Le fil** : un courriel parti sans ligne visible dans le fil (envoi par modèle, automatique) y laisse une note « Courriel envoyé à …,
  sujet, expéditeur » après l'envoi réussi. Les messages écrits depuis le fil y sont déjà.

Non fait : l'envoi d'un message depuis la boîte personnelle d'un utilisateur (seule la boîte partagée de la société est prise).
