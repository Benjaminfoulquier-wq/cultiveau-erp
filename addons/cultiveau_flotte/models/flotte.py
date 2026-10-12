"""La flotte des camions : échéances (contrôle technique, entretien, assurance, contrats), kilométrage, carburant, alertes.

Chaque véhicule est relié à son conducteur (un utilisateur) : c'est le camion de cette personne sur la map. Les échéances
sont lues en un seul endroit (`echeances`) : l'alerte du matin, la fiche du camion sur la map, la tuile « Aujourd'hui », la
page du téléphone et Mathis s'en servent tous.
"""
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError

DELAI_ALERTE_JOURS = 30
DELAI_ALERTE_KM = 1000


def _euros(m):
    return f"{m:,.0f}".replace(",", " ") + " €"


class Vehicule(models.Model):
    _inherit = "fleet.vehicle"

    cultiveau_user_id = fields.Many2one("res.users", "Conducteur (équipe)", domain=[("share", "=", False)], tracking=True,
                                        help="La personne de l'équipe qui conduit ce camion : il apparaît sur la map avec elle.")
    cultiveau_ct_prochain = fields.Date("Prochain contrôle technique", tracking=True)
    cultiveau_entretien_date = fields.Date("Prochain entretien (date)", tracking=True)
    cultiveau_entretien_km = fields.Float("Prochain entretien (km)", tracking=True)
    cultiveau_intervalle_km = fields.Float("Entretien tous les (km)", default=20000)
    cultiveau_alerte = fields.Selection([("ok", "À jour"), ("bientot", "Échéance proche"), ("depasse", "Échéance dépassée")], "Échéances",
                                        compute="_compute_cultiveau_alerte", store=True)
    cultiveau_prochaine = fields.Char("Prochaine échéance", compute="_compute_cultiveau_alerte", store=True)
    cultiveau_alertes_faites = fields.Char("Alertes envoyées", copy=False, help="Les échéances déjà signalées (une alerte par échéance).")
    cultiveau_carburant_mois = fields.Float("Carburant du mois", compute="_compute_cultiveau_carburant")
    cultiveau_carburant_annee = fields.Float("Carburant de l'année", compute="_compute_cultiveau_carburant")

    # ---------------------------------------------------------------- les échéances

    def echeances(self):
        """[{cle, nom, quand, reste, etat}] triées : contrôle technique, entretien (date et km), contrats qui arrivent à échéance."""
        self.ensure_one()
        aujourd_hui = fields.Date.context_today(self)
        res = []

        def par_date(cle, nom, d):
            if d:
                jours = (d - aujourd_hui).days
                etat = "depasse" if jours < 0 else ("bientot" if jours <= DELAI_ALERTE_JOURS else "ok")
                res.append({"cle": f"{cle}:{d}", "nom": nom, "quand": d.strftime("%d/%m/%Y"), "reste": f"dépassé de {-jours} j" if jours < 0 else f"dans {jours} j",
                            "etat": etat, "tri": jours})

        par_date("ct", "Contrôle technique", self.cultiveau_ct_prochain)
        par_date("entretien", "Entretien", self.cultiveau_entretien_date)
        if self.cultiveau_entretien_km:
            reste = self.cultiveau_entretien_km - (self.odometer or 0)
            etat = "depasse" if reste < 0 else ("bientot" if reste <= DELAI_ALERTE_KM else "ok")
            res.append({"cle": f"km:{self.cultiveau_entretien_km:.0f}", "nom": "Entretien (kilométrage)", "quand": f"{self.cultiveau_entretien_km:,.0f} km".replace(",", " "),
                        "reste": f"dépassé de {-reste:,.0f} km".replace(",", " ") if reste < 0 else f"encore {reste:,.0f} km".replace(",", " "), "etat": etat,
                        "tri": reste / 100})
        for c in self.sudo().log_contracts.filtered(lambda c: c.state in ("open", "expired", "futur") and c.expiration_date):
            par_date(f"contrat{c.id}", c.cost_subtype_id.name or c.name or "Contrat", c.expiration_date)
        return sorted(res, key=lambda e: e["tri"])

    @api.depends("cultiveau_ct_prochain", "cultiveau_entretien_date", "cultiveau_entretien_km", "log_contracts.expiration_date", "log_contracts.state", "log_services")
    def _compute_cultiveau_alerte(self):
        for v in self:
            e = v.echeances() if v.id else []
            pire = "depasse" if any(x["etat"] == "depasse" for x in e) else ("bientot" if any(x["etat"] == "bientot" for x in e) else "ok")
            v.cultiveau_alerte = pire
            v.cultiveau_prochaine = f"{e[0]['nom']} · {e[0]['reste']}" if e else ""

    def _compute_cultiveau_carburant(self):
        aujourd_hui = fields.Date.context_today(self)
        for v in self:
            depenses = self.env["hr.expense"].sudo().search([("cultiveau_vehicule_id", "=", v.id), ("date", ">=", aujourd_hui.replace(month=1, day=1)),
                                                             ("state", "not in", ("refused",))])
            carbu = depenses.filtered(lambda x: x.product_id.default_code == "CV_CARBU")
            v.cultiveau_carburant_annee = sum(carbu.mapped("total_amount"))
            v.cultiveau_carburant_mois = sum(carbu.filtered(lambda x: x.date >= aujourd_hui.replace(day=1)).mapped("total_amount"))

    # ---------------------------------------------------------------- le compteur

    def relever_compteur(self, km, user=None):
        """Un relevé de compteur (depuis le téléphone ou la map). Refuse un compteur qui recule."""
        self.ensure_one()
        km = float(km)
        if self.odometer and km < self.odometer:
            raise ValidationError(f"Le compteur ne peut pas reculer : dernier relevé {self.odometer:,.0f} km.".replace(",", " "))
        self.env["fleet.vehicle.odometer"].sudo().create({"vehicle_id": self.id, "value": km, "date": fields.Date.context_today(self),
                                                          "driver_id": (user or self.env.user).partner_id.id})
        self.invalidate_recordset(["odometer"])
        self.sudo()._cultiveau_recalculer()
        return {"message": f"Compteur enregistré : {km:,.0f} km.".replace(",", " "), "echeances": self.echeances()}

    def _cultiveau_recalculer(self):
        """Le kilométrage n'est pas un champ stocké : on redemande le calcul des échéances après un relevé, et chaque matin."""
        for nom in ("cultiveau_alerte", "cultiveau_prochaine"):
            self.env.add_to_compute(self._fields[nom], self)
        self.flush_recordset(["cultiveau_alerte", "cultiveau_prochaine"])

    # ---------------------------------------------------------------- les alertes

    @api.model
    def _cron_cultiveau_alertes(self):
        todo = self.env.ref("mail.mail_activity_data_todo")
        vehicules = self.sudo().search([("active", "=", True)])
        vehicules._cultiveau_recalculer()
        for v in vehicules:
            faites = set(filter(None, (v.cultiveau_alertes_faites or "").split(",")))
            for e in v.echeances():
                if e["etat"] == "ok" or e["cle"] in faites:
                    continue
                destinataires = v.manager_id or (self.env["cultiveau.equipe"].gerants(v.company_id)[:1] if v.company_id else self.env["res.users"])
                for u in destinataires:
                    v.activity_schedule(activity_type_id=todo.id, user_id=u.id, summary=f"{v.license_plate or v.name} : {e['nom']} {e['reste']}",
                                        note=f"{e['nom']} prévu le {e['quand']} ({e['reste']}).")
                self.env["cultiveau.evenement"].publier("flotte", v, f"{e['nom']} — {v.license_plate or v.name}", e["reste"],
                                                        charge={"vehicule_id": v.id, "user_id": v.cultiveau_user_id.id, "etat": e["etat"]},
                                                        company=v.company_id or self.env.company)
                faites.add(e["cle"])
            v.cultiveau_alertes_faites = ",".join(sorted(faites))

    @api.model
    def _cultiveau_preparer(self):
        """Les gérants gèrent la flotte."""
        groupe = self.env.ref("fleet.fleet_group_manager")
        for company in self.env["res.company"].sudo().search([]):
            for g in self.env["cultiveau.equipe"].gerants(company):
                if groupe not in g.groups_id:
                    g.sudo().write({"groups_id": [(4, groupe.id)]})
        return True

    @api.model
    def du_conducteur(self, user):
        return self.sudo().search([("cultiveau_user_id", "=", user.id), ("active", "=", True)], limit=1)

    def ligne_map(self):
        self.ensure_one()
        return {"id": self.id, "nom": self.name, "plaque": self.license_plate or "", "km": round(self.odometer or 0), "alerte": self.cultiveau_alerte,
                "prochaine": self.cultiveau_prochaine or "", "conducteur": self.cultiveau_user_id.name or "", "carburant_mois": round(self.cultiveau_carburant_mois, 2),
                "echeances": self.echeances()}


class Service(models.Model):
    _inherit = "fleet.vehicle.log.services"

    @api.model_create_multi
    def create(self, vals_list):
        services = super().create(vals_list)
        entretien = self.env.ref("cultiveau_flotte.type_entretien", raise_if_not_found=False)
        ct = self.env.ref("cultiveau_flotte.type_controle_technique", raise_if_not_found=False)
        for s in services:
            v = s.vehicle_id
            if entretien and s.service_type_id == entretien:
                # l'entretien fait fixe le suivant : un an plus tard, ou l'intervalle de kilomètres
                km = s.odometer or v.odometer or 0
                v.write({"cultiveau_entretien_date": (s.date or fields.Date.context_today(s)) + relativedelta(years=1),
                         "cultiveau_entretien_km": km + (v.cultiveau_intervalle_km or 20000) if km else v.cultiveau_entretien_km})
            elif ct and s.service_type_id == ct:
                v.cultiveau_ct_prochain = (s.date or fields.Date.context_today(s)) + relativedelta(years=2)
        return services


class Depense(models.Model):
    _inherit = "hr.expense"

    cultiveau_vehicule_id = fields.Many2one("fleet.vehicle", "Véhicule", compute="_compute_cultiveau_vehicule", store=True, readonly=False,
                                            help="Le camion du salarié : le carburant et les péages s'y rattachent.")

    @api.depends("employee_id")
    def _compute_cultiveau_vehicule(self):
        Vehicule = self.env["fleet.vehicle"]
        for x in self:
            if not x.cultiveau_vehicule_id and x.employee_id.user_id:
                x.cultiveau_vehicule_id = Vehicule.du_conducteur(x.employee_id.user_id)


class Equipe(models.AbstractModel):
    _inherit = "cultiveau.equipe"

    @api.model
    def espace(self):
        d = super().espace()
        v = self.env["fleet.vehicle"].du_conducteur(self.env.user)
        d["camion"] = v.ligne_map() if v else None
        return d


class Aujourdhui(models.AbstractModel):
    _inherit = "cultiveau.aujourdhui"

    def _sources(self):
        return super()._sources() + [self._t_flotte]

    def _t_flotte(self):
        if not self.env.user.has_group("fleet.fleet_group_user"):
            return None
        domaine = [("cultiveau_alerte", "in", ("bientot", "depasse")), ("company_id", "in", (self.env.company.id, False))]
        recs = self.env["fleet.vehicle"].search(domaine, order="cultiveau_alerte desc")
        couleur = "rouge" if any(v.cultiveau_alerte == "depasse" for v in recs) else "ambre"
        return self._tuile("flotte", "Échéances des véhicules", recs, lambda v: f"{v.license_plate or v.name}", lambda v: v.cultiveau_prochaine or "",
                           couleur=couleur, icone="fa-truck", action={"type": "ir.actions.act_window", "name": "Échéances des véhicules", "res_model": "fleet.vehicle",
                                                                     "domain": domaine, "views": [[False, "list"], [False, "form"]], "target": "current"})


class Evenement(models.Model):
    _inherit = "cultiveau.evenement"

    genre = fields.Selection(selection_add=[("flotte", "Véhicule")], ondelete={"flotte": "cascade"})


class Scene(models.AbstractModel):
    _inherit = "cultiveau.scene"

    def _actions(self):
        return {**super()._actions(), "flotte": ("fleet.fleet_vehicle_action", {"name": "Flotte des camions"})}


class Map(models.AbstractModel):
    _inherit = "cultiveau.map"

    def _portes(self):
        portes = super()._portes()
        if "flotte" in self.env["cultiveau.scene"]._actions_disponibles():
            for zone in ("atelier", "administratif"):
                if "flotte" not in {p["cle"] for p in portes.get(zone, [])}:
                    portes.setdefault(zone, []).append({"cle": "flotte", "nom": "Flotte des camions", "icone": "fa-truck"})
        return portes

    def _fiche_camion(self, company, uid):
        f = super()._fiche_camion(company, uid)
        v = self.env["fleet.vehicle"].du_conducteur(self.env["res.users"].browse(uid))
        if v:
            couleurs = {"depasse": "rouge", "bientot": "ambre", "ok": "vert"}
            lignes = [{"icone": "fa-tachometer", "texte": f"{v.license_plate or v.name}", "detail": f"{v.odometer:,.0f} km".replace(",", " ") + (f" · carburant du mois {_euros(v.cultiveau_carburant_mois)}" if v.cultiveau_carburant_mois else ""),
                       "ouvrir": {"cle": "fiche", "modele": "fleet.vehicle", "id": v.id}}]
            for e in v.echeances()[:5]:
                lignes.append({"icone": "fa-calendar-check-o", "texte": e["nom"], "detail": e["quand"], "badge": e["reste"], "couleur": couleurs[e["etat"]]})
            f["blocs"] = list(f.get("blocs", [])) + [{"titre": "Le véhicule", "lignes": lignes}]
            f["nom"] = f"{f.get('nom', '')} · {v.license_plate}" if v.license_plate and v.license_plate not in (f.get("nom") or "") else f.get("nom")
        return f


class Mathis(models.AbstractModel):
    _inherit = "cultiveau.mathis"

    def _outils(self):
        return super()._outils() + [{"type": "function", "function": {
            "name": "flotte", "description": "Les camions de l'équipe : plaque, conducteur, kilométrage, carburant du mois, prochaines échéances (contrôle technique, entretien, assurance).",
            "parameters": {"type": "object", "properties": {}}}}]

    def _executer(self, nom, args):
        if nom == "flotte":
            return [v.ligne_map() for v in self.env["fleet.vehicle"].sudo().search([("company_id", "in", (self.env.company.id, False)), ("active", "=", True)])], None
        return super()._executer(nom, args)
