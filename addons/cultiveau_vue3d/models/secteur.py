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
        {"cle": "equipe", "nom": "Équipe"}, {"cle": "camions", "nom": "Camions"}, {"cle": "dossiers", "nom": "Dossiers"}, {"cle": "stock", "nom": "Stock"},
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

ROLES_GROUPES = [  # dans l'ordre de priorité : le premier groupe trouvé donne le rôle
    ("gerant", "sales_team.group_sale_manager"), ("comptable", "account.group_account_readonly"), ("technicien", "project.group_project_user"),
    ("commercial", "sales_team.group_sale_salesman_all_leads"), ("comptoir", "sales_team.group_sale_salesman"),
]
