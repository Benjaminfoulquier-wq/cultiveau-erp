from odoo import api, fields, models
from odoo.exceptions import ValidationError

MOIS = [(str(i), n) for i, n in enumerate(
    ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"], start=1)]
MOIS_COURTS = ["Jan", "Fév", "Mar", "Avr", "Mai", "Juin", "Juil", "Août", "Sep", "Oct", "Nov", "Déc"]
CATEGORIES = [("vigne", "Vigne"), ("arbo", "Arboriculture"), ("grandes_cultures", "Grandes cultures"),
              ("maraichage", "Maraîchage"), ("prairies", "Prairies et fourrages"), ("sous_abri", "Sous abri"), ("autre", "Autre")]


def mois_couverts(debut, fin):
    """De `debut` à `fin` inclus, en passant l'hiver si besoin : (11, 2) → [11, 12, 1, 2]."""
    debut, fin = int(debut), int(fin)
    if debut <= fin:
        return list(range(debut, fin + 1))
    return list(range(debut, 13)) + list(range(1, fin + 1))


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

    _sql_constraints = [("nom_unique", "unique(name)", "Cette culture existe déjà.")]

    def _compute_nb_clients(self):
        groupes = self.env["cultiveau.culture.client"]._read_group([("culture_id", "in", self.ids)], ["culture_id"], ["__count"])
        compte = {c.id: n for c, n in groupes}
        for c in self:
            c.nb_clients = compte.get(c.id, 0)

    def _pour_departement(self, objets, departement):
        """Les objets du département s'il y en a, sinon ceux valables partout (département vide)."""
        locaux = objets.filtered(lambda o: o.departement == departement) if departement else objets.browse()
        return locaux or objets.filtered(lambda o: not o.departement)

    def stades_pour(self, departement):
        self.ensure_one()
        return self._pour_departement(self.stade_ids, departement)

    def fenetres_pour(self, departement):
        self.ensure_one()
        return self._pour_departement(self.fenetre_ids, departement)

    def ligne_frise(self, departement=""):
        """Douze cases (stade, intensité, fenêtres) pour cette culture dans ce département."""
        self.ensure_one()
        cases = [{"mois": m, "stade": None, "intensite": 0, "projet": False, "achat": False} for m in range(1, 13)]
        for s in self.stades_pour(departement):
            for m in s.mois():
                case = cases[m - 1]
                if case["stade"] is None or s.intensite > case["intensite"]:
                    case.update(stade=s, intensite=s.intensite)
        projet, achat = set(), set()
        for f in self.fenetres_pour(departement):
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

    @api.depends("kc_max", "kc_min")
    def _compute_intensite(self):
        for s in self:
            kc = s.kc_max or s.kc_min or 0.0
            s.intensite = 0 if kc < 0.35 else 1 if kc < 0.6 else 2 if kc < 0.85 else 3 if kc < 1.05 else 4

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


class CultureClient(models.Model):
    """Ce que cultive un agriculteur, et sur combien d'hectares."""

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
    fenetres = fields.Char("Fenêtres", compute="_compute_fenetres")
    projet_mois = fields.Char("Projet", compute="_compute_fenetres")
    achat_mois = fields.Char("Achat", compute="_compute_fenetres")

    _sql_constraints = [("culture_unique_par_client", "unique(partner_id, culture_id)", "Cette culture est déjà sur la fiche de ce client.")]

    @api.depends("partner_id.departement")
    def _compute_departement(self):
        for cc in self:
            if not cc.departement:
                cc.departement = cc.partner_id.departement or ""

    def _compute_fenetres(self):
        for cc in self:
            ligne = cc.culture_id.ligne_frise(cc.departement) if cc.culture_id else {"projet": [], "achat": []}
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
        return {f.genre for f in self.culture_id.fenetres_pour(self.departement) if mois in f.mois()}

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
            partner.activity_schedule(
                act_type_xmlid="mail.mail_activity_data_call" if type_appel else None,
                summary=f"Fenêtre {MOIS[mois - 1][1]} : {resume}",
                note="<p>La frise culturale ouvre une fenêtre commerciale ce mois-ci. Projet : proposer l'analyse des besoins. "
                     "Achat : proposer la commande, la livraison, la visite de pré-saison.</p>",
                user_id=(partner.user_id or self.env.user).id)
            n += 1
        return n
