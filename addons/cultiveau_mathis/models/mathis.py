"""Mathis dans l'ERP : il lit les données avec les droits de la personne connectée, propose des actions, les fait une fois confirmées.

Le cerveau est le modèle de langue du réseau (clé Mistral des réglages). Les outils sont ceux de l'API de l'ERP (resume, lister,
lire, chercher, créer…) plus ceux de la map (qui est où, le stock d'un article, ouvrir un écran, un brouillon de courriel,
badger). Une action qui écrit n'est jamais faite sans un clic de confirmation.
"""
import base64
import json
import logging

import requests

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.addons.cultiveau_api.controllers.api_v1 import _appeler, _outils
from odoo.addons.cultiveau_vue3d.models.secteur import SECTEUR

_logger = logging.getLogger(__name__)
MISTRAL = "https://api.mistral.ai/v1"
ECRITURE = {"creer_client", "creer_intervention", "creer_opportunite", "ajouter_note", "badger", "brouillon_courriel"}
TITRES = {"creer_client": "Créer le client", "creer_intervention": "Créer l'intervention", "creer_opportunite": "Créer l'opportunité", "ajouter_note": "Ajouter la note",
          "badger": "Enregistrer le pointage", "brouillon_courriel": "Préparer le courriel"}
TOURS_MAX = 5

SYSTEME = """Tu es {prenom}, l'assistant du réseau Cultiveau (installateurs d'irrigation agricole), ici dans l'ERP de {societe}.
Tu parles à {utilisateur} ({role}). Nous sommes le {date}, il est {heure}.
Tu réponds en français, court et concret, comme un collègue efficace : une à quatre phrases, des listes quand il y a plusieurs éléments.
Tu t'appuies TOUJOURS sur les outils pour répondre sur les données (clients, interventions, chantiers, installations, devis, factures,
articles et stock, équipe) : ne devine jamais un chiffre, un nom ou un état. Si l'outil ne trouve rien, dis-le.
Quand tu cites une fiche, écris-la ainsi pour qu'elle devienne cliquable : [[ressource:id|Libellé]] (ressource parmi clients,
interventions, chantiers, installations, devis, factures, articles, opportunites).
Pour agir (créer un client, une intervention, une opportunité, une note, un courriel, un pointage), appelle l'outil : l'ERP
demandera confirmation à la personne avant de faire quoi que ce soit ; ne prétends jamais qu'une action est faite avant son résultat.
Si une demande dépasse tes outils, dis ce que tu sais faire. Ne mentionne jamais l'éditeur du logiciel : c'est « l'ERP Cultiveau ».
{contexte}"""


class Conversation(models.Model):
    _name = "cultiveau.mathis.conversation"
    _description = "Conversation avec Mathis"
    _order = "write_date desc"

    name = fields.Char("Sujet", default="Conversation")
    user_id = fields.Many2one("res.users", "Personne", required=True, default=lambda self: self.env.user, index=True)
    company_id = fields.Many2one("res.company", "Adhérent", required=True, default=lambda self: self.env.company, index=True)
    messages = fields.Json("Messages", default=list)
    attente = fields.Json("Propositions en attente", default=list)
    nb_messages = fields.Integer(compute="_compute_nb")

    def _compute_nb(self):
        for c in self:
            c.nb_messages = len([m for m in (c.messages or []) if m.get("role") in ("user", "assistant") and m.get("content")])


class Mathis(models.AbstractModel):
    _name = "cultiveau.mathis"
    _description = "Mathis (assistant)"

    # ---------------------------------------------------------------- les réglages

    @api.model
    def prenom(self):
        return (self.env["ir.config_parameter"].sudo().get_param("cultiveau.mathis_prenom") or "Mathis").strip() or "Mathis"

    @api.model
    def _cle(self):
        return (self.env["ir.config_parameter"].sudo().get_param("cultiveau.mistral_cle") or "").strip()

    @api.model
    def _modele(self):
        return (self.env["ir.config_parameter"].sudo().get_param("cultiveau.mathis_modele") or "mistral-small-latest").strip()

    @api.model
    def pret(self):
        return bool(self._cle())

    @api.model
    def transcrire(self, audio_b64, mimetype="audio/webm"):
        """La dictée : l'enregistrement du micro → le texte (Voxtral de Mistral, comme l'assistant téléphonique)."""
        cle = self._cle()
        if not cle:
            raise UserError("La dictée a besoin de la clé Mistral (Réglages → Cultiveau → Fiches techniques et IA).")
        audio = base64.b64decode(audio_b64 or "")
        if not audio:
            raise UserError("Aucun son enregistré.")
        if len(audio) > 10 * 1024 * 1024:
            raise UserError("Dictée trop longue : une minute au plus.")
        extension = {"audio/ogg": "ogg", "audio/mp4": "m4a", "audio/mpeg": "mp3", "audio/wav": "wav"}.get((mimetype or "").split(";")[0], "webm")
        try:
            r = requests.post(f"{MISTRAL}/audio/transcriptions", headers={"Authorization": f"Bearer {cle}"}, timeout=120,
                              data={"model": "voxtral-mini-latest", "language": "fr"}, files={"file": (f"dictee.{extension}", audio, (mimetype or "audio/webm").split(";")[0])})
            r.raise_for_status()
            texte = (r.json().get("text") or "").strip()
        except Exception as e:  # noqa: BLE001
            raise UserError(f"La dictée n'a pas pu être transcrite : {str(e)[:200]}") from e
        if not texte:
            raise UserError("Je n'ai rien entendu : parlez un peu plus près du micro.")
        return {"texte": texte}

    # ---------------------------------------------------------------- les outils

    def _ecritures(self):
        """Les outils qui écrivent : jamais exécutés sans un clic de confirmation."""
        return set(ECRITURE)

    def _titres(self):
        return dict(TITRES)

    def _outils(self):
        """Les outils de l'API (avec les droits de la personne) et ceux de la map, au format du modèle."""
        moteur = self.env["cultiveau.api.moteur"]
        outils = []
        for o in _outils(moteur, None):
            outils.append({"type": "function", "function": {"name": o["name"], "description": o["description"], "parameters": o["inputSchema"]}})
        portes = sorted({p["cle"] for z in self.env["cultiveau.map"]._portes().values() for p in z})
        outils += [
            {"type": "function", "function": {"name": "equipe", "description": "Qui est où en ce moment : chaque personne de l'équipe, son rôle, son statut (au poste, en pause, en intervention, sur chantier, absent), son intervention ou chantier en cours.",
                                              "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "stock_article", "description": "Le stock et le prix d'un article (par nom ou référence).",
                                              "parameters": {"type": "object", "properties": {"texte": {"type": "string"}}, "required": ["texte"]}}},
            {"type": "function", "function": {"name": "ouvrir_ecran", "description": "Ouvre un écran de l'ERP pour la personne. Écrans : " + ", ".join(portes) + ".",
                                              "parameters": {"type": "object", "properties": {"ecran": {"type": "string", "enum": portes}}, "required": ["ecran"]}}},
            {"type": "function", "function": {"name": "brouillon_courriel", "description": "Prépare un courriel à un client (brouillon que la personne relit et envoie).",
                                              "parameters": {"type": "object", "properties": {"client_id": {"type": "integer"}, "objet": {"type": "string"}, "texte": {"type": "string"}},
                                                             "required": ["client_id", "objet", "texte"]}}},
            {"type": "function", "function": {"name": "badger", "description": "Enregistre un pointage pour la personne connectée : arrivee, pause_debut, pause_fin, depart_intervention, retour_intervention, depart.",
                                              "parameters": {"type": "object", "properties": {"genre": {"type": "string", "enum": ["arrivee", "pause_debut", "pause_fin", "depart_intervention", "retour_intervention", "depart"]}},
                                                             "required": ["genre"]}}},
        ]
        return outils

    def _executer(self, nom, args):
        """Exécute un outil (lecture tout de suite, écriture après confirmation). Renvoie (résultat, action client éventuelle)."""
        Map = self.env["cultiveau.map"]
        if nom == "equipe":
            company = self.env.company
            local = fields.Datetime.context_timestamp(self.with_context(tz=company.partner_id.tz or "Europe/Paris"), fields.Datetime.now())
            return [{"nom": p["nom"], "role": p["role_nom"], "statut": p["statut_nom"], "intervention": (p["tache"] or {}).get("nom"), "chantier": (p["chantier"] or {}).get("nom"),
                     "arrivee": p["arrivee"]} for p in Map._personnes(company, local)], None
        if nom == "stock_article":
            res = self.env["cultiveau.api.moteur"].lister("articles", {"q": args.get("texte", ""), "limite": 8}, None)
            return res.get("resultats", res), None
        if nom == "ouvrir_ecran":
            action = self.env["cultiveau.scene"].action(args.get("ecran"))
            return {"ouvert": args.get("ecran")}, {"type": "action", "action": action}
        if nom == "brouillon_courriel":
            partner = self.env["res.partner"].browse(int(args.get("client_id") or 0)).exists()
            if not partner:
                raise UserError("Client introuvable.")
            action = {"type": "ir.actions.act_window", "res_model": "mail.compose.message", "view_mode": "form", "target": "new",
                      "context": {"default_model": "res.partner", "default_res_ids": [partner.id], "default_partner_ids": [partner.id], "default_subject": args.get("objet", ""),
                                  "default_body": "<p>" + (args.get("texte", "") or "").replace("\n", "<br/>") + "</p>", "default_composition_mode": "comment"}}
            return {"brouillon": f"courriel à {partner.name} prêt à relire"}, {"type": "action", "action": action}
        if nom == "badger":
            self.env["cultiveau.pointage"].badger(args.get("genre"), user=self.env.user, source="erp", note="par Mathis")
            return {"pointage": args.get("genre")}, None
        moteur = self.env["cultiveau.api.moteur"]
        resultat = _appeler(moteur, None, nom, args)
        action = None
        if nom in ("creer_client", "creer_intervention", "creer_opportunite") and isinstance(resultat, dict) and resultat.get("id"):
            modele = {"creer_client": "res.partner", "creer_intervention": "project.task", "creer_opportunite": "crm.lead"}[nom]
            action = {"type": "lien", "modele": modele, "id": resultat["id"], "libelle": resultat.get("nom") or resultat.get("titre") or "Ouvrir"}
        return resultat, action

    # ---------------------------------------------------------------- le modèle

    def _appel_modele(self, messages, outils):
        cle = self._cle()
        if not cle:
            raise UserError("La clé Mistral manque : Réglages → Cultiveau → Fiches techniques et IA.")
        r = requests.post(f"{MISTRAL}/chat/completions", headers={"Authorization": f"Bearer {cle}"}, timeout=90, json={
            "model": self._modele(), "temperature": 0.2, "messages": messages, "tools": outils, "tool_choice": "auto"})
        if r.status_code >= 400:
            raise UserError(f"{self.prenom()} ne répond pas (HTTP {r.status_code}) : {r.text[:200]}")
        return r.json()["choices"][0]["message"]

    def _systeme(self):
        company = self.env.company
        user = self.env.user
        local = fields.Datetime.context_timestamp(self.with_context(tz=company.partner_id.tz or "Europe/Paris"), fields.Datetime.now())
        Map = self.env["cultiveau.map"]
        roles = {r["cle"]: r["nom"] for r in SECTEUR["roles"]}
        try:
            resume = self.env["cultiveau.api.moteur"].resume(None)
            ligne = next((a for a in resume.get("adherents", []) if a["adherent"].get("id") == company.id), None)
        except Exception:  # noqa: BLE001
            ligne = None
        contexte = ""
        if ligne:
            contexte = (f"Repères du moment pour {company.name} : {ligne.get('interventions_ouvertes', 0)} interventions ouvertes dont {ligne.get('urgences', 0)} urgentes, "
                        f"{ligne.get('devis_en_cours', 0)} devis en cours ({ligne.get('devis_montant', 0):,.0f} €), {ligne.get('factures_a_encaisser', 0)} factures à encaisser "
                        f"({ligne.get('reste_a_encaisser', 0):,.0f} €), {ligne.get('chantiers_actifs', 0)} chantiers actifs.").replace(",", " ")
        return SYSTEME.format(prenom=self.prenom(), societe=company.name, utilisateur=user.name, role=roles.get(Map._role(user), Map._role(user)),
                              date=Map._date_fr(local), heure=local.strftime("%H:%M"), contexte=contexte)

    @api.model
    def conversation(self, conversation_id=None):
        Conv = self.env["cultiveau.mathis.conversation"]
        conv = Conv.browse(conversation_id).exists() if conversation_id else Conv.browse()
        if conv and (conv.user_id != self.env.user or conv.company_id != self.env.company):
            conv = Conv.browse()
        if not conv:
            conv = Conv.search([("user_id", "=", self.env.user.id), ("company_id", "=", self.env.company.id)], order="write_date desc", limit=1)
        if not conv or len(conv.messages or []) > 60:
            conv = Conv.create({})
        return conv

    def _affichage(self, conv):
        """Ce que le panneau montre : les messages de la personne et de Mathis, et les propositions en attente."""
        msgs = [{"role": m["role"], "texte": m.get("content") or "", "action": m.get("action")} for m in (conv.messages or [])
                if m.get("role") in ("user", "assistant") and (m.get("content") or m.get("action"))]
        return {"conversation_id": conv.id, "messages": msgs, "propositions": conv.attente or [], "prenom": self.prenom(), "pret": self.pret()}

    @api.model
    def ouvrir(self, conversation_id=None):
        return {**self._affichage(self.conversation(conversation_id)), "suggestions": self.suggestions()}

    @api.model
    def nouvelle(self):
        conv = self.env["cultiveau.mathis.conversation"].create({})
        return {**self._affichage(conv), "suggestions": self.suggestions()}

    @api.model
    def suggestions(self):
        role = self.env["cultiveau.map"]._role(self.env.user)
        base = ["Qui est en intervention en ce moment ?", "Quels devis faut-il relancer ?", "Qu'est-ce qui attend aujourd'hui ?"]
        par_role = {"technicien": ["Ma tournée du jour", "Il reste combien de tubes PE 63 ?", "Badge mon arrivée"],
                    "gerant": ["Combien reste-t-il à encaisser ?", "Les chantiers en cours", "Ouvre le tableau de bord"],
                    "comptable": ["Les factures à encaisser", "Ouvre les écritures à lettrer", "Combien de devis en cours ?"],
                    "commercial": ["Les études en cours", "Crée une opportunité pour un client", "Prépare un courriel de relance"],
                    "comptoir": ["Il reste combien d'asperseurs ?", "Trouve le client Durand", "Crée un dépannage"]}
        return base + par_role.get(role, [])

    @api.model
    def repondre(self, conversation_id, texte):
        """Un message de la personne : Mathis répond, en appelant ses outils ; une écriture s'arrête en proposition à confirmer."""
        texte = (texte or "").strip()
        if not texte:
            raise UserError("Dites-moi quelque chose.")
        conv = self.conversation(conversation_id)
        messages = list(conv.messages or [])
        messages.append({"role": "user", "content": texte})
        attente = []
        outils = self._outils()
        for _tour in range(TOURS_MAX):
            reponse = self._appel_modele([{"role": "system", "content": self._systeme()}] + self._fenetre(messages), outils)
            appels = reponse.get("tool_calls") or []
            assistant = {"role": "assistant", "content": reponse.get("content") or ""}
            if appels:
                assistant["tool_calls"] = [{"id": a["id"], "type": "function", "function": {"name": a["function"]["name"], "arguments": a["function"]["arguments"]}} for a in appels]
            messages.append(assistant)
            if not appels:
                break
            arret = False
            for a in appels:
                nom = a["function"]["name"]
                try:
                    args = json.loads(a["function"]["arguments"] or "{}") if isinstance(a["function"]["arguments"], str) else (a["function"]["arguments"] or {})
                except ValueError:
                    args = {}
                if nom in self._ecritures():
                    attente.append({"id": a["id"], "nom": nom, "titre": self._titres().get(nom, nom), "arguments": args, "resume": self._resumer(nom, args)})
                    messages.append({"role": "tool", "name": nom, "tool_call_id": a["id"], "content": json.dumps({"statut": "en attente de la confirmation de la personne"}, ensure_ascii=False)})
                    arret = True
                    continue
                try:
                    with self.env.cr.savepoint():
                        resultat, action = self._executer(nom, args)
                    contenu = json.dumps(resultat, ensure_ascii=False, default=str)[:6000]
                except Exception as e:  # noqa: BLE001 — l'outil a échoué : le modèle le dit
                    contenu = json.dumps({"erreur": str(e.args[0] if e.args else e)}, ensure_ascii=False)
                    action = None
                messages.append({"role": "tool", "name": nom, "tool_call_id": a["id"], "content": contenu})
                if action and action.get("type") == "action":
                    messages.append({"role": "assistant", "content": "", "action": action})
            if arret:
                if not assistant["content"]:
                    assistant["content"] = "Je peux le faire : confirmez ci-dessous."
                break
        conv.write({"messages": messages, "attente": attente, "name": conv.name if conv.name != "Conversation" else texte[:60]})
        return self._affichage(conv)

    @api.model
    def confirmer(self, conversation_id, proposition_id, oui=True):
        """La personne confirme (ou refuse) une proposition : l'action est faite, Mathis conclut."""
        conv = self.conversation(conversation_id)
        attente = list(conv.attente or [])
        prop = next((p for p in attente if p["id"] == proposition_id), None)
        if not prop:
            raise UserError("Cette proposition n'est plus en attente.")
        messages = list(conv.messages or [])
        action = None
        if oui:
            try:
                with self.env.cr.savepoint():
                    resultat, action = self._executer(prop["nom"], prop["arguments"])
                contenu = json.dumps({"fait": True, "resultat": resultat}, ensure_ascii=False, default=str)[:4000]
            except Exception as e:  # noqa: BLE001
                contenu = json.dumps({"fait": False, "erreur": str(e.args[0] if e.args else e)}, ensure_ascii=False)
        else:
            contenu = json.dumps({"fait": False, "refuse": "la personne a refusé"}, ensure_ascii=False)
        # le résultat remplace le « en attente » du même appel d'outil
        for m in messages:
            if m.get("role") == "tool" and m.get("tool_call_id") == proposition_id:
                m["content"] = contenu
        attente = [p for p in attente if p["id"] != proposition_id]
        if not attente:
            try:
                reponse = self._appel_modele([{"role": "system", "content": self._systeme()}] + self._fenetre(messages), self._outils())
                messages.append({"role": "assistant", "content": reponse.get("content") or ("C'est fait." if oui else "D'accord, je ne le fais pas.")})
            except Exception as e:  # noqa: BLE001
                messages.append({"role": "assistant", "content": ("C'est fait." if oui else "D'accord, je ne le fais pas.") + f" ({e})"})
        if action:
            messages.append({"role": "assistant", "content": "", "action": action})
        conv.write({"messages": messages, "attente": attente})
        return self._affichage(conv)

    def _fenetre(self, messages, n=30):
        """Les derniers messages, sans couper un appel d'outil de ses résultats."""
        fen = messages[-n:]
        while fen and fen[0].get("role") == "tool":
            fen = fen[1:]
        return [{k: v for k, v in m.items() if k != "action"} for m in fen if m.get("content") or m.get("tool_calls")]

    def _resumer(self, nom, args):
        if nom == "creer_intervention":
            return f"{args.get('titre', '')} — {args.get('urgence', 'semaine')}" + (f" · client n° {args['client_id']}" if args.get("client_id") else (f" · {args['client'].get('nom', '')}" if args.get("client") else ""))
        if nom == "creer_client":
            return ", ".join(str(v) for k, v in args.items() if k in ("nom", "telephone", "commune") and v)
        if nom == "creer_opportunite":
            return f"{args.get('titre', '')}" + (f" · {args.get('montant_espere')} €" if args.get("montant_espere") else "")
        if nom == "ajouter_note":
            return (args.get("texte") or "")[:120]
        if nom == "brouillon_courriel":
            return f"{args.get('objet', '')}"
        if nom == "badger":
            return args.get("genre", "")
        return json.dumps(args, ensure_ascii=False)[:120]


class Settings(models.TransientModel):
    _inherit = "res.config.settings"

    cultiveau_mathis_prenom = fields.Char("Prénom de l'assistant", config_parameter="cultiveau.mathis_prenom", default="Mathis")
    cultiveau_mathis_modele = fields.Char("Modèle", config_parameter="cultiveau.mathis_modele", default="mistral-small-latest")
