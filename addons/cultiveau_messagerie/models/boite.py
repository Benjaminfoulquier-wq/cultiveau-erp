"""Les boîtes mail branchées sur l'ERP : Gmail, Outlook ou n'importe quelle messagerie (IMAP).

La boîte porte l'autorisation Google ou Microsoft (un seul clic « Connecter ») et la transmet aux serveurs de réception
et d'envoi de l'ERP. La relève ne touche jamais la boîte : les courriels sont lus sans être marqués comme lus, rien n'est
déplacé ni supprimé ; on peut continuer à utiliser Gmail ou Outlook comme avant. Le dossier « Envoyés » est lu aussi : une
réponse faite depuis Gmail ou Outlook compte comme une réponse.
"""
import email
import email.policy
import email.utils
import logging
import re
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

FOURNISSEURS = [("gmail", "Gmail / Google Workspace"), ("outlook", "Outlook / Microsoft 365"), ("imap", "Autre messagerie (IMAP)")]
MOIS_IMAP = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
LOT_MAX = 200


def _date_imap(d):
    return f"{d.day:02d}-{MOIS_IMAP[d.month - 1]}-{d.year}"


def _ids_message(texte):
    return re.findall(r"<[^<>\s]+>", texte or "")


class Boite(models.Model):
    _name = "cultiveau.boite"
    _description = "Boîte mail branchée sur l'ERP"
    _inherit = ["google.gmail.mixin", "microsoft.outlook.mixin"]
    _order = "name"

    # une seule autorisation Microsoft pour lire (IMAP) et envoyer (SMTP)
    _OUTLOOK_SCOPE = "https://outlook.office.com/IMAP.AccessAsUser.All https://outlook.office.com/SMTP.Send"

    name = fields.Char("Nom", required=True, help="Par exemple : Contact, Paul (personnelle), Comptabilité.")
    adresse = fields.Char("Adresse", required=True)
    fournisseur = fields.Selection(FOURNISSEURS, "Messagerie", required=True, default="gmail")
    company_id = fields.Many2one("res.company", "Société", required=True, default=lambda self: self.env.company)
    user_id = fields.Many2one("res.users", "Responsable", default=lambda self: self.env.user, domain=[("share", "=", False)],
                              help="Les courriels sans client connu lui reviennent ; c'est aussi la boîte personnelle de cette personne si elle n'est pas partagée.")
    partagee = fields.Boolean("Boîte partagée", default=True, help="Partagée (contact@, devis@…) : toute l'équipe voit ses courriels. Sinon : seulement son responsable et le gérant.")
    ranger_sur_fiches = fields.Boolean("Signaler sur les fiches", default=True, help="Une note sur le client, le devis, la facture ou l'intervention à chaque courriel reçu.")
    active = fields.Boolean(default=True)
    # la messagerie IMAP classique
    imap_hote = fields.Char("Serveur de réception (IMAP)")
    imap_port = fields.Integer("Port IMAP", default=993)
    smtp_hote = fields.Char("Serveur d'envoi (SMTP)")
    smtp_port = fields.Integer("Port SMTP", default=587)
    identifiant = fields.Char("Identifiant", help="Souvent l'adresse elle-même.")
    mot_de_passe = fields.Char("Mot de passe", groups="base.group_system", copy=False)
    # l'état
    fetchmail_id = fields.Many2one("fetchmail.server", "Serveur de réception", readonly=True, copy=False, ondelete="set null")
    mail_server_id = fields.Many2one("ir.mail_server", "Serveur d'envoi", readonly=True, copy=False, ondelete="set null")
    etat = fields.Selection([("a_connecter", "À connecter"), ("connectee", "Connectée"), ("erreur", "Erreur")], "État", default="a_connecter", readonly=True, copy=False)
    message = fields.Char("Dernier message", readonly=True, copy=False)
    derniere_releve = fields.Datetime("Dernière relève", readonly=True, copy=False)
    depuis_jours = fields.Integer("Reprendre les courriels des derniers", default=14, help="Jours relus à la première relève.")
    courriel_ids = fields.One2many("cultiveau.courriel", "boite_id", "Courriels")
    nb_a_traiter = fields.Integer("À traiter", compute="_compute_compteurs")
    nb_sans_reponse = fields.Integer("Sans réponse", compute="_compute_compteurs")

    _sql_constraints = [("adresse_unique", "unique(adresse, company_id)", "Cette adresse est déjà branchée.")]

    def _compute_compteurs(self):
        Courriel = self.env["cultiveau.courriel"]
        for b in self:
            b.nb_a_traiter = Courriel.search_count([("boite_id", "=", b.id), ("etat", "=", "a_traiter")])
            b.nb_sans_reponse = Courriel.search_count([("boite_id", "=", b.id), ("etat", "=", "a_traiter"), ("sans_reponse", "=", True)])

    @api.onchange("fournisseur", "adresse")
    def _onchange_fournisseur(self):
        if self.fournisseur == "imap" and self.adresse and "@" in self.adresse:
            domaine = self.adresse.split("@", 1)[1].lower()
            hotes = {"orange.fr": ("imap.orange.fr", "smtp.orange.fr"), "wanadoo.fr": ("imap.orange.fr", "smtp.orange.fr"), "free.fr": ("imap.free.fr", "smtp.free.fr"),
                     "sfr.fr": ("imap.sfr.fr", "smtp.sfr.fr"), "laposte.net": ("imap.laposte.net", "smtp.laposte.net")}
            imap, smtp = hotes.get(domaine, ("ssl0.ovh.net", "ssl0.ovh.net"))
            self.imap_hote = self.imap_hote or imap
            self.smtp_hote = self.smtp_hote or smtp
            self.identifiant = self.identifiant or self.adresse

    # ---------------------------------------------------------------- les serveurs de l'ERP

    def _valeurs_serveurs(self):
        self.ensure_one()
        nom = f"Cultiveau — {self.name} <{self.adresse}>"
        reception = {"name": nom, "user": self.adresse, "is_ssl": True, "port": 993, "object_id": self.env.ref("cultiveau_messagerie.model_cultiveau_courriel").id,
                     "attach": True, "original": False, "active": True}
        envoi = {"name": nom, "smtp_user": self.adresse, "from_filter": self.adresse, "smtp_encryption": "starttls", "smtp_port": 587, "active": True}
        if self.fournisseur == "gmail":
            reception.update({"server_type": "gmail", "server": "imap.gmail.com"})
            envoi.update({"smtp_authentication": "gmail", "smtp_host": "smtp.gmail.com", "smtp_pass": False})
        elif self.fournisseur == "outlook":
            reception.update({"server_type": "outlook", "server": "imap.outlook.com"})
            envoi.update({"smtp_authentication": "outlook", "smtp_host": "smtp.outlook.com", "smtp_pass": False})
        else:
            if not (self.imap_hote and self.smtp_hote):
                raise UserError("Indiquez les serveurs de réception et d'envoi de cette messagerie.")
            ident = self.identifiant or self.adresse
            reception.update({"server_type": "imap", "server": self.imap_hote, "port": self.imap_port or 993, "user": ident, "password": self.sudo().mot_de_passe})
            envoi.update({"smtp_authentication": "login", "smtp_host": self.smtp_hote, "smtp_port": self.smtp_port or 587, "smtp_user": ident,
                          "smtp_pass": self.sudo().mot_de_passe, "smtp_encryption": "ssl" if (self.smtp_port or 587) == 465 else "starttls"})
        return reception, envoi

    def _preparer_serveurs(self):
        """Crée ou met à jour les serveurs de réception et d'envoi (la réception reste hors de la relève standard : c'est la
        boîte qui relève, sans rien marquer comme lu)."""
        for b in self.sudo():
            reception, envoi = b._valeurs_serveurs()
            if b.fetchmail_id:
                b.fetchmail_id.write(reception)
            else:
                b.fetchmail_id = self.env["fetchmail.server"].sudo().create({**reception, "state": "draft"})
            if b.mail_server_id:
                b.mail_server_id.write(envoi)
            else:
                b.mail_server_id = self.env["ir.mail_server"].sudo().create(envoi)
            b._transmettre_jetons()

    def _transmettre_jetons(self):
        """L'autorisation de la boîte → ses serveurs (le jeton d'accès Microsoft dépend du service : chacun refait le sien)."""
        for b in self.sudo():
            if b.fournisseur == "gmail" and b.google_gmail_refresh_token:
                vals = {"google_gmail_refresh_token": b.google_gmail_refresh_token, "google_gmail_access_token": b.google_gmail_access_token,
                        "google_gmail_access_token_expiration": b.google_gmail_access_token_expiration}
                for s in (b.fetchmail_id, b.mail_server_id):
                    if s and s.google_gmail_refresh_token != b.google_gmail_refresh_token:
                        s.write(vals)
            if b.fournisseur == "outlook" and b.microsoft_outlook_refresh_token:
                for s in (b.fetchmail_id, b.mail_server_id):
                    if s and s.microsoft_outlook_refresh_token != b.microsoft_outlook_refresh_token:
                        s.write({"microsoft_outlook_refresh_token": b.microsoft_outlook_refresh_token, "microsoft_outlook_access_token": False,
                                 "microsoft_outlook_access_token_expiration": False})

    def write(self, vals):
        res = super().write(vals)
        if {"google_gmail_refresh_token", "microsoft_outlook_refresh_token"} & set(vals):
            # retour de Google ou Microsoft : la boîte est autorisée, on la teste tout de suite
            self._transmettre_jetons()
            for b in self:
                b._tester()
        return res

    @api.model
    def _identifiants_oauth(self):
        """Gmail et Outlook reprennent, à défaut des leurs, les identifiants déjà saisis pour les agendas (même application)."""
        ICP = self.env["ir.config_parameter"].sudo()
        for a, b in (("google_gmail_client_id", "google_calendar_client_id"), ("google_gmail_client_secret", "google_calendar_client_secret"),
                     ("microsoft_outlook_client_id", "microsoft_calendar_client_id"), ("microsoft_outlook_client_secret", "microsoft_calendar_client_secret")):
            if not ICP.get_param(a) and ICP.get_param(b):
                ICP.set_param(a, ICP.get_param(b))

    def action_connecter(self):
        """Gmail ou Outlook : l'écran d'autorisation (un clic) ; IMAP : un essai de connexion."""
        self.ensure_one()
        if not self.env.user.has_group("base.group_system"):
            raise UserError("Seul l'administrateur de l'ERP peut brancher une boîte mail.")
        self._identifiants_oauth()
        self._preparer_serveurs()
        if self.fournisseur == "gmail":
            self.invalidate_recordset(["google_gmail_uri"])
            if not self.google_gmail_uri:
                raise UserError("Saisissez l'identifiant Google (Réglages → Cultiveau → Messagerie) : le même projet Google Cloud que l'agenda convient, avec l'API Gmail activée.")
            return self.open_google_gmail_uri()
        if self.fournisseur == "outlook":
            self.invalidate_recordset(["microsoft_outlook_uri"])
            if not self.microsoft_outlook_uri:
                raise UserError("Saisissez l'identifiant Microsoft (Réglages → Cultiveau → Messagerie) : la même application que l'agenda convient.")
            return self.open_microsoft_outlook_uri()
        self._tester()
        if self.etat == "erreur":
            raise UserError(self.message)
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"title": "Boîte connectée", "message": f"{self.adresse} est relevée toutes les cinq minutes.", "type": "success", "sticky": False}}

    def _tester(self):
        for b in self.sudo():
            connexion = None
            try:
                connexion = b.fetchmail_id.connect(allow_archived=True)
                b.write({"etat": "connectee", "message": "Connexion réussie."})
            except Exception as e:  # noqa: BLE001
                b.write({"etat": "erreur", "message": f"Connexion impossible : {str(e)[:200]}"})
            finally:
                if connexion:
                    try:
                        connexion.logout()
                    except Exception:  # noqa: BLE001
                        pass

    # ---------------------------------------------------------------- la relève (sans rien toucher)

    def action_relever(self):
        n = self.relever()
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"title": "Relève terminée", "message": f"{n} nouveau(x) courriel(s).", "type": "success", "sticky": False}}

    def relever(self):
        """Lit la boîte de réception (courriels nouveaux depuis la dernière relève) et le dossier « Envoyés ». Renvoie le nombre de courriels ajoutés."""
        total = 0
        for b in self.sudo().filtered(lambda b: b.active and b.fetchmail_id):
            connexion = None
            debut = fields.Datetime.now()
            try:
                connexion = b.fetchmail_id.connect(allow_archived=True)
                depuis = (b.derniere_releve - timedelta(days=1)) if b.derniere_releve else (debut - timedelta(days=b.depuis_jours or 14))
                total += b._relever_reception(connexion, depuis)
                b._relever_envoyes(connexion, depuis)
                b.write({"etat": "connectee", "derniere_releve": debut, "message": f"Relevée le {fields.Datetime.context_timestamp(b, debut):%d/%m à %H:%M}."})
            except Exception as e:  # noqa: BLE001
                _logger.warning("Boîte %s : relève impossible (%s)", b.adresse, e)
                b.write({"etat": "erreur", "message": f"Relève impossible : {str(e)[:200]}"})
            finally:
                if connexion:
                    try:
                        connexion.logout()
                    except Exception:  # noqa: BLE001
                        pass
        return total

    def _deja_vus(self, ids):
        ids = [i for i in ids if i]
        if not ids:
            return set()
        return set(self.env["mail.message"].sudo().search([("message_id", "in", ids)]).mapped("message_id"))

    def _relever_reception(self, connexion, depuis):
        self.ensure_one()
        connexion.select("INBOX", readonly=True)  # lecture seule : rien n'est marqué comme lu
        typ, donnees = connexion.search(None, f"(SINCE {_date_imap(depuis)})")
        numeros = (donnees[0] or b"").split()[-LOT_MAX:]
        entetes = {}
        for num in numeros:
            typ, d = connexion.fetch(num, "(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID)])")
            brut = next((x[1] for x in d if isinstance(x, tuple)), b"")
            ids = _ids_message(brut.decode("utf-8", "ignore"))
            entetes[num] = ids[0] if ids else None
        vus = self._deja_vus(list(entetes.values()))
        n = 0
        Thread = self.env["mail.thread"].with_company(self.company_id)
        for num, mid in entetes.items():
            if mid and mid in vus:
                continue
            typ, d = connexion.fetch(num, "(BODY.PEEK[])")
            brut = next((x[1] for x in d if isinstance(x, tuple)), None)
            if not brut:
                continue
            entete = email.message_from_bytes(brut, policy=email.policy.SMTP)
            masse = bool(entete.get("List-Unsubscribe") or (entete.get("Precedence") or "").lower() in ("bulk", "list", "junk")
                         or (entete.get("Auto-Submitted") or "no").lower() != "no")
            if (entete.get("From") or "").lower().find(self.adresse.lower()) >= 0:
                continue  # nos propres envois copiés dans la réception
            try:
                with self.env.cr.savepoint():
                    res = Thread.with_context(cultiveau_boite_id=self.id, cultiveau_masse=masse, default_fetchmail_server_id=self.fetchmail_id.id,
                                              fetchmail_cron_running=True).message_process("cultiveau.courriel", brut, save_original=False, strip_attachments=False)
                if res:
                    n += 1
            except Exception as e:  # noqa: BLE001
                _logger.info("Boîte %s : courriel ignoré (%s)", self.adresse, e)
        return n

    def _dossier_envoyes(self, connexion):
        typ, dossiers = connexion.list()
        for ligne in dossiers or []:
            texte = ligne.decode("utf-8", "ignore") if isinstance(ligne, bytes) else str(ligne)
            if "\\Sent" in texte:
                m = re.search(r'"([^"]+)"\s*$', texte) or re.search(r"\s(\S+)\s*$", texte)
                if m:
                    return m.group(1)
        return None

    def _relever_envoyes(self, connexion, depuis):
        """Les réponses envoyées depuis Gmail ou Outlook : le courriel auquel elles répondent est marqué « répondu »."""
        self.ensure_one()
        dossier = self._dossier_envoyes(connexion)
        if not dossier:
            return 0
        typ, _r = connexion.select(f'"{dossier}"', readonly=True)
        if typ != "OK":
            return 0
        typ, donnees = connexion.search(None, f"(SINCE {_date_imap(depuis)})")
        references = {}
        for num in (donnees[0] or b"").split()[-LOT_MAX:]:
            typ, d = connexion.fetch(num, "(BODY.PEEK[HEADER.FIELDS (IN-REPLY-TO REFERENCES DATE)])")
            brut = next((x[1] for x in d if isinstance(x, tuple)), b"")
            entete = email.message_from_bytes(brut, policy=email.policy.SMTP)
            date = None
            try:
                date = email.utils.parsedate_to_datetime(entete.get("Date")).astimezone(tz=None).replace(tzinfo=None) if entete.get("Date") else None
            except (TypeError, ValueError):
                date = None
            for mid in _ids_message(str(entete.get("In-Reply-To") or "")) + _ids_message(str(entete.get("References") or ""))[-3:]:
                references[mid] = date
        if not references:
            return 0
        messages = self.env["mail.message"].sudo().search([("message_id", "in", list(references)), ("model", "=", "cultiveau.courriel")])
        n = 0
        for m in messages:
            c = self.env["cultiveau.courriel"].sudo().browse(m.res_id)
            quand = references.get(m.message_id) or fields.Datetime.now()
            if c.exists() and c.etat == "a_traiter" and (not c.date_reception or quand >= c.date_reception):
                c.write({"etat": "repondu", "date_reponse": quand, "sans_reponse": False})
                n += 1
        return n

    @api.model
    def _cron_relever(self):
        for b in self.sudo().search([("etat", "=", "connectee"), ("fetchmail_id", "!=", False)]):
            b.relever()
            self.env.cr.commit()
