"""Le CRM de l'assistant téléphonique recopié dans l'ERP : clients, notes, tâches, équipements.

Chaque élément arrive avec sa référence dans l'assistant (« CLI-12 », « NOTE-40 »…) ; la table de correspondance
retient la fiche ERP qui lui répond. Renvoyer un élément ne crée jamais de doublon : on met à jour, ou on ne fait rien.
"""
from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.exceptions import UserError

# type de contact de l'assistant -> type de contact de l'ERP
GENRES = {"fournisseur": "fournisseur", "partenaire": "partenaire", "administration": "collectivite", "autre": "autre"}
# famille de matériel de l'assistant -> catégorie d'équipement de l'ERP
FAMILLES = {"pivot": ("pivot", "Pivot"), "rampe_frontale": ("pivot", "Rampe frontale"), "enrouleur": ("enrouleur", "Enrouleur / canon"),
            "couverture_integrale": ("asperseur", "Aspersion en couverture"), "goutte_a_goutte": ("gaine", "Goutte-à-goutte"),
            "micro_aspersion": ("asperseur", "Micro-aspersion"), "station_pompage": ("pompe", "Station de pompage"), "filtration": ("filtration", "Filtration"),
            "automatisme": ("programmateur", "Automatisme / programmateur"), "reseau_canalisations": ("canalisation_enterree", "Réseau / canalisations"),
            "antigel": ("asperseur", "Antigel (aspersion)"), "autre": ("autre", "Matériel")}
INSTALLATION_ASSISTANT = "Matériel connu de l'assistant"


class Lien(models.Model):
    _name = "cultiveau.assistant.lien"
    _description = "Correspondance entre un élément de l'assistant téléphonique et sa fiche dans l'ERP"

    company_id = fields.Many2one("res.company", "Adhérent", required=True, index=True, ondelete="cascade")
    reference = fields.Char("Référence dans l'assistant", required=True, index=True)
    res_model = fields.Char("Modèle", required=True)
    res_id = fields.Integer("Fiche", required=True)
    cree_par_assistant = fields.Boolean("Créé par l'assistant")

    _sql_constraints = [("reference_unique", "unique(company_id, reference)", "Cet élément de l'assistant est déjà relié à une fiche.")]


class Synchro(models.AbstractModel):
    _name = "cultiveau.assistant.synchro"
    _description = "Synchronisation du CRM de l'assistant téléphonique"

    @api.model
    def synchroniser(self, societe, elements):
        """Traite une liste d'éléments ; chacun réussit ou échoue seul. Renvoie un résultat par élément."""
        resultats = []
        for e in elements or []:
            reference = str((e or {}).get("reference") or "").strip()
            try:
                if not reference:
                    raise UserError("référence manquante")
                fabrique = {"client": self._client, "note": self._note, "tache": self._tache, "equipement": self._equipement}.get(e.get("type"))
                if not fabrique:
                    raise UserError(f"type inconnu : {e.get('type')!r} (client, note, tache, equipement)")
                with self.env.cr.savepoint():
                    resultats.append({"reference": reference, "ok": True, **fabrique(societe, reference, e)})
            except (UserError, ValueError) as err:
                resultats.append({"reference": reference, "ok": False, "erreur": str(err.args[0] if err.args else err)})
        return resultats

    # ---------------------------------------------------------------- la table de correspondance

    def _lien(self, societe, reference):
        return self.env["cultiveau.assistant.lien"].sudo().search([("company_id", "=", societe.id), ("reference", "=", reference)], limit=1)

    def _fiche(self, societe, reference, modele):
        lien = self._lien(societe, reference)
        return (self.env[modele].browse(lien.res_id).exists() if lien and lien.res_model == modele else self.env[modele]), lien

    def _relier(self, societe, reference, rec, lien=None, cree=False):
        if lien:
            if (lien.res_model, lien.res_id) != (rec._name, rec.id):
                lien.write({"res_model": rec._name, "res_id": rec.id, "cree_par_assistant": cree})
            return lien
        return self.env["cultiveau.assistant.lien"].sudo().create({"company_id": societe.id, "reference": reference, "res_model": rec._name,
                                                                     "res_id": rec.id, "cree_par_assistant": cree})

    def _client_de(self, societe, e):
        reference = e.get("client")
        if not reference:
            return self.env["res.partner"]
        partner, _lien = self._fiche(societe, str(reference), "res.partner")
        if not partner:
            raise UserError(f"client {reference} inconnu de l'ERP : l'envoyer d'abord")
        return partner

    # ---------------------------------------------------------------- les éléments

    def _client(self, societe, reference, e):
        Partner = self.env["res.partner"].with_company(societe).with_context(mail_create_nolog=True)
        partner, lien = self._fiche(societe, reference, "res.partner")
        telephone, telephone2 = e.get("telephone"), e.get("telephone2")
        if not partner:
            for numero in (telephone, telephone2):
                partner = partner or (Partner.cultiveau_par_telephone(numero, societe) if numero else Partner.browse())
        if not partner and e.get("email"):
            partner = Partner.search([("email", "=ilike", e["email"]), ("company_id", "in", (societe.id, False))], limit=1)
        valeurs = {k: v for k, v in {
            "name": (e.get("nom") or "").strip(), "exploitation": e.get("exploitation"), "mobile": telephone, "phone": telephone2,
            "email": e.get("email"), "street": e.get("adresse"), "city": e.get("commune"), "zip": e.get("code_postal"),
        }.items() if v}
        cree = not partner
        if cree:
            if not valeurs.get("name"):
                raise UserError("client : le nom est requis")
            partner = Partner.create({**valeurs, "company_id": societe.id, "customer_rank": 1,
                                      "cultiveau_type": GENRES.get(e.get("genre"), "agriculteur"),
                                      "comment": e.get("notes") or "Venu de l'assistant téléphonique."})
        else:
            # une fiche que l'assistant a créée suit l'assistant ; une fiche de l'ERP n'est que complétée
            suit = bool(lien and lien.cree_par_assistant)
            maj = {k: v for k, v in valeurs.items() if suit or not partner[k]}
            if not partner.cultiveau_type and e.get("genre"):
                maj["cultiveau_type"] = GENRES.get(e["genre"], "agriculteur")
            if maj:
                partner.write(maj)
        self._relier(societe, reference, partner, lien, cree=cree or bool(lien and lien.cree_par_assistant))
        return {"id": partner.id, "cree": cree, "url": f"/app/contacts/{partner.id}"}

    def _note(self, societe, reference, e):
        message, lien = self._fiche(societe, reference, "mail.message")
        if message:
            return {"id": message.id, "deja": True}
        partner = self._client_de(societe, e)
        if not partner:
            raise UserError("note : le client est requis")
        texte = (e.get("texte") or "").strip()
        if not texte:
            raise UserError("note : texte vide")
        signature = " · ".join(x for x in (e.get("auteur"), {"dictee": "dictée", "appel": "appel", "manuel": "note"}.get(e.get("source"), ""), e.get("date")) if x)
        corps = Markup("<p>%s</p>") % escape(texte).replace("\n", Markup("<br/>"))
        if signature:
            corps += Markup("<p><i>— %s, dans l'assistant</i></p>") % signature
        message = partner.message_post(body=corps, subtype_xmlid="mail.mt_note", message_type="comment")
        self._relier(societe, reference, message, lien, cree=True)
        return {"id": message.id, "cree": True}

    def _responsable(self, societe, email, partner):
        Users = self.env["res.users"].sudo()
        if email:
            u = Users.search([("share", "=", False), "|", ("login", "=ilike", email), ("email", "=ilike", email)], limit=1)
            if u:
                return u
        if partner and partner.user_id:
            return partner.user_id
        return Users.search([("share", "=", False), ("company_ids", "in", societe.id), ("id", "!=", self.env.ref("base.user_root").id)], order="id", limit=1) \
            or self.env.ref("base.user_admin")

    def _tache(self, societe, reference, e):
        activite, lien = self._fiche(societe, reference, "mail.activity")
        etat = e.get("etat") or "a_faire"
        if lien and not activite:
            return {"deja": True, "termine": True}  # déjà faite ou supprimée dans l'ERP
        if activite and etat in ("fait", "annule"):
            if etat == "fait":
                activite.action_feedback(feedback="Fait dans l'assistant téléphonique.")
            else:
                activite.unlink()
            return {"termine": True}
        if etat in ("fait", "annule"):
            return {"ignore": True}
        partner = self._client_de(societe, e)
        support = partner or societe.partner_id
        titre = (e.get("titre") or "").strip()[:200] or "À faire"
        echeance = fields.Date.to_date(e.get("echeance")) if e.get("echeance") else fields.Date.context_today(self)
        note = e.get("detail") or ""
        if e.get("heure"):
            note = f"À {e['heure']}. {note}".strip()
        valeurs = {"summary": titre, "note": Markup("<p>%s</p>") % note if note else False, "date_deadline": echeance,
                   "user_id": self._responsable(societe, e.get("pour_email"), partner).id}
        if activite:
            activite.write(valeurs)
            return {"id": activite.id, "maj": True}
        type_xmlid = "mail.mail_activity_data_meeting" if e.get("heure") else "mail.mail_activity_data_todo"
        activite = support.activity_schedule(type_xmlid, **valeurs)
        self._relier(societe, reference, activite, lien, cree=True)
        return {"id": activite.id, "cree": True}

    def _equipement(self, societe, reference, e):
        equipement, lien = self._fiche(societe, reference, "cultiveau.equipement")
        partner = self._client_de(societe, e)
        if not partner and not equipement:
            raise UserError("équipement : le client est requis")
        categorie, libelle = FAMILLES.get(e.get("famille"), FAMILLES["autre"])
        annee = next((int(m) for m in "".join(c if c.isdigit() else " " for c in str(e.get("pose_le") or "")).split() if len(m) == 4), 0)
        valeurs = {k: v for k, v in {
            "name": " ".join(x for x in (libelle, e.get("marque"), e.get("modele")) if x) + (f" — {e['site']}" if e.get("site") else ""),
            "categorie": categorie, "marque": e.get("marque"), "modele": e.get("modele"), "numero_serie": e.get("numero_serie"),
            "annee_pose": annee or None, "notes": (e.get("notes") or "")[:250] or None,
        }.items() if v}
        valeurs["actif"] = e.get("actif", True) is not False
        if equipement:
            equipement.write(valeurs)
            return {"id": equipement.id, "maj": True}
        Installation = self.env["cultiveau.installation"].with_company(societe)
        installation = Installation.search([("partner_id", "=", partner.id), ("name", "=", INSTALLATION_ASSISTANT)], limit=1) or Installation.create({
            "name": INSTALLATION_ASSISTANT, "partner_id": partner.id, "company_id": societe.id, "type_systeme": "mixte"})
        equipement = self.env["cultiveau.equipement"].create({**valeurs, "installation_id": installation.id})
        self._relier(societe, reference, equipement, lien, cree=True)
        return {"id": equipement.id, "cree": True}
