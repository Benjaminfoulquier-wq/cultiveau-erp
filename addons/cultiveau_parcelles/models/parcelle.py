"""Les parcelles des clients, lues dans leur déclaration PAC (Telepac), suivies par Sentinel-2 (NDVI, NDWI) ; une alerte quand ça cloche."""
import json
import logging
import re
from datetime import date, timedelta

from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import UserError

from . import geo, sentinel, telepac

_logger = logging.getLogger(__name__)

GENRES_ALERTE = [("vigueur", "Chute de vigueur"), ("stress", "Signe de stress hydrique"), ("heterogene", "Parcelle hétérogène")]
CONSEILS = {
    "vigueur": "La vigueur de la culture a nettement baissé : vérifier sur place (arrosage arrêté, panne, gel, grêle, ravageur, maladie).",
    "stress": "L'eau contenue dans les feuilles baisse : la culture manque d'eau. Vérifier que l'irrigation tourne et que les doses suivent le besoin (pression, débit, bouchage).",
    "heterogene": "La parcelle n'est pas uniforme : une partie pousse moins bien. C'est souvent un défaut de répartition de l'eau (buses, goutteurs bouchés, pression) — un diagnostic d'uniformité s'impose.",
}
MOTS_FIN_DE_CYCLE = re.compile(r"récolte|recolte|moisson|vendange|arrachage|maturation|défanage|sénescence|chute des feuilles|repos|dernière", re.I)


class CodePac(models.Model):
    _name = "cultiveau.code.pac"
    _description = "Code culture de la déclaration PAC"
    _order = "a_relier desc, code"
    _rec_name = "code"

    code = fields.Char("Code PAC", size=3, required=True, index=True)
    libelle = fields.Char("Libellé PAC")
    culture_id = fields.Many2one("cultiveau.culture", "Culture Cultiveau", help="La culture de la frise qui lui correspond : ses Kc, sa frise, ses besoins.")
    sans_culture = fields.Boolean("Pas une culture", help="Jachère, bande tampon, surface non exploitée… : rien à irriguer ni à suivre.")
    a_relier = fields.Boolean("À relier", compute="_compute_a_relier", store=True)
    nb_parcelles = fields.Integer("Parcelles", compute="_compute_nb")

    _sql_constraints = [("code_unique", "unique(code)", "Ce code PAC existe déjà.")]

    @api.depends("culture_id", "sans_culture")
    def _compute_a_relier(self):
        for c in self:
            c.a_relier = not c.culture_id and not c.sans_culture

    @api.model
    def _completer_codes(self, codes):
        for code, libelle, sans_culture in codes:
            existant = self.search([("code", "=", code)], limit=1)
            if not existant:
                self.create({"code": code, "libelle": libelle, "sans_culture": sans_culture})
            elif not existant.culture_id:
                existant.write({"libelle": existant.libelle or libelle, "sans_culture": sans_culture})

    def _compute_nb(self):
        compte = {c.id: n for c, n in self.env["cultiveau.parcelle"]._read_group([("code_id", "in", self.ids)], ["code_id"], ["__count"])}
        for c in self:
            c.nb_parcelles = compte.get(c.id, 0)

    def write(self, vals):
        res = super().write(vals)
        if "culture_id" in vals:  # relier un code met à jour les parcelles et les cultures des clients
            parcelles = self.env["cultiveau.parcelle"].search([("code_id", "in", self.ids)])
            parcelles.write({"culture_id": vals["culture_id"]})
            for partner in parcelles.partner_id:
                partner.cultiveau_cultures_depuis_parcelles()
        if vals.get("sans_culture"):  # une jachère ne se suit pas au satellite
            self.env["cultiveau.parcelle"].search([("code_id", "in", self.ids)]).write({"suivi": False})
        return res


class Parcelle(models.Model):
    _name = "cultiveau.parcelle"
    _description = "Parcelle d'un client (déclaration PAC)"
    _inherit = ["mail.thread"]
    _order = "partner_id, campagne desc, tri, id"

    name = fields.Char("Parcelle", compute="_compute_name", store=True)
    partner_id = fields.Many2one("res.partner", "Client", required=True, index=True, ondelete="cascade")
    company_id = fields.Many2one("res.company", "Adhérent", related="partner_id.company_id", store=True)
    campagne = fields.Integer("Campagne PAC", required=True, default=lambda self: fields.Date.context_today(self).year, index=True)
    pacage = fields.Char("N° PACAGE")
    ilot = fields.Char("Îlot")
    numero = fields.Char("N° de parcelle")
    tri = fields.Integer(compute="_compute_tri", store=True, index=True)
    code_id = fields.Many2one("cultiveau.code.pac", "Code culture PAC", index=True)
    precision = fields.Char("Précision PAC")
    culture_id = fields.Many2one("cultiveau.culture", "Culture", index=True, tracking=True)
    surface_ha = fields.Float("Surface (ha)", digits=(8, 2))
    commune = fields.Char("Commune (INSEE)")
    contour = fields.Text("Contour (GPS)", help="Liste [[longitude, latitude], …] du contour extérieur.")
    longitude = fields.Float("Longitude", digits=(9, 6))
    latitude = fields.Float("Latitude", digits=(9, 6))
    irriguee = fields.Boolean("Irriguée", default=True)
    suivi = fields.Boolean("Suivi par satellite", default=True)
    indice_ids = fields.One2many("cultiveau.parcelle.indice", "parcelle_id", string="Mesures satellite")
    alerte_ids = fields.One2many("cultiveau.parcelle.alerte", "parcelle_id", string="Alertes")
    dernier_ndvi = fields.Float("NDVI", digits=(3, 2), compute="_compute_dernieres", store=True)
    dernier_ndwi = fields.Float("NDWI", digits=(3, 2), compute="_compute_dernieres", store=True)
    derniere_mesure = fields.Date("Dernière image", compute="_compute_dernieres", store=True)
    etat = fields.Selection([("ok", "Rien à signaler"), ("alerte", "À vérifier"), ("inconnu", "Pas encore d'image"), ("hors_suivi", "Non suivie")], "État",
                            compute="_compute_etat", store=True)
    carte = fields.Html("Contour", compute="_compute_carte", sanitize=False)
    courbe = fields.Html("Évolution", compute="_compute_courbe", sanitize=False)
    lien_geoportail = fields.Char("Géoportail", compute="_compute_liens")
    lien_copernicus = fields.Char("Copernicus Browser", compute="_compute_liens")

    @api.depends("ilot", "numero", "culture_id", "code_id", "campagne")
    def _compute_name(self):
        for p in self:
            culture = p.culture_id.name or (p.code_id.code and f"code {p.code_id.code}") or "culture inconnue"
            p.name = f"Îlot {p.ilot or '?'} · parcelle {p.numero or '?'} — {culture} ({p.campagne})"

    @api.depends("indice_ids.date", "indice_ids.ndvi", "indice_ids.ndwi")
    def _compute_dernieres(self):
        for p in self:
            d = p.indice_ids.sorted("date")[-1:] if p.indice_ids else p.indice_ids
            p.dernier_ndvi, p.dernier_ndwi, p.derniere_mesure = (d.ndvi, d.ndwi, d.date) if d else (0.0, 0.0, False)

    @api.depends("alerte_ids.etat", "indice_ids", "suivi")
    def _compute_etat(self):
        for p in self:
            if p.alerte_ids.filtered(lambda a: a.etat == "nouvelle"):
                p.etat = "alerte"
            elif not p.suivi:
                p.etat = "hors_suivi"
            else:
                p.etat = "ok" if p.indice_ids else "inconnu"

    @api.depends("ilot", "numero")
    def _compute_tri(self):
        """Îlot 2 avant îlot 10 : l'ordre des numéros, pas celui des lettres."""
        def nombre(v):
            chiffres = "".join(c for c in (v or "") if c.isdigit())[:6]
            return int(chiffres) if chiffres else 0
        for p in self:
            p.tri = nombre(p.ilot) * 1000 + nombre(p.numero) % 1000

    def anneau(self):
        self.ensure_one()
        try:
            return [tuple(pt) for pt in json.loads(self.contour or "[]")]
        except ValueError:
            return []

    @api.depends("longitude", "latitude")
    def _compute_liens(self):
        for p in self:
            if p.longitude and p.latitude:
                p.lien_geoportail = (f"https://www.geoportail.gouv.fr/carte?c={p.longitude:.6f},{p.latitude:.6f}&z=17"
                                     "&l0=ORTHOIMAGERY.ORTHOPHOTOS::GEOPORTAIL:OGC:WMTS(1)&l1=LANDUSE.AGRICULTURE.LATEST::GEOPORTAIL:OGC:WMTS(0.6)&permalink=yes")
                p.lien_copernicus = f"https://browser.dataspace.copernicus.eu/?zoom=15&lat={p.latitude:.5f}&lng={p.longitude:.5f}&datasetId=S2_L2A_CDAS"
            else:
                p.lien_geoportail = p.lien_copernicus = False

    @api.depends("contour", "culture_id.couleur", "etat")
    def _compute_carte(self):
        for p in self:
            p.carte = dessiner_carte(p, 260, 200, legende=False) if p.contour else False

    @api.depends("indice_ids")
    def _compute_courbe(self):
        for p in self:
            p.courbe = dessiner_courbe(p) if p.indice_ids else False

    # ---------------------------------------------------------------- l'import de la déclaration PAC

    @api.model
    def importer(self, partner, nom_fichier, contenu, campagne=None):
        """Lit le fichier, crée ou met à jour les parcelles du client, relie les codes PAC aux cultures, met à jour ses cultures."""
        try:
            lues = telepac.lire(nom_fichier, contenu)
        except (ValueError, KeyError) as e:
            raise UserError(f"Fichier illisible : {e}")
        except Exception as e:  # noqa: BLE001 — XML mal formé, ZIP abîmé…
            raise UserError(f"Fichier illisible ({e.__class__.__name__}) : envoyez l'export XML de Telepac ou le ZIP des parcelles.")
        if not lues:
            raise UserError("Aucune parcelle trouvée dans ce fichier (il faut l'export des parcelles avec leur code culture).")
        campagne = int(campagne or fields.Date.context_today(self).year)
        Code = self.env["cultiveau.code.pac"].sudo()
        bilan = {"parcelles": 0, "creees": 0, "sans_contour": 0, "codes_inconnus": set()}
        for p in lues:
            code = Code.search([("code", "=", p["code"])], limit=1) or Code.create({"code": p["code"]})
            if code.a_relier:
                bilan["codes_inconnus"].add(code.code)
            anneau = geo.vers_wgs84(geo.fermer(p["anneau"])) if p["anneau"] else None
            valeurs = {"partner_id": partner.id, "campagne": campagne, "pacage": p.get("pacage"), "ilot": p.get("ilot"), "numero": p.get("numero"),
                       "code_id": code.id, "culture_id": code.culture_id.id, "precision": p.get("precision"), "commune": p.get("commune")}
            if code.sans_culture:
                valeurs["suivi"] = False
            if anneau:
                lon, lat = geo.centre(anneau[:-1])
                valeurs.update(contour=json.dumps([[round(x, 6), round(y, 6)] for x, y in anneau]), longitude=lon, latitude=lat)
                dessinee = geo.surface_ha(anneau[:-1])
                declaree = p.get("surface_ha")
                # Telepac donne la surface admissible en ares dans son XML (403 = 4,03 ha) : on garde l'unité qui colle au dessin
                if declaree and dessinee and abs(declaree / 100 - dessinee) < abs(declaree - dessinee):
                    declaree = declaree / 100
                valeurs["surface_ha"] = round(declaree or dessinee, 2)
            else:
                valeurs["surface_ha"] = p.get("surface_ha") or 0.0
                bilan["sans_contour"] += 1
            existante = self.search([("partner_id", "=", partner.id), ("campagne", "=", campagne), ("ilot", "=", valeurs["ilot"]),
                                     ("numero", "=", valeurs["numero"])], limit=1) if valeurs["ilot"] or valeurs["numero"] else self.browse()
            if existante:
                existante.write(valeurs)
            else:
                self.create(valeurs)
                bilan["creees"] += 1
            bilan["parcelles"] += 1
        self._completer_client(partner, nom_fichier, contenu, lues)
        partner.cultiveau_cultures_depuis_parcelles(campagne)
        partner.message_post(body=Markup("<p>Déclaration PAC %s importée : %s parcelles, %s ha.</p>") % (
            campagne, bilan["parcelles"], round(sum(self.search([("partner_id", "=", partner.id), ("campagne", "=", campagne)]).mapped("surface_ha")), 1)),
            subtype_xmlid="mail.mt_note")
        bilan["codes_inconnus"] = sorted(bilan["codes_inconnus"])
        return bilan

    @api.model
    def _completer_client(self, partner, nom_fichier, contenu, lues):
        """Ce que la déclaration dit du client et que sa fiche ignore encore : exploitation, e-mail, SIRET, département."""
        entete = telepac.lire_entete(contenu) if nom_fichier.lower().endswith(".xml") else {}
        valeurs = {}
        if entete.get("courriel") and not partner.email:
            valeurs["email"] = entete["courriel"]
        if entete.get("siret") and "company_registry" in partner._fields and not partner.company_registry:
            valeurs["company_registry"] = entete["siret"]
        communes = [p["commune"] for p in lues if p.get("commune")]
        if communes and not partner.departement:
            insee = max(set(communes), key=communes.count)
            valeurs["departement"] = insee[:3] if insee.startswith("97") else insee[:2]
        if entete.get("exploitation") and not partner.exploitation and entete["exploitation"].lower() != (partner.name or "").lower():
            valeurs["exploitation"] = entete["exploitation"]
        if valeurs:
            partner.write(valeurs)

    # ---------------------------------------------------------------- le satellite

    @api.model
    def _identifiants(self):
        param = self.env["ir.config_parameter"].sudo().get_param
        return param("cultiveau.copernicus_id") or "", param("cultiveau.copernicus_secret") or ""

    def action_actualiser(self):
        n = self.actualiser_satellite(forcer=True)
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"title": "Suivi satellite", "message": f"{n} nouvelle(s) image(s) Sentinel-2 analysée(s).", "sticky": False,
                           "next": {"type": "ir.actions.client", "tag": "soft_reload"}}}

    def actualiser_satellite(self, forcer=False, aujourdhui=None):
        """Va chercher les nouvelles images de chaque parcelle suivie, puis cherche ce qui cloche. Renvoie le nombre de mesures ajoutées."""
        client_id, secret = self._identifiants()
        if not (client_id and secret):
            raise UserError("Le suivi satellite n'est pas branché : saisir l'identifiant et le secret Copernicus dans Réglages → Cultiveau.")
        aujourdhui = aujourdhui or fields.Date.context_today(self)
        acces, ajoutees = None, 0
        for p in self.filtered(lambda p: p.suivi and p.contour):
            debut = (p.derniere_mesure + timedelta(days=1)) if p.derniere_mesure else max(date(p.campagne, 3, 1), aujourdhui - timedelta(days=150))
            if debut > aujourdhui or (not forcer and p.derniere_mesure and (aujourdhui - p.derniere_mesure).days < 5):
                continue
            acces = acces or sentinel.jeton(client_id, secret)
            try:
                mesures = sentinel.statistiques(acces, p.anneau(), debut.isoformat(), aujourdhui.isoformat())
            except sentinel.ErreurSatellite as e:
                if "Quota" in str(e):
                    raise UserError(str(e))
                _logger.warning("Parcelle %s : %s", p.id, e)
                continue
            deja = {i.date.isoformat() for i in p.indice_ids}
            nouvelles = [m for m in mesures if m["date"] not in deja]
            if nouvelles:
                self.env["cultiveau.parcelle.indice"].create([{**m, "parcelle_id": p.id} for m in nouvelles])
                ajoutees += len(nouvelles)
                p.analyser(aujourdhui)
        return ajoutees

    @api.model
    def _cron_satellite(self):
        """Chaque jour : les parcelles de la campagne dont la dernière image date de plus de 5 jours, un lot à la fois."""
        if not all(self._identifiants()):
            return
        campagne = fields.Date.context_today(self).year
        lot = self.search([("campagne", "=", campagne), ("suivi", "=", True), ("contour", "!=", False)], order="derniere_mesure asc nulls first", limit=200)
        try:
            lot.actualiser_satellite()
        except UserError as e:
            _logger.warning("Suivi satellite : %s", e)

    # ---------------------------------------------------------------- ce qui cloche

    def _stade(self, jour):
        """Le stade de la culture ce jour-là, d'après la frise du client (son département, ses dates) : (nom, kc_max) ou (None, 0)."""
        self.ensure_one()
        if not self.culture_id:
            return None, 0.0
        cc = self.env["cultiveau.culture.client"].search([("partner_id", "=", self.partner_id.id), ("culture_id", "=", self.culture_id.id)], limit=1)
        ligne = cc.ligne_frise() if cc else self.culture_id.ligne_frise(self.partner_id.departement or "")
        case = ligne["cases"][jour.month - 1]
        stade = case["stade"]
        return (stade.name, stade.kc_max or 0.0) if stade else (None, 0.0)

    def analyser(self, aujourdhui=None):
        """Les trois signaux : chute de vigueur, stress hydrique, hétérogénéité — seulement aux stades où la culture doit être verte."""
        aujourdhui = aujourdhui or fields.Date.context_today(self)
        Alerte = self.env["cultiveau.parcelle.alerte"]
        creees = Alerte
        for p in self:
            serie = p.indice_ids.sorted("date")
            if len(serie) < 2:
                continue
            derniere = serie[-1]
            if (aujourdhui - derniere.date).days > 20:
                continue  # rien de récent : on ne lève pas d'alerte sur une vieille image
            stade, kc = p._stade(derniere.date)
            if not stade or kc < 0.5 or MOTS_FIN_DE_CYCLE.search(stade):
                continue  # repos, semis, maturation, récolte : le vert qui baisse est normal
            recentes = serie.filtered(lambda i: (derniere.date - i.date).days <= 20 and i != derniere)
            constats = []
            if recentes:
                plus_vert = max(recentes.mapped("ndvi"))
                if plus_vert >= 0.4 and plus_vert - derniere.ndvi >= 0.15:
                    constats.append(("vigueur", f"NDVI passé de {plus_vert:.2f} à {derniere.ndvi:.2f} en moins de 3 semaines ({stade.lower()})."))
                plus_humide = max(recentes.mapped("ndwi"))
                if derniere.ndvi >= 0.4 and plus_humide - derniere.ndwi >= 0.10:
                    constats.append(("stress", f"NDWI passé de {plus_humide:.2f} à {derniere.ndwi:.2f} en moins de 3 semaines ({stade.lower()})."))
            if derniere.ndvi >= 0.5 and derniere.ndwi < 0.15 and not any(g == "stress" for g, _ in constats):
                constats.append(("stress", f"NDWI bas ({derniere.ndwi:.2f}) sur une culture bien développée (NDVI {derniere.ndvi:.2f}, {stade.lower()})."))
            if derniere.ndvi >= 0.4 and derniere.ndvi_ecart >= 0.15 and kc >= 0.8:
                constats.append(("heterogene", f"NDVI très dispersé dans la parcelle (écart-type {derniere.ndvi_ecart:.2f}) en pleine saison."))
            for genre, detail in constats:
                if p.alerte_ids.filtered(lambda a: a.genre == genre and (aujourdhui - a.date).days < 14):
                    continue  # déjà signalé il y a moins de deux semaines
                creees |= Alerte.create({"parcelle_id": p.id, "genre": genre, "date": derniere.date, "detail": detail,
                                         "ndvi": derniere.ndvi, "ndwi": derniere.ndwi})
        return creees


class Indice(models.Model):
    _name = "cultiveau.parcelle.indice"
    _description = "Mesure Sentinel-2 d'une parcelle"
    _order = "parcelle_id, date"

    parcelle_id = fields.Many2one("cultiveau.parcelle", required=True, ondelete="cascade", index=True)
    date = fields.Date("Date", required=True)
    ndvi = fields.Float("NDVI", digits=(4, 3))
    ndwi = fields.Float("NDWI", digits=(4, 3))
    ndvi_ecart = fields.Float("Dispersion du NDVI", digits=(4, 3))
    couverture = fields.Float("Part visible", digits=(3, 2), help="Part des pixels sans nuage ni ombre.")

    _sql_constraints = [("date_unique", "unique(parcelle_id, date)", "Une seule mesure par date et par parcelle.")]


class Alerte(models.Model):
    _name = "cultiveau.parcelle.alerte"
    _description = "Alerte satellite sur une parcelle"
    _inherit = ["mail.thread"]
    _order = "date desc, id desc"

    parcelle_id = fields.Many2one("cultiveau.parcelle", required=True, ondelete="cascade", index=True)
    partner_id = fields.Many2one(related="parcelle_id.partner_id", store=True, index=True)
    company_id = fields.Many2one(related="parcelle_id.company_id", store=True)
    culture_id = fields.Many2one(related="parcelle_id.culture_id", store=True)
    genre = fields.Selection(GENRES_ALERTE, "Ce qui cloche", required=True)
    date = fields.Date("Image du", required=True)
    detail = fields.Char("Constat")
    conseil = fields.Text("Que faire", compute="_compute_conseil")
    ndvi = fields.Float("NDVI", digits=(3, 2))
    ndwi = fields.Float("NDWI", digits=(3, 2))
    etat = fields.Selection([("nouvelle", "À traiter"), ("client_prevenu", "Client prévenu"), ("verifiee", "Vérifiée, rien d'anormal")],
                            string="État", default="nouvelle", required=True, tracking=True)

    def _compute_conseil(self):
        for a in self:
            a.conseil = CONSEILS.get(a.genre, "")

    @api.model_create_multi
    def create(self, vals_list):
        alertes = super().create(vals_list)
        for a in alertes:
            partner = a.partner_id
            societe = a.parcelle_id.company_id or self.env.company
            responsable = partner.user_id or self.env["res.users"].search([("company_ids", "in", societe.id), ("share", "=", False)], limit=1) or self.env.user
            if responsable:
                partner.activity_schedule("mail.mail_activity_data_call", user_id=responsable.id,
                                          summary=f"{'Irrigation' if a.genre == 'irrigation' else 'Satellite'} : {dict(self._fields['genre'].selection)[a.genre].lower()} — {a.parcelle_id.name}",
                                          note=Markup("<p>%s</p><p>%s</p>") % (a.detail or "", a.conseil))
        if self.env["ir.config_parameter"].sudo().get_param("cultiveau.parcelles_prevenir_client") == "True":
            alertes.filtered(lambda a: a.partner_id.email).action_prevenir_client()
        return alertes

    def action_prevenir_client(self):
        modele = self.env.ref("cultiveau_parcelles.modele_mail_alerte")
        for a in self:
            if not a.partner_id.email:
                raise UserError(f"{a.partner_id.name} n'a pas d'e-mail.")
            a.message_post_with_source(modele, subtype_xmlid="mail.mt_comment", email_layout_xmlid="mail.mail_notification_light")
            a.etat = "client_prevenu"

    def action_rien_d_anormal(self):
        self.write({"etat": "verifiee"})


# ---------------------------------------------------------------- les dessins (SVG, sans bibliothèque)

def _cadre(anneaux, largeur, hauteur, marge=8):
    pts = [pt for a in anneaux for pt in a]
    lon0, lon1 = min(p[0] for p in pts), max(p[0] for p in pts)
    lat0, lat1 = min(p[1] for p in pts), max(p[1] for p in pts)
    import math
    kx = math.cos(math.radians((lat0 + lat1) / 2))
    l, h = max((lon1 - lon0) * kx, 1e-9), max(lat1 - lat0, 1e-9)
    echelle = min((largeur - 2 * marge) / l, (hauteur - 2 * marge) / h)
    ox = (largeur - l * echelle) / 2
    oy = (hauteur - h * echelle) / 2
    return lambda lon, lat: (ox + (lon - lon0) * kx * echelle, hauteur - oy - (lat - lat0) * echelle)


def couleur_ndvi(ndvi):
    if ndvi is None or ndvi <= 0:
        return "#c9b79c"
    paliers = [(0.2, "#d9c27a"), (0.4, "#c3d36b"), (0.6, "#8cc152"), (0.75, "#4fa83a"), (2, "#2e7d32")]
    return next(c for seuil, c in paliers if ndvi < seuil)


def dessiner_carte(parcelles, largeur=640, hauteur=360, selon="culture", legende=True):
    """Les contours des parcelles, colorés par culture (ou par NDVI), une pastille rouge sur celles à vérifier."""
    avec = [p for p in parcelles if p.contour]
    anneaux = [p.anneau() for p in avec]
    if not any(anneaux):
        return False
    proj = _cadre([a for a in anneaux if a], largeur, hauteur)
    formes = []
    for p, a in zip(avec, anneaux):
        if not a:
            continue
        points = " ".join("%.1f,%.1f" % proj(x, y) for x, y in a)
        teinte = couleur_ndvi(p.dernier_ndvi) if selon == "ndvi" else (p.culture_id.couleur or ("#dfe6d6" if p.code_id.sans_culture else "#9aa3ab"))
        cx, cy = proj(p.longitude, p.latitude)
        titre = f"{p.name} — {p.surface_ha:g} ha" + (f" — NDVI {p.dernier_ndvi:.2f}" if p.derniere_mesure else "")
        formes.append(f"<polygon points='{points}' fill='{teinte}' fill-opacity='0.75' stroke='#1d3b45' stroke-width='1'><title>{Markup.escape(titre)}</title></polygon>")
        if p.etat == "alerte":
            formes.append(f"<circle cx='{cx:.1f}' cy='{cy:.1f}' r='6' fill='#d94f45' stroke='#ffffff' stroke-width='2'/>")
    bas = _legende(avec, hauteur, selon) if legende else ""
    return Markup(f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {largeur} {hauteur + (30 if legende else 0)}' style='width:100%;max-width:{largeur}px;background:#eef3ea;"
                  f"border-radius:8px'>{''.join(formes)}{bas}</svg>")


def _legende(parcelles, y, selon):
    """Sous la carte : chaque culture avec sa surface, ou l'échelle du NDVI."""
    if selon == "ndvi":
        items = [("#c9b79c", "sol nu"), ("#d9c27a", "< 0,2"), ("#c3d36b", "0,2"), ("#8cc152", "0,4"), ("#4fa83a", "0,6"), ("#2e7d32", "> 0,75")]
    else:
        surfaces = {}
        for p in parcelles:
            if p.culture_id:
                cle = (p.culture_id.couleur or "#9aa3ab", p.culture_id.name)
            elif p.code_id.sans_culture:
                cle = ("#dfe6d6", "Jachère, bordures")
            else:
                cle = ("#9aa3ab", f"{p.code_id.code or 'Code'} à relier")
            surfaces[cle] = surfaces.get(cle, 0) + p.surface_ha
        items = [(c, f"{nom} {ha:.1f} ha".replace(".", ",")) for (c, nom), ha in sorted(surfaces.items(), key=lambda kv: -kv[1])]
    x, morceaux = 10, []
    for couleur, texte in items:
        morceaux.append(f"<rect x='{x}' y='{y + 9}' width='12' height='12' rx='2' fill='{couleur}' stroke='#1d3b45' stroke-width='0.5'/>"
                        f"<text x='{x + 16}' y='{y + 19}' font-size='11' fill='#33414d'>{Markup.escape(texte)}</text>")
        x += 24 + 5.6 * len(texte)
    return "".join(morceaux)


def dessiner_courbe(parcelle, largeur=620, hauteur=200):
    serie = parcelle.indice_ids.sorted("date")
    d0, d1 = serie[0].date, serie[-1].date
    span = max((d1 - d0).days, 1)
    G, D, H, B = 34, 10, 10, 24
    x = lambda d: G + (largeur - G - D) * (d - d0).days / span  # noqa: E731
    y = lambda v: H + (hauteur - H - B) * (1 - (max(-0.2, min(1.0, v)) + 0.2) / 1.2)  # noqa: E731
    ligne = lambda attr: " ".join(f"{x(i.date):.1f},{y(i[attr]):.1f}" for i in serie)  # noqa: E731
    grille = "".join(f"<line x1='{G}' y1='{y(v):.1f}' x2='{largeur - D}' y2='{y(v):.1f}' stroke='#e3e7ea'/>"
                     f"<text x='{G - 4}' y='{y(v) + 3:.1f}' font-size='9' text-anchor='end' fill='#6c7883'>{v:.1f}</text>" for v in (0.0, 0.4, 0.8))
    alertes = "".join(f"<line x1='{x(a.date):.1f}' y1='{H}' x2='{x(a.date):.1f}' y2='{hauteur - B}' stroke='#d94f45' stroke-dasharray='3 3'/>"
                      for a in parcelle.alerte_ids if d0 <= a.date <= d1)
    dates = f"<text x='{G}' y='{hauteur - 6}' font-size='10' fill='#4a5560'>{d0:%d/%m}</text><text x='{largeur - D}' y='{hauteur - 6}' font-size='10' text-anchor='end' fill='#4a5560'>{d1:%d/%m}</text>"
    legende = (f"<text x='{G + 6}' y='{H + 10}' font-size='10' fill='#2e7d32' font-weight='600'>NDVI (vigueur)</text>"
               f"<text x='{G + 110}' y='{H + 10}' font-size='10' fill='#1f6fb2' font-weight='600'>NDWI (eau dans les feuilles)</text>")
    return Markup(f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {largeur} {hauteur}' style='width:100%;max-width:{largeur}px'>{grille}{alertes}"
                  f"<polyline points='{ligne('ndvi')}' fill='none' stroke='#2e7d32' stroke-width='2.5'/>"
                  f"<polyline points='{ligne('ndwi')}' fill='none' stroke='#1f6fb2' stroke-width='2'/>{dates}{legende}</svg>")


class Partner(models.Model):
    _inherit = "res.partner"

    cultiveau_parcelle_ids = fields.One2many("cultiveau.parcelle", "partner_id", string="Parcelles")
    cultiveau_nb_parcelles = fields.Integer("Nombre de parcelles", compute="_compute_parcelles")
    cultiveau_alertes_parcelles = fields.Integer("Alertes satellite", compute="_compute_parcelles")
    cultiveau_carte_parcelles = fields.Html("Carte des parcelles", compute="_compute_parcelles", sanitize=False)
    cultiveau_carte_ndvi = fields.Html("Vigueur des parcelles", compute="_compute_parcelles", sanitize=False)

    def _compute_parcelles(self):
        for p in self:
            campagne = max(p.cultiveau_parcelle_ids.mapped("campagne") or [0])
            parcelles = p.cultiveau_parcelle_ids.filtered(lambda x: x.campagne == campagne)
            p.cultiveau_nb_parcelles = len(parcelles)
            p.cultiveau_alertes_parcelles = len(parcelles.alerte_ids.filtered(lambda a: a.etat == "nouvelle"))
            p.cultiveau_carte_parcelles = dessiner_carte(parcelles) if parcelles else False
            p.cultiveau_carte_ndvi = dessiner_carte(parcelles, selon="ndvi") if parcelles.filtered("derniere_mesure") else False

    def cultiveau_cultures_depuis_parcelles(self, campagne=None):
        """Les cultures du client d'après ses parcelles : la surface de chaque culture = la somme de ses parcelles de la campagne."""
        CultureClient = self.env["cultiveau.culture.client"]
        for p in self:
            campagne_p = campagne or max(p.cultiveau_parcelle_ids.mapped("campagne") or [0])
            surfaces = {}
            for parcelle in p.cultiveau_parcelle_ids.filtered(lambda x: x.campagne == campagne_p and x.culture_id):
                surfaces[parcelle.culture_id] = surfaces.get(parcelle.culture_id, 0.0) + parcelle.surface_ha
            for culture, surface in surfaces.items():
                cc = CultureClient.search([("partner_id", "=", p.id), ("culture_id", "=", culture.id)], limit=1)
                valeurs = {"surface_ha": round(surface, 2), "notes": f"D'après la déclaration PAC {campagne_p}"}
                if cc:
                    cc.write(valeurs)
                else:
                    CultureClient.create({**valeurs, "partner_id": p.id, "culture_id": culture.id})

    def action_voir_parcelles(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("cultiveau_parcelles.action_parcelles")
        action["domain"] = [("partner_id", "=", self.id)]
        action["context"] = {"default_partner_id": self.id}
        return action

    def action_importer_telepac(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "name": "Importer la déclaration PAC", "res_model": "cultiveau.import.telepac", "view_mode": "form",
                "target": "new", "context": {"default_partner_id": self.id}}

    def action_demander_telepac(self):
        self.ensure_one()
        if not self.email:
            raise UserError("Ce client n'a pas d'e-mail : demandez-lui son fichier Telepac par téléphone ou par SMS.")
        modele = self.env.ref("cultiveau_parcelles.modele_mail_demande_telepac")
        return {"type": "ir.actions.act_window", "res_model": "mail.compose.message", "view_mode": "form", "target": "new",
                "context": {"default_model": "res.partner", "default_res_ids": self.ids, "default_template_id": modele.id,
                            "default_composition_mode": "comment", "default_email_layout_xmlid": "mail.mail_notification_light"}}

    def action_actualiser_satellite(self):
        self.ensure_one()
        return self.cultiveau_parcelle_ids.filtered(lambda x: x.campagne == max(self.cultiveau_parcelle_ids.mapped("campagne") or [0])).action_actualiser()
