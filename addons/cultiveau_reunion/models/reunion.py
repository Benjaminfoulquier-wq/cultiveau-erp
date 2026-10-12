"""Les réunions : les créneaux libres de tout le monde, la planification avec la visio choisie, la salle de la map, les agendas.

Les réunions sont des événements de l'agenda de l'ERP. Quand l'organisateur a connecté son agenda Google, l'événement part chez
Google, qui crée le lien Meet et le renvoie ; avec Outlook, Microsoft crée le lien Teams. Sans agenda connecté, la visio intégrée
de l'ERP sert à tout le monde (un lien que les clients ouvrent dans leur navigateur).
"""
import os
from datetime import datetime, time, timedelta

import pytz

from odoo import api, fields, models
from odoo.exceptions import UserError

VISIOS = [("erp", "Visio intégrée"), ("google_meet", "Google Meet"), ("teams", "Teams"), ("lien", "Lien personnalisé"), ("aucune", "Sans visio")]
JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]


def _h(d):
    return f"{d.hour} h {d.minute:02d}" if d.minute else f"{d.hour} h"


class Evenement(models.Model):
    _inherit = "calendar.event"

    cultiveau_salle = fields.Boolean("Dans la salle de réunion", index=True)
    cultiveau_visio = fields.Selection(VISIOS, "Visio")

    def _need_video_call(self):
        """Google Meet ou Teams seulement quand on l'a choisi (sinon la visio intégrée, ou rien)."""
        self.ensure_one()
        if self.cultiveau_visio:
            return self.cultiveau_visio in ("google_meet", "teams")
        return super()._need_video_call()

    @api.model_create_multi
    def create(self, vals_list):
        evenements = super().create(vals_list)
        evenements._cultiveau_signaler("Réunion planifiée")
        return evenements

    def write(self, vals):
        res = super().write(vals)
        if {"start", "stop", "partner_ids", "name", "cultiveau_salle", "videocall_location", "active"} & set(vals) and not self.env.context.get("dont_notify"):
            self._cultiveau_signaler("Réunion modifiée")
        return res

    def _cultiveau_signaler(self, titre):
        """La map de la société de l'organisateur se met à jour (la salle, les personnes en réunion)."""
        if "cultiveau.evenement" not in self.env:
            return
        for e in self:
            organisateur = e.user_id
            if not organisateur or organisateur.share:
                continue
            self.env["cultiveau.evenement"].sudo().publier("reunion", e, titre, f"{e.name} — {e._cultiveau_quand()}", {"reunion_id": e.id, "salle": e.cultiveau_salle},
                                                            company=organisateur.company_id)

    def _cultiveau_quand(self):
        self.ensure_one()
        tz = pytz.timezone(self.env.user.tz or self.user_id.tz or "Europe/Paris")
        d = pytz.utc.localize(self.start).astimezone(tz)
        return f"{JOURS[d.weekday()].lower()} {d.day} {MOIS[d.month - 1]} à {_h(d)}"


class Reunion(models.AbstractModel):
    _name = "cultiveau.reunion"
    _description = "Réunions (créneaux, planification, salle)"

    # ---------------------------------------------------------------- les réglages

    @api.model
    def _param(self, cle, defaut=""):
        return (self.env["ir.config_parameter"].sudo().get_param(cle) or defaut).strip()

    @api.model
    def salle_nom(self):
        return self._param("cultiveau.salle_nom", "Salle de réunion") or "Salle de réunion"

    @api.model
    def _plages(self):
        """Les heures où l'on propose des réunions, « 8:30-12:00,13:30-18:00 » par défaut."""
        plages = []
        for morceau in self._param("cultiveau.heures_reunion", "8:30-12:00,13:30-18:00").split(","):
            try:
                a, b = morceau.strip().split("-")
                ha, ma = (int(x) for x in a.split(":"))
                hb, mb = (int(x) for x in b.split(":"))
                plages.append((time(ha, ma), time(hb, mb)))
            except ValueError:
                continue
        return plages or [(time(8, 30), time(12, 0)), (time(13, 30), time(18, 0))]

    @api.model
    def _tz(self):
        return pytz.timezone(self.env.user.tz or self.env.company.partner_id.tz or "Europe/Paris")

    # ---------------------------------------------------------------- les agendas connectés

    # ---------------------------------------------------------------- les identifiants du réseau

    # Les applications Google et Microsoft du réseau Cultiveau, fournies au serveur (variables d'environnement, depuis les
    # secrets GitHub) : chaque personne connecte alors son agenda et sa messagerie d'un clic, sans réglage chez l'adhérent.
    IDENTIFIANTS_RESEAU = {
        "CULTIVEAU_GOOGLE_CLIENT_ID": ("google_calendar_client_id", "google_gmail_client_id"),
        "CULTIVEAU_GOOGLE_CLIENT_SECRET": ("google_calendar_client_secret", "google_gmail_client_secret"),
        "CULTIVEAU_MICROSOFT_CLIENT_ID": ("microsoft_calendar_client_id", "microsoft_outlook_client_id"),
        "CULTIVEAU_MICROSOFT_CLIENT_SECRET": ("microsoft_calendar_client_secret", "microsoft_outlook_client_secret"),
    }

    @api.model
    def appliquer_identifiants_reseau(self, environ=None):
        """Recopie les identifiants du réseau dans les réglages de l'ERP (ils l'emportent sur une saisie locale). Renvoie les
        variables appliquées."""
        environ = os.environ if environ is None else environ
        ICP = self.env["ir.config_parameter"].sudo()
        appliques = []
        for variable, parametres in self.IDENTIFIANTS_RESEAU.items():
            valeur = (environ.get(variable) or "").strip()
            if not valeur:
                continue
            for p in parametres:
                if ICP.get_param(p) != valeur:
                    ICP.set_param(p, valeur)
            appliques.append(variable)
        return appliques

    def _register_hook(self):
        super()._register_hook()
        if any(os.environ.get(v) for v in self.IDENTIFIANTS_RESEAU):
            try:
                with self.env.cr.savepoint():
                    self.sudo().appliquer_identifiants_reseau()
            except Exception:  # noqa: BLE001 — base pas encore prête : la mise à jour du module les appliquera
                pass

    @api.model
    def synchro(self):
        """Pour la personne connectée : Google Agenda et Outlook sont-ils configurés (par l'administrateur) et connectés (par elle) ?"""
        u = self.env.user.sudo()
        ICP = self.env["ir.config_parameter"].sudo()
        google = {"configure": bool(ICP.get_param("google_calendar_client_id") and ICP.get_param("google_calendar_client_secret")), "connecte": bool(getattr(u, "google_calendar_rtoken", False)) and not getattr(u, "google_synchronization_stopped", False)}
        outlook = {"configure": bool(ICP.get_param("microsoft_calendar_client_id") and ICP.get_param("microsoft_calendar_client_secret")), "connecte": bool(getattr(u, "microsoft_calendar_rtoken", False)) and not getattr(u, "microsoft_synchronization_stopped", False)}
        return {"google": google, "outlook": outlook, "admin": self.env.user.has_group("base.group_system")}

    # ---------------------------------------------------------------- l'occupation

    def _occupations(self, partners, users, debut, fin, salle=False):
        """Les plages occupées (UTC naïf) des participants, et de la salle si on la veut : agenda et interventions planifiées."""
        plages = []
        Event = self.env["calendar.event"].sudo()
        if partners:
            for e in Event.search([("partner_ids", "in", partners.ids), ("start", "<", fin), ("stop", ">", debut), ("show_as", "=", "busy")]):
                if e.allday:
                    plages.append((datetime.combine(e.start_date, time.min), datetime.combine(e.stop_date, time.max)))
                else:
                    plages.append((e.start, e.stop))
        if salle:
            for e in Event.search([("cultiveau_salle", "=", True), ("start", "<", fin), ("stop", ">", debut)]):
                plages.append((e.start, e.stop))
        Task = self.env["project.task"].sudo()
        if users and "cultiveau_debut" in Task._fields:
            for t in Task.search([("user_ids", "in", users.ids), ("cultiveau_debut", "!=", False), ("cultiveau_debut", "<", fin), ("state", "not in", ("1_done", "1_canceled"))]):
                fin_t = t.cultiveau_fin or (t.cultiveau_debut + timedelta(hours=t.cultiveau_duree_prevue or 2))
                if fin_t > debut:
                    plages.append((t.cultiveau_debut, fin_t))
        return plages

    @api.model
    def creneaux(self, user_ids=None, duree_min=60, salle=True, jours=14, nombre=6, maintenant=None):
        """Les premiers créneaux où l'organisateur et les participants sont libres (et la salle, si on la prend), dans les heures
        ouvrées, deux au plus par jour pour laisser le choix. Chaque créneau : {jour, heures, debut (local), debut_utc}."""
        duree = timedelta(minutes=int(duree_min or 60))
        users = (self.env["res.users"].browse([int(i) for i in (user_ids or [])]) | self.env.user).exists()
        partners = users.mapped("partner_id")
        tz = self._tz()
        maintenant = maintenant or fields.Datetime.now()
        local = pytz.utc.localize(maintenant).astimezone(tz)
        # le premier départ possible : dans au moins une demi-heure, sur une demi-heure ronde
        depart = (local + timedelta(minutes=30)).replace(second=0, microsecond=0)
        depart += timedelta(minutes=(30 - depart.minute % 30) % 30)
        fin_recherche = local + timedelta(days=jours)
        occupe = self._occupations(partners, users, maintenant, fin_recherche.astimezone(pytz.utc).replace(tzinfo=None), salle=salle)
        resultat = []
        jour = depart.date()
        while jour <= fin_recherche.date() and len(resultat) < nombre:
            if jour.weekday() < 5:
                par_jour = 0
                for debut_plage, fin_plage in self._plages():
                    t = tz.localize(datetime.combine(jour, debut_plage))
                    limite = tz.localize(datetime.combine(jour, fin_plage))
                    while t + duree <= limite and par_jour < 2 and len(resultat) < nombre:
                        if t >= depart:
                            a = t.astimezone(pytz.utc).replace(tzinfo=None)
                            b = a + duree
                            if not any(o_a < b and o_b > a for o_a, o_b in occupe):
                                fin_local = t + duree
                                resultat.append({"jour": f"{JOURS[t.weekday()]} {t.day} {MOIS[t.month - 1]}", "heures": f"{_h(t)} – {_h(fin_local)}",
                                                 "debut": t.strftime("%Y-%m-%dT%H:%M"), "debut_utc": fields.Datetime.to_string(a)})
                                par_jour += 1
                                t += max(duree, timedelta(hours=2))  # le créneau suivant du même jour, plus tard
                                continue
                        t += timedelta(minutes=30)
            jour += timedelta(days=1)
        return resultat

    # ---------------------------------------------------------------- la planification

    @api.model
    def planifier(self, vals):
        """Crée la réunion dans l'agenda de l'organisateur (la personne connectée), invite l'équipe et le client, pose la visio."""
        titre = (vals.get("titre") or "").strip()
        if not titre:
            raise UserError("Donnez un objet à la réunion.")
        debut = fields.Datetime.to_datetime(vals.get("debut"))
        if not debut:
            raise UserError("Choisissez un créneau.")
        duree = int(vals.get("duree_min") or 60)
        fin = debut + timedelta(minutes=duree)
        lieu = vals.get("lieu") or "salle"
        visio = vals.get("visio") or self._param("cultiveau.visio_defaut", "erp") or "erp"
        users = (self.env["res.users"].browse([int(i) for i in (vals.get("user_ids") or [])]) | self.env.user).exists()
        client = self.env["res.partner"].browse(int(vals.get("client_id") or 0)).exists()
        salle = lieu == "salle"
        if salle and self.env["calendar.event"].sudo().search_count([("cultiveau_salle", "=", True), ("start", "<", fin), ("stop", ">", debut)]):
            raise UserError(f"{self.salle_nom()} est déjà prise sur ce créneau : choisissez-en un autre.")
        note = ""
        synchro = self.synchro()
        if visio == "google_meet" and not synchro["google"]["connecte"]:
            visio, note = "erp", "Votre agenda Google n'est pas connecté : la visio intégrée remplace Google Meet."
        if visio == "teams" and not synchro["outlook"]["connecte"]:
            visio, note = "erp", "Votre agenda Outlook n'est pas connecté : la visio intégrée remplace Teams."
        if lieu == "exterieur":
            visio = "aucune"
        lien = (vals.get("lien") or "").strip()
        if visio == "lien" and not lien.startswith(("http://", "https://")):
            raise UserError("Collez le lien complet de la visio (https://…).")
        description = (vals.get("description") or "").strip()
        location = ""
        if salle and visio not in ("google_meet", "teams"):
            location = self.salle_nom()  # Google et Microsoft ne créent le lien que sans lieu : la salle passe alors dans la description
        elif salle:
            description = f"{self.salle_nom()}\n{description}".strip()
        elif lieu == "exterieur" and client:
            location = ", ".join(x for x in (client.street, client.zip, client.city) if x)
        valeurs = {"name": titre, "start": debut, "stop": fin, "user_id": self.env.user.id, "partner_ids": [(6, 0, (users.mapped("partner_id") | client).ids)],
                   "location": location, "description": description.replace("\n", "<br/>"), "cultiveau_salle": salle, "cultiveau_visio": visio}
        if visio == "lien":
            valeurs["videocall_location"] = lien
        evenement = self.env["calendar.event"].create(valeurs)
        if visio == "erp":
            evenement._set_discuss_videocall_location()
        if visio in ("google_meet", "teams") and not note:
            note = ("Google crée le lien Meet dans quelques secondes ; il apparaît dans l'agenda et dans l'invitation." if visio == "google_meet"
                    else "Microsoft crée le lien Teams dans quelques secondes ; il apparaît dans l'agenda et dans l'invitation.")
        return {"id": evenement.id, "titre": evenement.name, "quand": evenement._cultiveau_quand(), "lien": evenement.videocall_location or "", "note": note,
                "participants": evenement.partner_ids.mapped("name")}

    # ---------------------------------------------------------------- la salle et les réunions du jour

    def _ligne(self, e):
        return {"id": e.id, "titre": e.name, "debut": fields.Datetime.to_string(e.start), "fin": fields.Datetime.to_string(e.stop), "organisateur": e.user_id.name or "",
                "participants": e.partner_ids.mapped("name"), "lien": e.videocall_location or "", "salle": e.cultiveau_salle}

    def _journee(self):
        tz = self._tz()
        local = pytz.utc.localize(fields.Datetime.now()).astimezone(tz)
        debut = tz.localize(datetime.combine(local.date(), time.min)).astimezone(pytz.utc).replace(tzinfo=None)
        return debut, debut + timedelta(days=1)

    @api.model
    def etat_salle(self, company=None):
        company = company or self.env.company
        debut, fin = self._journee()
        maintenant = fields.Datetime.now()
        evenements = self.env["calendar.event"].sudo().search([("cultiveau_salle", "=", True), ("start", "<", fin), ("stop", ">", debut),
                                                                 ("user_id.company_id", "=", company.id)], order="start")
        en_cours = evenements.filtered(lambda e: e.start <= maintenant < e.stop)[:1]
        prochaine = evenements.filtered(lambda e: e.start > maintenant)[:1]
        return {"en_cours": en_cours and self._ligne(en_cours) or None, "prochaine": prochaine and self._ligne(prochaine) or None,
                "aujourdhui": [self._ligne(e) for e in evenements]}

    @api.model
    def mes_reunions(self):
        debut, fin = self._journee()
        evenements = self.env["calendar.event"].search([("partner_ids", "in", self.env.user.partner_id.id), ("start", "<", fin), ("stop", ">", debut)], order="start")
        return [self._ligne(e) for e in evenements]

    @api.model
    def en_cours(self, users):
        """{user_id: réunion} pour les personnes qui sont en réunion à cet instant (selon l'agenda, invitations refusées exclues)."""
        maintenant = fields.Datetime.now()
        resultat = {}
        par_partner = {u.partner_id.id: u for u in users}
        Attendee = self.env["calendar.attendee"].sudo()
        for a in Attendee.search([("partner_id", "in", list(par_partner)), ("state", "!=", "declined"), ("event_id.start", "<=", maintenant),
                                  ("event_id.stop", ">", maintenant), ("event_id.allday", "=", False), ("event_id.show_as", "=", "busy")]):
            u = par_partner[a.partner_id.id]
            e = a.event_id
            if u.id not in resultat or e.cultiveau_salle:
                resultat[u.id] = {"titre": e.name, "debut": fields.Datetime.to_string(e.start), "fin": fields.Datetime.to_string(e.stop),
                                  "salle": e.cultiveau_salle, "visio": bool(e.videocall_location), "lien": e.videocall_location or "", "lieu": e.location or ""}
        return resultat


class Map(models.AbstractModel):
    _inherit = "cultiveau.map"

    def _reunions_en_cours(self, company, users):
        return self.env["cultiveau.reunion"].en_cours(users)

    @api.model
    def vivant(self):
        d = super().vivant()
        R = self.env["cultiveau.reunion"]
        d["reunion"] = {"salle_nom": R.salle_nom(), "salle": R.etat_salle(self.env.company), "synchro": R.synchro(),
                        "visio_defaut": R._param("cultiveau.visio_defaut", "erp") or "erp"}
        # les statuts en réunion se lisent avec leur réunion
        for p in d["personnes"]:
            r = p.get("reunion")
            if r and p["statut"] == "en_rendez_vous":
                p["statut_nom"] = "En visio (à distance)" if r.get("visio") else ("En rendez-vous" + (f" · {r['lieu']}" if r.get("lieu") else ""))
        return d

    def _fiche_zone(self, company, _id, cle=None):
        f = super()._fiche_zone(company, _id, cle=cle)
        if cle == "reunion":
            R = self.env["cultiveau.reunion"]
            synchro = R.synchro()
            f.update({"nom": R.salle_nom(), "salle": R.etat_salle(company), "mes": R.mes_reunions(), "synchro": synchro})
            actions = [{"cle": "planifier_reunion", "nom": "Planifier une réunion", "icone": "fa-calendar-plus-o"}]
            actions.append({"cle": "rendez_vous", "nom": "Mon agenda", "icone": "fa-calendar"})
            if not synchro["google"]["connecte"]:
                actions.append({"cle": "connecter_google", "nom": "Connecter mon agenda Google", "icone": "fa-google"})
            if not synchro["outlook"]["connecte"]:
                actions.append({"cle": "connecter_outlook", "nom": "Connecter mon agenda Outlook", "icone": "fa-windows"})
            f["actions"] = actions + [a for a in f.get("actions", []) if a["cle"] != "rendez_vous"]
        return f

    def _fiche_personne(self, company, uid):
        f = super()._fiche_personne(company, uid)
        if uid != self.env.user.id:
            f["actions"] = f["actions"] + [{"cle": "planifier_reunion", "nom": "Proposer une réunion", "icone": "fa-calendar-plus-o", "user_id": uid, "titre": f"Point avec {f['nom']}"}]
        return f

    def _fiche_client(self, company, pid):
        f = super()._fiche_client(company, pid)
        f["actions"] = f["actions"] + [{"cle": "planifier_reunion", "nom": "Proposer une réunion", "icone": "fa-calendar-plus-o", "client_id": pid, "client_nom": f["nom"]}]
        return f

    def _fiche_dossier(self, company, iid):
        f = super()._fiche_dossier(company, iid)
        if f.get("client_id"):
            f["actions"] = f["actions"] + [{"cle": "planifier_reunion", "nom": "Proposer un rendez-vous au client", "icone": "fa-calendar-plus-o", "client_id": f["client_id"],
                                            "client_nom": f.get("client", ""), "titre": f"Rendez-vous — {f.get('nom', '')}"}]
        return f


class Mathis(models.AbstractModel):
    _inherit = "cultiveau.mathis"

    def _ecritures(self):
        return super()._ecritures() | {"planifier_reunion"}

    def _titres(self):
        return {**super()._titres(), "planifier_reunion": "Planifier la réunion"}

    def _outils(self):
        equipe = {u.id: u.name for u in self.env["res.users"].sudo().search([("company_ids", "in", self.env.company.id), ("share", "=", False)])}
        description_equipe = "Identifiants de l'équipe : " + ", ".join(f"{n} = {i}" for i, n in equipe.items())
        return super()._outils() + [
            {"type": "function", "function": {"name": "creneaux_reunion", "description": "Les prochains créneaux où la personne connectée et les participants sont libres (agenda, interventions, salle). " + description_equipe,
                                              "parameters": {"type": "object", "properties": {"participants": {"type": "array", "items": {"type": "integer"}, "description": "identifiants des personnes de l'équipe"},
                                                                                              "duree_min": {"type": "integer", "description": "durée en minutes (60 par défaut)"},
                                                                                              "salle": {"type": "boolean", "description": "dans la salle de réunion (vrai par défaut)"}}}}},
            {"type": "function", "function": {"name": "planifier_reunion", "description": "Planifie une réunion et invite les participants (après confirmation). Prendre un debut_utc renvoyé par creneaux_reunion. "
                                                                                          "lieu : salle, visio ou exterieur ; visio : erp (intégrée), google_meet, teams, lien, aucune.",
                                              "parameters": {"type": "object", "properties": {"titre": {"type": "string"}, "debut_utc": {"type": "string"}, "duree_min": {"type": "integer"},
                                                                                              "participants": {"type": "array", "items": {"type": "integer"}}, "client_id": {"type": "integer"},
                                                                                              "lieu": {"type": "string", "enum": ["salle", "visio", "exterieur"]},
                                                                                              "visio": {"type": "string", "enum": ["erp", "google_meet", "teams", "lien", "aucune"]}, "lien": {"type": "string"}},
                                                             "required": ["titre", "debut_utc"]}}},
            {"type": "function", "function": {"name": "mes_reunions", "description": "Les réunions du jour de la personne connectée, avec leur lien de visio.", "parameters": {"type": "object", "properties": {}}}},
        ]

    def _executer(self, nom, args):
        R = self.env["cultiveau.reunion"]
        if nom == "creneaux_reunion":
            return R.creneaux(args.get("participants") or [], args.get("duree_min") or 60, salle=args.get("salle", True)), None
        if nom == "mes_reunions":
            return R.mes_reunions(), None
        if nom == "planifier_reunion":
            res = R.planifier({"titre": args.get("titre"), "debut": args.get("debut_utc"), "duree_min": args.get("duree_min") or 60, "user_ids": args.get("participants") or [],
                               "client_id": args.get("client_id"), "lieu": args.get("lieu") or "salle", "visio": args.get("visio") or "", "lien": args.get("lien") or ""})
            return res, {"type": "lien", "modele": "calendar.event", "id": res["id"], "libelle": f"{res['titre']} — {res['quand']}"}
        return super()._executer(nom, args)

    def _resumer(self, nom, args):
        if nom == "planifier_reunion":
            debut = fields.Datetime.to_datetime(args.get("debut_utc")) if args.get("debut_utc") else None
            quand = ""
            if debut:
                d = pytz.utc.localize(debut).astimezone(self.env["cultiveau.reunion"]._tz())
                quand = f"{JOURS[d.weekday()].lower()} {d.day} {MOIS[d.month - 1]} à {_h(d)}"
            return f"{args.get('titre', '')} · {quand} · {args.get('duree_min') or 60} min · {dict(VISIOS).get(args.get('visio') or 'erp', '')}"
        return super()._resumer(nom, args)


class Settings(models.TransientModel):
    _inherit = "res.config.settings"

    cultiveau_salle_nom = fields.Char("Nom de la salle", config_parameter="cultiveau.salle_nom", default="Salle de réunion")
    cultiveau_heures_reunion = fields.Char("Heures des réunions", config_parameter="cultiveau.heures_reunion", default="8:30-12:00,13:30-18:00",
                                           help="Les plages où l'on propose des créneaux, du lundi au vendredi.")
    cultiveau_visio_defaut = fields.Selection([v for v in VISIOS if v[0] != "lien"], "Visio par défaut", config_parameter="cultiveau.visio_defaut", default="erp")
    cultiveau_url_retour_google = fields.Char("Adresse de retour Google", compute="_compute_urls_retour")
    cultiveau_url_retour_microsoft = fields.Char("Adresse de retour Microsoft", compute="_compute_urls_retour")

    def _compute_urls_retour(self):
        base = self.env["ir.config_parameter"].sudo().get_param("web.base.url") or ""
        for s in self:
            s.cultiveau_url_retour_google = f"{base}/google_account/authentication"
            s.cultiveau_url_retour_microsoft = f"{base}/microsoft_account/authentication"
