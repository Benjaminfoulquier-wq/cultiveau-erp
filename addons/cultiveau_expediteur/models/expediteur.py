"""L'expéditeur des courriels : notification@cultiveau.fr au nom de l'adhérent, ou la boîte de l'adhérent ; et chaque envoi écrit
dans le fil de la fiche."""
from email.utils import formataddr

from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.tools import email_normalize

ADRESSE_RESEAU_DEFAUT = "notification@cultiveau.fr"
MODES = [("reseau", "Par le réseau : notification@cultiveau.fr, au nom de l'adhérent, réponses à son adresse"), ("boite", "Par la boîte de l'adhérent (Courriels › Boîtes mail)")]


class Societe(models.Model):
    _inherit = "res.company"

    cultiveau_envoi = fields.Selection(MODES, "Expéditeur des courriels", default="reseau", required=True)
    cultiveau_boite_envoi_id = fields.Many2one("cultiveau.boite", "Boîte d'envoi", domain="[('company_id', '=', id), ('partagee', '=', True)]",
                                               help="La boîte branchée par laquelle partent les courriels de la société (mode « par la boîte »).")
    cultiveau_expediteur_apercu = fields.Char("Vu par le client", compute="_compute_expediteur_apercu")

    def _cultiveau_adresse_reseau(self):
        return (self.env["ir.config_parameter"].sudo().get_param("cultiveau.expediteur_reseau") or ADRESSE_RESEAU_DEFAUT).strip()

    @api.depends("cultiveau_envoi", "cultiveau_boite_envoi_id.adresse", "cultiveau_boite_envoi_id.etat", "email", "name")
    def _compute_expediteur_apercu(self):
        for c in self:
            if c.cultiveau_envoi == "boite" and c.cultiveau_boite_envoi_id:
                b = c.cultiveau_boite_envoi_id
                c.cultiveau_expediteur_apercu = f"{c.name} <{b.adresse}>" + ("" if b.etat == "connectee" and b.mail_server_id else " (boîte pas encore connectée : le réseau prend le relais)")
            else:
                c.cultiveau_expediteur_apercu = f"{c.name} <{c._cultiveau_adresse_reseau()}>" + (f", réponses à {c.email}" if c.email else ", sans adresse de réponse : renseignez l'e-mail de la société")

    def cultiveau_expediteur(self):
        """(email_from, reply_to, mail_server) pour un courriel de cette société."""
        self.ensure_one()
        nom = self.name or ""
        if self.cultiveau_envoi == "boite" and self.cultiveau_boite_envoi_id and self.cultiveau_boite_envoi_id.mail_server_id and self.cultiveau_boite_envoi_id.etat == "connectee":
            b = self.cultiveau_boite_envoi_id
            return formataddr((nom, b.adresse)), False, b.mail_server_id
        return formataddr((nom, self._cultiveau_adresse_reseau())), (formataddr((nom, self.email)) if self.email else False), False


class Reglages(models.TransientModel):
    _inherit = "res.config.settings"

    cultiveau_envoi = fields.Selection(related="company_id.cultiveau_envoi", readonly=False)
    cultiveau_boite_envoi_id = fields.Many2one(related="company_id.cultiveau_boite_envoi_id", readonly=False)
    cultiveau_expediteur_apercu = fields.Char(related="company_id.cultiveau_expediteur_apercu")
    cultiveau_expediteur_reseau = fields.Char("Adresse d'envoi du réseau", config_parameter="cultiveau.expediteur_reseau", default=ADRESSE_RESEAU_DEFAUT)


class Mail(models.Model):
    _inherit = "mail.mail"

    cultiveau_expediteur_pose = fields.Boolean("Expéditeur Cultiveau posé", default=False, copy=False)

    def _cultiveau_societe(self, vals):
        """La société du courriel : celle de la fiche, sinon celle de l'auteur, sinon la courante."""
        modele, res_id = vals.get("model"), vals.get("res_id")
        if modele and res_id and modele in self.env:
            Modele = self.env[modele]
            if "company_id" in Modele._fields:
                rec = Modele.sudo().browse(int(res_id)).exists()
                if rec and rec.company_id:
                    return rec.company_id
        auteur = vals.get("author_id")
        if auteur:
            p = self.env["res.partner"].sudo().browse(int(auteur)).exists()
            if p and p.user_ids and p.user_ids[0].company_id:
                return p.user_ids[0].company_id
        return self.env.company

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("cultiveau_expediteur_pose") or self.env.context.get("cultiveau_expediteur_brut"):
                continue
            societe = self._cultiveau_societe(vals)
            email_from, reply_to, serveur = societe.cultiveau_expediteur()
            vals["email_from"] = email_from
            if reply_to and not vals.get("reply_to"):
                vals["reply_to"] = reply_to
            if serveur:
                vals["mail_server_id"] = serveur.id
            vals["cultiveau_expediteur_pose"] = True
        return super().create(vals_list)

    def _postprocess_sent_message(self, success_pids, failure_reason=False, failure_type=None):
        """Un courriel parti sans ligne visible dans le fil (envoi automatique, modèle) y laisse sa trace : le fil est la base de tout."""
        # on lit avant : un courriel « à supprimer après envoi » n'existe plus au retour de super()
        a_noter = []
        for mail in self.filtered(lambda m: m.state == "sent" and m.model and m.res_id and m.model in self.env and not failure_type):
            msg = mail.mail_message_id
            visible = msg and msg.model == mail.model and msg.res_id == mail.res_id and msg.message_type in ("comment", "email")
            if visible:
                continue
            a_noter.append((mail.model, mail.res_id, mail.email_to or ", ".join(mail.recipient_ids.mapped("email")), mail.subject or "", mail.email_from or ""))
        res = super()._postprocess_sent_message(success_pids, failure_reason=failure_reason, failure_type=failure_type)
        for modele, res_id, destinataires, sujet, expediteur in a_noter:
            rec = self.env[modele].sudo().browse(res_id).exists()
            if not rec or not hasattr(rec, "message_post"):
                continue
            corps = Markup("<p>Courriel envoyé à %s : <b>%s</b><br/><span class='text-muted'>expéditeur %s</span></p>") % (escape(destinataires or "?"), escape(sujet), escape(expediteur))
            rec.with_context(mail_notrack=True, mail_create_nosubscribe=True).message_post(body=corps, message_type="notification", subtype_xmlid="mail.mt_note")
        return res
