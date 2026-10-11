"""Dessine les portraits animés des clients (un véhicule par type) dans cultiveau_base/static/src/img/clients/.

Animation en SMIL (balises <animate>) et non en CSS : le serveur envoie les images avec « Content-Security-Policy:
default-src 'none' », qui bloque les styles internes mais pas SMIL. Le véhicule arrive en roulant, freine (le nez plonge,
un peu de poussière), puis vit : fumée, gyrophare, vagues, feuillage, reflet sur les vitres, nuage qui passe.

    python3 scripts/dessiner_vehicules.py
"""
import os

ICI = os.path.dirname(os.path.abspath(__file__))
SORTIE = os.path.join(ICI, "..", "addons", "cultiveau_base", "static", "src", "img", "clients")
SOL = 140          # la route
ARRIVEE = 1.25     # durée de l'arrivée (s)
ECHELLE = 0.8      # taille du véhicule dans la vignette


def a(attr, valeurs, dur, debut="0s", temps=None, courbes=None, fin="freeze", repete=None, mode=None):
    """Une balise <animate>."""
    s = f"<animate attributeName='{attr}' values='{valeurs}' dur='{dur}s' begin='{debut}'"
    if temps:
        s += f" keyTimes='{temps}'"
    if courbes:
        s += f" calcMode='spline' keySplines='{courbes}'"
    elif mode:
        s += f" calcMode='{mode}'"
    s += f" repeatCount='{repete}'" if repete else f" fill='{fin}'"
    return s + "/>"


def t(type_, valeurs, dur, debut="0s", temps=None, courbes=None, repete=None, somme=False):
    """Une balise <animateTransform>."""
    s = f"<animateTransform attributeName='transform' type='{type_}' values='{valeurs}' dur='{dur}s' begin='{debut}'"
    if temps:
        s += f" keyTimes='{temps}'"
    if courbes:
        s += f" calcMode='spline' keySplines='{courbes}'"
    if somme:
        s += " additive='sum'"
    s += f" repeatCount='{repete}'" if repete else " fill='freeze'"
    return s + "/>"


def roue(cx, cy, r, jante="#d9dee3", pneu="#2b2f33"):
    """Une roue qui tourne pendant l'arrivée puis s'arrête (on voit les trous de la jante tourner)."""
    trous = "".join(
        f"<circle cx='{cx + r * 0.36 * __import__('math').cos(k * 1.2566):.1f}' cy='{cy + r * 0.36 * __import__('math').sin(k * 1.2566):.1f}' "
        f"r='{r * 0.1:.1f}' fill='{pneu}' opacity='0.55'/>" for k in range(5))
    return (f"<g><circle cx='{cx}' cy='{cy}' r='{r}' fill='{pneu}'/>"
            f"<circle cx='{cx}' cy='{cy}' r='{r * 0.6:.1f}' fill='{jante}'/>"
            f"<circle cx='{cx}' cy='{cy}' r='{r * 0.6:.1f}' fill='none' stroke='#ffffff' stroke-opacity='0.5' stroke-width='1'/>"
            + trous +
            f"<circle cx='{cx}' cy='{cy}' r='{r * 0.16:.1f}' fill='{pneu}'/>"
            + t("rotate", f"0 {cx} {cy};900 {cx} {cy}", ARRIVEE, courbes="0.15 0.55 0.35 1") + "</g>")


def passage(cx, r):
    """L'ombre du passage de roue."""
    return f"<circle cx='{cx}' cy='{SOL - r}' r='{r + 3}' fill='#000000' opacity='0.18'/>"


def reflet(chemin):
    """Un reflet qui balaie la vitre toutes les cinq secondes."""
    return (f"<clipPath id='vitre'><path d='{chemin}'/></clipPath>"
            f"<g clip-path='url(#vitre)'><rect x='-40' y='40' width='14' height='90' fill='#ffffff' opacity='0.65' transform='skewX(-25)'>"
            + a("x", "-40;220;220", 5, debut=f"{ARRIVEE + 0.2}s", temps="0;0.2;1", repete="indefinite") + "</rect></g>")


def gradient(id_, haut, bas):
    return f"<linearGradient id='{id_}' x1='0' y1='0' x2='0' y2='1'><stop offset='0' stop-color='{haut}'/><stop offset='1' stop-color='{bas}'/></linearGradient>"


def nuage(y, debut, dur, couleur="#ffffff"):
    return (f"<g opacity='0.85'><g><circle cx='0' cy='{y}' r='7' fill='{couleur}'/><circle cx='9' cy='{y - 4}' r='9' fill='{couleur}'/>"
            f"<circle cx='19' cy='{y}' r='7' fill='{couleur}'/><rect x='0' y='{y}' width='19' height='7' fill='{couleur}'/>"
            + t("translate", "-30 0;200 0", dur, debut=debut, repete="indefinite") + "</g></g>")


def svg(fond_haut, fond_bas, decor, vehicule, details_fixes="", ralenti=False):
    """Assemble le portrait : fond, décor, route, véhicule qui arrive, ombre, vitesse, poussière."""
    ralenti_g = (t("translate", "0 0;0 -0.9;0 0", 0.5, debut=f"{ARRIVEE}s", repete="indefinite") if ralenti else "")
    vitesse = "".join(f"<rect x='{x}' y='{y}' width='{w}' height='3' rx='1.5' fill='#ffffff'/>" for x, y, w in ((-4, 92, 18), (-12, 104, 24), (0, 116, 14)))
    poussiere = "".join(
        f"<circle cx='{x}' cy='{SOL - 3}' r='0' fill='#c8b89a'>"
        + a("r", f"0;{rr};{rr + 2}", 0.7, debut=f"{ARRIVEE * 0.62:.2f}s")
        + a("opacity", "0.8;0.5;0", 0.7, debut=f"{ARRIVEE * 0.62:.2f}s")
        + a("cx", f"{x};{x - 10};{x - 16}", 0.7, debut=f"{ARRIVEE * 0.62:.2f}s") + "</circle>"
        for x, rr in ((40, 5), (48, 4), (118, 4)))
    return (
        "<?xml version='1.0' encoding='UTF-8'?>\n"
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 180 180' width='180' height='180'>"
        "<defs>" + gradient("fond", fond_haut, fond_bas) +
        "<clipPath id='cadre'><rect width='180' height='180' rx='30'/></clipPath>"
        "<radialGradient id='ombre'><stop offset='0' stop-color='#000000' stop-opacity='0.28'/><stop offset='1' stop-color='#000000' stop-opacity='0'/></radialGradient>"
        "</defs>"
        "<g clip-path='url(#cadre)'>"
        "<rect width='180' height='180' fill='url(#fond)'/>"
        + nuage(30, "0s", 22) + nuage(52, "-11s", 30) + decor +
        f"<rect x='0' y='{SOL}' width='180' height='40' fill='#ffffff' opacity='0.45'/>"
        f"<rect x='0' y='{SOL}' width='180' height='2' fill='#ffffff' opacity='0.8'/>"
        # réduit autour du milieu de la route : la vignette des cartes recadre l'image, le véhicule doit y tenir entier
        + f"<g transform='translate({90 * (1 - ECHELLE):.1f} {SOL * (1 - ECHELLE):.1f}) scale({ECHELLE})'>"
        + poussiere +
        "<g>" + t("translate", "-205 0;7 0;-2 0;0 0", ARRIVEE, temps="0;0.72;0.88;1",
                  courbes="0.2 0.65 0.35 1;0.45 0 0.55 1;0.45 0 0.55 1") +
        f"<ellipse cx='90' cy='{SOL + 1}' rx='70' ry='6' fill='url(#ombre)'/>"
        "<g opacity='0'>" + a("opacity", "0;0.9;0;0", ARRIVEE, temps="0;0.3;0.7;1") + vitesse + "</g>"
        # le nez plonge au freinage puis la caisse se redresse
        "<g>" + t("rotate", f"0 90 {SOL};0 90 {SOL};2.6 90 {SOL};-1.2 90 {SOL};0 90 {SOL}", ARRIVEE + 0.25,
                  temps="0;0.55;0.72;0.86;1", courbes="0 0 1 1;0.3 0 0.6 1;0.4 0 0.6 1;0.4 0 0.6 1") +
        "<g>" + ralenti_g + vehicule + "</g></g></g></g>"
        + details_fixes +
        "</g></svg>\n")


# ------------------------------------------------------------------ les véhicules

def fourgon(haut, bas, vitre="#bfe3f4", galerie="", logo="", feux=True):
    """Fourgonnette type Partner / Berlingo, de profil, nez à droite."""
    r = 13
    c = (f"<defs>{gradient('caisse', haut, bas)}{gradient('verre', '#e9f7fd', vitre)}</defs>"
         + galerie +
         f"<path d='M30 {SOL - 18} V80 Q30 66 44 66 H104 Q111 66 116 71 L136 92 H147 Q155 93 155 101 V{SOL - 18} Z' fill='url(#caisse)'/>"
         f"<path d='M30 {SOL - 18} V80 Q30 66 44 66 H104 Q111 66 116 71 L136 92 H147 Q155 93 155 101 V{SOL - 18} Z' fill='none' stroke='#000000' stroke-opacity='0.12' stroke-width='1.5'/>"
         f"<path d='M102 72 H110 Q113 72 115 74 L131 92 H102 Z' fill='url(#verre)'/>"
         + reflet("M102 72 H110 Q113 72 115 74 L131 92 H102 Z") +
         f"<path d='M98 70 V{SOL - 19} M136 93 V{SOL - 19}' stroke='#000000' stroke-opacity='0.15' stroke-width='1.2'/>"
         "<rect x='103' y='98' width='8' height='2.5' rx='1.2' fill='#000000' opacity='0.3'/>"
         "<path d='M128 88 h6 v6 h-4 z' fill='#2b2f33' opacity='0.8'/>"
         + logo +
         f"<rect x='26' y='{SOL - 24}' width='10' height='7' rx='2' fill='#3a3f45'/><rect x='144' y='{SOL - 24}' width='13' height='7' rx='2' fill='#3a3f45'/>"
         + ("<rect x='150' y='97' width='6' height='6' rx='2' fill='#fff3b0'>" + a("fill", "#fff3b0;#ffffff;#fff3b0", 0.5, debut=f"{ARRIVEE * 0.7:.2f}s") + "</rect>"
            "<rect x='29' y='80' width='4' height='9' rx='1.5' fill='#e5533d'/>" if feux else "")
         + passage(56, r) + passage(128, r) + roue(56, SOL - r, r) + roue(128, SOL - r, r))
    return c


def tracteur():
    R, r = 25, 14
    fumee = "".join(
        f"<circle cx='117' cy='44' r='3' fill='#9aa3ab' opacity='0'>"
        + a("cy", "44;20", 1.8, debut=f"{ARRIVEE + k * 0.6:.1f}s", repete="indefinite")
        + a("r", "3;8", 1.8, debut=f"{ARRIVEE + k * 0.6:.1f}s", repete="indefinite")
        + a("cx", "117;111", 1.8, debut=f"{ARRIVEE + k * 0.6:.1f}s", repete="indefinite")
        + a("opacity", "0.7;0", 1.8, debut=f"{ARRIVEE + k * 0.6:.1f}s", repete="indefinite") + "</circle>" for k in range(3))
    return (f"<defs>{gradient('caisse', '#3fae4c', '#25803a')}{gradient('verre', '#eaf8ff', '#a9dcf1')}</defs>"
            + fumee +
            "<rect x='114' y='46' width='6' height='36' rx='2' fill='#3a3f45'/><rect x='113' y='44' width='8' height='4' rx='1.5' fill='#2b2f33'/>"
            "<path d='M48 86 V44 Q48 36 56 36 H96 Q104 36 104 44 V86 Z' fill='url(#caisse)'/>"
            "<path d='M55 82 V46 Q55 42 59 42 H93 Q97 42 97 46 V82 Z' fill='url(#verre)'/>"
            + reflet("M55 82 V46 Q55 42 59 42 H93 Q97 42 97 46 V82 Z") +
            "<path d='M76 42 V82' stroke='#25803a' stroke-width='3'/>"
            "<rect x='44' y='32' width='64' height='6' rx='3' fill='#25803a'/>"
            "<path d='M38 86 H128 Q146 86 150 98 L152 112 H38 Z' fill='url(#caisse)'/>"
            "<path d='M108 90 h36 M110 96 h38 M112 102 h38' stroke='#1d6a2f' stroke-width='2.2' stroke-linecap='round'/>"
            "<rect x='146' y='92' width='7' height='6' rx='2' fill='#fff3b0'/>"
            "<rect x='36' y='108' width='120' height='7' rx='3.5' fill='#1d6a2f'/>"
            "<rect x='150' y='112' width='8' height='12' rx='2' fill='#3a3f45'/>"
            + f"<path d='M28 112 A30 30 0 0 1 88 112 Z' fill='#1d6a2f'/>"
            + roue(58, SOL - R, R, jante="#f4c542") + roue(136, SOL - r, r, jante="#f4c542"))


def berline():
    r = 14
    return (f"<defs>{gradient('caisse', '#4b8af0', '#1f55c0')}{gradient('verre', '#eef8ff', '#a8d6f2')}</defs>"
            f"<path d='M22 {SOL - 16} V108 Q22 99 31 98 L56 95 L73 78 Q78 73 86 73 H118 Q125 73 130 78 L144 94 L157 97 Q164 99 164 106 V{SOL - 16} Z' fill='url(#caisse)'/>"
            f"<path d='M22 {SOL - 16} V108 Q22 99 31 98 L56 95 L73 78 Q78 73 86 73 H118 Q125 73 130 78 L144 94 L157 97 Q164 99 164 106 V{SOL - 16} Z' fill='none' stroke='#000000' stroke-opacity='0.12' stroke-width='1.5'/>"
            "<path d='M62 94 L76 80 Q79 78 83 78 H99 V94 Z M103 78 H118 Q122 78 125 81 L137 94 H103 Z' fill='url(#verre)'/>"
            + reflet("M62 94 L76 80 Q79 78 83 78 H99 V94 Z M103 78 H118 Q122 78 125 81 L137 94 H103 Z") +
            f"<path d='M101 76 V{SOL - 17} M60 96 V{SOL - 17}' stroke='#000000' stroke-opacity='0.15' stroke-width='1.2'/>"
            "<rect x='88' y='100' width='8' height='2.5' rx='1.2' fill='#000000' opacity='0.3'/><rect x='126' y='100' width='8' height='2.5' rx='1.2' fill='#000000' opacity='0.3'/>"
            f"<rect x='20' y='{SOL - 24}' width='146' height='5' fill='#1a479f'/>"
            "<rect x='156' y='101' width='8' height='6' rx='2' fill='#fff3b0'>" + a("fill", "#fff3b0;#ffffff;#fff3b0", 0.5, debut=f"{ARRIVEE * 0.7:.2f}s") + "</rect>"
            "<rect x='22' y='102' width='6' height='6' rx='2' fill='#e5533d'/>"
            "<path d='M136 90 h5 v5 h-4 z' fill='#1a479f'/>"
            + passage(54, r) + passage(134, r) + roue(54, SOL - r, r) + roue(134, SOL - r, r))


def plateau(cabine_haut, cabine_bas, chargement, gyrophare=False, bande=False):
    r = 13
    gyro = ""
    if gyrophare:
        gyro = ("<rect x='128' y='54' width='12' height='4' rx='1.5' fill='#3a3f45'/>"
                "<path d='M129 54 V49 Q129 45 134 45 Q139 45 139 49 V54 Z' fill='#f39a2b'>"
                + a("fill", "#f39a2b;#ffd27a;#f39a2b", 0.6, debut="0s", repete="indefinite") + "</path>"
                "<circle cx='134' cy='49' r='6' fill='#ffb347' opacity='0'>"
                + a("r", "5;14", 0.6, repete="indefinite") + a("opacity", "0.55;0", 0.6, repete="indefinite") + "</circle>")
    trico = ("<rect x='122' y='104' width='30' height='3' fill='#1f4ea1'/><rect x='122' y='107' width='30' height='3' fill='#ffffff'/>"
             "<rect x='122' y='110' width='30' height='3' fill='#d8342b'/>") if bande else ""
    return (f"<defs>{gradient('caisse', cabine_haut, cabine_bas)}{gradient('verre', '#eef8ff', '#a8d6f2')}</defs>"
            + chargement +
            f"<rect x='22' y='{SOL - 26}' width='100' height='9' rx='2' fill='#5a6069'/>"
            f"<rect x='20' y='{SOL - 30}' width='102' height='5' rx='1.5' fill='#8d949c'/>"
            + gyro +
            f"<path d='M118 {SOL - 17} V66 Q118 58 126 58 H140 Q147 58 150 64 L158 82 V{SOL - 17} Z' fill='url(#caisse)'/>"
            f"<path d='M118 {SOL - 17} V66 Q118 58 126 58 H140 Q147 58 150 64 L158 82 V{SOL - 17} Z' fill='none' stroke='#000000' stroke-opacity='0.12' stroke-width='1.5'/>"
            "<path d='M125 64 H139 Q143 64 145 68 L151 82 H125 Z' fill='url(#verre)'/>"
            + reflet("M125 64 H139 Q143 64 145 68 L151 82 H125 Z") + trico +
            "<rect x='127' y='90' width='8' height='2.5' rx='1.2' fill='#000000' opacity='0.3'/>"
            "<rect x='152' y='88' width='6' height='6' rx='2' fill='#fff3b0'/>"
            f"<rect x='150' y='{SOL - 24}' width='10' height='7' rx='2' fill='#3a3f45'/>"
            + passage(48, r) + passage(138, r) + roue(48, SOL - r, r) + roue(138, SOL - r, r))


# ------------------------------------------------------------------ les décors

def soleil(x, y, couleur="#ffd75e"):
    return (f"<circle cx='{x}' cy='{y}' r='16' fill='{couleur}' opacity='0.25'>" + a("r", "14;19;14", 4, repete="indefinite") + "</circle>"
            f"<circle cx='{x}' cy='{y}' r='10' fill='{couleur}' opacity='0.9'/>")


def maison(x, couleur, opacite=0.5):
    return (f"<g opacity='{opacite}'><path d='M{x} {SOL} V{SOL - 34} L{x + 22} {SOL - 54} L{x + 44} {SOL - 34} V{SOL} Z' fill='{couleur}'/>"
            f"<rect x='{x + 16}' y='{SOL - 22}' width='12' height='22' fill='#ffffff' opacity='0.5'/></g>")


def arbre(x, couleur, h=40, opacite=0.55):
    return (f"<g opacity='{opacite}'><rect x='{x - 2}' y='{SOL - h * 0.45}' width='4' height='{h * 0.45}' fill='#8a6a4a'/>"
            f"<circle cx='{x}' cy='{SOL - h * 0.62}' r='{h * 0.32}' fill='{couleur}'>"
            + t("rotate", f"-2 {x} {SOL};2 {x} {SOL};-2 {x} {SOL}", 3.2, repete="indefinite") + "</circle></g>")


DECORS = {
    "agriculteur": soleil(142, 46) +
        f"<path d='M0 {SOL - 22} Q45 {SOL - 40} 90 {SOL - 26} T180 {SOL - 30} V{SOL} H0 Z' fill='#9fd17f' opacity='0.55'/>"
        + "".join(f"<path d='M{x} {SOL} L{x + 30} {SOL - 24}' stroke='#7fbf5e' stroke-width='2' opacity='0.5'/>" for x in range(-10, 180, 16)),
    "plombier": maison(118, "#9fb6c8") + soleil(40, 40, "#ffe08a"),
    "industrie": "<g opacity='0.45'>"
        f"<path d='M96 {SOL} V{SOL - 30} L114 {SOL - 44} V{SOL - 30} L132 {SOL - 44} V{SOL - 30} L150 {SOL - 44} V{SOL} Z' fill='#8e98a4'/>"
        f"<rect x='154' y='{SOL - 70}' width='9' height='70' fill='#8e98a4'/></g>"
        + "".join(f"<circle cx='158' cy='{SOL - 74}' r='4' fill='#b8c0c8' opacity='0'>"
                  + a("cy", f"{SOL - 74};{SOL - 110}", 3, debut=f"{k}s", repete="indefinite")
                  + a("r", "4;11", 3, debut=f"{k}s", repete="indefinite")
                  + a("opacity", "0.6;0", 3, debut=f"{k}s", repete="indefinite") + "</circle>" for k in range(3)),
    "particulier": maison(108, "#a8b9e8") + arbre(160, "#86c27a", 44) + soleil(36, 40),
    "pisciniste": soleil(146, 42) +
        f"<rect x='86' y='{SOL - 12}' width='94' height='12' fill='#5cc6e0' opacity='0.6'/>"
        + "".join(f"<ellipse cx='{cx}' cy='{SOL - 6}' rx='2' ry='1' fill='none' stroke='#ffffff' stroke-width='1.2' opacity='0'>"
                  + a("rx", "2;14", 2.4, debut=f"{d}s", repete="indefinite") + a("ry", "1;4", 2.4, debut=f"{d}s", repete="indefinite")
                  + a("opacity", "0.9;0", 2.4, debut=f"{d}s", repete="indefinite") + "</ellipse>" for cx, d in ((120, 0), (156, 1.2))),
    "paysagiste": f"<path d='M0 {SOL - 18} Q40 {SOL - 52} 86 {SOL - 22} Q120 {SOL - 46} 180 {SOL - 20} V{SOL} H0 Z' fill='#a9d78c' opacity='0.5'/>"
        + arbre(26, "#6db35a", 46) + arbre(156, "#6db35a", 38) + soleil(110, 38),
    "collectivite": "<g opacity='0.45'>"
        f"<rect x='92' y='{SOL - 40}' width='70' height='40' fill='#a7b0bd'/>"
        f"<path d='M86 {SOL - 40} L127 {SOL - 62} L168 {SOL - 40} Z' fill='#a7b0bd'/>"
        + "".join(f"<rect x='{x}' y='{SOL - 34}' width='6' height='30' fill='#ffffff' opacity='0.6'/>" for x in (100, 114, 134, 148))
        + f"<circle cx='127' cy='{SOL - 48}' r='5' fill='#ffffff' opacity='0.8'/>"
        f"<rect x='126' y='{SOL - 82}' width='2' height='22' fill='#7c8592'/></g>"
        f"<g><rect x='128' y='{SOL - 82}' width='4' height='8' fill='#1f4ea1' opacity='0.7'/><rect x='132' y='{SOL - 82}' width='4' height='8' fill='#ffffff' opacity='0.8'/>"
        f"<rect x='136' y='{SOL - 82}' width='4' height='8' fill='#d8342b' opacity='0.7'/>"
        + t("scale", "1 1;0.86 1;1 1", 1.4, repete="indefinite") + "</g>",
    "autre": "<g opacity='0.35'>" + "".join(f"<rect x='{x}' y='{SOL - h}' width='18' height='{h}' fill='#9aa3ad'/>" for x, h in ((96, 40), (116, 58), (136, 34), (156, 48))) + "</g>",
}


def tuyaux():
    goutte = ("<circle cx='150' cy='52' r='2' fill='#2f7fc1' opacity='0'>"
              + a("cy", "52;66", 0.9, debut=f"{ARRIVEE + 0.6}s; {ARRIVEE + 3.6}s; {ARRIVEE + 6.6}s")
              + a("opacity", "1;0", 0.9, debut=f"{ARRIVEE + 0.6}s; {ARRIVEE + 3.6}s; {ARRIVEE + 6.6}s") + "</circle>")
    return ("<rect x='38' y='58' width='4' height='9' fill='#4a4f55'/><rect x='100' y='58' width='4' height='9' fill='#4a4f55'/>"
            "<rect x='30' y='56' width='84' height='4' rx='2' fill='#4a4f55'/>"
            "<rect x='20' y='45' width='132' height='6' rx='3' fill='#2f7fc1'/><rect x='20' y='45' width='132' height='2' rx='1' fill='#ffffff' opacity='0.4'/>"
            "<rect x='24' y='51' width='120' height='5' rx='2.5' fill='#c57a3a'/><rect x='24' y='51' width='120' height='1.6' rx='0.8' fill='#ffffff' opacity='0.45'/>"
            + goutte)


def echelle():
    return ("<g fill='none' stroke='#d6dde3' stroke-width='3.2' stroke-linecap='round'>"
            "<path d='M44 66 V40 Q44 33 51 33 Q56 33 56 38'/><path d='M64 66 V40 Q64 33 71 33 Q76 33 76 38'/>"
            "<path d='M44 48 H64 M44 57 H64'/></g>"
            "<rect x='36' y='64' width='50' height='3' rx='1.5' fill='#4a4f55'/>")


def vagues():
    return ("<clipPath id='flanc'><rect x='34' y='100' width='96' height='16'/></clipPath>"
            "<g clip-path='url(#flanc)'><path d='M10 110 q8 -7 16 0 t16 0 t16 0 t16 0 t16 0 t16 0 t16 0 t16 0' fill='none' stroke='#ffffff' stroke-width='3.4' stroke-linecap='round'>"
            + t("translate", "0 0;-32 0", 1.6, repete="indefinite") + "</path></g>")


def engrenage():
    dents = "".join(f"<rect x='-2' y='-12' width='4' height='5' fill='#f0b429' transform='rotate({k * 45})'/>" for k in range(8))
    return ("<g transform='translate(116 106)'><g>" + dents + "<circle r='8.5' fill='#f0b429'/><circle r='3.4' fill='#5f6874'/>"
            + t("rotate", "0;360", 6, repete="indefinite") + "</g></g>"
            "<rect x='44' y='101' width='58' height='10' rx='2' fill='#f0b429'/>")


def herbe_et_branches():
    feuilles = "".join(f"<circle cx='{x}' cy='{y}' r='{r}' fill='{c}'/>" for x, y, r, c in (
        (48, 64, 7, '#4f9e3a'), (56, 58, 6, '#62b44a'), (42, 58, 5, '#62b44a'), (88, 60, 7, '#4f9e3a'), (96, 54, 6, '#62b44a'), (82, 54, 5, '#76c25c')))
    return ("<path d='M24 110 q5 -14 10 0 q5 -16 10 0 q5 -12 10 0 q5 -16 10 0 q5 -12 10 0 q5 -16 10 0 q5 -12 10 0 q5 -16 10 0 q5 -12 10 0' fill='#5fae3e'/>"
            "<rect x='24' y='98' width='94' height='12' fill='#5fae3e'/>"
            "<g>" + t("rotate", "-3 66 100;3 66 100;-3 66 100", 2.4, debut=f"{ARRIVEE}s", repete="indefinite") +
            "<path d='M50 100 L48 66 M48 78 L40 62 M86 100 L90 64 M89 76 L98 58' stroke='#7a4b22' stroke-width='3' stroke-linecap='round' fill='none'/>"
            + feuilles + "</g>"
            "<path d='M100 60 q3 -3 6 0 q-3 3 -6 0 z' fill='#76c25c' opacity='0'>"
            + t("translate", "0 0;-14 44", 2.2, debut=f"{ARRIVEE + 0.8}s", repete="indefinite")
            + a("opacity", "1;1;0", 2.2, debut=f"{ARRIVEE + 0.8}s", temps="0;0.7;1", repete="indefinite") + "</path>")


def benne():
    return ("<path d='M24 110 L28 82 H118 L116 110 Z' fill='#7d8fa3'/><path d='M24 110 L28 82 H118 L116 110 Z' fill='none' stroke='#000000' stroke-opacity='0.12' stroke-width='1.5'/>"
            "<path d='M40 86 V106 M60 86 V106 M80 86 V106 M100 86 V106' stroke='#ffffff' stroke-opacity='0.25' stroke-width='2'/>")


VEHICULES = {
    "agriculteur": (("#eef8e6", "#d6efc6"), tracteur(), True),
    "plombier": (("#edf3fa", "#d4e3f2"), fourgon("#ffffff", "#e4e9ee", galerie=tuyaux()), False),
    "industrie": (("#eff0f3", "#d9dce2"), fourgon("#7b8592", "#555e6a", logo=engrenage()), False),
    "particulier": (("#edf2fd", "#d3def8"), berline(), False),
    "pisciniste": (("#e6f7fb", "#c7ebf4"), fourgon("#27b8d6", "#138ea9", galerie=echelle(), logo=vagues()), False),
    "paysagiste": (("#eff8e8", "#d7ecc8"), plateau("#f5b04a", "#d98a24", herbe_et_branches()), True),
    "collectivite": (("#eef1f6", "#d8dee8"), plateau("#ffffff", "#e3e8ee", benne(), gyrophare=True, bande=True), True),
    "autre": (("#f1f2f4", "#dde0e4"), fourgon("#f4f6f8", "#d8dde2"), False),
}


if __name__ == "__main__":
    os.makedirs(SORTIE, exist_ok=True)
    for nom, ((haut, bas), dessin, diesel) in VEHICULES.items():
        with open(os.path.join(SORTIE, f"{nom}.svg"), "w") as f:
            f.write(svg(haut, bas, DECORS[nom], dessin, ralenti=diesel))
        print(nom, os.path.getsize(os.path.join(SORTIE, f"{nom}.svg")), "octets")
