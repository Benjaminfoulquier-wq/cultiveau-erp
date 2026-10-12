"""La fiche secteur de la Map vivante : le vocabulaire, les étapes du dossier, les zones, les objets, les KPI et les événements.

C'est la configuration d'un installateur d'irrigation agricole. Rien de tout cela n'est codé dans les composants : la map,
les fiches, le stepper et le scénario de démo lisent cette fiche. Un autre métier changerait cette fiche, pas le code.
"""

SECTEUR = {
    "nom": "Installateur d'irrigation agricole",
    "pays": "France", "langue": "fr", "devise": "EUR", "tva": 20.0,
    "ambiance": "atelier propre et chaleureux : enduit clair, bois, bardage, une seule couleur d'accent (celle de l'adhérent)",
    "accent_defaut": "#0b9bb8",
    # Le dossier central : l'installation d'irrigation, de la demande à l'entretien.
    "dossier": {
        "nom": "Installation", "pluriel": "Installations", "modele": "cultiveau.installation",
        "etapes": [
            {"cle": "demande", "nom": "Demande", "etats": ["projet"]},
            {"cle": "etude", "nom": "Étude", "etats": ["etude"]},
            {"cle": "devis", "nom": "Devis", "etats": []},
            {"cle": "pose", "nom": "Pose", "etats": ["realisation"]},
            {"cle": "mise_en_service", "nom": "Mise en service", "etats": []},
            {"cle": "entretien", "nom": "Entretien", "etats": ["en_service", "arretee"]},
        ],
        "objet_physique": "la parcelle irriguée (pivot, enrouleur, goutte à goutte, aspersion)",
    },
    # Les zones du site, dans l'ordre du parcours client.
    "zones": [
        {"cle": "accueil", "nom": "Accueil et comptoir", "type": "accueil", "icone": "fa-shopping-basket"},
        {"cle": "magasin", "nom": "Magasin", "type": "magasin", "icone": "fa-cubes"},
        {"cle": "stockage", "nom": "Stockage", "type": "stockage", "icone": "fa-archive"},
        {"cle": "atelier", "nom": "Atelier et SAV", "type": "atelier", "icone": "fa-wrench"},
        {"cle": "bureau", "nom": "Bureau d'étude", "type": "bureau", "icone": "fa-pencil-square-o"},
        {"cle": "reunion", "nom": "Salle de réunion", "type": "reunion", "icone": "fa-users"},
        {"cle": "administratif", "nom": "Administratif", "type": "bureau", "icone": "fa-file-text-o"},
        {"cle": "pause", "nom": "Salle de pause", "type": "pause", "icone": "fa-coffee"},
        {"cle": "parking", "nom": "Parking clients", "type": "parking", "icone": "fa-car"},
        {"cle": "cour", "nom": "Cour et dépôt extérieur", "type": "cour", "icone": "fa-truck"},
        {"cle": "champs", "nom": "Chez les agriculteurs", "type": "champs", "icone": "fa-leaf"},
    ],
    # Les rôles de l'équipe et le poste de travail qui va avec.
    "roles": [
        {"cle": "gerant", "nom": "Gérant", "zone": "administratif", "tenue": "chemise"},
        {"cle": "commercial", "nom": "Commercial / bureau d'étude", "zone": "bureau", "tenue": "chemise"},
        {"cle": "comptoir", "nom": "Comptoir", "zone": "accueil", "tenue": "polo"},
        {"cle": "technicien", "nom": "Technicien", "zone": "atelier", "tenue": "travail"},
        {"cle": "comptable", "nom": "Comptable", "zone": "administratif", "tenue": "chemise"},
    ],
    # Les statuts de présence et leur couleur.
    "statuts": {
        "au_poste": {"nom": "Au poste", "couleur": "vert"}, "en_reunion": {"nom": "En réunion", "couleur": "bleu"},
        "en_pause": {"nom": "En pause", "couleur": "ambre"}, "en_intervention": {"nom": "En intervention", "couleur": "accent"},
        "en_visio": {"nom": "En visio", "couleur": "bleu"}, "en_rendez_vous": {"nom": "En rendez-vous", "couleur": "bleu"},
        "sur_chantier": {"nom": "Sur chantier", "couleur": "accent"}, "en_route": {"nom": "En route", "couleur": "ambre"},
        "absent": {"nom": "Absent", "couleur": "ardoise"}, "pas_arrive": {"nom": "Pas encore arrivé", "couleur": "ardoise"},
        "parti": {"nom": "Parti", "couleur": "ardoise"},
    },
    # Les trois indicateurs d'en-tête.
    "kpi": [
        {"cle": "interventions", "nom": "Interventions du jour", "sous_titre": "{faites} faites · {restantes} à faire"},
        {"cle": "devis", "nom": "Devis en attente", "sous_titre": "{nombre} devis · {relancer} à relancer"},
        {"cle": "chantiers", "nom": "Chantiers en cours", "sous_titre": "{heures} h posées cette semaine"},
    ],
    # Les onglets du tableau en direct.
    "onglets": [
        {"cle": "equipe", "nom": "Équipe"}, {"cle": "camions", "nom": "Camions"}, {"cle": "dossiers", "nom": "Dossiers"}, {"cle": "clients", "nom": "Clients"}, {"cle": "stock", "nom": "Stock"},
    ],
    # Les événements du scénario de démonstration (rejoués dans les 75 premières secondes).
    "evenements_demo": [
        {"genre": "arrivee", "titre": "Arrivée au dépôt", "texte": "{personne} badge à l'entrée et rejoint son poste."},
        {"genre": "depart_intervention", "titre": "Départ en dépannage", "texte": "{personne} part chez {client} : {intervention}."},
        {"genre": "livraison", "titre": "Livraison fournisseur", "texte": "Un camion de {fournisseur} se présente à la cour."},
        {"genre": "pause", "titre": "Pause", "texte": "{personne} badge sa pause et passe à la salle de pause."},
        {"genre": "bon_signe", "titre": "Bon signé sur place", "texte": "{client} a signé le bon d'intervention : {montant} € HT."},
        {"genre": "devis_signe", "titre": "Devis signé", "texte": "{client} accepte le devis {devis} : {montant} € HT."},
    ],
    # Les notifications d'ambiance, toutes les 14 à 20 secondes.
    "ambiance": [
        "Réassort du camion de {personne} préparé", "Stock bas : {article}", "Avis client reçu : 5 étoiles pour {personne}",
        "Pièce reçue pour {intervention}", "Salle de réunion réservée à 14 h", "Relevé bancaire importé : 12 lignes rapprochées",
        "Conseil d'irrigation envoyé à {client}", "Facture {facture} payée", "Tarif fournisseur mis à jour : {fournisseur}",
    ],
}

# Les portes : ce que chaque zone de la map ouvre dans le back-office (clé de cultiveau.scene._actions, libellé, icône).
PORTES = {
    "accueil": [("comptoir", "Vente au comptoir", "fa-shopping-basket"), ("agriculteurs", "Mes clients", "fa-users"), ("agriculteur_nouveau", "Nouveau client", "fa-user-plus"),
                ("a_contacter", "À contacter ce mois-ci", "fa-phone"), ("ventes_comptoir", "Ventes au comptoir", "fa-list"), ("import_clients", "Importer mes clients", "fa-upload"),
                ("pipeline", "Demandes et opportunités", "fa-filter"), ("rendez_vous", "Rendez-vous", "fa-calendar")],
    "magasin": [("mon_catalogue", "Mon catalogue", "fa-book"), ("catalogue", "Catalogue Cultiveau", "fa-globe"), ("fiches", "Fiches techniques", "fa-file-pdf-o"),
                ("comparateur", "Comparer des articles", "fa-columns"), ("grille_remises", "Ma grille de remises", "fa-percent"), ("import_articles", "Importer des articles", "fa-upload"),
                ("occasion", "Occasion et reprises", "fa-recycle")],
    "stockage": [("inventaire", "Inventaire", "fa-archive"), ("reappro", "Règles de réassort", "fa-refresh"), ("mouvements", "Mouvements de stock", "fa-exchange"),
                 ("achats", "Commandes fournisseurs", "fa-shopping-cart"), ("achat_nouveau", "Nouvelle commande fournisseur", "fa-plus"), ("tarifs_fournisseurs", "Tarifs fournisseurs", "fa-tags"),
                 ("commandes_groupees", "Commandes groupées réseau", "fa-cubes"), ("fournisseurs", "Fournisseurs", "fa-truck")],
    "atelier": [("interventions", "Interventions", "fa-bolt"), ("depannage_nouveau", "Nouveau dépannage", "fa-plus"), ("depannages", "Dépannages en cours", "fa-wrench"),
                ("entretiens", "Entretiens et diagnostics", "fa-calendar-check-o"), ("bons", "Bons d'intervention", "fa-pencil-square-o"), ("bons_a_facturer", "Bons à facturer", "fa-euro"),
                ("contrats", "Contrats d'entretien", "fa-file-text-o"), ("equipements_a_renouveler", "Équipements à renouveler", "fa-cogs"), ("registre", "Registre des installations", "fa-book"),
                ("techniciens", "Techniciens et camions", "fa-id-badge")],
    "bureau": [("etudes", "Études en cours", "fa-pencil"), ("etude_nouvelle", "Nouvelle étude", "fa-plus"), ("installations", "Installations", "fa-leaf"), ("devis", "Devis", "fa-file-text"),
               ("devis_nouveau", "Nouveau devis", "fa-plus"), ("commandes", "Commandes", "fa-check"), ("usages", "Simulateur irrigation à l'usage", "fa-calculator"),
               ("matrice_pose", "Matrice de pose", "fa-clock-o"), ("schema3d", "Cultiveau 3D", "fa-cube")],
    "reunion": [("planning", "Planning des chantiers", "fa-calendar"), ("planning_techniciens", "Planning des techniciens", "fa-calendar-o"), ("rendez_vous", "Rendez-vous", "fa-calendar-check-o"),
                ("crm_analyse", "Analyse commerciale", "fa-bar-chart"), ("ventes_analyse", "Analyse des ventes", "fa-line-chart")],
    "administratif": [("tableau_de_bord", "Tableau de bord", "fa-dashboard"), ("factures_a_encaisser", "Factures à encaisser", "fa-euro"), ("facture_nouvelle", "Nouvelle facture", "fa-plus"),
                      ("factures", "Factures clients", "fa-file-text-o"), ("factures_fournisseurs", "Factures fournisseurs", "fa-file-o"), ("a_payer", "Fournisseurs à payer", "fa-money"),
                      ("banque_a_rapprocher", "Relevés à rapprocher", "fa-university"), ("banque_import", "Importer un relevé", "fa-upload"), ("a_lettrer", "Écritures à lettrer", "fa-link"),
                      ("lettrage_auto", "Lettrage automatique", "fa-magic"), ("tva", "Déclaration de TVA", "fa-percent"), ("bilan", "Bilan et compte de résultat", "fa-balance-scale"),
                      ("cloture", "Clôture d'exercice", "fa-lock"), ("immobilisations", "Immobilisations", "fa-building-o"), ("export_comptable", "Export pour le comptable", "fa-download"),
                      ("paiements", "Paiements", "fa-credit-card"), ("reglages", "Réglages Cultiveau", "fa-cog"), ("utilisateurs", "Utilisateurs", "fa-users"),
                      ("nouvel_adherent", "Nouvel adhérent", "fa-user-plus")],
    "pause": [("a_contacter", "Qui appeler ce mois-ci", "fa-phone"), ("cultures", "Les cultures et la frise", "fa-leaf"), ("personas", "Les personas", "fa-smile-o")],
    "parking": [("agriculteurs", "Mes clients", "fa-users"), ("clients_type", "Clients par type", "fa-sitemap"), ("a_contacter", "À contacter", "fa-phone")],
    "cour": [("receptions", "Réceptions fournisseurs", "fa-sign-in"), ("livraisons", "Livraisons", "fa-sign-out"), ("demandes_prix", "Demandes de prix", "fa-question-circle"),
             ("achats", "Commandes fournisseurs", "fa-shopping-cart"), ("commandes_groupees", "Commandes groupées", "fa-cubes")],
    "champs": [("chantiers", "Chantiers", "fa-wrench"), ("chantier_nouveau", "Nouveau chantier", "fa-plus"), ("planning", "Planning des chantiers", "fa-calendar"),
               ("parc", "Parc installé", "fa-leaf"), ("parcelles", "Parcelles et conseil d'eau", "fa-tint"), ("alertes_parcelles", "Alertes irrigation", "fa-exclamation-triangle"),
               ("ma_journee", "Ma journée (technicien)", "fa-sun-o"), ("registre", "Registre", "fa-book")],
}

ROLES_GROUPES = [  # dans l'ordre de priorité : le premier groupe trouvé donne le rôle
    ("gerant", "sales_team.group_sale_manager"), ("comptable", "account.group_account_readonly"), ("technicien", "project.group_project_user"),
    ("commercial", "sales_team.group_sale_salesman_all_leads"), ("comptoir", "sales_team.group_sale_salesman"),
]
