"""L'Agent (Journées Cultiveau 2025, pilier 4) : « l'IA ne remplace pas le commercial, elle l'augmente ».

Il croise les trois autres piliers pour recommander le moment et le ton :
le persona (qui est l'agriculteur), la frise (où en est sa culture : posture du mois, période
critique) et les cours (le contexte économique). Exemple du deck : viticulteur CHAT, après
vendanges, cours du vin en baisse → attendre la fin du stress, approche rassurante, fiabilité et
témoignages, ne pas parler prix tout de suite.

Logique pure (sans ORM) pour être lisible et testable ; res.partner l'appelle avec ses données.
"""

TIMING = {
    "discret": "Rester discret : ne pas solliciter. Être joignable et rapide sur l'urgence qu'il signale lui-même.",
    "ecoute": "Le bon moment pour écouter : visite, bilan de campagne, analyse des besoins (A1.1). Pas de devis avant d'avoir compris.",
    "support": "Être présent : remise en service, réglages, pièces d'usure, livraisons. Pas de nouveau projet, du service.",
    "proposition": "Le moment de proposer : bilan de la saison, puis chiffrage et planning pour la prochaine.",
}

# Ce que chaque persona a besoin d'entendre quand les cours baissent ou montent (pilier 3 lu à travers le pilier 1).
TON_PERSONA = {
    ("lion", "baisse"): "Même en baisse, il veut avancer : parler efficacité et avantage concurrentiel, pas repli.",
    ("lion", "hausse"): "Il est dans son élément : solutions premium, performance, être le premier équipé.",
    ("jaguar", "baisse"): "Le ROI d'abord : chiffrer l'eau et l'énergie économisées, l'échelonnement, la valeur résiduelle.",
    ("jaguar", "hausse"): "Un bon deal reste un bon deal : comparatif chiffré, options qui rapportent, pas de superflu.",
    ("chat", "baisse"): "Rassurer : fiabilité, matériel connu, témoignages de voisins ; ne pas parler prix tout de suite.",
    ("chat", "hausse"): "Même quand ça va mieux, il n'aime pas changer : proposer l'amélioration de l'existant, pas la rupture.",
    ("tortue", "baisse"): "Il a besoin d'être accompagné : expliquer, étaler, garantir ; c'est son technicien qui le rassure.",
    ("tortue", "hausse"): "Lui proposer ce que son technicien recommande, avec le suivi dans la durée.",
    ("abeille", "baisse"): "Parler sens et collectif : économies d'eau, durabilité, ce que font les autres membres du groupe.",
    ("abeille", "hausse"): "Il investit pour durer : technologie éprouvée, formation, partage d'expérience avec ses pairs.",
}


def recommander(persona, situation):
    """persona : dict {code, name, approche, arguments, pieges, canal} ou None ;
    situation : dict de res.partner.cultiveau_situation (posture, critique, critiques, cours, ton, mois).
    Renvoie {"timing", "ton", "approche", "eviter": [..], "resume"}."""
    posture = situation.get("posture") or "ecoute"
    cours = situation.get("cours") or "stable"
    critiques = situation.get("critiques") or []
    eviter = []
    if critiques:
        timing = f"Attendre : {', '.join(critiques)} en période critique ce mois-ci. Reprendre contact à la fin du stade, pas avant."
        eviter.append("Toute relance commerciale pendant la période critique.")
    else:
        timing = TIMING[posture]
    if posture == "discret" and not critiques:
        eviter.append("Les propositions et les relances en pleine saison.")
    ton = situation.get("ton") or ""
    if persona:
        ton_persona = TON_PERSONA.get((persona.get("code"), cours))
        if ton_persona:
            ton = f"{ton} {ton_persona}"
        if cours == "baisse":
            eviter.append("Parler prix d'achat avant d'avoir parlé sécurité et rentabilité.")
        approche = persona.get("approche") or ""
        if persona.get("pieges_texte"):
            eviter.extend(persona["pieges_texte"])
    else:
        approche = "Persona inconnu : huit questions depuis la fiche suffisent. En attendant, écouter avant de proposer."
    nom = persona.get("name") if persona else "persona non évalué"
    resume = f"{situation.get('mois', '').capitalize()} · {nom} · posture {posture}" + (" (période critique)" if critiques else "") + f" · cours {cours}"
    return {"timing": timing, "ton": ton.strip(), "approche": approche, "eviter": eviter, "resume": resume,
            "posture": posture, "cours": cours, "critique": bool(critiques)}
