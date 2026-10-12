"""La prise de rendez-vous en ligne : des motifs, des créneaux libres, une réservation qui tombe dans l'agenda.

Les créneaux viennent du moteur de la salle de réunion (agenda, interventions planifiées, congés), calculés pour chaque
personne qui peut prendre le motif : un créneau est proposé dès qu'une d'elles est libre, et c'est elle qui reçoit le rendez-vous.
"""
import secrets
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

LIEUX = [("chez_client", "Chez le client (sur l'exploitation)"), ("depot", "Au dépôt"), ("visio", "En visio"), ("telephone", "Par téléphone")]
MOTIFS = [("Visite conseil irrigation", "Nous venons sur votre exploitation étudier votre projet ou votre installation.", 60, "chez_client"),
          ("Diagnostic d'une installation", "Une installation qui fonctionne mal : nous venons voir et mesurer.", 90, "chez_client"),
          ("Rendez-vous au dépôt", "Pour choisir du matériel ou parler d'un devis, au comptoir.", 30, "depot"),
          ("Appel découverte", "Vingt minutes au téléphone pour faire le point sur votre besoin.", 20, "telephone")]


def _jeton(*_args):
    return secrets.token_urlsafe(9)


class Societe(models.Model):
    _inherit = "res.company"

    cultiveau_rdv_jeton = fields.Char("Jeton des rendez-vous en ligne", copy=False, default=_jeton)

    def _cultiveau_rdv_url(self):
        base = self.env["ir.config_parameter"].sudo().get_param("web.base.url") or ""
        return f"{base}/rdv/{self.sudo().cultiveau_rdv_jeton}"


class TypeRdv(models.Model):
    _name = "cultiveau.rdv.type"
    _description = "Motif de rendez-vous en ligne"
    _order = "sequence, id"

    name = fields.Char("Motif", required=True)
    description = fields.Text("Ce que le client lit")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    duree_min = fields.Integer("Durée (minutes)", default=60, required=True)
    lieu = fields.Selection(LIEUX, "Lieu", default="chez_client", required=True)
    user_ids = fields.Many2many("res.users", "cultiveau_rdv_type_user_rel", "type_id", "user_id", "Qui le prend", domain=[("share", "=", False)],
                                help="Le rendez-vous va à la première de ces personnes qui est libre sur le créneau choisi.")
    jours = fields.Integer("Réservable sur (jours)", default=21)
    delai_heures = fields.Integer("Au plus tôt dans (heures)", default=24, help="Pas de rendez-vous pris au dernier moment.")
    company_id = fields.Many2one("res.company", "Société", required=True, default=lambda self: self.env.company)
    jeton = fields.Char(copy=False, default=_jeton, readonly=True)
    url = fields.Char("Lien à partager", compute="_compute_url")
    nb_rdv = fields.Integer("Rendez-vous pris", compute="_compute_nb_rdv")

    def _compute_url(self):
        base = self.env["ir.config_parameter"].sudo().get_param("web.base.url") or ""
        for t in self:
            t.url = f"{base}/rdv/{t.jeton}"

    def _compute_nb_rdv(self):
        Event = self.env["calendar.event"].sudo()
        for t in self:
            t.nb_rdv = Event.search_count([("cultiveau_rdv_type_id", "=", t.id)])

    @api.model
    def preparer(self, companies=None):
        """Les motifs de départ (pris par le gérant), pour chaque société qui n'en a pas."""
        vus = set()
        for c in self.env["res.company"].sudo().search([]):
            # un jeton propre à chaque société (la valeur par défaut a pu être la même pour toutes à l'installation)
            if not c.cultiveau_rdv_jeton or c.cultiveau_rdv_jeton in vus:
                c.cultiveau_rdv_jeton = _jeton()
            vus.add(c.cultiveau_rdv_jeton)
        for c in companies or self.env["res.company"].sudo().search([]):
            if self.sudo().with_context(active_test=False).search_count([("company_id", "=", c.id)]):
                continue
            gerants = self.env["cultiveau.equipe"].gerants(c)
            for i, (nom, texte, duree, lieu) in enumerate(MOTIFS):
                self.sudo().create({"name": nom, "description": texte, "duree_min": duree, "lieu": lieu, "company_id": c.id, "sequence": i * 10,
                                    "user_ids": [(6, 0, gerants.ids)]})
        return True

    # ---------------------------------------------------------------- les créneaux

    def creneaux(self, nombre=24):
        """[{jour, heures, debut_utc, user_id}] : les créneaux où au moins une personne du motif est libre."""
        self.ensure_one()
        R = self.env["cultiveau.reunion"]
        au_plus_tot = fields.Datetime.now() + timedelta(hours=self.delai_heures or 0)
        vus = {}
        for u in self.sudo().user_ids.filtered("active"):
            for c in R.with_user(u).sudo().with_company(self.company_id).creneaux([], self.duree_min, salle=False, jours=self.jours or 21, nombre=nombre):
                if fields.Datetime.to_datetime(c["debut_utc"]) < au_plus_tot:
                    continue
                vus.setdefault(c["debut_utc"], {**c, "user_id": u.id})
        return [vus[k] for k in sorted(vus)][:nombre]

    def jours_creneaux(self):
        """Les créneaux groupés par jour, pour la page."""
        jours = []
        for c in self.creneaux():
            if not jours or jours[-1]["jour"] != c["jour"]:
                jours.append({"jour": c["jour"], "creneaux": []})
            jours[-1]["creneaux"].append(c)
        return jours

    # ---------------------------------------------------------------- la réservation

    def reserver(self, debut_utc, nom, telephone="", email="", adresse="", message=""):
        """Réserve le créneau pour le client (retrouvé ou créé) chez la première personne libre. Renvoie l'événement."""
        self.ensure_one()
        nom, email = (nom or "").strip(), (email or "").strip().lower()
        if not nom or not (email or telephone):
            raise UserError("Indiquez votre nom et un moyen de vous joindre (téléphone ou courriel).")
        libre = next((c for c in self.creneaux(nombre=200) if c["debut_utc"] == debut_utc), None)
        if not libre:
            raise UserError("Ce créneau vient d'être pris : choisissez-en un autre.")
        Event = self.env["calendar.event"].sudo()
        if email and Event.search_count([("cultiveau_rdv_email", "=", email), ("create_date", ">", fields.Datetime.now() - timedelta(days=1))]) >= 3:
            raise UserError("Vous avez déjà pris plusieurs rendez-vous aujourd'hui : appelez-nous pour en ajouter.")
        user = self.env["res.users"].sudo().browse(libre["user_id"])
        client = self._client(nom, telephone, email, adresse)
        debut = fields.Datetime.to_datetime(debut_utc)
        lieu = {"chez_client": adresse or ", ".join(x for x in (client.street, client.zip, client.city) if x), "telephone": f"Appel au {telephone or client.phone or ''}",
                "depot": ", ".join(x for x in (self.company_id.street, self.company_id.zip, self.company_id.city) if x), "visio": ""}[self.lieu]
        description = "<br/>".join(x for x in (f"Pris en ligne par {nom}", f"Téléphone : {telephone}" if telephone else "", f"Courriel : {email}" if email else "",
                                              f"Message : {message}" if message else "") if x)
        evenement = Event.with_user(user).with_context(mail_create_nolog=True).create({
            "name": f"{self.name} — {client.name}", "start": debut, "stop": debut + timedelta(minutes=self.duree_min), "user_id": user.id,
            "partner_ids": [(6, 0, (user.partner_id | client).ids)], "location": lieu, "description": description,
            "cultiveau_rdv_type_id": self.id, "cultiveau_rdv_email": email or False})
        if self.lieu == "visio":
            evenement._set_discuss_videocall_location()
        client.message_post(body=f"Rendez-vous pris en ligne : {self.name}, {libre['jour']} {libre['heures']} avec {user.name}.", subtype_xmlid="mail.mt_note")
        self.env["cultiveau.evenement"].sudo().publier("rdv", evenement, f"Rendez-vous pris en ligne — {client.name}", f"{self.name} · {libre['jour']} {libre['heures']} · {user.name}",
                                                       charge={"client_id": client.id, "user_id": user.id}, company=self.company_id)
        return evenement

    def _client(self, nom, telephone, email, adresse):
        Partner = self.env["res.partner"].sudo()
        societe = ["|", ("company_id", "=", False), ("company_id", "=", self.company_id.id)]
        client = Partner.search([("email_normalized", "=", email)] + societe, limit=1) if email else Partner
        if not client and telephone:
            chiffres = "".join(ch for ch in telephone if ch.isdigit())[-9:]
            if len(chiffres) == 9:
                client = Partner.search(societe + ["|", ("phone_sanitized", "like", chiffres), ("mobile", "ilike", chiffres)], limit=1) if "phone_sanitized" in Partner._fields else Partner
        if not client:
            client = Partner.create({"name": nom, "email": email or False, "phone": telephone or False, "street": adresse or False, "company_id": self.company_id.id})
        return client

    def action_ouvrir_page(self):
        self.ensure_one()
        return {"type": "ir.actions.act_url", "url": self.url, "target": "new"}


class Evenement(models.Model):
    _inherit = "calendar.event"

    cultiveau_rdv_type_id = fields.Many2one("cultiveau.rdv.type", "Pris en ligne (motif)", readonly=True, index=True)
    cultiveau_rdv_email = fields.Char(readonly=True)


class EvenementMap(models.Model):
    _inherit = "cultiveau.evenement"

    genre = fields.Selection(selection_add=[("rdv", "Rendez-vous pris en ligne")], ondelete={"rdv": "cascade"})


class Scene(models.AbstractModel):
    _inherit = "cultiveau.scene"

    def _actions(self):
        return {**super()._actions(), "rdv_en_ligne": ("cultiveau_rdv.action_rdv_types", {"name": "Rendez-vous en ligne"})}


class Map(models.AbstractModel):
    _inherit = "cultiveau.map"

    def _portes(self):
        portes = super()._portes()
        if "rdv_en_ligne" in self.env["cultiveau.scene"]._actions_disponibles():
            for zone in ("accueil", "reunion"):
                if "rdv_en_ligne" not in {p["cle"] for p in portes.get(zone, [])}:
                    portes.setdefault(zone, []).append({"cle": "rdv_en_ligne", "nom": "Rendez-vous en ligne", "icone": "fa-calendar-plus-o"})
        return portes


class Mathis(models.AbstractModel):
    _inherit = "cultiveau.mathis"

    def _outils(self):
        return super()._outils() + [{"type": "function", "function": {
            "name": "liens_rendez_vous", "description": "Les liens de prise de rendez-vous en ligne à donner à un client (un par motif, et la page de tous les motifs), avec les prochains créneaux libres.",
            "parameters": {"type": "object", "properties": {}}}}]

    def _executer(self, nom, args):
        if nom == "liens_rendez_vous":
            types = self.env["cultiveau.rdv.type"].search([("company_id", "=", self.env.company.id)])
            return {"page": self.env.company._cultiveau_rdv_url(),
                    "motifs": [{"motif": t.name, "lien": t.url, "duree_min": t.duree_min, "prochains": [f"{c['jour']} {c['heures']}" for c in t.creneaux(nombre=3)]}
                               for t in types]}, None
        return super()._executer(nom, args)


class Settings(models.TransientModel):
    _inherit = "res.config.settings"

    cultiveau_url_rdv = fields.Char("Page de rendez-vous", compute="_compute_url_rdv")

    def _compute_url_rdv(self):
        for s in self:
            s.cultiveau_url_rdv = self.env.company._cultiveau_rdv_url()
