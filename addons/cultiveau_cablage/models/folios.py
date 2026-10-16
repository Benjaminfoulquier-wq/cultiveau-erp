"""Les folios du dossier d'exécution, tracés en SVG (A3 paysage) : puissance (unifilaire), commande (échelle), borniers, nomenclature.

Un folio est une feuille avec son cadre, son cartouche et son indice. Les symboles suivent l'esprit de l'IEC 60617 en représentation
unifilaire (une ligne, la barre « 3 » marque le triphasé) : lisible par un électricien, assez simple pour être généré.
"""
from markupsafe import escape

LARGEUR, HAUTEUR = 1587, 1123  # A3 paysage à 96 dpi
MARGE = 24
CARTOUCHE_H = 96
ENCRE = "#1d2f38"
GRIS = "#6b7a83"
ACCENT = "#0b8aa3"
ROUGE = "#c9473d"
VERT = "#2e9d63"
POLICE = "font-family='Helvetica, Arial, sans-serif'"


class Feuille:
    """Un folio : on y ajoute des formes, puis on la rend en SVG."""

    def __init__(self, titre, cartouche, numero, total):
        self.parts = []
        self.titre = titre
        self.cartouche = cartouche
        self.numero = numero
        self.total = total

    # ---------------------------------------------------------------- primitives

    def ligne(self, x1, y1, x2, y2, couleur=ENCRE, epaisseur=1.8, tirets=None):
        d = f" stroke-dasharray='{tirets}'" if tirets else ""
        self.parts.append(f"<line x1='{x1:.1f}' y1='{y1:.1f}' x2='{x2:.1f}' y2='{y2:.1f}' stroke='{couleur}' stroke-width='{epaisseur}'{d} stroke-linecap='round'/>")

    def rect(self, x, y, w, h, fond="none", couleur=ENCRE, epaisseur=1.6, rayon=0):
        self.parts.append(f"<rect x='{x:.1f}' y='{y:.1f}' width='{w:.1f}' height='{h:.1f}' rx='{rayon}' fill='{fond}' stroke='{couleur}' stroke-width='{epaisseur}'/>")

    def cercle(self, x, y, r, fond="white", couleur=ENCRE, epaisseur=1.8):
        self.parts.append(f"<circle cx='{x:.1f}' cy='{y:.1f}' r='{r}' fill='{fond}' stroke='{couleur}' stroke-width='{epaisseur}'/>")

    def texte(self, x, y, t, taille=12, couleur=ENCRE, ancre="start", gras=False, italique=False):
        g = " font-weight='700'" if gras else ""
        i = " font-style='italic'" if italique else ""
        self.parts.append(f"<text x='{x:.1f}' y='{y:.1f}' font-size='{taille}' fill='{couleur}' text-anchor='{ancre}' {POLICE}{g}{i}>{escape(str(t))}</text>")

    # ---------------------------------------------------------------- symboles (verticaux, le courant descend)

    def triphase(self, x, y, n=3):
        """La barre oblique « 3 » (ou « 2 ») d'un conducteur unifilaire."""
        self.ligne(x - 6, y + 6, x + 6, y - 6, epaisseur=1.4)
        self.texte(x + 8, y + 4, str(n), 10, GRIS)

    def disjoncteur(self, x, y, repere, calibre, moteur=True):
        """Disjoncteur (moteur : magnétothermique) : contact ouvert et croix de protection, 44 px de haut."""
        self.ligne(x, y, x, y + 10)
        self.ligne(x, y + 34, x - 11, y + 12, epaisseur=2)
        self.ligne(x - 5, y + 9, x + 5, y + 19, epaisseur=1.4)
        self.ligne(x - 5, y + 19, x + 5, y + 9, epaisseur=1.4)
        if moteur:
            self.rect(x - 7, y + 20, 14, 10, epaisseur=1.2)
        self.ligne(x, y + 34, x, y + 44)
        self.texte(x + 14, y + 20, repere, 12, gras=True)
        self.texte(x + 14, y + 34, calibre, 10, GRIS)
        return y + 44

    def contact(self, x, y, repere, note=""):
        """Un contact de contacteur (pouvoir de coupure en charge), 36 px."""
        self.ligne(x, y, x, y + 8)
        self.ligne(x, y + 28, x - 11, y + 8, epaisseur=2)
        self.ligne(x - 4, y + 4, x + 4, y + 4, epaisseur=1.4)
        self.ligne(x, y + 28, x, y + 36)
        self.texte(x + 14, y + 18, repere, 12, gras=True)
        if note:
            self.texte(x + 14, y + 31, note, 10, GRIS)
        return y + 36

    def boite(self, x, y, repere, lignes, w=78, h=46):
        """Un appareil en boîte (variateur, démarreur, protection) centré sur x."""
        self.ligne(x, y, x, y + 6)
        self.rect(x - w / 2, y + 6, w, h, rayon=3)
        for k, l in enumerate(lignes):
            self.texte(x, y + 6 + 17 + k * 14, l, 10 if k else 12, ancre="middle", gras=not k)
        self.ligne(x, y + 6 + h, x, y + 12 + h)
        self.texte(x + w / 2 + 6, y + 24, repere, 12, gras=True)
        return y + 12 + h

    def transformateur(self, x, y, repere, texte):
        self.ligne(x, y, x, y + 6)
        self.cercle(x, y + 18, 12)
        self.cercle(x, y + 34, 12)
        self.ligne(x, y + 46, x, y + 52)
        self.texte(x + 18, y + 22, repere, 12, gras=True)
        self.texte(x + 18, y + 36, texte, 10, GRIS)
        return y + 52

    def moteur(self, x, y, repere, texte, phases="3~"):
        self.ligne(x, y, x, y + 8)
        self.cercle(x, y + 30, 22)
        self.texte(x, y + 28, "M", 15, ancre="middle", gras=True)
        self.texte(x, y + 41, phases, 10, ancre="middle")
        self.texte(x, y + 70, repere, 12, ancre="middle", gras=True)
        self.texte(x, y + 84, texte, 10, GRIS, ancre="middle")
        return y + 52

    def prise(self, x, y, repere, texte):
        self.ligne(x, y, x, y + 10)
        self.parts.append(f"<path d='M {x - 14} {y + 10} A 14 14 0 0 0 {x + 14} {y + 10}' fill='none' stroke='{ENCRE}' stroke-width='1.8'/>")
        self.texte(x, y + 44, repere, 12, ancre="middle", gras=True)
        self.texte(x, y + 58, texte, 10, GRIS, ancre="middle")

    def borne(self, x, y, numero, cote="droite"):
        self.cercle(x, y, 4, fond="white", epaisseur=1.4)
        self.texte(x + 7 if cote == "droite" else x - 7, y + 4, numero, 9, GRIS, ancre="start" if cote == "droite" else "end")

    def masse(self, x, y):
        self.ligne(x, y, x, y + 10)
        for k, w in enumerate((14, 9, 4)):
            self.ligne(x - w, y + 10 + k * 5, x + w, y + 10 + k * 5, epaisseur=1.6)

    # ---------------------------------------------------------------- symboles horizontaux (schéma de commande en échelle)

    def contact_h(self, x, y, repere, ferme=False, bouton=False, note=""):
        """Un contact sur une ligne horizontale (NO par défaut, NC avec « ferme »), 56 px de large."""
        self.ligne(x, y, x + 18, y)
        if ferme:
            self.ligne(x + 18, y, x + 38, y - 12, epaisseur=2)
            self.ligne(x + 38, y, x + 38, y - 14, epaisseur=1.4)
        else:
            self.ligne(x + 18, y, x + 38, y - 12, epaisseur=2)
        if bouton:
            self.ligne(x + 28, y - 8, x + 28, y - 20, epaisseur=1.4)
            self.ligne(x + 22, y - 20, x + 34, y - 20, epaisseur=1.4)
        self.ligne(x + 38, y, x + 56, y)
        self.texte(x + 28, y + 16, repere, 11, ancre="middle", gras=True)
        if note:
            self.texte(x + 28, y + 28, note[:16], 9, GRIS, ancre="middle")
        return x + 56

    def bobine_h(self, x, y, repere, note=""):
        self.ligne(x, y, x + 8, y)
        self.rect(x + 8, y - 10, 30, 20)
        self.ligne(x + 38, y, x + 46, y)
        self.texte(x + 23, y + 26, repere, 11, ancre="middle", gras=True)
        if note:
            self.texte(x + 23, y + 38, note, 9, GRIS, ancre="middle")
        return x + 46

    def voyant_h(self, x, y, repere, note=""):
        self.ligne(x, y, x + 10, y)
        self.cercle(x + 22, y, 12)
        self.ligne(x + 14, y - 8, x + 30, y + 8, epaisseur=1.4)
        self.ligne(x + 30, y - 8, x + 14, y + 8, epaisseur=1.4)
        self.ligne(x + 34, y, x + 44, y)
        self.texte(x + 22, y + 26, repere, 11, ancre="middle", gras=True)
        if note:
            self.texte(x + 22, y + 38, note, 9, GRIS, ancre="middle")
        return x + 44

    def electrovanne_h(self, x, y, repere, note=""):
        """Une électrovanne (bobine avec son clapet), à droite d'une ligne horizontale."""
        self.ligne(x, y, x + 8, y)
        self.rect(x + 8, y - 10, 30, 20)
        self.ligne(x + 8, y + 10, x + 38, y - 10, epaisseur=1.2)
        self.texte(x + 44, y + 4, repere, 11, gras=True)
        if note:
            self.texte(x + 44, y + 16, note, 9, GRIS)

    # ---------------------------------------------------------------- tableaux

    def tableau(self, x, y, colonnes, lignes, largeurs, hauteur_ligne=20, taille=10.5, max_lignes=None):
        """Un tableau simple ; renvoie le y après la dernière ligne et le nombre de lignes tracées."""
        total = sum(largeurs)
        self.rect(x, y, total, hauteur_ligne, fond="#eef3f5", epaisseur=1.2)
        cx = x
        for c, w in zip(colonnes, largeurs):
            self.texte(cx + 6, y + hauteur_ligne - 6, c, taille, gras=True)
            cx += w
        yy = y + hauteur_ligne
        n = 0
        for l in lignes[:max_lignes] if max_lignes else lignes:
            self.rect(x, yy, total, hauteur_ligne, epaisseur=0.8, couleur="#c9d3d8")
            cx = x
            for v, w in zip(l, largeurs):
                t = str(v if v is not None else "")
                if len(t) * taille * 0.55 > w - 10:
                    t = t[: int((w - 10) / (taille * 0.55)) - 1] + "…"
                self.texte(cx + 6, yy + hauteur_ligne - 6, t, taille)
                cx += w
            yy += hauteur_ligne
            n += 1
        return yy, n

    # ---------------------------------------------------------------- le cadre et le cartouche

    def rendre(self):
        c = self.cartouche
        cadre = [f"<rect x='{MARGE}' y='{MARGE}' width='{LARGEUR - 2 * MARGE}' height='{HAUTEUR - 2 * MARGE}' fill='white' stroke='{ENCRE}' stroke-width='2'/>"]
        # en-tête
        cadre.append(f"<rect x='{MARGE}' y='{MARGE}' width='{LARGEUR - 2 * MARGE}' height='34' fill='#f2f5f6' stroke='{ENCRE}' stroke-width='1.2'/>")
        entete = Feuille.__new__(Feuille)
        entete.parts = cadre
        entete.texte(MARGE + 14, MARGE + 23, f"{c['dossier']} · {self.titre}", 15, gras=True)
        entete.texte(LARGEUR - MARGE - 14, MARGE + 23, f"FOLIO {self.numero:02d} / {self.total:02d} · INDICE {c['indice']}", 13, ancre="end", gras=True)
        # cartouche
        yc = HAUTEUR - MARGE - CARTOUCHE_H
        entete.rect(MARGE, yc, LARGEUR - 2 * MARGE, CARTOUCHE_H, fond="#fbfcfc", epaisseur=1.2)
        colonnes = [("Adhérent", c["societe"], 300), ("Client · installation", c["client"], 380), ("Titre", self.titre, 320), ("Dossier", c["dossier"], 150),
                    ("Indice", c["indice"], 70), ("Date", c["date"], 110), ("Auteur", c["auteur"], 170)]
        xx = MARGE
        for nom, val, w in colonnes:
            entete.ligne(xx, yc, xx, yc + CARTOUCHE_H, epaisseur=1)
            entete.texte(xx + 8, yc + 18, nom.upper(), 9, GRIS)
            entete.texte(xx + 8, yc + 42, val, 13 if len(str(val)) < 36 else 11, gras=True)
            xx += w
        entete.ligne(MARGE, yc + 56, LARGEUR - MARGE, yc + 56, epaisseur=1)
        entete.texte(MARGE + 8, yc + 76, c["mention"], 10, ROUGE, italique=True)
        entete.texte(LARGEUR - MARGE - 8, yc + 76, c["normes"], 10, GRIS, ancre="end")
        contenu = "".join(cadre) + "".join(self.parts)
        return (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {LARGEUR} {HAUTEUR}' width='100%' style='max-width:{LARGEUR}px;display:block;background:white'>"
                f"{contenu}</svg>")


# ====================================================================== les folios

def folio_puissance(d, cartouche, numero, total):
    """Le schéma unifilaire de puissance : arrivée, protection générale, départs."""
    f = Feuille("Puissance — schéma unifilaire", cartouche, numero, total)
    g = d["general"]
    y_bus = 330
    x0 = MARGE + 60
    # l'arrivée
    f.texte(x0, 120, f"Arrivée {g['tension']} · {g['source']}", 13, gras=True)
    f.texte(x0, 138, f"Régime de neutre {g['regime']} · {g['longueur_alimentation']}", 11, GRIS)
    f.ligne(x0, 146, x0, 160)
    f.triphase(x0, 153, 3 if g["reseau"] == "tri" else 2)
    y = f.disjoncteur(x0, 160, "Q0", f"Int.-sectionneur {g['calibre']} A", moteur=False)
    y = f.boite(x0, y, "Q0.1", ["ΔI 300 mA", f"type {g['ddr']}", f"{g['calibre']} A"], w=86, h=50)
    if g["parafoudre"]:
        f.ligne(x0, y - 4, x0 + 46, y - 4)
        f.rect(x0 + 46, y - 16, 44, 24, rayon=2)
        f.texte(x0 + 68, y, "F0", 10, ancre="middle", gras=True)
        f.texte(x0 + 94, y - 4, "parafoudre type 2", 9, GRIS)
        f.masse(x0 + 68, y + 8)
    f.ligne(x0, y, x0, y_bus)
    # le jeu de barres
    f.ligne(x0, y_bus, LARGEUR - MARGE - 60, y_bus, epaisseur=4)
    f.texte(LARGEUR - MARGE - 62, y_bus - 8, "L1 L2 L3" if g["reseau"] == "tri" else "L N", 11, ancre="end", gras=True)
    f.ligne(x0, y_bus + 10, LARGEUR - MARGE - 60, y_bus + 10, couleur="#4a7cb5", epaisseur=1.4, tirets="6 4")
    f.texte(LARGEUR - MARGE - 62, y_bus + 24, "N", 10, "#4a7cb5", ancre="end")
    f.ligne(x0, y_bus + 18, LARGEUR - MARGE - 60, y_bus + 18, couleur="#7a9a2a", epaisseur=1.4, tirets="10 4")
    f.texte(LARGEUR - MARGE - 62, y_bus + 32, "PE", 10, "#7a9a2a", ancre="end")
    # les départs
    pas = 190
    x = x0 + 190
    for dep in d["departs"]:
        f.ligne(x, y_bus, x, y_bus + 50)
        f.triphase(x, y_bus + 40, 3 if dep["reseau"] == "tri" else 2)
        y = f.disjoncteur(x, y_bus + 50, dep["repere_q"], dep["disjoncteur"], moteur=dep["moteur"])
        if dep["genre"] == "transformateur":
            y = f.transformateur(x, y, dep["repere"], dep["texte"])
            f.ligne(x, y, x, y + 14)
            f.texte(x, y + 30, "→ commande 24 V", 10, ACCENT, ancre="middle")
            f.texte(x, y + 44, "(folio commande)", 9, GRIS, ancre="middle")
        elif dep["genre"] == "auxiliaire":
            f.borne(x, y + 6, dep["borne"])
            f.ligne(x, y + 10, x, y + 24)
            f.prise(x, y + 24, dep["repere"], dep["texte"])
        else:
            if dep["demarrage"] == "variateur":
                y = f.boite(x, y, dep["repere_km"], ["~ / =", f"variateur {dep['variateur_kw']:g} kW", "réglage pression" if dep["regulation"] else ""], w=96, h=54)
            elif dep["demarrage"] == "etoile_triangle":
                y = f.contact(x, y, dep["repere_km"], "ligne")
                y = f.boite(x, y, "", ["Y / Δ", f"{dep['repere_km']}.2 / {dep['repere_km']}.3", "KT temporisé"], w=96, h=48)
            elif dep["demarrage"] == "progressif":
                y = f.boite(x, y, dep["repere_km"], ["démarreur", "progressif", f"{dep['puissance_kw']:g} kW"], w=90, h=48)
            else:
                y = f.contact(x, y, dep["repere_km"], f"{dep['contacteur_kw']:g} kW AC-3")
            f.borne(x, y + 6, dep["borne"])
            f.ligne(x, y + 10, x, y + 50)
            f.texte(x + 8, y + 32, dep["cable"], 10, ACCENT)
            f.texte(x + 8, y + 45, f"{dep['longueur_cable_m']:g} m · chute {dep['chute_pct']:.1f} %", 9, ROUGE if dep["chute_pct"] > 5 else GRIS)
            f.moteur(x, y + 50, dep["repere"], dep["texte"], "3~" if dep["reseau"] == "tri" else "1~")
        f.texte(x, y_bus - 16, dep["nom"], 11, ancre="middle", gras=True)
        x += pas
    # la légende
    yl = HAUTEUR - MARGE - CARTOUCHE_H - 60
    f.texte(x0, yl, "Représentation unifilaire : « 3 » = trois phases, « 2 » = phase + neutre. Sections en cuivre, pose en conduit ou enterrée.", 10, GRIS)
    f.texte(x0, yl + 16, f"Courant total {g['courant_total']:.1f} A · calibre général {g['calibre']} A · " + (f"{len(d['departs'])} départs"), 10, GRIS)
    for k, a in enumerate(d["alertes"][:3]):
        f.texte(x0, yl + 34 + k * 14, "⚠ " + a, 10, ROUGE)
    return f.rendre()


def folio_commande(d, cartouche, numero, total):
    """Le schéma de commande : l'échelle 230 V (marche de la pompe) et le 24 V (programmateur, électrovannes, entrées)."""
    f = Feuille("Commande — pompe, programmateur, électrovannes", cartouche, numero, total)
    g = d["general"]
    # ---- échelle 230 V
    xg, xd = MARGE + 70, MARGE + 640
    yh, yb = 110, 560
    f.ligne(xg, yh, xg, yb, epaisseur=2.4)
    f.ligne(xd, yh, xd, yb, epaisseur=2.4)
    f.texte(xg, yh - 14, "L (230 V, depuis Q1.0 commande 2 A)", 11, gras=True)
    f.texte(xd, yh - 14, "N", 11, ancre="end", gras=True)
    y = yh + 50
    for rung in d["commande"]["echelons"]:
        f.ligne(xg, y, xg + 20, y)
        x = xg + 20
        for el in rung["elements"]:
            if el["type"] == "contact":
                x = f.contact_h(x, y, el["repere"], ferme=el.get("ferme"), bouton=el.get("bouton"), note=el.get("note", ""))
            elif el["type"] == "bobine":
                x = f.bobine_h(x, y, el["repere"], el.get("note", ""))
            elif el["type"] == "voyant":
                x = f.voyant_h(x, y, el["repere"], el.get("note", ""))
            x += 14
            f.ligne(x - 14, y, x, y)
        f.ligne(x, y, xd, y)
        f.texte(xd + 10, y + 4, rung["nom"], 10, GRIS)
        y += 62
    # ---- le 24 V
    xa = MARGE + 900
    f.texte(xa - 130, yh - 14, f"24 V AC — transformateur T1 {g['transfo_va']} VA (230/24 V, Q1.0)", 11, gras=True)
    pil = d["commande"]["pilotage"]
    hauteur = max(190, 34 + 22 * len(d["sorties"]))
    f.rect(xa, yh + 10, 210, hauteur, rayon=4, epaisseur=2)
    f.texte(xa + 105, yh + 32, pil["repere"], 13, ancre="middle", gras=True)
    f.texte(xa + 105, yh + 48, pil["nom"], 10, GRIS, ancre="middle")
    f.texte(xa + 105, yh + 62, pil["detail"], 10, GRIS, ancre="middle")
    # entrées à gauche
    ye = yh + 90
    for e in d["commande"]["entrees"]:
        f.ligne(xa - 60, ye, xa, ye)
        f.contact_h(xa - 110, ye, e["repere"], ferme=e.get("ferme"), note=e["note"])
        f.texte(xa + 6, ye + 4, e["entree"], 9, GRIS)
        ye += 40
    # alimentation
    f.ligne(xa + 105, yh + 10, xa + 105, yh - 2)
    f.texte(xa + 110, yh + 4, "24 V · COM", 9, GRIS)
    # sorties à droite
    ys = yh + 36
    for s in d["sorties"]:
        f.ligne(xa + 210, ys, xa + 250, ys)
        f.texte(xa + 214, ys - 4, s["sortie"], 9, GRIS)
        f.borne(xa + 250, ys, s["borne"])
        f.ligne(xa + 254, ys, xa + 300, ys)
        f.electrovanne_h(xa + 300, ys, s["repere"], f"{s['nom']} · {s['cable']} · {s['longueur_m']:g} m" + (f" · chute {s['chute_v']:.1f} V" if s["chute_v"] > 3 else ""))
        ys += 22
    # commun
    f.ligne(xa + 105, yh + 10 + hauteur, xa + 105, yh + 10 + hauteur + 18)
    f.texte(xa + 112, yh + 10 + hauteur + 14, f"COM commun des électrovannes · {d['commande']['commun']}", 10, ACCENT)
    yl = HAUTEUR - MARGE - CARTOUCHE_H - 60
    f.texte(MARGE + 70, yl, "Échelle 230 V : S0 arrêt d'urgence (NC), S1 Auto / 0 / Manu, F thermique, B1 manque d'eau, KA1 ordre du programmateur → KM (ou RUN du variateur).", 10, GRIS)
    f.texte(MARGE + 70, yl + 16, "24 V : une sortie par secteur, la vanne maître sur MV ; les bornes XB reprennent chaque conducteur (folio borniers).", 10, GRIS)
    return f.rendre()


def folio_borniers(d, cartouche, numero, total):
    f = Feuille("Borniers XA (puissance), XB (24 V), XC (entrées)", cartouche, numero, total)
    x, y = MARGE + 40, 100
    f.texte(x, y - 10, "XA — puissance", 13, gras=True)
    ya, _n = f.tableau(x, y, ["Borne", "Repère", "Vers", "Câble", "Longueur", "Note"], [[b["numero"], b["repere"], b["destination"], b["cable"], b["longueur"], b["note"]] for b in d["borniers"]["XA"]],
                       [60, 80, 260, 120, 80, 140], max_lignes=38)
    x2 = x + 780
    f.texte(x2, y - 10, "XB — 24 V électrovannes", 13, gras=True)
    yb, _n = f.tableau(x2, y, ["Borne", "Repère", "Vers", "Câble", "Longueur", "Note"], [[b["numero"], b["repere"], b["destination"], b["cable"], b["longueur"], b["note"]] for b in d["borniers"]["XB"]],
                       [60, 80, 230, 110, 80, 140], max_lignes=38)
    yc = max(ya, yb) + 40
    if yc < HAUTEUR - CARTOUCHE_H - 200:
        f.texte(x, yc - 10, "XC — entrées et capteurs", 13, gras=True)
        f.tableau(x, yc, ["Borne", "Repère", "Capteur", "Contact", "Câble", "Note"], [[b["numero"], b["repere"], b["destination"], b["cable"], b["longueur"], b["note"]] for b in d["borniers"]["XC"]],
                  [60, 80, 260, 120, 80, 140], max_lignes=8)
    return f.rendre()


def folio_nomenclature(d, cartouche, numero, total):
    f = Feuille("Nomenclature", cartouche, numero, total)
    x, y = MARGE + 40, 100
    lignes = [[l["repere"], l["designation"], l["caracteristiques"], f"{l['quantite']:g} {l['unite']}", l["folio"], l["article"]] for l in d["nomenclature"]]
    f.tableau(x, y, ["Rep.", "Désignation", "Caractéristiques", "Qté", "Folio", "Article du catalogue"], lignes, [70, 360, 420, 80, 90, 460], max_lignes=42)
    return f.rendre()
