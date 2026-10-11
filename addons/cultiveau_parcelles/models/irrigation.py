"""Le conseil d'irrigation : chaque semaine, ce qu'il manque à chaque parcelle, d'après la météo réelle, la frise du client et son sol."""

from datetime import timedelta

from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.exceptions import UserError

from .meteo import JOURS_A_VENIR, JOURS_PASSES, station

JOURS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
SEUIL = 0.7  # on conseille d'arroser quand la réserve facilement utilisable est entamée aux deux tiers


def dose_par_tour(systeme):
    """Ce qu'un tour d'eau apporte d'ordinaire : un enrouleur ou de l'aspersion 30 à 35 mm, un pivot 12, du goutte-à-goutte 8."""
    s = (systeme or "").lower()
    if "goutte" in s or "micro" in s:
        return 8
    if "pivot" in s or "rampe" in s:
        return 12
    return 35


def pluie_utile(mm):
    """La pluie d'un jour qui atteint vraiment les racines : rien sous 2 mm, 80 % au-delà."""
    return 0.8 * mm if mm >= 2 else 0.0


class Apport(models.Model):
    _name = "cultiveau.parcelle.apport"
    _description = "Arrosage noté sur une parcelle"
    _order = "date desc, id desc"

    parcelle_id = fields.Many2one("cultiveau.parcelle", required=True, ondelete="cascade", index=True)
    partner_id = fields.Many2one(related="parcelle_id.partner_id", store=True)
    date = fields.Date("Jour", required=True, default=fields.Date.context_today)
    mm = fields.Float("Dose (mm)", digits=(5, 1), required=True)
    note = fields.Char("Remarque")


class Parcelle(models.Model):
    _inherit = "cultiveau.parcelle"

    apport_ids = fields.One2many("cultiveau.parcelle.apport", "parcelle_id", "Arrosages notés")
    deficit_mm = fields.Float("Déficit (mm)", digits=(5, 0), readonly=True, help="Ce qui manque dans la réserve du sol aujourd'hui, d'après la météo réelle.")
    rfu_mm = fields.Float("Réserve utile (mm)", digits=(5, 0), readonly=True)
    dose_mm = fields.Float("Dose conseillée (mm)", digits=(5, 0), readonly=True)
    volume_m3 = fields.Float("Soit (m³)", digits=(8, 0), readonly=True, help="Le volume à pomper pour cette dose sur la parcelle, efficience du système comprise.")
    date_limite = fields.Date("Avant le", readonly=True)
    conseil = fields.Char("Conseil", readonly=True)
    etat_eau = fields.Selection([("hors_saison", "Hors saison"), ("ok", "Réserve suffisante"), ("bientot", "À arroser dans la semaine"), ("arroser", "À arroser"), ("inconnu", "Pas de météo")],
                                "Eau", readonly=True, default="inconnu")
    bilan_eau = fields.Html("Bilan hydrique", readonly=True, sanitize=False)
    derniere_meteo = fields.Date("Météo du", readonly=True)

    def _station(self):
        self.ensure_one()
        return station(self.latitude, self.longitude) if self.latitude and self.longitude else None

    def _culture_client(self):
        self.ensure_one()
        return self.env["cultiveau.culture.client"].search([("partner_id", "=", self.partner_id.id), ("culture_id", "=", self.culture_id.id)], limit=1)

    # ---------------------------------------------------------------- le bilan

    def calculer_bilan(self, aujourdhui=None):
        """Le bilan hydrique jour par jour (21 jours passés, 7 à venir) et le conseil qui en découle."""
        aujourdhui = aujourdhui or fields.Date.context_today(self)
        Meteo = self.env["cultiveau.meteo.jour"]
        for p in self:
            cc = p._culture_client() if p.culture_id else None
            st = p._station()
            if not p.irriguee or not cc or not st:
                p.write({"etat_eau": "hors_saison" if not p.irriguee else "inconnu", "conseil": "Parcelle non irriguée." if not p.irriguee else "Culture ou position inconnue.",
                         "deficit_mm": 0, "dose_mm": 0, "heures_conseillees": 0, "date_limite": False, "bilan_eau": False})
                continue
            debut, fin = aujourdhui - timedelta(days=JOURS_PASSES), aujourdhui + timedelta(days=JOURS_A_VENIR - 1)
            meteo = Meteo.serie(st, debut, fin)
            if not any(d < aujourdhui for d in meteo):
                p.write({"etat_eau": "inconnu", "conseil": "Pas encore de météo pour cette parcelle.", "bilan_eau": False})
                continue
            rfu = cc.rfu_mm or 60.0
            apports = {}
            for a in p.apport_ids.filtered(lambda a: debut <= a.date <= fin):
                apports[a.date] = apports.get(a.date, 0.0) + a.mm
            deficit, lignes, deficit_aujourdhui, vide_le, kc_aujourdhui = 0.0, [], None, None, 0.0
            jour = debut
            while jour <= fin:
                eto, pluie, prevision = meteo.get(jour, (0.0, 0.0, True))
                kc = cc.kc_a_la_date(jour)
                etc = eto * kc
                deficit = min(rfu, max(0.0, deficit + etc - pluie_utile(pluie) - apports.get(jour, 0.0)))
                if jour == aujourdhui:
                    deficit_aujourdhui, kc_aujourdhui = deficit, kc
                if jour > aujourdhui and vide_le is None and deficit >= rfu - 0.5 and kc > 0:
                    vide_le = jour
                lignes.append((jour, eto, kc, etc, pluie, apports.get(jour, 0.0), deficit, prevision))
                jour += timedelta(days=1)
            if deficit_aujourdhui is None:
                deficit_aujourdhui = lignes[-1][6]
            valeurs = {"rfu_mm": rfu, "deficit_mm": round(deficit_aujourdhui), "derniere_meteo": max(d for d in meteo if d <= aujourdhui), "dose_mm": 0,
                       "volume_m3": 0, "date_limite": False}
            efficience = cc.efficience or 0.8
            if kc_aujourdhui <= 0.05:
                valeurs.update(etat_eau="hors_saison", conseil="Hors saison d'irrigation pour cette culture.")
            elif deficit_aujourdhui >= SEUIL * rfu:
                manque = round(deficit_aujourdhui)
                dose = min(manque, dose_par_tour(cc.systeme))
                volume = round(dose * 10 * (p.surface_ha or 0) / efficience)
                valeurs.update(etat_eau="arroser", dose_mm=dose, volume_m3=volume, date_limite=vide_le or aujourdhui + timedelta(days=1))
                quand = f"avant {JOURS_FR[valeurs['date_limite'].weekday()]} {valeurs['date_limite']:%d/%m}"
                suite = f", puis renouveler : il manque {manque} mm en tout" if manque > dose + 5 else ""
                valeurs["conseil"] = f"Apporter {dose} mm (environ {volume:,} m³) {quand}{suite} — réserve à {100 - 100 * deficit_aujourdhui / rfu:.0f} %.".replace(",", " ")
            elif vide_le:
                valeurs.update(etat_eau="bientot", dose_mm=min(round(rfu * SEUIL), dose_par_tour(cc.systeme)), date_limite=vide_le,
                               conseil=f"Réserve à {100 - 100 * deficit_aujourdhui / rfu:.0f} % : prévoir un tour d'eau d'ici {JOURS_FR[vide_le.weekday()]} {vide_le:%d/%m} si la pluie annoncée ne vient pas.")
            else:
                valeurs.update(etat_eau="ok", conseil=f"Réserve à {100 - 100 * deficit_aujourdhui / rfu:.0f} % : rien à faire cette semaine.")
            valeurs["bilan_eau"] = self._tableau_bilan(lignes, rfu, aujourdhui)
            p.write(valeurs)
        return True

    @api.model
    def _tableau_bilan(self, lignes, rfu, aujourdhui):
        entete = "<tr><th>Jour</th><th>ETo</th><th>Kc</th><th>Besoin</th><th>Pluie</th><th>Arrosage</th><th>Déficit</th></tr>"
        corps = []
        for jour, eto, kc, etc, pluie, apport, deficit, prevision in lignes:
            if jour < aujourdhui - timedelta(days=10):
                continue
            classe = " class='table-info'" if jour == aujourdhui else (" class='text-muted fst-italic'" if prevision else "")
            corps.append(f"<tr{classe}><td>{JOURS_FR[jour.weekday()][:3]} {jour:%d/%m}{' (prévu)' if prevision and jour > aujourdhui else ''}</td><td>{eto:.1f}</td><td>{kc:.2f}</td>"
                         f"<td>{etc:.1f}</td><td>{pluie:.1f}</td><td>{apport:.0f}</td><td><b>{deficit:.0f}</b> / {rfu:.0f}</td></tr>")
        return Markup(f"<table class='table table-sm'>{entete}{''.join(corps)}</table><p class='text-muted small'>mm par jour ; le déficit est ce qui manque dans la réserve facilement utilisable du sol.</p>")

    # ---------------------------------------------------------------- actions et cron

    def action_actualiser_eau(self):
        stations = {p._station() for p in self if p._station()}
        n = self.env["cultiveau.meteo.jour"].actualiser(stations)
        self.calculer_bilan()
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"title": "Conseil d'irrigation", "message": f"Météo relevée pour {n} station(s), bilan recalculé.", "sticky": False,
                           "next": {"type": "ir.actions.client", "tag": "soft_reload"}}}

    def action_noter_arrosage(self):
        return {"type": "ir.actions.act_window", "res_model": "cultiveau.apport.assistant", "view_mode": "form", "target": "new", "name": "Noter un arrosage",
                "context": {"default_parcelle_ids": self.ids, "default_partner_id": self[:1].partner_id.id}}

    @api.model
    def _cron_irrigation(self, aujourdhui=None):
        """Chaque matin : météo des stations, bilan des parcelles irriguées ; celles à arroser lèvent une alerte (une par semaine au plus)."""
        aujourdhui = aujourdhui or fields.Date.context_today(self)
        parcelles = self.search([("irriguee", "=", True), ("culture_id", "!=", False), ("latitude", "!=", 0), ("campagne", ">=", aujourdhui.year - 1)])
        self.env["cultiveau.meteo.jour"].actualiser({p._station() for p in parcelles}, aujourdhui)
        parcelles.calculer_bilan(aujourdhui)
        Alerte = self.env["cultiveau.parcelle.alerte"]
        for p in parcelles.filtered(lambda p: p.etat_eau == "arroser"):
            if p.alerte_ids.filtered(lambda a: a.genre == "irrigation" and (aujourdhui - a.date).days < 6):
                continue
            Alerte.create({"parcelle_id": p.id, "genre": "irrigation", "date": aujourdhui, "detail": p.conseil})
        return len(parcelles)


class Alerte(models.Model):
    _inherit = "cultiveau.parcelle.alerte"

    genre = fields.Selection(selection_add=[("irrigation", "Tour d'eau à prévoir")], ondelete={"irrigation": "cascade"})

    def _compute_conseil(self):
        super()._compute_conseil()
        for a in self.filtered(lambda a: a.genre == "irrigation"):
            a.conseil = "D'après la météo des trois dernières semaines et la frise de la culture, la réserve du sol est entamée : lancer le tour d'eau indiqué, ou noter l'arrosage déjà fait pour corriger le bilan."

    def action_prevenir_client(self):
        irrigation = self.filtered(lambda a: a.genre == "irrigation")
        for a in irrigation:
            if not a.partner_id.email:
                raise UserError(f"{a.partner_id.name} n'a pas d'e-mail.")
            a.message_post_with_source(self.env.ref("cultiveau_parcelles.modele_mail_conseil_irrigation"), subtype_xmlid="mail.mt_comment", email_layout_xmlid="mail.mail_notification_light")
            a.etat = "client_prevenu"
        return super(Alerte, self - irrigation).action_prevenir_client()


class ApportAssistant(models.TransientModel):
    _name = "cultiveau.apport.assistant"
    _description = "Noter un arrosage"

    partner_id = fields.Many2one("res.partner", "Client")
    parcelle_ids = fields.Many2many("cultiveau.parcelle", string="Parcelles arrosées", domain="[('partner_id', '=', partner_id)]")
    date = fields.Date("Jour", required=True, default=fields.Date.context_today)
    mm = fields.Float("Dose (mm)", required=True, default=25, help="Un tour d'eau d'enrouleur fait souvent 25 à 35 mm ; un pivot 8 à 15 mm ; du goutte-à-goutte 3 à 6 mm par jour.")
    note = fields.Char("Remarque")

    def action_noter(self):
        self.ensure_one()
        if not self.parcelle_ids:
            raise UserError("Choisissez au moins une parcelle.")
        self.env["cultiveau.parcelle.apport"].create([{"parcelle_id": p.id, "date": self.date, "mm": self.mm, "note": self.note} for p in self.parcelle_ids])
        self.parcelle_ids.calculer_bilan()
        return {"type": "ir.actions.act_window_close"}


class Partner(models.Model):
    _inherit = "res.partner"

    cultiveau_conseil_eau = fields.Html("Conseil d'irrigation", compute="_compute_conseil_eau", sanitize=False)

    @api.depends("cultiveau_parcelle_ids.etat_eau", "cultiveau_parcelle_ids.conseil")
    def _compute_conseil_eau(self):
        libelles = dict(self.env["cultiveau.parcelle"]._fields["etat_eau"].selection)
        for p in self:
            parcelles = p.cultiveau_parcelle_ids.filtered(lambda x: x.irriguee and x.culture_id and x.etat_eau not in ("inconnu", False))
            if not parcelles:
                p.cultiveau_conseil_eau = False
                continue
            ordre = {"arroser": 0, "bientot": 1, "ok": 2, "hors_saison": 3}
            lignes = []
            for x in parcelles.sorted(lambda x: (ordre.get(x.etat_eau, 9), x.name)):
                couleur = {"arroser": "danger", "bientot": "warning", "ok": "success"}.get(x.etat_eau, "secondary")
                lignes.append(f"<tr><td><span class='badge text-bg-{couleur}'>{escape(libelles.get(x.etat_eau, ''))}</span></td><td>{escape(x.name)}</td>"
                              f"<td>{escape(x.conseil or '')}</td></tr>")
            p.cultiveau_conseil_eau = Markup(f"<table class='table table-sm mb-0'>{''.join(lignes)}</table>")

    def action_actualiser_eau(self):
        self.ensure_one()
        return self.cultiveau_parcelle_ids.filtered(lambda p: p.irriguee and p.culture_id).action_actualiser_eau()

    def action_noter_arrosage(self):
        self.ensure_one()
        return self.cultiveau_parcelle_ids.filtered(lambda p: p.irriguee and p.culture_id).action_noter_arrosage()
