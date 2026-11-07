{
    "name": "Cultiveau — Le chantier en un clic",
    "summary": "Démarrer une phase sort son matériel du stock (sur la livraison de la commande, jamais deux fois) ; terminer une phase facture son jalon ; la mise en service facture le solde, clôt l'intervention, propose l'entretien",
    "description": """
Le chantier en un clic
======================

Sur le chantier, trois gestes, et tout le reste suit :

- **Démarrer la phase** : le matériel de la phase sort du stock, sur la livraison déjà créée par la commande (une seule sortie,
  le reste attend en reliquat pour les phases suivantes) ; le chantier démarre s'il ne l'était pas ;
- **Terminer la phase** : le posé se remplit, la facture du jalon se prépare ;
- **Mise en service** : le PV est enregistré, l'installation passe en service, la facture de solde se prépare, l'intervention de
  mise en service se clôt, et le commercial reçoit « proposer le contrat d'entretien » ; le matériel non posé revient au dépôt.

Avant ce module, le chantier créait son propre bon de sortie à côté de la livraison de la commande : le stock sortait deux fois.
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "website": "https://cultiveau.fr",
    "license": "LGPL-3",
    "depends": ["cultiveau_phases_devis", "cultiveau_declenche", "cultiveau_jalons", "cultiveau_crm_effort"],
    "data": ["views/views.xml"],
    "installable": True,
    "auto_install": False,
}
