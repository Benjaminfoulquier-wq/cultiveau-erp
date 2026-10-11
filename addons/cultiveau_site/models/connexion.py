"""La connexion d'un adhérent à l'API externe de cultiveau.fr, et la synchronisation (lecture seule côté site).

API du site : ``<url>/api/external``, en-tête ``X-API-Key`` (une clé par entreprise adhérente, créée dans
l'administration du site, page « Clés API », avec les droits clients:read, interventions:read, chantiers:read,
bons:read). 600 requêtes par heure et par clé. Les routes de lecture renvoient les lignes de la base du site.
"""
import logging
from datetime import timedelta

import requests

from odoo import api, fields, models
from odoo.exceptions import UserError

from odoo.addons.cultiveau_base.models.res_partner import normaliser_telephone

_logger = logging.getLogger(__name__)

NATURES = {"depannage": "depannage", "maintenance": "entretien", "installation": "modification", "mise_en_service": "mise_en_service",
           "diagnostic": "diagnostic", "autre": "autre"}
URGENCES = {"urgente": "immediate", "haute": "journee", "normale": "semaine"}
ETAPES = {"brouillon": "À planifier", "planifiee": "Planifiée", "en_cours": "En cours", "terminee": "Terminée", "facturee": "Terminée"}
ETATS_TACHE = {"terminee": "1_done", "facturee": "1_done", "annulee": "1_canceled"}
ETATS_CHANTIER = {"brouillon": "brouillon", "planifie": "planifie", "en_cours": "en_cours", "en_pause": "en_cours", "termine": "termine", "annule": "annule"}
JETONS = ("validationToken", "ratingToken", "shortCode", "signatureClient", "signatureTechnicien")


def _nombre(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _date(v):
    if not v:
        return False
    texte = str(v).replace("T", " ").replace("Z", "")[:19]
    try:
        return fields.Datetime.to_datetime(texte) if len(texte) > 10 else fields.Date.to_date(texte)
    except ValueError:
        return False


class SiteConnexion(models.Model):
    _name = "cultiveau.site.connexion"
    _description = "Connexion à l'espace adhérent de cultiveau.fr"
    _order = "company_id"

    company_id = fields.Many2one("res.company", "Adhérent", required=True, index=True)
    url = fields.Char("Adresse du site", required=True, default=lambda self: self.env["ir.config_parameter"].sudo().get_param("cultiveau.url_site") or "https://cultiveau.fr")
    cle = fields.Char("Clé d'API du site", groups="cultiveau_base.group_equipe", copy=False,
                      help="Créée sur cultiveau.fr, administration → Clés API, pour l'entreprise de cet adhérent, avec les droits "
                           "clients:read, interventions:read, chantiers:read et bons:read. Attention : en créer une nouvelle révoque "
                           "l'ancienne clé de cet adhérent sur le site.")
    active = fields.Boolean(default=True)
    clients = fields.Boolean("Clients", default=True)
    interventions = fields.Boolean("Interventions", default=True)
    chantiers = fields.Boolean("Chantiers", default=True)
    bons = fields.Boolean("Bons d'intervention", default=True)
    curseur_clients = fields.Datetime("Clients lus jusqu'au", readonly=True)
    curseur_bons = fields.Datetime("Bons lus jusqu'au", readonly=True)
    derniere_synchro = fields.Datetime("Dernière synchronisation", readonly=True)
    resultat = fields.Text("Résultat", readonly=True)
    en_erreur = fields.Boolean("En erreur", readonly=True)
    nb_bons = fields.Integer("Bons", compute="_compute_nb_bons")

    _sql_constraints = [("societe_unique", "unique(company_id)", "Une seule connexion au site par adhérent.")]

    def _compute_nb_bons(self):
        for c in self:
            c.nb_bons = self.env["cultiveau.site.bon"].search_count([("connexion_id", "=", c.id)])

    # ---------------------------------------------------------------- l'appel au site

    def _appeler(self, chemin, params=None):
        """Un GET sur l'API externe du site ; renvoie le JSON. Isolé pour les tests."""
        self.ensure_one()
        cle = self.sudo().cle
        if not cle:
            raise UserError(f"{self.company_id.name} : la clé d'API du site n'est pas renseignée.")
        url = f"{self.url.rstrip('/')}/api/external/{chemin.lstrip('/')}"
        try:
            r = requests.get(url, params={k: v for k, v in (params or {}).items() if v not in (None, "")}, headers={"X-API-Key": cle, "Accept": "application/json"}, timeout=30)
        except requests.RequestException as e:
            raise UserError(f"Site injoignable : {e}") from e
        if r.status_code == 401:
            raise UserError("Le site refuse la clé (absente, invalide ou révoquée).")
        if r.status_code == 403:
            raise UserError(f"La clé n'a pas le droit nécessaire ({chemin}) : {r.text[:200]}")
        if r.status_code == 429:
            raise UserError("Limite de 600 requêtes par heure atteinte sur le site : la suite à la prochaine synchronisation.")
        if r.status_code >= 400:
            raise UserError(f"Le site répond {r.status_code} sur {chemin} : {r.text[:200]}")
        try:
            return r.json()
        except ValueError as e:
            raise UserError(f"Réponse illisible du site sur {chemin}.") from e

    def _pages(self, chemin, cle_liste, params=None, taille=200):
        """Toutes les pages d'une liste (limit / offset)."""
        decalage, resultats = 0, []
        while True:
            rep = self._appeler(chemin, {**(params or {}), "limit": taille, "offset": decalage})
            lot = rep.get(cle_liste) or []
            resultats += lot
            total = rep.get("total")
            decalage += len(lot)
            if not lot or len(lot) < taille or (total is not None and decalage >= total):
                return resultats

    # ---------------------------------------------------------------- les boutons

    def action_tester(self):
        self.ensure_one()
        rep = self._appeler("clients", {"limit": 1})
        n = rep.get("total", len(rep.get("clients") or []))
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"title": "Connexion au site réussie", "message": f"{self.company_id.name} : {n} client(s) sur cultiveau.fr.", "type": "success"}}

    def action_synchroniser(self):
        for c in self:
            c._synchroniser()
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"title": "Synchronisation", "message": "\n".join(f"{c.company_id.name} : {c.resultat}" for c in self),
                           "type": "danger" if any(self.mapped("en_erreur")) else "success", "sticky": any(self.mapped("en_erreur"))}}

    def action_reinitialiser(self):
        """Tout relire au prochain passage (les curseurs « lu jusqu'au » sont effacés)."""
        self.write({"curseur_clients": False, "curseur_bons": False})

    def action_voir_bons(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "name": "Bons du site", "res_model": "cultiveau.site.bon", "view_mode": "list,form",
                "domain": [("connexion_id", "=", self.id)]}

    @api.model
    def _cron_synchroniser(self):
        for c in self.search([("active", "=", True)]):
            if c.sudo().cle:
                c._synchroniser()
                self.env.cr.commit()  # chaque adhérent pour soi : une erreur chez l'un ne défait pas les autres

    # ---------------------------------------------------------------- la synchronisation

    def _synchroniser(self):
        self.ensure_one()
        debut = fields.Datetime.now()
        bilan = []
        try:
            with self.env.cr.savepoint():
                if self.clients:
                    bilan.append(self._synchro_clients())
                if self.interventions:
                    bilan.append(self._synchro_interventions())
                if self.chantiers:
                    bilan.append(self._synchro_chantiers())
                if self.bons:
                    bilan.append(self._synchro_bons())
            self.write({"derniere_synchro": debut, "resultat": " · ".join(bilan) or "Rien à synchroniser.", "en_erreur": False})
        except UserError as e:
            self.write({"derniere_synchro": debut, "resultat": str(e.args[0] if e.args else e), "en_erreur": True})
        except Exception as e:  # noqa: BLE001 — une erreur inattendue est notée, la tâche continue avec l'adhérent suivant
            _logger.exception("Synchronisation cultiveau.fr de %s", self.company_id.name)
            self.write({"derniere_synchro": debut, "resultat": f"Erreur : {e}", "en_erreur": True})

    def _ref(self, ident):
        return f"{self.id}:{ident}"

    def _env(self):
        return self.sudo().with_company(self.company_id).with_context(mail_create_nolog=True, mail_notrack=True, tracking_disable=True,
                                                                        mail_auto_subscribe_no_notify=True).env

    # ---- clients

    def _client(self, nom, telephone=None, email=None, adresse=None, code_postal=None, ville=None, entreprise=None, ident=None, notes=None):
        """Le contact de l'adhérent : retrouvé par référence du site, téléphone, e-mail ou nom ; créé sinon."""
        env = self._env()
        Partner = env["res.partner"]
        societe = self.company_id
        p = Partner.browse()
        if ident:
            p = Partner.search([("cultiveau_site_ref", "=", self._ref(ident))], limit=1)
        if not p and telephone and normaliser_telephone(telephone):
            p = Partner.cultiveau_par_telephone(telephone, societe)
        if not p and email:
            p = Partner.search([("email", "=ilike", email.strip()), ("company_id", "in", (societe.id, False))], limit=1)
        if not p and nom:
            p = Partner.search([("name", "=ilike", nom.strip()), ("company_id", "in", (societe.id, False)), ("parent_id", "=", False)], limit=1)
        valeurs = {k: v for k, v in {"name": nom, "mobile": telephone, "email": email, "street": adresse, "zip": code_postal, "city": ville,
                                     "exploitation": entreprise}.items() if v}
        if p:
            p.write({k: v for k, v in valeurs.items() if not p[k]} | ({"cultiveau_site_ref": self._ref(ident)} if ident and not p.cultiveau_site_ref else {}))
            return p, False
        if not nom:
            return p, False
        p = Partner.create({**valeurs, "company_id": societe.id, "cultiveau_type": "agriculteur", "comment": notes or False,
                            "cultiveau_site_ref": self._ref(ident) if ident else False})
        return p, True

    def _synchro_clients(self):
        debut = fields.Datetime.now()
        depuis = self.curseur_clients and (self.curseur_clients - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%S")
        lus = self._pages("clients", "clients", {"updatedSince": depuis}, taille=500)
        crees = 0
        for c in lus:
            nom = " ".join(x for x in (c.get("prenom"), c.get("nom")) if x).strip() or c.get("entreprise")
            _p, cree = self._client(nom, c.get("telephonePortable") or c.get("telephone"), c.get("email"), c.get("adresse"), c.get("codePostal"),
                                    c.get("ville"), c.get("entreprise") if c.get("entreprise") != nom else None, c.get("id"), c.get("notes"))
            crees += cree
        self.curseur_clients = debut
        return f"{len(lus)} client(s) lus, {crees} créé(s)"

    # ---- interventions

    def _synchro_interventions(self):
        env = self._env()
        Task = env["project.task"]
        projet = env["project.project"].cultiveau_projet_interventions(self.company_id)
        etapes = {e.name: e for e in projet.type_ids}
        lus = self._pages("interventions", "interventions", taille=200)
        crees = maj = 0
        for i in lus:
            i = {k: v for k, v in i.items() if k not in JETONS}
            partner, _ = self._client(i.get("clientName"), i.get("clientPhone"), i.get("clientEmail"), i.get("clientAddress"))
            equipement = " ".join(x for x in (i.get("equipmentType"), i.get("equipmentBrand"), i.get("equipmentModel")) if x)
            textes = [("Symptômes", i.get("symptoms")), ("Premier diagnostic", i.get("initialDiagnosis")), ("Travaux réalisés", i.get("workPerformed")),
                      ("Pièces utilisées", i.get("partsUsed")), ("Recommandations", i.get("recommendations")),
                      ("Équipement", " ".join(x for x in (equipement, i.get("equipmentSerial") and f"(n° {i['equipmentSerial']})") if x)),
                      ("Technicien", i.get("technicianName"))]
            description = "".join(f"<p><b>{t}</b> : {v}</p>" for t, v in textes if v)
            statut = i.get("status") or "brouillon"
            valeurs = {
                "name": " — ".join(x for x in (i.get("reference"), (i.get("symptoms") or equipement or "Intervention")[:120]) if x),
                "partner_id": partner.id or False, "cultiveau_nature": NATURES.get(i.get("interventionType"), "autre"),
                "cultiveau_urgence": URGENCES.get(i.get("priority"), "semaine"), "cultiveau_symptome": (i.get("symptoms") or "")[:200] or False,
                "description": description, "date_deadline": _date(i.get("scheduledDate")) or False,
                "state": ETATS_TACHE.get(statut, "01_in_progress"),
            }
            if ETAPES.get(statut) in etapes:
                valeurs["stage_id"] = etapes[ETAPES[statut]].id
            ref = self._ref(i.get("id"))
            t = Task.search([("cultiveau_site_ref", "=", ref)], limit=1)
            if t:
                t.write(valeurs)
                maj += 1
            else:
                Task.create({**valeurs, "project_id": projet.id, "company_id": self.company_id.id, "cultiveau_site_ref": ref, "cultiveau_origine": "autre"})
                crees += 1
        return f"{len(lus)} intervention(s) : {crees} nouvelle(s), {maj} à jour"

    # ---- chantiers

    def _synchro_chantiers(self):
        env = self._env()
        Chantier, Inst = env["cultiveau.chantier"], env["cultiveau.installation"]
        lus = self._appeler("chantiers").get("chantiers") or []
        crees = maj = 0
        for c in lus:
            partner, _ = self._client(c.get("clientName"), c.get("clientPhone"), c.get("clientEmail"), c.get("clientAddress"), ident=None)
            if not partner:
                continue
            ref = self._ref(c.get("id"))
            chantier = Chantier.search([("cultiveau_site_ref", "=", ref)], limit=1)
            installation = chantier.installation_id
            if not installation:
                installation = Inst.search([("cultiveau_site_ref", "=", ref)], limit=1) or Inst.create({
                    "name": c.get("nom") or f"Chantier {c.get('reference') or c.get('id')}", "partner_id": partner.id, "type_systeme": "mixte",
                    "etat": "realisation" if c.get("statut") in ("en_cours", "en_pause") else "projet", "company_id": self.company_id.id,
                    "cultiveau_site_ref": ref})
            acces = " — ".join(x for x in (c.get("adresseChantier"), c.get("description")) if x)
            valeurs = {
                "titre": " — ".join(x for x in (c.get("reference"), c.get("nom")) if x) or "Chantier du site",
                "etat": ETATS_CHANTIER.get(c.get("statut"), "brouillon"),
                "date_debut": _date(c.get("dateDebutPrevue")) and fields.Date.to_date(_date(c.get("dateDebutPrevue"))) or False,
                "date_fin": _date(c.get("dateFinPrevue")) and fields.Date.to_date(_date(c.get("dateFinPrevue"))) or False,
                "date_debut_reel": _date(c.get("dateDebutReelle")) and fields.Date.to_date(_date(c.get("dateDebutReelle"))) or False,
                "date_fin_reel": _date(c.get("dateFinReelle")) and fields.Date.to_date(_date(c.get("dateFinReelle"))) or False,
                "acces": acces[:250] or False, "notes": c.get("notes") or False,
                "machines": " ".join(x for x in (c.get("typeEquipement"), c.get("marqueEquipement"), c.get("modeleEquipement")) if x) or False,
            }
            if chantier:
                chantier.write(valeurs)
                maj += 1
            else:
                Chantier.create({**valeurs, "installation_id": installation.id, "company_id": self.company_id.id, "cultiveau_site_ref": ref, "chef_id": False})
                crees += 1
        return f"{len(lus)} chantier(s) : {crees} nouveau(x), {maj} à jour"

    # ---- bons d'intervention

    def _synchro_bons(self):
        env = self._env()
        Bon, Task, Chantier, Produit = env["cultiveau.site.bon"], env["project.task"], env["cultiveau.chantier"], env["product.product"]
        debut = fields.Datetime.now()
        depuis = self.curseur_bons and (self.curseur_bons - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%S")
        lus = self._pages("bons-intervention", "bons", {"updatedSince": depuis}, taille=200)
        crees = maj = 0
        for resume in lus:
            b = (self._appeler(f"bons-intervention/{resume['id']}").get("bon") or resume)
            b = {k: v for k, v in b.items() if k not in JETONS}
            partner, _ = self._client(b.get("clientNom"), b.get("clientTelephone"), b.get("clientEmail"), b.get("clientAdresse"), b.get("clientCodePostal"),
                                      b.get("clientVille"), ident=b.get("clientId"))
            lignes = []
            for n, a in enumerate(b.get("articles") or []):
                produit = Produit.search([("default_code", "=", a.get("reference"))], limit=1) if a.get("reference") else Produit.browse()
                lignes.append((0, 0, {"sequence": n, "genre": "article", "reference": a.get("reference"), "designation": a.get("designation"), "product_id": produit.id or False,
                                      "quantite": _nombre(a.get("quantite")), "unite": a.get("unite"), "prix_unitaire_ht": _nombre(a.get("prixUnitaireHT")),
                                      "remise": _nombre(a.get("remise")), "tva": _nombre(a.get("tvaRate")), "total_ht": _nombre(a.get("totalHT"))}))
            for n, m in enumerate(b.get("mainOeuvre") or []):
                lignes.append((0, 0, {"sequence": 100 + n, "genre": "mo", "designation": m.get("description"), "quantite": _nombre(m.get("quantite")),
                                      "unite": m.get("uniteFacturation"), "prix_unitaire_ht": _nombre(m.get("tauxHoraire")), "total_ht": _nombre(m.get("totalHT")),
                                      "duree_minutes": int(_nombre(m.get("dureeMinutes")))}))
            for n, h in enumerate(b.get("heuresMachines") or []):
                lignes.append((0, 0, {"sequence": 200 + n, "genre": "machine", "designation": " ".join(x for x in (h.get("machine"), h.get("immatriculation")) if x),
                                      "duree_minutes": int(_nombre(h.get("dureeMinutes")))}))
            valeurs = {
                "numero": b.get("numero"), "date": _date(b.get("dateIntervention")) and fields.Date.to_date(_date(b.get("dateIntervention"))) or False,
                "statut": b.get("statut"), "type_intervention": b.get("typeIntervention"), "partner_id": partner.id or False, "client_nom": b.get("clientNom"),
                "task_id": Task.search([("cultiveau_site_ref", "=", self._ref(b.get("ficheInterventionId")))], limit=1).id if b.get("ficheInterventionId") else False,
                "chantier_id": Chantier.search([("cultiveau_site_ref", "=", self._ref(b.get("chantierId")))], limit=1).id if b.get("chantierId") else False,
                "technicien": b.get("technicienNom"),
                "equipement": " ".join(x for x in (b.get("equipmentType"), b.get("equipmentBrand"), b.get("equipmentModel")) if x) or False,
                "description": b.get("description"), "observations": b.get("observations"), "recommandations": b.get("recommandations"),
                "duree_minutes": int(_nombre(b.get("dureeInterventionMinutes"))),
                "total_articles_ht": _nombre(b.get("totalArticlesHT")), "total_mo_ht": _nombre(b.get("totalMOHT")), "total_deplacement_ht": _nombre(b.get("totalDeplacementHT")),
                "total_ht": _nombre(b.get("totalHT")), "total_tva": _nombre(b.get("totalTVA")), "total_ttc": _nombre(b.get("totalTTC")),
                "signe_client": bool(b.get("signeParLeClient")), "signe_technicien": bool(b.get("signeParLeTechnicien")), "exporte": bool(b.get("exporte")),
                "modifie_sur_site": _date(b.get("updatedAt")) or False,
            }
            ref = self._ref(b.get("id"))
            bon = Bon.search([("connexion_id", "=", self.id), ("ref", "=", ref)], limit=1)
            if bon:
                bon.ligne_ids.unlink()
                bon.write({**valeurs, "ligne_ids": lignes})
                maj += 1
            else:
                Bon.create({**valeurs, "connexion_id": self.id, "ref": ref, "ligne_ids": lignes})
                crees += 1
        self.curseur_bons = debut
        return f"{len(lus)} bon(s) : {crees} nouveau(x), {maj} à jour"
