"""Les règles électriques de l'armoire de pompage : des fonctions pures, sans base de données.

Hypothèses du métier (à valider par l'électricien qui réalise l'armoire — le dossier le rappelle) :
moteurs asynchrones cos φ 0,85 et rendement 0,85 ; câbles cuivre, isolant PVC, pose en conduit ou enterrée (trois conducteurs
chargés) ; chute de tension admise 5 % sur un départ moteur (NF C 15-100, alimentation par le réseau public) ; électrovannes
24 V AC (appel 0,4 A, maintien 0,2 A), chute admise 3 V ; démarrage direct jusqu'à 5,5 kW, étoile-triangle jusqu'à 30 kW,
variateur au-delà ou dès qu'on régule la pression.
"""
import math

COS_PHI = 0.85
RENDEMENT = 0.85
RHO_CUIVRE = 0.0225  # Ω·mm²/m à chaud
TENSIONS = {"tri": 400.0, "mono": 230.0}
# disjoncteurs moteurs magnétothermiques : plages de réglage thermique (A)
PLAGES_DISJONCTEUR_MOTEUR = [(0.63, 1), (1, 1.6), (1.6, 2.5), (2.5, 4), (4, 6.3), (6, 10), (9, 14), (13, 18), (17, 23), (20, 25), (24, 32), (30, 40), (37, 50), (48, 65),
                             (55, 70), (63, 80), (80, 100)]
# contacteurs AC-3 : puissance moteur à 400 V (kW) et courant (A)
CONTACTEURS = [(4, 9), (5.5, 12), (7.5, 18), (11, 25), (15, 32), (18.5, 40), (22, 50), (30, 65), (37, 80), (45, 95), (55, 115), (75, 150)]
VARIATEURS_KW = [0.75, 1.5, 2.2, 3, 4, 5.5, 7.5, 11, 15, 18.5, 22, 30, 37, 45, 55, 75]
# sections cuivre (mm²) et courant admissible approché (A) — PVC, 3 conducteurs chargés, conduit / enterré
SECTIONS = [(1.5, 15), (2.5, 21), (4, 28), (6, 36), (10, 50), (16, 68), (25, 89), (35, 110), (50, 134), (70, 171), (95, 207), (120, 239)]
SECTIONS_COMMANDE = [0.75, 1.0, 1.5, 2.5, 4.0]
CALIBRES_GENERAUX = [16, 20, 25, 32, 40, 50, 63, 80, 100, 125, 160, 200, 250]
TRANSFORMATEURS_VA = [50, 75, 100, 150, 250, 400]
PROGRAMMATEURS_VOIES = [4, 6, 8, 12, 16, 24, 32, 48]
EV_APPEL_A = 0.4
EV_MAINTIEN_A = 0.2
EV_CHUTE_MAX_V = 3.0
CHUTE_MAX_PCT = 5.0


def courant_moteur(kw, reseau="tri"):
    """Le courant nominal absorbé par un moteur (A)."""
    if not kw:
        return 0.0
    u = TENSIONS[reseau]
    if reseau == "tri":
        return kw * 1000 / (math.sqrt(3) * u * COS_PHI * RENDEMENT)
    return kw * 1000 / (u * COS_PHI * RENDEMENT)


def courant_resistif(kw, reseau="tri"):
    """Le courant d'une charge sans moteur (résistance, prise, éclairage)."""
    if not kw:
        return 0.0
    u = TENSIONS[reseau]
    return kw * 1000 / (math.sqrt(3) * u) if reseau == "tri" else kw * 1000 / u


def demarrage_conseille(kw, regulation=False):
    if regulation:
        return "variateur"
    if kw <= 5.5:
        return "direct"
    if kw <= 30:
        return "etoile_triangle"
    return "variateur"


def disjoncteur_moteur(courant):
    """La plage du disjoncteur moteur qui contient le courant (réglé au nominal), sinon la plus proche au-dessus."""
    for lo, hi in PLAGES_DISJONCTEUR_MOTEUR:
        if lo <= courant <= hi:
            return lo, hi
    for lo, hi in PLAGES_DISJONCTEUR_MOTEUR:
        if hi >= courant:
            return lo, hi
    return PLAGES_DISJONCTEUR_MOTEUR[-1]


def contacteur(kw, courant, reseau="tri"):
    """Le contacteur AC-3 : par la puissance en triphasé 400 V, par le courant en monophasé."""
    for p, i in CONTACTEURS:
        if (reseau == "tri" and kw <= p) or (reseau == "mono" and courant <= i):
            return p, i
    return CONTACTEURS[-1]


def variateur(kw):
    return next((p for p in VARIATEURS_KW if p >= kw), VARIATEURS_KW[-1])


def chute_tension_pct(courant, longueur_m, section, reseau="tri"):
    """La chute de tension sur un câble de cette section (en % de la tension du réseau)."""
    if not section or not courant or not longueur_m:
        return 0.0
    u = TENSIONS[reseau]
    if reseau == "tri":
        du = math.sqrt(3) * RHO_CUIVRE * longueur_m * courant * COS_PHI / section
    else:
        du = 2 * RHO_CUIVRE * longueur_m * courant * COS_PHI / section
    return du / u * 100


def section_cable(courant, longueur_m, reseau="tri", chute_max=CHUTE_MAX_PCT):
    """La plus petite section qui tient le courant et la chute de tension. Renvoie (section, chute %)."""
    for s, iz in SECTIONS:
        if courant <= iz:
            chute = chute_tension_pct(courant, longueur_m, s, reseau)
            if chute <= chute_max:
                return s, chute
    s = SECTIONS[-1][0]
    return s, chute_tension_pct(courant, longueur_m, s, reseau)


def calibre_general(courant_total):
    """Le calibre de l'interrupteur-sectionneur et de la protection générale (marge 10 %)."""
    besoin = courant_total * 1.1
    return next((c for c in CALIBRES_GENERAUX if c >= besoin), CALIBRES_GENERAUX[-1])


def section_electrovanne(longueur_m, nb_simultanees=1):
    """La section du câble 24 V d'une électrovanne (aller + retour) pour une chute de 3 V au plus à l'appel. Renvoie (section, chute V)."""
    courant = EV_APPEL_A * max(1, nb_simultanees)
    for s in SECTIONS_COMMANDE:
        chute = 2 * RHO_CUIVRE * longueur_m * courant / s
        if chute <= EV_CHUTE_MAX_V:
            return s, chute
    s = SECTIONS_COMMANDE[-1]
    return s, 2 * RHO_CUIVRE * longueur_m * courant / s


def transformateur_va(nb_simultanees=1, pilotage_va=10.0):
    """Le transformateur 230/24 V des électrovannes : les vannes ouvertes en même temps (+ la vanne maître) à l'appel, et le programmateur."""
    besoin = 24.0 * EV_APPEL_A * (nb_simultanees + 1) + pilotage_va
    return next((va for va in TRANSFORMATEURS_VA if va >= besoin * 1.25), TRANSFORMATEURS_VA[-1])


def programmateur_voies(nb_sorties):
    return next((v for v in PROGRAMMATEURS_VOIES if v >= nb_sorties), PROGRAMMATEURS_VOIES[-1])


def arrondi(v, n=1):
    return round(v + 1e-9, n)
