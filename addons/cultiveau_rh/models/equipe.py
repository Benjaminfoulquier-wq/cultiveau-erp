"""L'équipe dans l'ERP : une fiche salarié par personne, le gérant qui valide, les jours fériés français, la page « Mon espace ».

Chaque utilisateur interne reçoit sa fiche salarié dans sa société (c'est elle qui porte les congés et les notes de frais).
Le gérant (le rôle « gérant » de la map) valide les demandes : il devient le valideur des congés et des notes de frais de
toute l'équipe. Les jours fériés sont posés sur l'agenda de la société pour l'année en cours et la suivante : ils ne sont
jamais décomptés d'un congé.
"""
from datetime import date, datetime, time, timedelta

import pytz

from odoo import api, fields, models

FERIES_FIXES = [((1, 1), "Jour de l'an"), ((5, 1), "Fête du travail"), ((5, 8), "Victoire 1945"), ((7, 14), "Fête nationale"),
                ((8, 15), "Assomption"), ((11, 1), "Toussaint"), ((11, 11), "Armistice 1918"), ((12, 25), "Noël")]
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]


def paques(annee):
    """Le dimanche de Pâques (calendrier grégorien, algorithme de Meeus)."""
    a = annee % 19
    b, c = divmod(annee, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7  # noqa: E741
    m = (a + 11 * h + 22 * l) // 451
    mois, jour = divmod(h + l - 7 * m + 114, 31)
    return date(annee, mois, jour + 1)


def jours_feries(annee):
    """Les onze jours fériés de France métropolitaine."""
    p = paques(annee)
    jours = [(date(annee, m, j), nom) for (m, j), nom in FERIES_FIXES]
    jours += [(p + timedelta(days=1), "Lundi de Pâques"), (p + timedelta(days=39), "Ascension"), (p + timedelta(days=50), "Lundi de Pentecôte")]
    return sorted(jours)


def jour_fr(d, annee=False):
    """« mardi 14 octobre » (et l'année si on la veut)."""
    return f"{JOURS[d.weekday()]} {d.day}{'er' if d.day == 1 else ''} {MOIS[d.month - 1]}" + (f" {d.year}" if annee else "")


def euros(montant):
    return f"{montant:,.2f}".replace(",", " ").replace(".", ",") + " €"


class Equipe(models.AbstractModel):
    _name = "cultiveau.equipe"
    _description = "L'équipe : salariés, valideur, jours fériés"

    @api.model
    def _tz(self, company=None):
        company = company or self.env.company
        try:
            return pytz.timezone(company.partner_id.tz or "Europe/Paris")  # celui de la société, jamais celui de la personne
        except pytz.UnknownTimeZoneError:
            return pytz.timezone("Europe/Paris")

    @api.model
    def _utilisateurs(self, company):
        root = self.env.ref("base.user_root")
        return self.env["res.users"].sudo().search([("share", "=", False), ("active", "=", True), ("company_ids", "in", company.id), ("id", "!=", root.id)])

    @api.model
    def gerants(self, company=None):
        """Les gérants de la société (le groupe « responsable des ventes », comme sur la map) ; l'administrateur en dernier recours."""
        company = company or self.env.company
        groupe = self.env.ref("sales_team.group_sale_manager")
        users = self._utilisateurs(company).filtered(lambda u: groupe in u.groups_id)
        admin = self.env.ref("base.user_admin", raise_if_not_found=False)
        return (users - admin) or users

    @api.model
    def est_gerant(self, user=None):
        user = user or self.env.user
        return user.has_group("hr_holidays.group_hr_holidays_user") or user.has_group("hr_expense.group_hr_expense_team_approver") or user in self.gerants()

    @api.model
    def employe(self, user=None, company=None, creer=True):
        """La fiche salarié de la personne dans la société (créée au besoin)."""
        user = user or self.env.user
        company = company or self.env.company
        Emp = self.env["hr.employee"].sudo().with_context(active_test=False)
        e = Emp.search([("user_id", "=", user.id), ("company_id", "=", company.id)], limit=1)
        if not e and creer and not user.share and company in user.company_ids:
            e = Emp.with_company(company).create({"name": user.name, "user_id": user.id, "company_id": company.id, "work_email": user.email or False,
                                                  "resource_calendar_id": company.resource_calendar_id.id})
        return e

    # ---------------------------------------------------------------- la mise en place

    @api.model
    def preparer(self, companies=None):
        """Mise en place idempotente : types de congés en français, catégories de frais, puis pour chaque société les fiches
        salarié, le valideur, les jours fériés et les congés payés de la période."""
        self.env["cultiveau.conges"]._preparer_types()
        self.env["cultiveau.frais"]._preparer_categories()
        for company in companies or self.env["res.company"].sudo().search([]):
            self._preparer_societe(company)
        return True

    def _preparer_societe(self, company):
        gerants = self.gerants(company)
        chef = gerants[:1]
        groupes = [g for g in (self.env.ref("hr_holidays.group_hr_holidays_user", raise_if_not_found=False),
                               self.env.ref("hr_expense.group_hr_expense_manager", raise_if_not_found=False)) if g]
        for g in gerants:
            manquants = [x for x in groupes if x not in g.groups_id]
            if manquants:
                g.sudo().write({"groups_id": [(4, x.id) for x in manquants]})
        for u in self._utilisateurs(company):
            e = self.employe(u, company)
            if not e or not chef or u == chef:
                continue
            vals = {}
            if not e.leave_manager_id:
                vals["leave_manager_id"] = chef.id
            if "expense_manager_id" in e._fields and not e.expense_manager_id:
                vals["expense_manager_id"] = chef.id
            if vals:
                e.write(vals)
        self.poser_jours_feries(company)
        self.env["cultiveau.conges"].allouer(company)

    @api.model
    def poser_jours_feries(self, company=None, annees=None):
        """Les jours fériés français sur l'agenda de la société (année en cours et suivante). Renvoie le nombre de jours posés."""
        company = company or self.env.company
        aujourd_hui = fields.Date.context_today(self)
        annees = annees or [aujourd_hui.year, aujourd_hui.year + 1]
        Ferie = self.env["resource.calendar.leaves"].sudo()
        tz = self._tz(company)
        n = 0
        for annee in annees:
            for jour, nom in jours_feries(annee):
                debut = tz.localize(datetime.combine(jour, time.min)).astimezone(pytz.utc).replace(tzinfo=None)
                fin = tz.localize(datetime.combine(jour, time(23, 59, 59))).astimezone(pytz.utc).replace(tzinfo=None)
                if Ferie.search_count([("company_id", "=", company.id), ("resource_id", "=", False), ("date_from", "<=", fin), ("date_to", ">=", debut)]):
                    continue
                Ferie.create({"name": nom, "company_id": company.id, "calendar_id": company.resource_calendar_id.id, "resource_id": False,
                              "date_from": debut, "date_to": fin, "time_type": "leave"})
                n += 1
        return n

    @api.model
    def feries(self, du, au, company=None):
        """Les jours fériés posés entre deux dates : [(date, nom)]."""
        company = company or self.env.company
        tz = self._tz(company)
        res = []
        for f in self.env["resource.calendar.leaves"].sudo().search([("company_id", "=", company.id), ("resource_id", "=", False),
                                                                       ("date_from", "<=", datetime.combine(au, time.max)), ("date_to", ">=", datetime.combine(du, time.min))],
                                                                      order="date_from"):
            res.append((pytz.utc.localize(f.date_from).astimezone(tz).date(), f.name))
        return res

    @api.model
    def _cron_equipe(self):
        """Chaque jour : les nouvelles personnes, les jours fériés de l'année suivante, les congés de la nouvelle période."""
        for company in self.env["res.company"].sudo().search([]):
            self._preparer_societe(company)

    # ---------------------------------------------------------------- « Mon espace » (la page du téléphone)

    @api.model
    def espace(self):
        """Tout ce que la page /moi affiche pour la personne connectée."""
        user = self.env.user
        company = self.env.company
        Conges = self.env["cultiveau.conges"]
        Frais = self.env["cultiveau.frais"]
        local = fields.Datetime.context_timestamp(self.with_context(tz=self._tz(company).zone), fields.Datetime.now())
        statut = {}
        try:
            p = next((p for p in self.env["cultiveau.map"]._personnes(company, local) if p["id"] == user.id), None)
            statut = p and {"cle": p["statut"], "nom": p["statut_nom"], "couleur": p["couleur"]} or {}
        except Exception:  # noqa: BLE001 — la page reste utile sans la map
            statut = {}
        aujourd_hui = local.date()
        return {
            "prenom": (user.name or "").split(" ")[0], "nom": user.name, "societe": company.name, "date": jour_fr(aujourd_hui, annee=True).capitalize(),
            "statut": statut, "gerant": self.est_gerant(),
            "soldes": Conges.soldes(), "demandes": Conges.demandes(limite=6), "types": Conges.types(),
            "feries": [{"date": jour_fr(d), "nom": n} for d, n in self.feries(aujourd_hui, aujourd_hui + timedelta(days=90), company)][:3],
            "frais": Frais.mes_frais(limite=12), "categories": Frais.categories(),
            "a_valider": {"conges": Conges.a_valider() if self.est_gerant() else [], "frais": Frais.a_valider() if self.est_gerant() else []},
            "absents": Conges.absences(aujourd_hui, aujourd_hui + timedelta(days=6)),
            "aujourd_hui": fields.Date.to_string(aujourd_hui),
        }


class Users(models.Model):
    _inherit = "res.users"

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        Equipe = self.env["cultiveau.equipe"]
        for u in users.filtered(lambda u: not u.share and u.company_id):
            Equipe.employe(u, u.company_id)
        return users


class Settings(models.TransientModel):
    _inherit = "res.config.settings"

    cultiveau_conges_jours_an = fields.Float("Congés payés par période", config_parameter="cultiveau.conges_jours_an", default=25,
                                             help="Jours ouvrés attribués à chaque salarié le 1er juin (25 = cinq semaines). 0 : vous les attribuez vous-même.")
    cultiveau_frais_km = fields.Float("Indemnité kilométrique (€/km)", config_parameter="cultiveau.frais_km", default=0.636, digits=(6, 3),
                                      help="Le taux appliqué aux kilomètres déclarés (barème fiscal, selon la puissance du véhicule).")
    cultiveau_frais_comptabiliser = fields.Boolean("Comptabiliser à la validation", config_parameter="cultiveau.frais_comptabiliser",
                                                   help="La note de frais validée passe directement en comptabilité (à rembourser au salarié).")
    cultiveau_url_moi = fields.Char("Page du téléphone", compute="_compute_url_moi")

    def _compute_url_moi(self):
        base = self.env["ir.config_parameter"].sudo().get_param("web.base.url") or ""
        for s in self:
            s.cultiveau_url_moi = f"{base}/moi"

    def action_cultiveau_preparer_equipe(self):
        self.env["cultiveau.equipe"].preparer(self.env.company)
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"title": "Équipe prête", "message": "Fiches salarié, valideur, jours fériés et congés payés à jour.", "type": "success", "sticky": False}}
