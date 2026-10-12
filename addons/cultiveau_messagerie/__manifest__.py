{
    "name": "Cultiveau — Messagerie : Gmail et Outlook rangés par client",
    "summary": "La boîte mail dans l'ERP : chaque courriel rangé sur son client et son dossier, trié par l'IA, suivi jusqu'à la réponse, réponse préparée par Mathis",
    "description": """
La boîte mail de l'entreprise (contact@, devis@…) ou celle de chacun, branchée en un clic :

- Gmail / Google Workspace et Outlook / Microsoft 365 par autorisation (sans mot de passe), toute autre messagerie en IMAP ;
- la relève ne touche jamais la boîte : rien n'est marqué comme lu, déplacé ou supprimé ;
- chaque courriel est rangé sur son client (adresse, puis domaine de l'entreprise) et sur son dossier (référence citée, ou
  devis, facture, intervention, chantier ouvert du client), trié par l'IA (devis, panne, facture…) et résumé ;
- une note le signale sur la fiche du client ou du document ; la map l'annonce ;
- on répond depuis l'ERP (la réponse part de la même boîte) ou depuis Gmail/Outlook (le dossier « Envoyés » est lu) ;
- sans réponse au bout de trois jours ouvrés : une activité pour le responsable, un repère rouge sur la map ;
- Mathis prépare la réponse avec le contexte du client et du dossier, à relire avant l'envoi.
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "website": "https://cultiveau.fr",
    "license": "LGPL-3",
    "depends": ["cultiveau_mathis", "cultiveau_vue3d", "google_gmail", "microsoft_outlook", "sale_management", "account", "project"],
    "data": [
        "security/ir.model.access.csv",
        "security/regles.xml",
        "data/messagerie_data.xml",
        "views/messagerie_views.xml",
    ],
    "installable": True,
    "auto_install": False,
}
