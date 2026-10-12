"""Les congés et absences : demander, valider en un clic, les soldes, qui est absent quand.

Sur le module standard des congés : les types sont renommés en français et validés par le gérant (une seule validation).
Les congés payés sont attribués par période (1er juin → 31 mai), 25 jours par défaut. Les arrêts maladie ne sont jamais
nommés comme tels devant les collègues : ils lisent « Absent ».
"""
from datetime import date, timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

from .equipe import jour_fr

TYPES = {
    "conges_payes": ("hr_holidays.holiday_status_cl", "Congés payés", {"requires_allocation": "yes", "leave_validation_type": "manager", "request_unit": "half_day"}),
    "rtt": ("hr_holidays.holiday_status_comp", "RTT et récupération", {"leave_validation_type": "manager", "request_unit": "half_day"}),
    "sans_solde": ("hr_holidays.holiday_status_unpaid", "Congé sans solde", {"leave_validation_type": "manager", "request_unit": "half_day"}),
    "familial": ("cultiveau_rh.type_familial", "Événement familial", {}),
    "maladie": ("hr_holidays.holiday_status_sl", "Arrêt maladie", {"leave_validation_type": "manager"}),
}
ETATS = {"confirm": ("À valider", "ambre"), "validate1": ("À valider", "ambre"), "validate": ("Validé", "vert"), "refuse": ("Refusé", "rouge"), "cancel": ("Annulé", "ardoise")}


class Conges(models.AbstractModel):
    _name = "cultiveau.conges"
    _description = "Congés et absences de l'équipe"

    # ---------------------------------------------------------------- les types

    def _preparer_types(self):
        """Une fois : les types standards en français, validés par le gérant en un clic."""
        ICP = self.env["ir.config_parameter"].sudo()
        if ICP.get_param("cultiveau.rh_types"):
            return
        langues = [code for code, _n in self.env["res.lang"].get_installed()]
        for _cle, (xmlid, nom, vals) in TYPES.items():
            t = self.env.ref(xmlid, raise_if_not_found=False)
            if not t:
                continue
            t = t.sudo()
            if vals:
                t.write(vals)
            for code in set(langues) | {"en_US"}:
                t.with_context(lang=code).write({"name": nom})
        ICP.set_param("cultiveau.rh_types", "1")

    @api.model
    def _type(self, cle):
        return self.env.ref(TYPES.get(cle or "conges_payes", TYPES["conges_payes"])[0], raise_if_not_found=False)

    @api.model
    def _cle(self, leave_type):
        refs = {self.env.ref(x, raise_if_not_found=False): cle for cle, (x, _n, _v) in TYPES.items()}
        return refs.get(leave_type, "autre")

    @api.model
    def types(self):
        return [{"cle": cle, "nom": nom} for cle, (xmlid, nom, _v) in TYPES.items() if self.env.ref(xmlid, raise_if_not_found=False)]

    # ---------------------------------------------------------------- les soldes

    @api.model
    def allouer(self, company=None, annee=None):
        """Les congés payés de la période qui a commencé le 1er juin, pour chaque salarié qui ne les a pas encore. Renvoie le nombre d'attributions."""
        company = company or self.env.company
        jours = float(self.env["ir.config_parameter"].sudo().get_param("cultiveau.conges_jours_an") or 25)
        cp = self._type("conges_payes")
        if jours <= 0 or not cp:
            return 0
        aujourd_hui = fields.Date.context_today(self)
        annee = annee or (aujourd_hui.year if aujourd_hui.month >= 6 else aujourd_hui.year - 1)
        debut = date(annee, 6, 1)
        Alloc = self.env["hr.leave.allocation"].sudo()
        n = 0
        for e in self.env["hr.employee"].sudo().search([("company_id", "=", company.id), ("user_id", "!=", False)]):
            if Alloc.with_context(active_test=False).search_count([("employee_id", "=", e.id), ("holiday_status_id", "=", cp.id), ("date_from", "=", debut)]):
                continue
            a = Alloc.create({"name": f"Congés payés {annee}-{annee + 1}", "holiday_status_id": cp.id, "employee_id": e.id, "number_of_days": jours,
                              "allocation_type": "regular", "date_from": debut})
            if a.state not in ("validate", "refuse"):
                a.action_validate()
            n += 1
        return n

    @api.model
    def soldes(self, user=None):
        """Les compteurs de la personne : [{nom, acquis, pris, restant}] (jours), pour les types à solde."""
        e = self.env["cultiveau.equipe"].employe(user, creer=False)
        if not e:
            return []
        lang = (user or self.env.user).lang or "fr_FR"
        types = self.env["hr.leave.type"].sudo().with_company(e.company_id).with_context(lang=lang).search(
            [("requires_allocation", "=", "yes"), "|", ("company_id", "=", False), ("company_id", "=", e.company_id.id)])
        donnees = types.get_allocation_data(e).get(e, [])
        return [{"nom": nom, "acquis": round(d.get("max_leaves", 0), 1), "pris": round(d.get("leaves_taken", 0), 1),
                 "restant": round(d.get("virtual_remaining_leaves", 0), 1), "type_id": tid}
                for nom, d, requiert, tid in donnees if requiert == "yes"]

    # ---------------------------------------------------------------- les demandes

    def _visible(self, l):
        """La nature d'une absence ne se lit que par la personne et le gérant (un arrêt maladie reste privé)."""
        return l.user_id == self.env.user or self.env["cultiveau.equipe"].est_gerant()

    @api.model
    def _periode(self, l):
        du, au = l.request_date_from, l.request_date_to or l.request_date_from
        if not du:
            return ""
        if du == au:
            demi = {"am": " (matin)", "pm": " (après-midi)"}.get(l.request_date_from_period, "") if l.request_unit_half else ""
            return f"le {jour_fr(du)}{demi}"
        return f"du {jour_fr(du)} au {jour_fr(au)}"

    @api.model
    def _ligne(self, l):
        l = l.sudo()
        cle = self._cle(l.holiday_status_id)
        visible = self._visible(l)
        etat, couleur = ETATS.get(l.state, (l.state, "ardoise"))
        return {"id": l.id, "employe": l.employee_id.name, "user_id": l.user_id.id, "cle": cle if visible or cle != "maladie" else "absence",
                "type": l.holiday_status_id.name if visible or cle != "maladie" else "Absence",
                "du": fields.Date.to_string(l.request_date_from), "au": fields.Date.to_string(l.request_date_to or l.request_date_from),
                "periode": self._periode(l), "jours": round(l.number_of_days, 1), "etat": l.state, "etat_nom": etat, "couleur": couleur,
                "motif": (l.private_name or "") if visible else ""}

    @api.model
    def demandes(self, user=None, limite=10):
        """Les demandes de la personne, les plus récentes d'abord (deux mois en arrière et tout ce qui vient)."""
        e = self.env["cultiveau.equipe"].employe(user, creer=False)
        if not e:
            return []
        depuis = fields.Date.context_today(self) - timedelta(days=60)
        leaves = self.env["hr.leave"].sudo().search([("employee_id", "=", e.id), ("request_date_to", ">=", depuis)], order="request_date_from desc", limit=limite)
        return [self._ligne(l) for l in leaves]

    @api.model
    def demander(self, cle="conges_payes", du=None, au=None, demi=False, motif=""):
        """Une demande de la personne connectée. demi : « am » ou « pm » pour une demi-journée. Renvoie la demande."""
        e = self.env["cultiveau.equipe"].employe()
        if not e:
            raise UserError("Vous n'avez pas de fiche salarié dans cette société.")
        t = self._type(cle)
        if not t:
            raise UserError("Type de congé inconnu.")
        du = fields.Date.to_date(du) if du else None
        if not du:
            raise UserError("Indiquez le premier jour.")
        au = fields.Date.to_date(au) if au else du
        if au < du:
            raise UserError("Le dernier jour est avant le premier.")
        vals = {"holiday_status_id": t.id, "employee_id": e.id, "request_date_from": du, "request_date_to": au}
        if demi in ("am", "pm"):
            vals.update({"request_unit_half": True, "request_date_to": du, "request_date_from_period": demi})
        if motif:
            vals["name"] = motif[:200]
        leave = self.env["hr.leave"].create(vals)
        if not leave.number_of_days:
            raise UserError("Aucun jour travaillé sur cette période (week-end ou jour férié).")
        return self._ligne(leave)

    @api.model
    def a_valider(self):
        """Les demandes que la personne connectée peut valider."""
        leaves = self.env["hr.leave"].search([("state", "in", ("confirm", "validate1")), ("employee_company_id", "=", self.env.company.id)], order="request_date_from")
        return [self._ligne(l) for l in leaves if l.can_approve]

    @api.model
    def decider(self, leave_id, oui=True, motif=""):
        """Valider (ou refuser) une demande, avec les droits de la personne connectée."""
        l = self.env["hr.leave"].browse(int(leave_id)).exists()
        if not l:
            raise UserError("Demande introuvable.")
        if oui:
            if l.state == "confirm":
                l.action_approve()
            if l.state == "validate1":
                l.action_validate()
            message = f"Congés de {l.employee_id.name} validés ({self._periode(l)})."
        else:
            l.action_refuse()
            if motif:
                l.message_post(body=f"Refusé : {motif}")
            message = f"Demande de {l.employee_id.name} refusée."
        return {"message": message, "conge": self._ligne(l)}

    # ---------------------------------------------------------------- qui est absent

    @api.model
    def absences(self, du=None, au=None, company=None):
        """Les absences (validées ou demandées) de l'équipe qui touchent la période."""
        company = company or self.env.company
        du = fields.Date.to_date(du) if du else fields.Date.context_today(self)
        au = fields.Date.to_date(au) if au else du
        leaves = self.env["hr.leave"].sudo().search([("employee_company_id", "=", company.id), ("state", "in", ("confirm", "validate1", "validate")),
                                                     ("request_date_from", "<=", au), ("request_date_to", ">=", du)], order="request_date_from")
        return [self._ligne(l) for l in leaves]

    @api.model
    def absents_maintenant(self, users):
        """{user_id: {type, cle, retour}} : les personnes en congé validé à cet instant."""
        maintenant = fields.Datetime.now()
        res = {}
        for l in self.env["hr.leave"].sudo().search([("user_id", "in", users.ids), ("state", "=", "validate"), ("date_from", "<=", maintenant), ("date_to", ">=", maintenant)]):
            retour = (l.request_date_to or l.date_to.date()) + timedelta(days=1)
            while retour.weekday() >= 5:
                retour += timedelta(days=1)
            ligne = self._ligne(l)
            res[l.user_id.id] = {"id": l.id, "type": ligne["type"], "cle": ligne["cle"], "retour": jour_fr(retour), "periode": ligne["periode"]}
        return res

    @api.model
    def plages_absence(self, users, debut, fin):
        """Les plages (UTC naïf) où ces personnes sont absentes : pour les créneaux de réunion."""
        leaves = self.env["hr.leave"].sudo().search([("user_id", "in", users.ids), ("state", "in", ("confirm", "validate1", "validate")),
                                                     ("date_from", "<", fin), ("date_to", ">", debut)])
        return [(l.date_from, l.date_to) for l in leaves]


class Leave(models.Model):
    _inherit = "hr.leave"

    TITRES = {"demande": ("Demande de congés", "Absence déclarée"), "valide": ("Congés validés", "Absence validée"), "refuse": ("Congés refusés", "Absence refusée")}

    def _cultiveau_signaler(self, etape):
        Conges = self.env["cultiveau.conges"]
        for l in self.sudo():
            ligne = Conges._ligne(l)
            titre = self.TITRES[etape][1 if ligne["cle"] in ("maladie", "absence") else 0]
            self.env["cultiveau.evenement"].publier("conge", l, f"{titre} — {l.employee_id.name}", ligne["periode"],
                                                    charge={"user_id": l.user_id.id, "etat": l.state, "jours": ligne["jours"]}, company=l.employee_company_id)

    @api.model_create_multi
    def create(self, vals_list):
        leaves = super().create(vals_list)
        leaves.filtered(lambda l: l.state in ("confirm", "validate1"))._cultiveau_signaler("demande")
        return leaves

    def action_validate(self, check_state=True):
        res = super().action_validate(check_state)
        self.filtered(lambda l: l.state == "validate")._cultiveau_signaler("valide")
        return res

    def action_refuse(self):
        res = super().action_refuse()
        self._cultiveau_signaler("refuse")
        return res
