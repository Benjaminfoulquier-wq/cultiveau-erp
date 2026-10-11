from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .climat import pluie_efficace

MOIS = [(str(i), n) for i, n in enumerate(
    ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"], start=1)]
MOIS_COURTS = ["Jan", "Fév", "Mar", "Avr", "Mai", "Juin", "Juil", "Août", "Sep", "Oct", "Nov", "Déc"]
CATEGORIES = [("vigne", "Vigne"), ("arbo", "Arboriculture"), ("petits_fruits", "Petits fruits"), ("grandes_cultures", "Grandes cultures"),
              ("maraichage", "Maraîchage"), ("prairies", "Prairies et fourrages"), ("sous_abri", "Sous abri"),
              ("ppam", "Plantes à parfum, aromatiques et médicinales"), ("espaces_verts", "Espaces verts et gazons"),
              ("pepiniere", "Pépinière et horticulture"), ("tropicales", "Cultures tropicales (DOM)"), ("autre", "Autre")]

# Les quatre saisons émotionnelles de la frise (Journées Cultiveau 2025, atelier 1, pilier 2) : ce que l'agriculteur
# attend de nous selon le moment de sa culture, et non selon notre calendrier commercial.
POSTURES = [("ecoute", "Écoute"), ("support", "Support"), ("discret", "Discret"), ("proposition", "Proposition")]
POSTURE_INFOS = {
    "ecoute": {"saison": "Hiver", "icone": "❄", "couleur": "#dceef1",
               "consigne": "Il a le temps et il réfléchit : écouter, comprendre, étudier (analyse des besoins, bilan, visite)."},
    "support": {"saison": "Printemps", "icone": "🌱", "couleur": "#e3f1d9",
                "consigne": "Il met en route : être là, remettre en service, régler, livrer ; pas de nouveau projet."},
    "discret": {"saison": "Été", "icone": "☀", "couleur": "#fde8c8",
                "consigne": "Plein travail, stress : ne pas solliciter, répondre vite à l'urgence qu'il signale lui-même."},
    "proposition": {"saison": "Automne", "icone": "🍂", "couleur": "#f3dcd0",
                    "consigne": "Après récolte, bilan de campagne : le moment de proposer, chiffrer, planifier la saison prochaine."},
}
# Posture de référence d'un mois sans information plus précise (le calendrier, à défaut du stade).
POSTURE_CALENDRIER = {11: "ecoute", 12: "ecoute", 1: "ecoute", 2: "ecoute", 3: "support", 4: "support", 5: "support", 6: "support",
                      7: "discret", 8: "discret", 9: "proposition", 10: "proposition"}
# Les stades où l'on ne dérange pas (semis, plantation, floraison, récolte, vendanges, fauche) : « éviter les périodes de stress ».
MOTS_CRITIQUES = ("semis", "plantation", "floraison", "récolte", "recolte", "vendange", "fauche", "cueillette", "moisson")

# Les cours agricoles (pilier 3) : le contexte économique change la psychologie du client, et donc le ton.
COURS = [("hausse", "En hausse"), ("stable", "Stables"), ("baisse", "En baisse")]
TON_COURS = {
    "baisse": "Cours en baisse : parler sécurité et retour sur investissement. Rassurer sur la rentabilité à long terme, "
              "insister sur les économies d'eau et d'énergie, proposer un financement adapté, mettre en avant fiabilité et durabilité.",
    "hausse": "Cours en hausse : parler innovation et ambition. Performance, rendement, optimisation ; les solutions premium et "
              "les technologies de pointe ont leur place ; encourager l'investissement.",
    "stable": "Cours stables : parler équilibre. Fiabilité, coût complet sur la durée, confort de travail, eau économisée.",
}


def posture_calendrier(mois_liste):
    """La posture majoritaire du calendrier sur ces mois (le premier mois tranche les égalités)."""
    if not mois_liste:
        return "ecoute"
    compte = {}
    for m in mois_liste:
        compte[POSTURE_CALENDRIER[m]] = compte.get(POSTURE_CALENDRIER[m], 0) + 1
    return max(compte, key=lambda p: (compte[p], -mois_liste.index(next(m for m in mois_liste if POSTURE_CALENDRIER[m] == p))))


def combiner_postures(postures, critique=False):
    """La posture d'un client qui a plusieurs cultures : une période critique l'emporte (discret) ;
    sinon une fenêtre qui s'ouvre (proposition), puis le temps d'écouter, puis le support."""
    if critique:
        return "discret"
    for p in ("proposition", "ecoute", "support", "discret"):
        if p in postures:
            return p
    return "ecoute"


def mois_couverts(debut, fin):
    """De `debut` à `fin` inclus, en passant l'hiver si besoin : (11, 2) → [11, 12, 1, 2]."""
    debut, fin = int(debut), int(fin)
    if debut <= fin:
        return list(range(debut, fin + 1))
    return list(range(debut, 13)) + list(range(1, fin + 1))


JOURS_MOIS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
DEBUT_MOIS = [sum(JOURS_MOIS[:i]) for i in range(12)]  # jour de l'année (0 = 1er janvier) où commence chaque mois


def mois_du_jour(jour):
    jour %= 365
    return next(m for m in range(12, 0, -1) if jour >= DEBUT_MOIS[m - 1])


def decaler_plage(debut, fin, jours):
    """La plage de mois (debut, fin) décalée de `jours` : un mois est retenu s'il est couvert à plus de moitié."""
    debut, fin = int(debut), int(fin)
    liste = mois_couverts(debut, fin)
    if not jours or len(liste) >= 12:
        return debut, fin
    a = DEBUT_MOIS[debut - 1] + jours
    longueur = sum(JOURS_MOIS[m - 1] for m in liste)
    couverture = {}
    for j in range(a, a + longueur):
        couverture[mois_du_jour(j)] = couverture.get(mois_du_jour(j), 0) + 1
    ordre = [mois_du_jour(a + i * 30) for i in range(13)]  # les mois dans l'ordre du cycle décalé
    retenus = [m for m in dict.fromkeys(ordre) if couverture.get(m, 0) * 2 > JOURS_MOIS[m - 1]]
    if not retenus:
        retenus = [mois_du_jour(a + longueur // 2)]
    return retenus[0], retenus[-1]


def courbe_kc(ini, mi, fin, durees, jour):
    """Le Kc au jour `jour` du cycle (FAO-56) : plat, montée, plateau, descente."""
    a, b, c = durees[0], durees[0] + durees[1], durees[0] + durees[1] + durees[2]
    d = c + durees[3]
    jour = max(0, min(jour, d))
    if jour <= a:
        return ini
    if jour <= b:
        return ini + (mi - ini) * (jour - a) / max(1, b - a)
    if jour <= c:
        return mi
    return mi + (fin - mi) * (jour - c) / max(1, d - c)


def libelle_mois(liste):
    if not liste:
        return "—"
    if len(liste) == 1:
        return MOIS_COURTS[liste[0] - 1]
    return f"{MOIS_COURTS[liste[0] - 1]}–{MOIS_COURTS[liste[-1] - 1]}"


class Culture(models.Model):
    _name = "cultiveau.culture"
    _description = "Culture (frise culturale)"
    _order = "sequence, name"

    name = fields.Char("Culture", required=True, translate=False)
    categorie = fields.Selection(CATEGORIES, string="Famille", default="autre", required=True)
    couleur = fields.Char("Couleur", default="#2a7f8f", help="Couleur de la ligne sur la frise (hexadécimal).")
    sequence = fields.Integer(default=10)
    actif = fields.Boolean(default=True)
    stade_ids = fields.One2many("cultiveau.culture.stade", "culture_id", string="Stades")
    fenetre_ids = fields.One2many("cultiveau.culture.fenetre", "culture_id", string="Fenêtres commerciales")
    nb_clients = fields.Integer("Clients", compute="_compute_nb_clients")
    cours_tendance = fields.Selection(COURS, "Cours agricoles", default="stable", required=True,
                                      help="La tendance du marché de cette culture : elle change le ton à adopter avec ses producteurs.")
    cours_note = fields.Char("Repère", help="Exemple : « Vin IGP Gard : −8 % sur un an (FranceAgriMer) ».")
    cours_date = fields.Date("Relevé le")
    cours_ton = fields.Char("Le ton", compute="_compute_cours_ton")
    # Les coefficients culturaux de référence (FAO-56, Allen et al. 1998, tableaux 11, 12 et 22) : Kc des quatre phases,
    # durée des phases, enracinement et fraction p de la réserve utile facilement utilisable. Besoin = ETo × Kc.
    kc_ini = fields.Float("Kc initial", digits=(3, 2), help="Du semis (ou de la reprise) à environ 10 % de couverture du sol.")
    kc_mi = fields.Float("Kc de mi-saison", digits=(3, 2), help="Pleine couverture : le besoin de pointe.")
    kc_fin = fields.Float("Kc de fin de cycle", digits=(3, 2), help="À la récolte (ou à la chute des feuilles).")
    duree_ini = fields.Integer("Phase initiale (j)")
    duree_dev = fields.Integer("Développement (j)")
    duree_mi = fields.Integer("Mi-saison (j)")
    duree_fin = fields.Integer("Arrière-saison (j)")
    duree_cycle = fields.Integer("Cycle (j)", compute="_compute_duree_cycle")
    hauteur_max = fields.Float("Hauteur maximale (m)", digits=(4, 1))
    racines_min = fields.Float("Enracinement min (m)", digits=(3, 1))
    racines_max = fields.Float("Enracinement max (m)", digits=(3, 1))
    p_tarissement = fields.Float("Fraction p", digits=(3, 2),
                                 help="Part de la réserve utile que la culture consomme sans stress (FAO-56, tableau 22) : la RFU = p × RU.")
    satisfaction = fields.Float("Part du besoin à couvrir", digits=(3, 2), default=1.0,
                                help="1 = on couvre tout le besoin ; moins pour une culture conduite en restriction (vigne de cuve 0,4, olivier 0,6, amandier 0,7…).")
    source_kc = fields.Char("Source des coefficients", default="FAO-56 (Allen et al., 1998)")
    courbe_kc = fields.Html("Courbe du Kc", compute="_compute_courbe_kc", sanitize=False)

    _sql_constraints = [("nom_unique", "unique(name)", "Cette culture existe déjà.")]

    @api.depends("cours_tendance")
    def _compute_cours_ton(self):
        for c in self:
            c.cours_ton = TON_COURS[c.cours_tendance or "stable"]

    @api.depends("duree_ini", "duree_dev", "duree_mi", "duree_fin")
    def _compute_duree_cycle(self):
        for c in self:
            c.duree_cycle = (c.duree_ini or 0) + (c.duree_dev or 0) + (c.duree_mi or 0) + (c.duree_fin or 0)

    def kc_au_jour(self, jour, departement=""):
        """Le Kc au jour `jour` du cycle (0 = semis ou reprise), selon la courbe FAO-56, corrigé pour le climat du département."""
        self.ensure_one()
        if not (self.kc_ini and self.kc_mi and self.duree_cycle):
            return 0.0
        ini, mi, fin = self.kc_ajustes(departement)
        return round(courbe_kc(ini, mi, fin or mi, (self.duree_ini, self.duree_dev, self.duree_mi, self.duree_fin), jour), 3)

    def kc_ajustes(self, departement=""):
        """(Kc ini, Kc mi-saison, Kc fin) pour le climat du département : FAO-56 équation 62 (et 65 pour la fin de cycle si Kc fin ≥ 0,45).
        Kc = Kc tableau + [0,04 (u2 − 2) − 0,004 (HRmin − 45)] × (h / 3)^0,3 ; sans climat connu, les valeurs du tableau."""
        self.ensure_one()
        climat = self.env["cultiveau.climat"].pour(departement)
        ini, mi, fin = self.kc_ini, self.kc_mi, self.kc_fin
        if not climat or not mi:
            return ini, mi, fin
        u2 = min(6.0, max(1.0, climat.vent_u2 or 2.0))
        hr = min(80.0, max(20.0, climat.hr_min or 45.0))
        h = min(10.0, max(0.1, self.hauteur_max or 1.0))
        correction = (0.04 * (u2 - 2) - 0.004 * (hr - 45)) * (h / 3) ** 0.3
        return ini, round(mi + correction, 2), round(fin + correction, 2) if fin >= 0.45 else fin

    def besoin_mm_jour(self, etp, jour):
        """Le besoin en eau de la culture (mm/j) pour une ETP de référence donnée."""
        return round(etp * self.kc_au_jour(jour), 2)

    @api.depends("kc_ini", "kc_mi", "kc_fin", "duree_ini", "duree_dev", "duree_mi", "duree_fin", "couleur")
    def _compute_courbe_kc(self):
        for c in self:
            if not (c.kc_ini and c.kc_mi and c.duree_cycle):
                c.courbe_kc = False
                continue
            L, H, G, D, B = 560, 170, 40, 14, 30  # largeur, hauteur, marge gauche, marge droite, marge basse
            x = lambda j: G + (L - G - D) * j / c.duree_cycle  # noqa: E731
            y = lambda k: 10 + (H - B - 10) * (1 - min(k, 1.35) / 1.35)  # noqa: E731
            a, b, m = c.duree_ini, c.duree_ini + c.duree_dev, c.duree_ini + c.duree_dev + c.duree_mi
            points = [(0, c.kc_ini), (a, c.kc_ini), (b, c.kc_mi), (m, c.kc_mi), (c.duree_cycle, c.kc_fin or c.kc_mi)]
            trace = " ".join(f"{x(j):.1f},{y(k):.1f}" for j, k in points)
            graduations = "".join(
                f"<line x1='{G}' y1='{y(v):.1f}' x2='{L - D}' y2='{y(v):.1f}' stroke='#e3e7ea'/>"
                f"<text x='{G - 6}' y='{y(v) + 4:.1f}' font-size='10' text-anchor='end' fill='#6c7883'>{v:.1f}</text>" for v in (0.4, 0.8, 1.2))
            phases = "".join(
                f"<line x1='{x(j):.1f}' y1='10' x2='{x(j):.1f}' y2='{H - B}' stroke='#c9d1d7' stroke-dasharray='3 3'/>" for j in (a, b, m))
            noms = "".join(
                f"<text x='{x((j1 + j2) / 2):.1f}' y='{H - 12}' font-size='10' text-anchor='middle' fill='#4a5560'>{n} ({j2 - j1} j)</text>"
                for n, j1, j2 in (("initiale", 0, a), ("développement", a, b), ("mi-saison", b, m), ("arrière-saison", m, c.duree_cycle)) if j2 > j1)
            valeurs = "".join(
                f"<text x='{x(j):.1f}' y='{y(k) - 7:.1f}' font-size='11' font-weight='600' text-anchor='middle' fill='{c.couleur or '#2a7f8f'}'>{k:.2f}</text>"
                for j, k in ((a / 2, c.kc_ini), ((b + m) / 2, c.kc_mi), (c.duree_cycle, c.kc_fin or c.kc_mi)))
            c.courbe_kc = Markup(
                f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {L} {H}' style='width:100%;max-width:{L}px'>{graduations}{phases}"
                f"<polyline points='{trace}' fill='none' stroke='{c.couleur or '#2a7f8f'}' stroke-width='3' stroke-linejoin='round'/>{valeurs}{noms}</svg>")

    def _compute_nb_clients(self):
        groupes = self.env["cultiveau.culture.client"]._read_group([("culture_id", "in", self.ids)], ["culture_id"], ["__count"])
        compte = {c.id: n for c, n in groupes}
        for c in self:
            c.nb_clients = compte.get(c.id, 0)

    def _pour_departement(self, objets, departement):
        """Les objets du département s'il y en a, sinon ceux valables partout (département vide)."""
        locaux = objets.filtered(lambda o: o.departement == departement) if departement else objets.browse()
        return locaux or objets.filtered(lambda o: not o.departement)

    def _decalage(self, objets, departement, decalage_client):
        """Le décalage à appliquer : la frise locale est déjà à l'heure du département ; la frise France prend l'avance du climat."""
        locale = bool(departement) and any(o.departement == departement for o in objets)
        climat = self.env["cultiveau.climat"].pour(departement) if not locale else self.env["cultiveau.climat"]
        return locale, (climat.decalage_jours if climat else 0) + (decalage_client or 0), climat

    def stades_pour(self, departement, decalage_client=0):
        """Les stades de la culture pour ce département : la frise locale s'il y en a une, sinon la frise France recalée sur le
        climat du département (calendrier avancé ou retardé, Kc corrigés, ETo du département) ; plus le décalage propre au client."""
        self.ensure_one()
        stades = self._pour_departement(self.stade_ids, departement)
        locale, jours, climat = self._decalage(self.stade_ids, departement, decalage_client)
        if not stades or (not jours and not climat):
            return stades
        ini, mi, fin = self.kc_ini, self.kc_mi, self.kc_fin
        ini2, mi2, fin2 = self.kc_ajustes(departement) if not locale else (ini, mi, fin)
        correspondance = {round(k, 2): k2 for k, k2 in ((ini, ini2), (mi, mi2), (fin, fin2)) if k}

        def kc(k):
            return correspondance.get(round(k or 0.0, 2), k or 0.0)

        Stade = self.env["cultiveau.culture.stade"]
        adaptes = Stade
        for st in stades:
            debut, fin_mois = decaler_plage(st.mois_debut, st.mois_fin, jours)
            mois = mois_couverts(debut, fin_mois)
            kmin, kmax = kc(st.kc_min), kc(st.kc_max)
            valeurs = {"culture_id": self.id, "departement": departement or False, "name": st.name, "sequence": st.sequence,
                       "mois_debut": str(debut), "mois_fin": str(fin_mois), "kc_min": kmin, "kc_max": kmax,
                       "besoin_min": round(kmin * 100), "besoin_max": round(kmax * 100), "irrigation": st.irrigation,
                       "etp_min": st.etp_min, "etp_max": st.etp_max}
            if climat and not locale:
                valeurs.update(etp_min=min(climat.eto(m) for m in mois), etp_max=max(climat.eto(m) for m in mois))
            adaptes |= Stade.new(valeurs)
        return adaptes

    def fenetres_pour(self, departement, decalage_client=0):
        self.ensure_one()
        fenetres = self._pour_departement(self.fenetre_ids, departement)
        _locale, jours, _climat = self._decalage(self.fenetre_ids, departement, decalage_client)
        if not fenetres or not jours:
            return fenetres
        Fenetre = self.env["cultiveau.culture.fenetre"]
        adaptees = Fenetre
        for f in fenetres:
            debut, fin_mois = decaler_plage(f.mois_debut, f.mois_fin, jours)
            adaptees |= Fenetre.new({"culture_id": self.id, "departement": departement or False, "genre": f.genre,
                                     "mois_debut": str(debut), "mois_fin": str(fin_mois)})
        return adaptees

    def ligne_frise(self, departement="", decalage_client=0):
        """Douze cases (stade, intensité, fenêtres) pour cette culture dans ce département (et pour ce client)."""
        self.ensure_one()
        cases = [{"mois": m, "stade": None, "intensite": 0, "projet": False, "achat": False,
                  "posture": POSTURE_CALENDRIER[m], "critique": False} for m in range(1, 13)]
        for s in self.stades_pour(departement, decalage_client):
            for m in s.mois():
                case = cases[m - 1]
                if case["stade"] is None or s.intensite > case["intensite"]:
                    case.update(stade=s, intensite=s.intensite, posture=s.posture or POSTURE_CALENDRIER[m])
                case["critique"] = case["critique"] or s.critique
        for case in cases:
            if case["critique"]:
                case["posture"] = "discret"
        projet, achat = set(), set()
        for f in self.fenetres_pour(departement, decalage_client):
            for m in f.mois():
                cases[m - 1][f.genre] = True
                (projet if f.genre == "projet" else achat).add(m)
        tri = lambda m: m if m >= 7 else m + 12  # noqa: E731 — l'hiver se lit nov → fév
        return {"culture": self, "cases": cases, "projet": sorted(projet, key=tri), "achat": sorted(achat, key=tri)}


class CultureStade(models.Model):
    _name = "cultiveau.culture.stade"
    _description = "Stade d'une culture, avec ses besoins en eau"
    _order = "culture_id, departement, sequence"

    culture_id = fields.Many2one("cultiveau.culture", required=True, ondelete="cascade")
    departement = fields.Char("Département", size=3, help="Vide = valable partout.")
    name = fields.Char("Stade", required=True)
    mois_debut = fields.Selection(MOIS, "Début", required=True)
    mois_fin = fields.Selection(MOIS, "Fin", required=True)
    kc_min = fields.Float("Kc min", digits=(3, 2))
    kc_max = fields.Float("Kc max", digits=(3, 2))
    besoin_min = fields.Integer("Besoin min (% ETP)")
    besoin_max = fields.Integer("Besoin max (% ETP)")
    etp_min = fields.Float("ETP min (mm/j)", digits=(3, 1))
    etp_max = fields.Float("ETP max (mm/j)", digits=(3, 1))
    irrigation = fields.Char("Irrigation recommandée")
    sequence = fields.Integer(default=1)
    intensite = fields.Integer("Intensité", compute="_compute_intensite", help="0 (repos) à 4 (besoin de pointe), d'après le Kc max.")
    periode = fields.Char("Période", compute="_compute_periode")
    critique = fields.Boolean("Période critique", compute="_compute_critique", store=True, readonly=False,
                              help="Semis, plantation, floraison, récolte, vendanges : on ne dérange pas.")
    posture = fields.Selection(POSTURES, "Posture", compute="_compute_posture", store=True, readonly=False,
                               help="Ce que l'agriculteur attend de nous pendant ce stade : écoute (hiver), support (printemps), "
                                    "discrétion (été, périodes critiques), proposition (automne, après récolte).")

    @api.depends("kc_max", "kc_min")
    def _compute_intensite(self):
        for s in self:
            kc = s.kc_max or s.kc_min or 0.0
            s.intensite = 0 if kc < 0.35 else 1 if kc < 0.6 else 2 if kc < 0.85 else 3 if kc < 1.05 else 4

    @api.depends("name")
    def _compute_critique(self):
        for s in self:
            nom = (s.name or "").lower()
            s.critique = any(mot in nom for mot in MOTS_CRITIQUES)

    @api.depends("mois_debut", "mois_fin", "kc_max", "kc_min", "critique")
    def _compute_posture(self):
        for s in self:
            if not (s.mois_debut and s.mois_fin):
                s.posture = "ecoute"
            elif s.critique or s.intensite >= 3:
                s.posture = "discret"
            else:
                s.posture = posture_calendrier(s.mois())

    @api.depends("mois_debut", "mois_fin")
    def _compute_periode(self):
        for s in self:
            s.periode = libelle_mois(s.mois()) if s.mois_debut and s.mois_fin else ""

    def mois(self):
        self.ensure_one()
        return mois_couverts(self.mois_debut, self.mois_fin)


class CultureFenetre(models.Model):
    _name = "cultiveau.culture.fenetre"
    _description = "Fenêtre commerciale d'une culture (projet ou achat)"
    _order = "culture_id, departement, genre"

    culture_id = fields.Many2one("cultiveau.culture", required=True, ondelete="cascade")
    departement = fields.Char("Département", size=3, help="Vide = valable partout.")
    genre = fields.Selection([("projet", "Projet : l'agriculteur a le temps d'étudier"),
                              ("achat", "Achat : il commande et se fait livrer")], required=True)
    mois_debut = fields.Selection(MOIS, "Début", required=True)
    mois_fin = fields.Selection(MOIS, "Fin", required=True)
    periode = fields.Char("Période", compute="_compute_periode")

    @api.depends("mois_debut", "mois_fin")
    def _compute_periode(self):
        for f in self:
            f.periode = libelle_mois(f.mois()) if f.mois_debut and f.mois_fin else ""

    def mois(self):
        self.ensure_one()
        return mois_couverts(self.mois_debut, self.mois_fin)


# Le sol : réserve utile par mètre de sol (mm/m), d'après la texture.
TEXTURES = [("sableux", "Sableux"), ("limono_sableux", "Limono-sableux"), ("limoneux", "Limoneux"), ("limono_argileux", "Limono-argileux"),
            ("argileux", "Argileux"), ("battant", "Battant")]
RU_TEXTURE = {"sableux": 70, "limono_sableux": 110, "limoneux": 170, "limono_argileux": 180, "argileux": 170, "battant": 150}
# Le système d'irrigation : efficience de l'application (part de l'eau pompée réellement utile à la culture).
SYSTEMES = [("goutte", "Goutte à goutte"), ("micro", "Micro-aspersion"), ("pivot", "Pivot, rampe"), ("couverture", "Couverture intégrale"),
            ("enrouleur", "Enrouleur, canon"), ("gravitaire", "Gravitaire, à la raie"), ("sec", "Non irriguée")]
EFFICIENCE_SYSTEME = {"goutte": 0.90, "micro": 0.85, "pivot": 0.85, "couverture": 0.75, "enrouleur": 0.70, "gravitaire": 0.55}
PRECOCITES = [("tres_precoce", "Très précoce (−15 j)"), ("precoce", "Précoce (−7 j)"), ("normale", "Normale"), ("tardive", "Tardive (+7 j)"),
              ("tres_tardive", "Très tardive (+15 j)")]
JOURS_PRECOCITE = {"tres_precoce": -15, "precoce": -7, "normale": 0, "tardive": 7, "tres_tardive": 15}


class CultureClient(models.Model):
    """Ce que cultive un agriculteur, et sur combien d'hectares ; et ce que ça demande en eau, chez lui."""

    _name = "cultiveau.culture.client"
    _description = "Culture d'un agriculteur"
    _order = "partner_id, culture_id"
    _rec_name = "culture_id"

    partner_id = fields.Many2one("res.partner", "Agriculteur", required=True, ondelete="cascade", index=True)
    culture_id = fields.Many2one("cultiveau.culture", "Culture", required=True, ondelete="restrict")
    surface_ha = fields.Float("Surface (ha)", digits=(8, 2))
    departement = fields.Char("Département", size=3, compute="_compute_departement", store=True, readonly=False,
                              help="Celui de l'agriculteur par défaut ; sinon les valeurs générales de la culture.")
    notes = fields.Char("Notes")
    company_id = fields.Many2one(related="partner_id.company_id", store=True)
    # ce que le client fait, lui : sa date de semis, sa variété, son sol, son système
    date_semis = fields.Date("Semis, plantation ou reprise", help="Sa date à lui : la frise et les besoins se recalent dessus. Vide = date habituelle du département.")
    precocite = fields.Selection(PRECOCITES, "Précocité de la variété", default="normale")
    sol_texture = fields.Selection(TEXTURES, "Sol", compute="_compute_depuis_installation", store=True, readonly=False)
    ru_mm_m = fields.Float("Réserve utile (mm par m de sol)", digits=(4, 0), compute="_compute_ru", store=True, readonly=False)
    systeme = fields.Selection(SYSTEMES, "Système d'irrigation", compute="_compute_depuis_installation", store=True, readonly=False)
    efficience = fields.Float("Efficience", digits=(3, 2), compute="_compute_efficience", store=True, readonly=False)
    heures_jour = fields.Float("Heures d'arrosage par jour", default=20.0, digits=(3, 1))
    # l'analyse : département + culture + client
    decalage_jours = fields.Integer("Décalage de sa frise (j)", compute="_compute_analyse",
                                    help="Avance (négatif) ou retard (positif) de ses stades sur la frise France : climat du département, variété, date de semis.")
    kc_ini_aj = fields.Float("Kc initial", digits=(3, 2), compute="_compute_analyse")
    kc_mi_aj = fields.Float("Kc de pointe (ajusté)", digits=(3, 2), compute="_compute_analyse")
    kc_fin_aj = fields.Float("Kc de fin (ajusté)", digits=(3, 2), compute="_compute_analyse")
    eto_pointe = fields.Float("ETo de pointe (mm/j)", digits=(3, 1), compute="_compute_analyse")
    besoin_pointe_mm = fields.Float("Besoin de pointe (mm/j)", digits=(3, 1), compute="_compute_analyse")
    dfc_l_s_ha = fields.Float("Débit fictif continu (l/s/ha)", digits=(4, 2), compute="_compute_analyse")
    debit_m3h = fields.Float("Débit à prévoir (m³/h)", digits=(6, 0), compute="_compute_analyse")
    besoin_saison_mm = fields.Float("Besoin de la culture sur le cycle (mm)", digits=(5, 0), compute="_compute_analyse")
    pluie_efficace_mm = fields.Float("Pluie efficace sur le cycle (mm)", digits=(5, 0), compute="_compute_analyse",
                                     help="Pluie réellement utile en année sèche (4 ans sur 5), formule FAO/AGLW.")
    irrigation_mm = fields.Float("À apporter, année sèche (mm)", digits=(5, 0), compute="_compute_analyse",
                                 help="(Besoin de la culture − pluie efficace − réserve facilement utilisable du sol) × part à couvrir, en année sèche (4 ans sur 5) : la valeur de dimensionnement.")
    irrigation_moyenne_mm = fields.Float("À apporter, année moyenne (mm)", digits=(5, 0), compute="_compute_analyse",
                                         help="Le même bilan avec 75 % de la pluie normale du département.")
    volume_m3 = fields.Float("Volume année sèche (m³, à la pompe)", digits=(8, 0), compute="_compute_analyse")
    volume_moyen_m3 = fields.Float("Volume année moyenne (m³, à la pompe)", digits=(8, 0), compute="_compute_analyse")
    rfu_mm = fields.Float("RFU (mm)", digits=(4, 0), compute="_compute_analyse", help="Réserve facilement utilisable = p × RU × profondeur d'enracinement.")
    tour_eau_j = fields.Float("Tour d'eau en pointe (j)", digits=(3, 1), compute="_compute_analyse")
    analyse = fields.Html("Analyse", compute="_compute_analyse", sanitize=False)
    fenetres = fields.Char("Fenêtres", compute="_compute_fenetres")
    projet_mois = fields.Char("Projet", compute="_compute_fenetres")
    achat_mois = fields.Char("Achat", compute="_compute_fenetres")

    _sql_constraints = [("culture_unique_par_client", "unique(partner_id, culture_id)", "Cette culture est déjà sur la fiche de ce client.")]

    @api.depends("partner_id.departement")
    def _compute_departement(self):
        for cc in self:
            if not cc.departement:
                cc.departement = cc.partner_id.departement or ""

    @api.depends("partner_id")
    def _compute_depuis_installation(self):
        """Repris de l'installation du client quand le module des installations est là ; sinon saisi à la main."""
        for cc in self:
            cc.sol_texture = cc.sol_texture or False
            cc.systeme = cc.systeme or False

    @api.depends("sol_texture")
    def _compute_ru(self):
        for cc in self:
            cc.ru_mm_m = RU_TEXTURE.get(cc.sol_texture, cc.ru_mm_m or 150)

    @api.depends("systeme")
    def _compute_efficience(self):
        for cc in self:
            cc.efficience = EFFICIENCE_SYSTEME.get(cc.systeme, cc.efficience or 0.8)

    def decalage_client(self):
        """Ce qui décale la frise de ce client par rapport à celle de son département : sa variété et sa date de semis."""
        self.ensure_one()
        jours = JOURS_PRECOCITE.get(self.precocite or "normale", 0)
        if self.date_semis and self.culture_id:
            depart = self._depart_habituel()
            if depart is not None:
                ecart = (self.date_semis.timetuple().tm_yday - 1) - depart
                ecart = (ecart + 182) % 365 - 182  # le plus court chemin dans l'année
                jours = ecart  # la date réelle remplace la précocité supposée
        return jours

    def _depart_habituel(self):
        """Le jour de l'année où le cycle commence habituellement dans le département (milieu du mois du premier stade actif)."""
        stades = self.culture_id.stades_pour(self.departement)
        actifs = stades.filtered(lambda s: (s.kc_max or 0) > 0) or stades
        if not actifs:
            return None
        return (DEBUT_MOIS[int(actifs[0].mois_debut) - 1] + 14) % 365

    def ligne_frise(self):
        """La frise de cette culture, pour ce client : son département et ses dates."""
        self.ensure_one()
        return self.culture_id.ligne_frise(self.departement, self.decalage_client())

    @api.depends("culture_id", "departement", "surface_ha", "date_semis", "precocite", "ru_mm_m", "efficience", "heures_jour",
                 "culture_id.kc_ini", "culture_id.kc_mi", "culture_id.kc_fin")
    def _compute_analyse(self):
        Climat = self.env["cultiveau.climat"]
        for cc in self:
            c = cc.culture_id
            vide = dict(decalage_jours=0, kc_ini_aj=0, kc_mi_aj=0, kc_fin_aj=0, eto_pointe=0, besoin_pointe_mm=0, dfc_l_s_ha=0, debit_m3h=0,
                        besoin_saison_mm=0, pluie_efficace_mm=0, irrigation_mm=0, volume_m3=0, irrigation_moyenne_mm=0, volume_moyen_m3=0, rfu_mm=0, tour_eau_j=0, analyse=False)
            if not c or not c.kc_mi or not c.duree_cycle:
                cc.update(vide)
                continue
            climat = Climat.pour(cc.departement)
            ini, mi, fin = c.kc_ajustes(cc.departement)
            durees = (c.duree_ini, c.duree_dev, c.duree_mi, c.duree_fin)
            client = cc.decalage_client()
            depart = cc._depart_habituel()
            depart = ((cc.date_semis.timetuple().tm_yday - 1) if cc.date_semis else (depart or 0) + JOURS_PRECOCITE.get(cc.precocite or "normale", 0)) % 365
            cycle = min(c.duree_cycle, 365)
            etc = pluie = pluie_brute = pointe = eto_pointe = 0.0
            for j in range(cycle):
                m = mois_du_jour(depart + j)
                eto = climat.eto(m) if climat else 0.0
                besoin = eto * courbe_kc(ini, mi, fin or mi, durees, j)
                etc += besoin
                if climat:
                    pluie += pluie_efficace(climat.pluie(m)) / JOURS_MOIS[m - 1]
                    pluie_brute += climat.pluie(m) / JOURS_MOIS[m - 1]
                if besoin > pointe:
                    pointe, eto_pointe = besoin, eto
            efficience = cc.efficience or 0.8
            racines = ((c.racines_min or c.racines_max or 0.6) + (c.racines_max or c.racines_min or 0.6)) / 2  # profondeur efficace moyenne
            rfu = (c.p_tarissement or 0.5) * (cc.ru_mm_m or 150) * racines
            # bilan de la saison : besoin de la culture − pluie utile − réserve du sol (pleine au départ), × la part du besoin à couvrir
            part = c.satisfaction or 1.0
            irrigation = max(0.0, etc - pluie - rfu) * part  # année sèche (4 ans sur 5) : pluie efficace FAO
            irrigation_moyenne = max(0.0, etc - 0.75 * pluie_brute - rfu) * part  # année moyenne
            valeurs = dict(
                decalage_jours=(climat.decalage_jours if climat and not c.stade_ids.filtered(lambda s: s.departement == cc.departement) else 0) + client,
                kc_ini_aj=ini, kc_mi_aj=mi, kc_fin_aj=fin, eto_pointe=eto_pointe, besoin_pointe_mm=round(pointe, 1),
                dfc_l_s_ha=round(pointe / efficience * 10000 / 86400, 2) if pointe else 0,
                debit_m3h=round(pointe / efficience * 10 * (cc.surface_ha or 0) / max(1.0, cc.heures_jour or 20)) if pointe else 0,
                besoin_saison_mm=round(etc), pluie_efficace_mm=round(pluie), irrigation_mm=round(irrigation),
                volume_m3=round(round(irrigation) / efficience * 10 * (cc.surface_ha or 0)), rfu_mm=round(rfu),
                irrigation_moyenne_mm=round(irrigation_moyenne), volume_moyen_m3=round(round(irrigation_moyenne) / efficience * 10 * (cc.surface_ha or 0)),
                tour_eau_j=round(rfu / pointe, 1) if pointe else 0)
            valeurs["analyse"] = cc._rediger_analyse(climat, valeurs) if climat else Markup(
                "<p class='text-muted'>Département inconnu ou sans climat renseigné : Kc et frise de la France entière.</p>")
            cc.update(valeurs)

    def _rediger_analyse(self, climat, v):
        c = self.culture_id
        decalage = v["decalage_jours"]
        quand = ("à l'heure de la frise France" if not decalage else
                 f"{abs(decalage)} jours {'en avance sur' if decalage < 0 else 'en retard sur'} la frise France")
        lignes = [
            f"<b>{c.name}</b> en {climat.name} ({climat.code}) — {dict(climat._fields['zone'].selection).get(climat.zone, '')} : stades {quand}.",
            f"Kc ajusté au climat (vent {climat.vent_u2:g} m/s, air à {climat.hr_min:g} % au plus sec) : initial {v['kc_ini_aj']:.2f}, "
            f"pointe <b>{v['kc_mi_aj']:.2f}</b> (tableau FAO {c.kc_mi:.2f}), fin {v['kc_fin_aj']:.2f}.",
            f"Besoin de pointe <b>{v['besoin_pointe_mm']:.1f} mm/j</b> (ETo {v['eto_pointe']:.1f} × Kc) ; débit fictif continu {v['dfc_l_s_ha']:.2f} l/s/ha"
            + (f" ; pour {self.surface_ha:g} ha en {self.heures_jour:g} h/j : <b>{v['debit_m3h']:,.0f} m³/h</b>".replace(",", " ") if self.surface_ha else "") + ".",
            f"Sur le cycle : besoin de la culture {v['besoin_saison_mm']:.0f} mm, réserve du sol {v['rfu_mm']:.0f} mm"
            + (f", {c.satisfaction:.0%} du besoin couvert (conduite en restriction)" if (c.satisfaction or 1) < 1 else "")
            + f". À apporter : <b>{v['irrigation_moyenne_mm']:.0f} mm en année moyenne</b>, {v['irrigation_mm']:.0f} mm en année sèche (4 ans sur 5, pour dimensionner)"
            + (f", soit <b>{v['volume_moyen_m3']:,.0f} m³</b> et {v['volume_m3']:,.0f} m³ à la pompe (efficience {self.efficience:.0%})".replace(",", " ") if self.surface_ha else "") + ".",
            f"RFU {v['rfu_mm']:.0f} mm (sol {dict(TEXTURES).get(self.sol_texture, 'non renseigné').lower()}, racines {((c.racines_min or c.racines_max) + c.racines_max) / 2:g} m) : "
            f"en pointe, elle tient <b>{v['tour_eau_j']:.1f} jours</b> : l'intervalle maximal entre deux apports qui la remplissent "
            f"(un pivot ou du goutte à goutte arrosent bien plus souvent, à doses plus faibles).",
        ]
        return Markup("<ul class='mb-0'>" + "".join(f"<li>{l}</li>" for l in lignes) + "</ul>")

    def _compute_fenetres(self):
        for cc in self:
            ligne = cc.ligne_frise() if cc.culture_id else {"projet": [], "achat": []}
            cc.projet_mois = libelle_mois(ligne["projet"])
            cc.achat_mois = libelle_mois(ligne["achat"])
            cc.fenetres = f"Projet {cc.projet_mois} · Achat {cc.achat_mois}"

    @api.constrains("surface_ha")
    def _verifier_surface(self):
        for cc in self:
            if cc.surface_ha < 0:
                raise ValidationError("La surface ne peut pas être négative.")

    def fenetres_du_mois(self, mois):
        """Les genres de fenêtre (projet/achat) de cette culture-client ouverts le mois donné."""
        self.ensure_one()
        return {f.genre for f in self.culture_id.fenetres_pour(self.departement, self.decalage_client()) if mois in f.mois()}

    def posture_du_mois(self, mois):
        """(posture, critique, stade) de cette culture-client le mois donné."""
        self.ensure_one()
        case = self.ligne_frise()["cases"][mois - 1]
        return case["posture"], case["critique"], case["stade"]

    @api.model
    def partenaires_a_contacter(self, mois=None, company=None):
        """{partner: [(culture, genre)]} pour un mois (celui d'aujourd'hui par défaut)."""
        mois = mois or fields.Date.context_today(self).month
        domaine = [("company_id", "in", [company.id, False])] if company else []
        resultat = {}
        for cc in self.search(domaine):
            for genre in sorted(cc.fenetres_du_mois(mois)):
                resultat.setdefault(cc.partner_id, []).append((cc.culture_id, genre))
        return resultat

    @api.model
    def _cron_fenetres(self):
        """Le 1er du mois : une activité « appeler » pour chaque client qui entre dans une fenêtre."""
        mois = fields.Date.context_today(self).month
        type_appel = self.env.ref("mail.mail_activity_data_call", raise_if_not_found=False)
        n = 0
        for partner, cultures in self.partenaires_a_contacter(mois).items():
            resume = " ; ".join(f"{c.name} ({'projet' if g == 'projet' else 'achat'})" for c, g in cultures)
            deja = partner.activity_ids.filtered(lambda a: a.summary and a.summary.startswith("Fenêtre ") and a.date_deadline.month == mois)
            if deja:
                continue
            critiques = [cc.culture_id.name for cc in partner.cultiveau_culture_ids if cc.posture_du_mois(mois)[1]]
            garde = (f"<p><b>Attention</b> : {', '.join(critiques)} en période critique ce mois-ci. Attendre la fin du stade avant d'appeler.</p>"
                     if critiques else "")
            partner.activity_schedule(
                act_type_xmlid="mail.mail_activity_data_call" if type_appel else None,
                summary=f"Fenêtre {MOIS[mois - 1][1]} : {resume}",
                note="<p>La frise culturale ouvre une fenêtre commerciale ce mois-ci. Projet : proposer l'analyse des besoins. "
                     "Achat : proposer la commande, la livraison, la visite de pré-saison.</p>" + garde,
                user_id=(partner.user_id or self.env.user).id)
            n += 1
        return n
