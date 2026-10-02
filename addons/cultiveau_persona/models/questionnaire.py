"""Le questionnaire du persona : huit questions, quatre personas (voir cultiveau.persona).

Chaque réponse donne des points ; le plus haut l'emporte (ordre de priorité en cas d'égalité).
"""

ORDRE = ['batisseur', 'pilote', 'fidele', 'pragmatique']

QUESTIONS = [
    {"code": 'surface', "texte": "Taille de l'exploitation", "options": [
        ('petite', 'Moins de 20 ha', {'fidele': 2, 'pragmatique': 1}),
        ('moyenne', '20 à 80 ha', {'pragmatique': 1, 'fidele': 1}),
        ('grande', '80 à 200 ha', {'batisseur': 1, 'pilote': 1}),
        ('tres_grande', 'Plus de 200 ha', {'batisseur': 2, 'pilote': 1}),
    ]},
    {"code": 'relation', "texte": 'Ancienneté de la relation', "options": [
        ('nouveau', 'Nouveau contact ou prospect', {'pragmatique': 1}),
        ('occasionnel', 'Achète de temps en temps', {'pragmatique': 2}),
        ('regulier', 'Client régulier', {'fidele': 2}),
        ('historique', "Client historique, recommande l'entreprise", {'fidele': 3}),
    ]},
    {"code": 'priorite', "texte": "Ce qui compte d'abord quand il achète", "options": [
        ('prix', 'Le prix', {'pragmatique': 3}),
        ('delai', 'La disponibilité et la rapidité', {'pragmatique': 2, 'fidele': 1}),
        ('technique', 'La performance technique', {'pilote': 3, 'batisseur': 1}),
        ('conseil', 'Le conseil et la confiance', {'fidele': 3, 'batisseur': 1}),
    ]},
    {"code": 'materiel', "texte": "Son matériel aujourd'hui", "options": [
        ('ancien', 'Ancien, à remplacer', {'batisseur': 2, 'pragmatique': 1}),
        ('entretenu', 'Fonctionnel, on entretient', {'fidele': 2, 'pragmatique': 1}),
        ('recent', 'Récent', {'fidele': 1, 'pilote': 1}),
        ('automatise', 'Automatisé, piloté', {'pilote': 3}),
    ]},
    {"code": 'horizon', "texte": 'Son horizon', "options": [
        ('saison', 'Passer la saison, dépanner', {'pragmatique': 3}),
        ('renouveler', 'Renouveler dans un à deux ans', {'fidele': 1, 'batisseur': 1, 'pragmatique': 1}),
        ('structurant', 'Un projet structurant (forage, réseau, pivot, bassin)', {'batisseur': 3}),
        ('veille', 'Veille technologique, essais', {'pilote': 3}),
    ]},
    {"code": 'decision', "texte": 'Comment il décide', "options": [
        ('seul_vite', 'Seul, vite', {'pragmatique': 2}),
        ('devis', 'Après comparaison de plusieurs devis', {'batisseur': 2, 'pragmatique': 1}),
        ('conseiller', 'Avec son conseiller, sa coopérative, sa chambre', {'batisseur': 2, 'fidele': 1}),
        ('demo', 'Après une démonstration ou un essai', {'pilote': 2, 'fidele': 1}),
    ]},
    {"code": 'canal', "texte": "Comment il préfère qu'on le contacte", "options": [
        ('telephone', 'Téléphone', {'pragmatique': 1, 'fidele': 1}),
        ('sms', 'SMS ou WhatsApp', {'pragmatique': 2}),
        ('mail', 'E-mail, avec les documents', {'pilote': 2, 'batisseur': 1}),
        ('visite', 'Une visite sur place', {'fidele': 2, 'batisseur': 1}),
    ]},
    {"code": 'pilotage', "texte": "Son rapport au pilotage de l'irrigation", "options": [
        ('non', 'Pas intéressé', {'pragmatique': 2, 'fidele': 1}),
        ('curieux', 'Curieux, pas encore équipé', {'pilote': 1, 'batisseur': 1}),
        ('equipe', 'Déjà équipé (sondes, programmateur)', {'pilote': 2}),
        ('connecte', 'Veut tout connecter et suivre à distance', {'pilote': 3}),
    ]},
]


def selection(code):
    return [(o[0], o[1]) for q in QUESTIONS if q["code"] == code for o in q["options"]]


def scorer(reponses):
    """reponses : {code_question: code_option}. Renvoie (code_persona, scores)."""
    scores = {c: 0 for c in ORDRE}
    for q in QUESTIONS:
        choix = reponses.get(q["code"])
        for code, _libelle, points in q["options"]:
            if code == choix:
                for c, n in points.items():
                    scores[c] += n
    meilleur = max(ORDRE, key=lambda c: (scores[c], -ORDRE.index(c)))
    return meilleur, scores
