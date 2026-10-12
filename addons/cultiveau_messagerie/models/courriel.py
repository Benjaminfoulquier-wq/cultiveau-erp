"""Les courriels reçus : rangés sur le bon client et le bon dossier, triés, suivis jusqu'à la réponse.

Un courriel qui répond à un envoi de l'ERP (un devis, une facture) retrouve tout seul son document. Les autres deviennent un
« courriel » : l'expéditeur est rapproché d'un client (adresse, puis domaine de l'entreprise), la référence citée (S00042,
FAC/2026/0012…) ou à défaut le dossier ouvert du client donne le document, l'IA trie (devis, panne, facture…), résume et
dit s'il attend une réponse. Une note signale le courriel sur la fiche du client ou du document.

On répond depuis l'ERP (la réponse part de la boîte qui a reçu le courriel) ou depuis Gmail/Outlook (la relève du dossier
« Envoyés » le voit). Sans réponse au bout de trois jours ouvrés, le responsable a une activité et la map le signale.
"""
import json
import logging
import re
from email.utils import formataddr, getaddresses

import requests
from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import html2plaintext

_logger = logging.getLogger(__name__)

MISTRAL = "https://api.mistral.ai/v1"
CATEGORIES = [("demande", "Demande de devis"), ("sav", "Panne / SAV"), ("facture", "Facture / paiement"), ("commande", "Commande / livraison"),
              ("fournisseur", "Fournisseur"), ("administratif", "Administratif"), ("publicite", "Publicité / lettre d'info"), ("autre", "Autre")]
MOTS = {"sav": ["panne", "fuite", "ne fonctionne", "ne marche", "ne démarre", "ne demarre", "plus d'eau", "arrosage arrêté", "dépannage", "depannage", "réparation", "reparation", "cassé", "bloqué", "alarme", "pression"],
        "facture": ["facture", "règlement", "reglement", "paiement", "virement", "échéance", "echeance", "avoir", "relance"],
        "commande": ["commande", "livraison", "expédition", "expedition", "colis", "bon de livraison"],
        "demande": ["devis", "prix", "tarif", "chiffrage", "proposition", "projet", "installation", "étude"]}
WEBMAILS = {"gmail.com", "googlemail.com", "orange.fr", "wanadoo.fr", "free.fr", "sfr.fr", "neuf.fr", "laposte.net", "hotmail.com", "hotmail.fr", "outlook.com",
            "outlook.fr", "live.fr", "live.com", "yahoo.fr", "yahoo.com", "icloud.com", "me.com", "bbox.fr", "aliceadsl.fr", "club-internet.fr", "msn.com", "gmx.fr", "aol.com"}
DOCUMENTS = [("sale.order", "Devis / commande"), ("account.move", "Facture"), ("project.task", "Intervention"), ("purchase.order", "Commande fournisseur"),
             ("cultiveau.chantier", "Chantier"), ("cultiveau.installation", "Installation"), ("crm.lead", "Opportunité")]

SYSTEME_TRI = """Tu tries le courrier d'une entreprise qui vend, installe et dépanne l'irrigation agricole. Réponds uniquement en JSON :
{"categorie": "demande|sav|facture|commande|fournisseur|administratif|publicite|autre", "urgent": true|false,
 "attend_reponse": true|false, "resume": "une phrase de 15 mots au plus", "document": "une clé de la liste ou null"}
urgent : une panne en pleine saison, une installation à l'arrêt, une échéance proche. attend_reponse : faux pour une
notification automatique, un accusé de réception, une lettre d'information, un simple merci. document : le document de la
liste dont parle le courriel, sinon null."""

SYSTEME_REPONSE = """Tu es {prenom}, l'assistant de {societe} (installation et dépannage d'irrigation agricole). Tu prépares la réponse
que {signataire} va relire puis envoyer. En français, vouvoiement, ton cordial et professionnel, court (3 à 8 phrases), concret.
N'invente jamais un prix, une date, un délai ou une disponibilité qui ne sont pas dans les éléments donnés : propose plutôt de
rappeler, ou dis que tu reviens vers le client. Si le courriel demande une information absente, pose la question. Pas d'objet,
pas de « Objet : ». Termine par une formule de politesse puis la signature : {signataire}, {societe}."""


def _jours_ouvres(debut, fin):
    """Les jours ouvrés (lundi→vendredi) écoulés entre deux instants."""
    if not debut or not fin or fin <= debut:
        return 0
    n, d = 0, debut.date()
    while d < fin.date():
        d = d.fromordinal(d.toordinal() + 1)
        if d.weekday() < 5:
            n += 1
    return n


class Courriel(models.Model):
    _name = "cultiveau.courriel"
    _description = "Courriel reçu"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_reception desc, id desc"
    _rec_name = "name"

    name = fields.Char("Objet", required=True, default="(sans objet)")
    boite_id = fields.Many2one("cultiveau.boite", "Boîte", index=True, ondelete="set null")
    company_id = fields.Many2one("res.company", "Société", required=True, default=lambda self: self.env.company, index=True)
    expediteur = fields.Char("De")
    expediteur_nom = fields.Char("Expéditeur", compute="_compute_expediteur_nom", store=True)
    partner_id = fields.Many2one("res.partner", "Client / contact", index=True, tracking=True)
    user_id = fields.Many2one("res.users", "Responsable", tracking=True, domain=[("share", "=", False)])
    date_reception = fields.Datetime("Reçu le", default=fields.Datetime.now, index=True)
    date_reponse = fields.Datetime("Répondu le", readonly=True)
    etat = fields.Selection([("a_traiter", "À traiter"), ("repondu", "Répondu"), ("classe", "Classé")], "État", default="a_traiter", required=True, index=True, tracking=True)
    categorie = fields.Selection(CATEGORIES, "Catégorie", default="autre", tracking=True)
    urgent = fields.Boolean("Urgent")
    resume = fields.Char("Résumé")
    apercu = fields.Text("Aperçu")
    document = fields.Reference(selection="_selection_documents", string="Dossier", tracking=True)
    document_nom = fields.Char("Dossier lié", compute="_compute_document_nom")
    sans_reponse = fields.Boolean("Sans réponse", index=True, help="En attente depuis plus que le délai réglé (trois jours ouvrés par défaut).")
    attente_jours = fields.Integer("Attente (jours ouvrés)", compute="_compute_attente")
    masse = fields.Boolean("Envoi groupé")

    @api.model
    def _selection_documents(self):
        return [(m, n) for m, n in DOCUMENTS if m in self.env]

    @api.depends("expediteur")
    def _compute_expediteur_nom(self):
        for c in self:
            nom, adresse = (getaddresses([c.expediteur or ""]) or [("", "")])[0]
            c.expediteur_nom = nom or adresse or c.expediteur or ""

    def _compute_document_nom(self):
        for c in self:
            c.document_nom = c.document.display_name if c.document else ""

    def _compute_attente(self):
        maintenant = fields.Datetime.now()
        for c in self:
            c.attente_jours = _jours_ouvres(c.date_reception, maintenant) if c.etat == "a_traiter" else 0

    # ---------------------------------------------------------------- l'arrivée

    @api.model
    def _trouver_client(self, adresse, company):
        """Le contact de cette adresse ; sinon l'entreprise du même domaine (hors messageries grand public)."""
        adresse = (adresse or "").strip().lower()
        if "@" not in adresse:
            return self.env["res.partner"]
        Partner = self.env["res.partner"].sudo().with_context(active_test=True)
        societe = ["|", ("company_id", "=", False), ("company_id", "=", company.id)]
        p = Partner.search([("email_normalized", "=", adresse)] + societe, order="customer_rank desc, id", limit=1)
        if p:
            return p
        domaine = adresse.split("@", 1)[1]
        if domaine in WEBMAILS:
            return Partner
        return Partner.search([("email_normalized", "=like", f"%@{domaine}"), ("is_company", "=", True)] + societe, limit=1) \
            or Partner.search([("email_normalized", "=like", f"%@{domaine}")] + societe, limit=1).commercial_partner_id

    @api.model
    def _candidats(self, partner, texte):
        """Les documents possibles : d'abord ceux dont la référence est citée, puis les dossiers ouverts du client. [(record, cité)]"""
        res = []
        jetons = set(re.findall(r"\b[A-Z]{1,6}[/-]?\d{4}[/-]\d{2,6}\b|\b[A-Z]{1,3}\d{4,6}\b", texte or ""))
        if jetons:
            for modele in ("sale.order", "account.move", "purchase.order"):
                if modele in self.env:
                    res += [(r, True) for r in self.env[modele].sudo().search([("name", "in", list(jetons))], limit=3)]
        if partner:
            client = partner.commercial_partner_id
            if "sale.order" in self.env:
                res += [(r, False) for r in self.env["sale.order"].sudo().search([("partner_id", "child_of", client.id), ("state", "in", ("draft", "sent", "sale"))],
                                                                                order="date_order desc", limit=3)]
            res += [(r, False) for r in self.env["account.move"].sudo().search([("partner_id", "child_of", client.id), ("move_type", "=", "out_invoice"), ("state", "=", "posted"),
                                                                               ("payment_state", "in", ("not_paid", "partial"))], order="invoice_date_due", limit=3)]
            Task = self.env["project.task"].sudo()
            if "cultiveau_intervention" in Task._fields:
                res += [(r, False) for r in Task.search([("partner_id", "child_of", client.id), ("cultiveau_intervention", "=", True),
                                                         ("state", "not in", ("1_done", "1_canceled"))], order="id desc", limit=3)]
            if "cultiveau.chantier" in self.env:
                res += [(r, False) for r in self.env["cultiveau.chantier"].sudo().search([("partner_id", "child_of", client.id), ("etat", "not in", ("termine", "annule"))], limit=2)]
        vus, uniques = set(), []
        for r, cite in res:
            if (r._name, r.id) not in vus:
                vus.add((r._name, r.id))
                uniques.append((r, cite))
        return uniques

    @api.model
    def _resume_document(self, r):
        if not r:
            return ""
        euros = lambda m: f"{m:,.2f}".replace(",", " ").replace(".", ",") + " €"  # noqa: E731
        if r._name == "sale.order":
            return f"Devis {r.name} · {euros(r.amount_total)} TTC · {dict(r._fields['state'].selection).get(r.state, r.state)}"
        if r._name == "account.move":
            return f"Facture {r.name} · {euros(r.amount_total)} · reste dû {euros(r.amount_residual)}" + (f" · échéance {r.invoice_date_due:%d/%m/%Y}" if r.invoice_date_due else "")
        if r._name == "project.task":
            quand = getattr(r, "cultiveau_debut", False)
            return f"Intervention « {r.name} » · {r.stage_id.name or ''}" + (f" · prévue le {fields.Datetime.context_timestamp(r, quand):%d/%m à %H:%M}" if quand else "")
        return r.display_name

    @api.model
    def _cle_mistral(self):
        return (self.env["ir.config_parameter"].sudo().get_param("cultiveau.mistral_cle") or "").strip()

    def _analyser(self, texte, candidats):
        """Le tri par l'IA ; sans clé (ou en cas d'échec), des mots-clés."""
        cle = self._cle_mistral()
        liste = {f"{r._name},{r.id}": self._resume_document(r) for r, _c in candidats}
        if cle:
            try:
                demande = "Documents du client :\n" + ("\n".join(f"- {k} : {v}" for k, v in liste.items()) or "aucun") + f"\n\nCourriel :\n{texte[:4000]}"
                r = requests.post(f"{MISTRAL}/chat/completions", headers={"Authorization": f"Bearer {cle}"}, timeout=60, json={
                    "model": "mistral-small-latest", "temperature": 0.0, "response_format": {"type": "json_object"},
                    "messages": [{"role": "system", "content": SYSTEME_TRI}, {"role": "user", "content": demande}]})
                r.raise_for_status()
                lu = json.loads(r.json()["choices"][0]["message"]["content"])
                if lu.get("document") not in liste:
                    lu["document"] = None
                if lu.get("categorie") not in dict(CATEGORIES):
                    lu["categorie"] = "autre"
                return lu
            except Exception as e:  # noqa: BLE001
                _logger.info("Courriel : tri par l'IA impossible (%s)", e)
        bas = (texte or "").lower()
        categorie = next((c for c, mots in MOTS.items() if any(m in bas for m in mots)), "autre")
        return {"categorie": categorie, "urgent": categorie == "sav" and any(m in bas for m in ("urgent", "urgence", "arrêt", "arret", "plus d'eau")),
                "attend_reponse": True, "resume": "", "document": None}

    def _ranger(self, msg_dict):
        """Client, dossier, tri, note sur la fiche, signal sur la map."""
        self.ensure_one()
        sujet = msg_dict.get("subject") or ""
        texte = html2plaintext(msg_dict.get("body") or "")
        partner = self.partner_id or self._trouver_client((getaddresses([self.expediteur or ""]) or [("", "")])[0][1], self.company_id)
        candidats = self._candidats(partner, f"{sujet}\n{texte}")
        analyse = {"categorie": "publicite", "urgent": False, "attend_reponse": False, "resume": "", "document": None} if self.masse \
            else self._analyser(f"Objet : {sujet}\n\n{texte}", candidats)
        document = next((r for r, cite in candidats if cite), None)
        if not document and analyse.get("document"):
            modele, rid = analyse["document"].split(",")
            document = self.env[modele].sudo().browse(int(rid))
        if not document and candidats:
            prefere = {"facture": "account.move", "demande": "sale.order", "commande": "sale.order", "sav": "project.task"}.get(analyse["categorie"])
            document = next((r for r, _c in candidats if r._name == prefere), None)
        responsable = self.user_id
        if partner and partner.commercial_partner_id.user_id and not partner.commercial_partner_id.user_id.share \
                and self.company_id in partner.commercial_partner_id.user_id.company_ids:
            responsable = partner.commercial_partner_id.user_id
        vals = {"categorie": analyse["categorie"], "urgent": bool(analyse.get("urgent")), "resume": (analyse.get("resume") or "")[:250],
                "apercu": texte[:600], "user_id": responsable.id}
        if partner:
            vals["partner_id"] = partner.id
        if document:
            vals["document"] = f"{document._name},{document.id}"
        if not analyse.get("attend_reponse", True) or self.masse:
            vals["etat"] = "classe"
        self.write(vals)
        if partner:
            self.message_subscribe(partner_ids=partner.ids)
        if vals.get("etat") == "classe":
            return
        cible = document or (partner and partner.commercial_partner_id)
        if cible and (not self.boite_id or self.boite_id.ranger_sur_fiches) and hasattr(cible, "message_post"):
            lien = Markup('<a href="/odoo/cultiveau.courriel/%s">%s</a>') % (self.id, sujet or "(sans objet)")
            corps = Markup("Courriel reçu de %s : %s") % (self.expediteur_nom or self.expediteur, lien)
            if self.resume:
                corps += Markup("<br/><i>%s</i>") % self.resume
            cible.sudo().message_post(body=corps, subtype_xmlid="mail.mt_note", message_type="comment", author_id=self.env.ref("base.partner_root").id)
        self.env["cultiveau.evenement"].sudo().publier("courriel", self, f"Courriel de {self.expediteur_nom or self.expediteur}", sujet,
                                                       charge={"courriel_id": self.id, "client_id": partner.commercial_partner_id.id if partner else 0,
                                                               "urgent": self.urgent, "user_id": self.user_id.id}, company=self.company_id)

    @api.model
    def message_new(self, msg_dict, custom_values=None):
        boite = self.env["cultiveau.boite"].sudo().browse(self.env.context.get("cultiveau_boite_id") or 0).exists()
        company = boite.company_id or self.env.company
        vals = {"name": (msg_dict.get("subject") or "(sans objet)")[:250], "expediteur": msg_dict.get("email_from"), "company_id": company.id,
                "boite_id": boite.id or False, "user_id": boite.user_id.id or False, "masse": bool(self.env.context.get("cultiveau_masse")),
                "date_reception": msg_dict.get("date") or fields.Datetime.now()}
        courriel = super(Courriel, self.with_context(mail_create_nosubscribe=True, tracking_disable=True)).message_new(msg_dict, {**(custom_values or {}), **vals})
        try:
            with self.env.cr.savepoint():
                courriel.with_context(tracking_disable=True)._ranger(msg_dict)
        except Exception as e:  # noqa: BLE001 — le courriel est là, même mal rangé
            _logger.warning("Courriel %s : rangement impossible (%s)", courriel.id, e)
        return courriel

    def message_update(self, msg_dict, update_vals=None):
        """Le client répond : le courriel repasse « à traiter »."""
        res = super().message_update(msg_dict, update_vals=update_vals)
        for c in self:
            c.write({"etat": "a_traiter", "sans_reponse": False, "date_reception": fields.Datetime.now()})
            self.env["cultiveau.evenement"].sudo().publier("courriel", c, f"Réponse de {c.expediteur_nom or c.expediteur}", c.name,
                                                           charge={"courriel_id": c.id, "client_id": c.partner_id.commercial_partner_id.id, "user_id": c.user_id.id},
                                                           company=c.company_id)
        return res

    # ---------------------------------------------------------------- la réponse

    def _notify_get_reply_to(self, default=None):
        """Les réponses du client reviennent dans la boîte qui a reçu le courriel."""
        res = super()._notify_get_reply_to(default=default)
        for c in self:
            if c.boite_id:
                res[c.id] = formataddr((c.company_id.name, c.boite_id.adresse))
        return res

    def message_post(self, **kwargs):
        sortant = False
        if len(self) == 1 and kwargs.get("message_type") == "comment" and self.env.user._is_internal():
            commentaire = self.env.ref("mail.mt_comment")
            sous_type = kwargs.get("subtype_id") or (self.env.ref(kwargs["subtype_xmlid"]).id if kwargs.get("subtype_xmlid") else False)
            sortant = sous_type == commentaire.id
            if sortant and self.boite_id:
                kwargs["email_from"] = formataddr((self.env.user.name, self.boite_id.adresse))  # la réponse part de la boîte qui a reçu
        message = super().message_post(**kwargs)
        if sortant:
            self.sudo().write({"etat": "repondu", "date_reponse": fields.Datetime.now(), "sans_reponse": False})
            self.activity_ids.filtered(lambda a: a.activity_type_id == self.env.ref("mail.mail_activity_data_todo")).sudo().action_feedback(feedback="Répondu")
        return message

    def _assurer_contact(self):
        """Pour répondre, il faut un contact : créé depuis l'adresse de l'expéditeur s'il n'existe pas."""
        self.ensure_one()
        if not self.partner_id:
            nom, adresse = (getaddresses([self.expediteur or ""]) or [("", "")])[0]
            if not adresse:
                raise UserError("Adresse de l'expéditeur inconnue.")
            self.partner_id = self.env["res.partner"].sudo().create({"name": nom or adresse, "email": adresse, "company_id": self.company_id.id})
        self.message_subscribe(partner_ids=self.partner_id.ids)
        return self.partner_id

    def _action_composer(self, corps=""):
        self.ensure_one()
        partner = self._assurer_contact()
        sujet = self.name if (self.name or "").lower().startswith(("re:", "re :")) else f"Re: {self.name}"
        return {"type": "ir.actions.act_window", "res_model": "mail.compose.message", "view_mode": "form", "views": [[False, "form"]], "target": "new",
                "name": f"Répondre à {self.expediteur_nom or partner.name}",
                "context": {"default_model": self._name, "default_res_ids": self.ids, "default_composition_mode": "comment", "default_partner_ids": partner.ids,
                            "default_subject": sujet, "default_body": corps or "", "default_subtype_xmlid": "mail.mt_comment", "default_message_type": "comment"}}

    def action_repondre(self):
        return self._action_composer()

    def action_brouillon_mathis(self):
        return self._action_composer(self._brouillon())

    def action_classer(self):
        self.write({"etat": "classe", "sans_reponse": False})
        self.activity_ids.sudo().unlink()

    def action_rouvrir(self):
        self.write({"etat": "a_traiter"})

    def _historique(self, limite=6):
        lignes = []
        for m in self.message_ids.filtered(lambda m: m.message_type in ("email", "comment") and m.subtype_id != self.env.ref("mail.mt_note"))[:limite][::-1]:
            qui = m.author_id.name or m.email_from or "?"
            lignes.append(f"--- {qui}, le {fields.Datetime.context_timestamp(self, m.date):%d/%m/%Y %H:%M} ---\n{html2plaintext(m.body or '')[:2500]}")
        return "\n\n".join(lignes)

    def _brouillon(self, consignes=""):
        """La réponse préparée par Mathis, en HTML, à relire avant l'envoi."""
        self.ensure_one()
        cle = self._cle_mistral()
        if not cle:
            raise UserError("Mathis a besoin de la clé Mistral (Réglages → Cultiveau → Fiches techniques et IA).")
        Mathis = self.env["cultiveau.mathis"]
        societe = self.company_id.name
        systeme = SYSTEME_REPONSE.format(prenom=Mathis.prenom(), societe=societe, signataire=self.env.user.name)
        client = self.partner_id.commercial_partner_id
        contexte = [f"Client : {client.name}" + (f" ({client.city})" if client.city else "") if client else "Expéditeur inconnu de l'ERP",
                    f"Catégorie : {dict(CATEGORIES).get(self.categorie)}"]
        if self.document:
            contexte.append(f"Dossier : {self._resume_document(self.document.sudo())}")
        autres = [self._resume_document(r) for r, _c in self._candidats(self.partner_id, "") if not self.document or (r._name, r.id) != (self.document._name, self.document.id)][:3]
        if autres:
            contexte.append("Autres dossiers du client : " + " ; ".join(autres))
        if consignes:
            contexte.append(f"Consignes de {self.env.user.name} : {consignes}")
        demande = "\n".join(contexte) + f"\n\nObjet : {self.name}\n\nÉchanges (du plus ancien au plus récent) :\n{self._historique()}"
        try:
            r = requests.post(f"{MISTRAL}/chat/completions", headers={"Authorization": f"Bearer {cle}"}, timeout=90, json={
                "model": Mathis._modele(), "temperature": 0.3, "messages": [{"role": "system", "content": systeme}, {"role": "user", "content": demande}]})
            r.raise_for_status()
            texte = (r.json()["choices"][0]["message"]["content"] or "").strip()
        except Exception as e:  # noqa: BLE001
            raise UserError(f"Mathis n'a pas pu préparer la réponse : {str(e)[:200]}") from e
        return Markup("").join(Markup("<p>%s</p>") % Markup("<br/>").join(escape(l) for l in bloc.split("\n")) for bloc in re.split(r"\n\s*\n", texte) if bloc.strip())

    # ---------------------------------------------------------------- les appels de la map et de Mathis

    @api.model
    def preparer_reponse(self, courriel_id, consignes=""):
        return self.browse(int(courriel_id)).exists()._action_composer(self.browse(int(courriel_id))._brouillon(consignes))

    @api.model
    def classer(self, courriel_id):
        c = self.browse(int(courriel_id)).exists()
        c.action_classer()
        return {"message": "Courriel classé."}

    @api.model
    def ligne(self, c):
        return {"id": c.id, "objet": c.name, "de": c.expediteur_nom or c.expediteur or "", "client": c.partner_id.commercial_partner_id.name or "",
                "client_id": c.partner_id.commercial_partner_id.id, "dossier": c.document_nom or "", "categorie": dict(CATEGORIES).get(c.categorie, ""),
                "resume": c.resume or "", "urgent": c.urgent, "etat": c.etat, "sans_reponse": c.sans_reponse, "attente_jours": c.attente_jours,
                "recu": fields.Datetime.to_string(c.date_reception), "responsable": c.user_id.name or ""}

    @api.model
    def a_traiter(self, user=None, client_id=None, limite=10):
        domaine = [("etat", "=", "a_traiter"), ("company_id", "=", self.env.company.id)]
        if user:
            domaine.append(("user_id", "=", user.id))
        if client_id:
            domaine.append(("partner_id", "child_of", int(client_id)))
        return self.search(domaine, order="sans_reponse desc, urgent desc, date_reception", limit=limite)

    # ---------------------------------------------------------------- sans réponse

    @api.model
    def _cron_sans_reponse(self):
        jours = int(self.env["ir.config_parameter"].sudo().get_param("cultiveau.courriel_jours_sans_reponse") or 3)
        maintenant = fields.Datetime.now()
        todo = self.env.ref("mail.mail_activity_data_todo")
        for c in self.sudo().search([("etat", "=", "a_traiter"), ("sans_reponse", "=", False), ("date_reception", "!=", False)]):
            if _jours_ouvres(c.date_reception, maintenant) < jours:
                continue
            c.sans_reponse = True
            responsable = c.user_id or c.boite_id.user_id
            if responsable:
                c.activity_schedule(activity_type_id=todo.id, user_id=responsable.id, summary=f"Sans réponse depuis {jours} jours",
                                    note=f"{c.expediteur_nom or c.expediteur} attend une réponse : {c.name}")
            self.env["cultiveau.evenement"].publier("courriel_relance", c, f"Sans réponse depuis {jours} jours", f"{c.expediteur_nom or c.expediteur} · {c.name}",
                                                    charge={"courriel_id": c.id, "client_id": c.partner_id.commercial_partner_id.id, "user_id": responsable.id},
                                                    company=c.company_id)
