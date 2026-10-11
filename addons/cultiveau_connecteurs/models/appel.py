"""Les appels reçus ou passés par l'assistant téléphonique, rangés dans l'ERP : le sujet d'abord, puis tout ce qui a été dit et l'audio."""
import re

from markupsafe import Markup

from odoo import api, fields, models

SENS = [("entrant", "Reçu"), ("sortant", "Passé par l'assistant")]


def sujet_court(texte, limite=240):
    """Les une ou deux premières phrases du résumé."""
    texte = " ".join((texte or "").split())
    phrases = re.split(r"(?<=[.!?…])\s+", texte)
    sujet = " ".join(phrases[:2]) if phrases else ""
    return sujet if len(sujet) <= limite else sujet[: limite - 1].rsplit(" ", 1)[0] + "…"


class Appel(models.Model):
    _name = "cultiveau.appel"
    _description = "Appel de l'assistant téléphonique"
    _order = "date desc, id desc"
    _rec_name = "sujet"

    reference = fields.Char("Référence", required=True, index=True, readonly=True)
    company_id = fields.Many2one("res.company", "Adhérent", required=True, index=True, readonly=True)
    partner_id = fields.Many2one("res.partner", "Client", index=True)
    date = fields.Datetime("Date", default=fields.Datetime.now, readonly=True)
    duree_s = fields.Integer("Durée (s)", readonly=True)
    duree = fields.Char("Durée", compute="_compute_duree")
    entete = fields.Char(compute="_compute_duree")
    sens = fields.Selection(SENS, "Sens", default="entrant", readonly=True)
    numero = fields.Char("Numéro", readonly=True)
    categorie = fields.Char("Catégorie", readonly=True)
    urgence = fields.Selection([("immediate", "Immédiate"), ("journee", "Dans la journée"), ("semaine", "Cette semaine"), ("non_urgent", "Non urgent")],
                               "Urgence", readonly=True)
    sujet = fields.Char("Sujet", required=True, readonly=True)
    resume = fields.Text("Résumé", readonly=True)
    transcription = fields.Text("Tout ce qui a été dit", readonly=True)
    lien_assistant = fields.Char("Fiche dans l'assistant", readonly=True)
    audio_url = fields.Char("Enregistrement", readonly=True, groups="base.group_user")
    audio_jusqu_au = fields.Date("Écoutable jusqu'au", readonly=True)
    audio_disponible = fields.Boolean(compute="_compute_lecteur")
    lecteur = fields.Html("Écouter", compute="_compute_lecteur", sanitize=False)
    task_id = fields.Many2one("project.task", "Intervention", readonly=True, index=True)
    lead_id = fields.Many2one("crm.lead", "Opportunité", readonly=True, index=True)

    _sql_constraints = [("reference_unique", "unique(company_id, reference)", "Cet appel est déjà enregistré.")]

    def _compute_duree(self):
        for a in self:
            a.duree = f"{a.duree_s // 60} min {a.duree_s % 60:02d} s" if a.duree_s else ""
            quand = fields.Datetime.context_timestamp(a, a.date).strftime("le %d/%m/%Y à %H:%M") if a.date else ""
            a.entete = " · ".join(x for x in (dict(SENS).get(a.sens, ""), quand, a.duree) if x)

    @api.depends("audio_url", "audio_jusqu_au")
    def _compute_lecteur(self):
        aujourdhui = fields.Date.context_today(self)
        for a in self:
            url = a.sudo().audio_url
            a.audio_disponible = bool(url and url.startswith("https://") and (not a.audio_jusqu_au or a.audio_jusqu_au >= aujourdhui))
            if a.audio_disponible:
                a.lecteur = Markup('<audio controls="controls" preload="none" style="width: 100%%; max-width: 640px;" src="%s"></audio>') % url
            elif url:
                a.lecteur = Markup("<p class='text-muted'>Enregistrement effacé (durée de conservation dépassée) : la transcription reste.</p>")
            else:
                a.lecteur = False

    def _lien(self):
        self.ensure_one()
        return f"/app/action-cultiveau_connecteurs.action_appels/{self.id}"

    def _ligne_du_fil(self):
        """Ce qu'on voit dans le fil : une ligne, le sujet, et de quoi ouvrir le reste."""
        self.ensure_one()
        quand = fields.Datetime.context_timestamp(self, self.date).strftime("%d/%m à %H:%M") if self.date else ""
        entete = " · ".join(x for x in ("Appel " + ("passé par l'assistant" if self.sens == "sortant" else "reçu par l'assistant"), quand, self.duree) if x)
        return Markup('<p>📞 <b>%s</b> — %s<br/><a href="%s">Voir la conversation%s</a></p>') % (
            entete, self.sujet, self._lien(), " et écouter" if self.audio_url else "")

    @api.model
    def cultiveau_enregistrer(self, societe, partner, donnees):
        """L'appel tel que l'assistant l'envoie ; une seule fiche par référence."""
        reference = donnees.get("reference") or ""
        appel = self.sudo().search([("company_id", "=", societe.id), ("reference", "=", reference)], limit=1) if reference else self.browse()
        resume = donnees.get("resume") or donnees.get("symptome") or ""
        valeurs = {
            "company_id": societe.id, "partner_id": partner.id if partner else False, "reference": reference or f"SANS-REF-{fields.Datetime.now():%Y%m%d%H%M%S}",
            "sujet": donnees.get("sujet") or sujet_court(resume) or "Appel reçu par l'assistant", "resume": resume,
            "transcription": donnees.get("transcription") or "", "duree_s": int(donnees.get("duree_s") or 0) if str(donnees.get("duree_s") or "0").isdigit() else 0,
            "sens": "sortant" if donnees.get("sens") == "sortant" else "entrant", "numero": donnees.get("numero") or (donnees.get("client") or {}).get("telephone") or "",
            "categorie": donnees.get("categorie") or "", "lien_assistant": donnees.get("lien_appel") or False,
            "urgence": donnees.get("urgence") if donnees.get("urgence") in ("immediate", "journee", "semaine", "non_urgent") else False,
            "audio_url": donnees.get("audio_url") or False, "audio_jusqu_au": donnees.get("audio_jusqu_au") or False,
        }
        if donnees.get("date"):
            try:
                valeurs["date"] = fields.Datetime.to_datetime(str(donnees["date"]).replace("T", " ")[:19])
            except ValueError:
                pass
        if appel:
            appel.write({k: v for k, v in valeurs.items() if v})
            return appel, False
        appel = self.sudo().create(valeurs)
        if partner:
            partner.message_post(body=appel._ligne_du_fil(), subtype_xmlid="mail.mt_note", message_type="comment")
        return appel, True

    def cultiveau_rattacher(self, rec):
        """L'intervention ou l'opportunité née de l'appel : liée, et la même ligne dans son fil."""
        for a in self:
            a.write({"task_id": rec.id} if rec._name == "project.task" else {"lead_id": rec.id} if rec._name == "crm.lead" else {})
            rec.message_post(body=a._ligne_du_fil(), subtype_xmlid="mail.mt_note", message_type="comment")


class Partner(models.Model):
    _inherit = "res.partner"

    cultiveau_appel_ids = fields.One2many("cultiveau.appel", "partner_id", string="Appels")
    cultiveau_nb_appels = fields.Integer("Nombre d'appels", compute="_compute_nb_appels")

    def _compute_nb_appels(self):
        donnees = {p.id: n for p, n in self.env["cultiveau.appel"]._read_group([("partner_id", "in", self.ids)], ["partner_id"], ["__count"])}
        for p in self:
            p.cultiveau_nb_appels = donnees.get(p.id, 0)

    def action_voir_appels(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("cultiveau_connecteurs.action_appels")
        action["domain"] = [("partner_id", "child_of", self.commercial_partner_id.id)]
        action["context"] = {"default_partner_id": self.id}
        return action
