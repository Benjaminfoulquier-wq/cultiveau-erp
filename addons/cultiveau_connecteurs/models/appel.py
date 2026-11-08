"""Les appels reçus ou passés par l'assistant téléphonique, rangés dans l'ERP : le sujet d'abord, puis tout ce qui a été dit et l'audio."""
import re

from markupsafe import Markup, escape

from odoo import api, fields, models

from .synchro import FAMILLES, INSTALLATION_ASSISTANT

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
    recueilli = fields.Html("Ce que l'assistant a retenu", readonly=True, sanitize=True)
    reperes = fields.Text("Repères pour le technicien", readonly=True, help="Repère du référentiel (§ 18.9) et pré-analyse des besoins quand il y en a.")
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

    def _ligne_du_fil(self, avec_recueilli=False):
        """Ce qu'on voit dans le fil : une ligne, le sujet, et de quoi ouvrir le reste. Sur la fiche du client, aussi tout ce que
        l'assistant a retenu de lui pendant l'appel : c'est son CRM, rien ne doit rester seulement dans l'assistant."""
        self.ensure_one()
        quand = fields.Datetime.context_timestamp(self, self.date).strftime("%d/%m à %H:%M") if self.date else ""
        entete = " · ".join(x for x in ("Appel " + ("passé par l'assistant" if self.sens == "sortant" else "reçu par l'assistant"), quand, self.duree) if x)
        corps = Markup('<p>📞 <b>%s</b> — %s<br/><a href="%s">Voir la conversation%s</a></p>') % (
            entete, self.sujet, self._lien(), " et écouter" if self.audio_url else "")
        if avec_recueilli and self.recueilli:
            corps += Markup(self.recueilli)
        return corps

    @staticmethod
    def _recueilli_html(lignes):
        """Les informations recueillies, telles que l'assistant les envoie : une liste de [libellé, valeur]."""
        paires = [(str(l[0]).strip(), str(l[1]).strip()) for l in (lignes or []) if isinstance(l, (list, tuple)) and len(l) == 2 and str(l[1]).strip()]
        if not paires:
            return False
        return Markup('<table class="table table-sm o_cultiveau_recueilli"><tbody>%s</tbody></table>') % Markup("").join(
            Markup("<tr><td><b>%s</b></td><td>%s</td></tr>") % (k, v) for k, v in paires[:60])

    @api.model
    def _completer_client(self, partner, donnees):
        """Ce que l'assistant a appris du client complète sa fiche : seulement les champs vides, jamais d'écrasement (ce que l'adhérent a saisi fait foi)."""
        client = donnees.get("client") or {}
        valeurs = {"email": client.get("email"), "street": client.get("adresse"), "zip": client.get("code_postal"), "city": client.get("commune"),
                   "exploitation": client.get("exploitation")}
        maj = {k: str(v).strip()[:255] for k, v in valeurs.items() if v and str(v).strip() and not partner[k]}
        if partner.mobile and client.get("telephone2") and not partner.phone and client["telephone2"] != partner.mobile:
            maj["phone"] = client["telephone2"]
        if maj:
            partner.with_context(mail_notrack=True).write(maj)
        return maj

    @api.model
    def _materiel_depuis_appel(self, societe, partner, donnees):
        """Le matériel dont le client a parlé devient un équipement de sa fiche, s'il n'y en a pas déjà un de cette famille ; marque et modèle
        complètent un équipement connu qui ne les avait pas."""
        famille = donnees.get("materiel_famille") or ""
        if not partner or famille not in FAMILLES or famille == "autre":
            return self.env["cultiveau.equipement"]
        categorie, libelle = FAMILLES[famille]
        marque, modele = (donnees.get("marque") or "").strip()[:64], (donnees.get("modele") or "").strip()[:64]
        Equipement = self.env["cultiveau.equipement"].sudo()
        existants = Equipement.search([("partner_id", "=", partner.id), ("categorie", "=", categorie)], order="id")
        if existants:
            cible = next((e for e in existants if (not marque or (e.marque or "").lower() == marque.lower())), existants[:1])
            maj = {k: v for k, v in (("marque", marque), ("modele", modele)) if v and not cible[k]}
            if maj:
                cible.write(maj)
            return cible
        Installation = self.env["cultiveau.installation"].sudo().with_company(societe)
        installation = Installation.search([("partner_id", "=", partner.id), ("name", "=", INSTALLATION_ASSISTANT)], limit=1) or Installation.create({
            "name": INSTALLATION_ASSISTANT, "partner_id": partner.id, "company_id": societe.id, "type_systeme": "mixte"})
        return Equipement.create({"installation_id": installation.id, "categorie": categorie, "marque": marque or False, "modele": modele or False,
                                  "name": " ".join(x for x in (libelle, marque, modele) if x), "notes": "Cité au téléphone à l'assistant ; à vérifier sur place."})

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
            "recueilli": self._recueilli_html(donnees.get("recueilli")), "reperes": (donnees.get("reperes") or "").strip() or False,
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
            self._completer_client(partner, donnees)
            self._materiel_depuis_appel(societe, partner, donnees)
            partner.message_post(body=appel._ligne_du_fil(avec_recueilli=True), subtype_xmlid="mail.mt_note", message_type="comment")
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
