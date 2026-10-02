"""Le questionnaire du persona : huit questions, cinq personas (voir cultiveau.persona).

Les cinq personas sont ceux de l'étude PRISM 2023 (BVA, Réussir, Agriconomie ; 1 766 chefs
d'exploitation) retenus par les Journées Cultiveau 2025 : Lion, Jaguar, Chat, Tortue, Abeille.
Les questions reprennent celles qui, dans l'étude, discriminent le mieux les cinq groupes :
le réflexe face à un problème technique (« question très discriminante »), le comportement
d'achat courant, la relation attendue avec le fournisseur, productivité ou charges, l'état
d'esprit, l'engagement et la diversification, le rapport à la technologie, les sources
d'information inspirantes.

Chaque réponse donne des points ; le plus haut l'emporte. En cas d'égalité l'ordre de priorité
tranche, et il commence par les profils prudents : une approche rassurante ne coûte rien, une
approche ambitieuse mal placée coûte le client.
"""

ORDRE = ['chat', 'tortue', 'abeille', 'jaguar', 'lion']

QUESTIONS = [
    {"code": 'probleme', "texte": "Face à un problème technique, la première chose qu'il fait", "options": [
        ('dialogue', "Il appelle quelqu'un : technicien, conseiller, collègue", {'tortue': 2, 'abeille': 2}),
        ('seul', "Il se débrouille seul, par essais, quitte à y passer du temps", {'chat': 3}),
        ('recherche', "Il cherche l'information : web, documentation, vidéos", {'jaguar': 3}),
        ('sait', "Il sait déjà ; ce sont ses collègues qui l'appellent, lui", {'lion': 3}),
    ]},
    {"code": 'achat', "texte": "Pour un achat courant (pièces, consommables)", "options": [
        ('memes', "Il reprend ce qui a fait ses preuves", {'chat': 3, 'tortue': 1}),
        ('meilleur', "Il cherche le meilleur produit du marché, sans rien exclure", {'jaguar': 3, 'lion': 1}),
        ('liste', "Il choisit dans la liste conseillée par son technicien", {'tortue': 3, 'abeille': 1}),
        ('pointe', "Il veut la nouveauté, la pointe de la technologie", {'lion': 3}),
    ]},
    {"code": 'relation', "texte": "La relation qu'il attend de son fournisseur", "options": [
        ('suivi', "Importante : il aime un suivi régulier, un interlocuteur attitré", {'tortue': 2, 'abeille': 2}),
        ('rythme', "C'est lui qui fixe le rythme : peu d'échanges, au bon moment", {'jaguar': 2, 'chat': 1}),
        ('efficace', "Ce qui compte, c'est l'efficacité et le temps gagné", {'lion': 2, 'chat': 1}),
        ('partenaire', "Un partenariat : il échange, il apprend, il partage", {'abeille': 3}),
    ]},
    {"code": 'strategie', "texte": "S'il devait choisir", "options": [
        ('productivite', "Maximiser la productivité, quitte à augmenter les charges", {'lion': 3}),
        ('charges', "Réduire les charges, quitte à perdre en productivité", {'chat': 1, 'tortue': 1, 'jaguar': 1}),
        ('autonomie', "Gagner en autonomie : dépendre moins de l'extérieur", {'jaguar': 3}),
        ('transmettre', "Sécuriser l'existant et transmettre", {'tortue': 2, 'abeille': 1}),
    ]},
    {"code": 'moral', "texte": "Son état d'esprit face à l'avenir", "options": [
        ('optimiste', "Optimiste : il a des projets", {'lion': 2, 'jaguar': 1, 'abeille': 1}),
        ('prudent', "Prudent : il attend de voir", {'tortue': 2}),
        ('inquiet', "Inquiet, voire désabusé", {'chat': 3}),
        ('entoure', "Confiant parce qu'entouré : groupe, réseau, filière", {'abeille': 3}),
    ]},
    {"code": 'engagement', "texte": "L'exploitation", "options": [
        ('base', "L'exploitation de base, sans démarche particulière", {'chat': 2, 'tortue': 2}),
        ('label', "Engagée dans une démarche qualité ou environnementale (HVE, bio, label)", {'abeille': 2, 'jaguar': 1}),
        ('diversifiee', "Diversifiée : vente directe, transformation, énergie", {'jaguar': 2, 'lion': 2}),
        ('societaire', "Plusieurs associés, des salariés, en croissance", {'lion': 3}),
    ]},
    {"code": 'techno', "texte": "Face aux nouvelles technologies (sondes, pilotage, connecté)", "options": [
        ('avance', "Il veut être en avance : il essaie en premier", {'lion': 3}),
        ('roi', "Si le retour sur investissement est démontré", {'jaguar': 3}),
        ('prouve', "Quand c'est éprouvé et que d'autres l'utilisent", {'abeille': 2, 'tortue': 1}),
        ('maitrise', "Pas convaincu : il préfère ce qu'il maîtrise", {'chat': 3}),
    ]},
    {"code": 'info', "texte": "Où il s'informe avant d'investir", "options": [
        ('internet', "Internet, vidéos, comparateurs, sites marchands", {'jaguar': 2, 'chat': 1}),
        ('presse', "Presse spécialisée, salons", {'lion': 2, 'abeille': 1}),
        ('pairs', "Son groupe, sa chambre, ses pairs, les rencontres", {'abeille': 3}),
        ('technicien', "Son technicien, son fournisseur habituel", {'tortue': 3}),
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
