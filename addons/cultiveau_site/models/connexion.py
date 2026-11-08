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
from odoo.tools import config

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
    articles = fields.Boolean("Articles (Clients & Articles)", default=True)
    curseur_articles = fields.Datetime("Articles lus jusqu'au", readonly=True)
    inventaires = fields.Boolean("Inventaires validés (Mon Inventaire) → stock", default=True,
                                 help="Un inventaire validé dans Mon Inventaire sur cultiveau.fr fixe les quantités en stock des articles comptés.")
    curseur_inventaires = fields.Datetime("Inventaires lus jusqu'au", readonly=True)
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
            r = requests.get(url, params={k: v for k, v in (params or {}).items() if v not in (None, "", False)}, headers={"X-API-Key": cle, "Accept": "application/json"}, timeout=30)
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
            rep = self._appeler(chemin, {**{k: v for k, v in (params or {}).items() if v not in (None, "", False)}, "limit": taille, "offset": decalage})
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
        self.write({"curseur_clients": False, "curseur_bons": False, "curseur_articles": False, "curseur_inventaires": False})

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

    def _acquis(self):
        """Une étape terminée est acquise tout de suite : une coupure (déploiement, redémarrage) ne perd pas tout, et personne n'attend
        derrière une transaction de vingt minutes. Rien dans les tests, qui tournent dans une seule transaction."""
        if not config["test_enable"]:
            self.env.cr.commit()

    def _synchroniser(self):
        self.ensure_one()
        # un seul passage à la fois par entreprise : le robot de l'heure et un lancement à la main ne se marchent pas dessus
        self.env.cr.execute("SELECT id FROM cultiveau_site_connexion WHERE id = %s FOR UPDATE SKIP LOCKED", (self.id,))
        if not self.env.cr.fetchone():
            _logger.info("Synchronisation cultiveau.fr de %s : déjà en cours, passage ignoré.", self.company_id.name)
            return
        if not self.sudo().cle:
            self.write({"resultat": "Pas de clé d'API du site : rien à synchroniser (la clé arrive quand quelqu'un de l'entreprise entre dans l'ERP depuis cultiveau.fr).", "en_erreur": False})
            return
        debut = fields.Datetime.now()
        bilan = []
        self._synchro_fiche_entreprise()
        try:
            # pas de savepoint autour des étapes : elles acquièrent elles-mêmes leur travail page par page (un commit détruirait le savepoint)
            for actif, etape in ((self.clients, self._synchro_clients), (self.interventions, self._synchro_interventions), (self.chantiers, self._synchro_chantiers),
                                 (self.bons, self._synchro_bons), (self.articles, self._synchro_articles), (self.inventaires, self._synchro_inventaires)):
                if not actif:
                    continue
                bilan.append(etape())
                self.write({"resultat": " · ".join(bilan) + " …", "en_erreur": False})
                self._acquis()
            self.write({"derniere_synchro": debut, "resultat": " · ".join(bilan) or "Rien à synchroniser.", "en_erreur": False})
            self._acquis()
        except UserError as e:
            self._reprendre_apres_erreur()
            self.write({"derniere_synchro": debut, "resultat": " · ".join(bilan + [str(e.args[0] if e.args else e)]), "en_erreur": True})
            self._acquis()
        except Exception as e:  # noqa: BLE001 — une erreur inattendue est notée, la tâche continue avec l'adhérent suivant
            _logger.exception("Synchronisation cultiveau.fr de %s", self.company_id.name)
            self._reprendre_apres_erreur()
            self.write({"derniere_synchro": debut, "resultat": " · ".join(bilan + [f"Erreur : {e}"]), "en_erreur": True})
            self._acquis()

    def _synchro_fiche_entreprise(self):
        """Le logo de l'entreprise suit celui de son espace cultiveau.fr, même posé après la première entrée dans l'ERP : la fiche est relue à
        chaque passage (GET /entreprise). Un site plus ancien sans cette route, ou injoignable, ne bloque pas la synchronisation."""
        try:
            fiche = (self._appeler("entreprise") or {}).get("entreprise") or {}
        except UserError as e:
            _logger.info("Fiche entreprise de %s non relue : %s", self.company_id.name, e)
            return False
        except Exception as e:  # noqa: BLE001
            _logger.info("Fiche entreprise de %s non relue : %s", self.company_id.name, e)
            return False
        if fiche.get("logo_url"):
            self.env["res.users"]._cultiveau_logo_depuis_site(self.company_id, fiche["logo_url"])
            self._acquis()
        return True

    def _reprendre_apres_erreur(self):
        """Après une erreur de base de données, la transaction est inutilisable : on revient au dernier acquis pour pouvoir noter l'erreur."""
        if not config["test_enable"]:
            self.env.cr.rollback()

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

    # ---- articles de « Clients & Articles »

    def _synchro_articles(self):
        """Les articles de l'adhérent sur cultiveau.fr deviennent des articles de sa société dans l'ERP (référence, désignation, prix, unité,
        famille, marque), reconnus par leur référence du site. Par pages de 500, chaque page acquise : une base de 40 000 articles passe sans
        transaction géante. Un site qui ne les expose pas encore (clé ancienne, version du site) ne bloque rien."""
        env = self._env()
        Produit = env["product.template"].with_context(active_test=False)
        debut = fields.Datetime.now()
        depuis = self.curseur_articles and (self.curseur_articles - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%S")
        params = {"updatedSince": depuis} if depuis else {}
        taille, decalage, lus, crees, maj = 500, 0, 0, 0, 0
        caches = {"categ": {}, "uom": {}}
        while True:
            try:
                rep = self._appeler("articles", {**params, "limit": taille, "offset": decalage})
            except UserError as e:
                texte = str(e.args[0] if e.args else e)
                if "404" in texte:
                    return "articles : pas encore exposés par le site"
                if ("403" in texte or "droit" in texte) and decalage == 0:
                    # clé remise avant le droit « articles » : on en redemande une, et on réessaie une fois
                    if hasattr(self, "_cultiveau_redemander_cle") and self._cultiveau_redemander_cle():
                        continue
                    return "articles : la clé du site n'a pas encore le droit « articles » (repassez par cultiveau.fr)"
                raise
            page = rep.get("articles") or []
            if not page:
                break
            c, m = self._articles_appliquer(page, Produit, env, caches)
            crees, maj, lus = crees + c, maj + m, lus + len(page)
            self.write({"resultat": f"articles : {lus} lus, {crees} créé(s), {maj} à jour …"})
            self._acquis()
            if not config["test_enable"]:
                env.invalidate_all()
            total = rep.get("total")
            decalage += len(page)
            if len(page) < taille or (total is not None and decalage >= total):
                break
        self.curseur_articles = debut
        return f"{lus} article(s) lus, {crees} créé(s), {maj} à jour"

    def _articles_appliquer(self, page, Produit, env, caches):
        """Une page d'articles : les existants retrouvés en deux requêtes, puis créés ou mis à jour."""
        refs = [self._ref(a.get("id")) for a in page]
        codes = [(a.get("reference") or "").strip() for a in page if (a.get("reference") or "").strip()]
        par_ref = {p.cultiveau_site_ref: p for p in Produit.search([("cultiveau_site_ref", "in", refs)])}
        par_code = {}
        if codes:
            for p in Produit.search([("default_code", "in", codes), ("company_id", "=", self.company_id.id), ("cultiveau_site_ref", "=", False)]):
                par_code.setdefault(p.default_code, p)
        crees = maj = 0
        a_creer = []
        for a in page:
            ref = self._ref(a.get("id"))
            reference = (a.get("reference") or "").strip()
            produit = par_ref.get(ref) or (par_code.get(reference) if reference else None)
            valeurs = {"name": (a.get("designation") or reference or f"Article {a.get('id')}")[:255], "default_code": reference[:64] or False,
                       "list_price": float(a.get("prixUnitaireHT") or 0.0), "barcode": (a.get("ean") or "").strip()[:64] or False,
                       "sale_ok": True, "purchase_ok": True, "type": "consu", "is_storable": True, "company_id": self.company_id.id,
                       "cultiveau_site_ref": ref, "active": bool(a.get("isActive", 1))}
            if "cultiveau_source" in Produit._fields:
                valeurs["cultiveau_source"] = "site"
            if a.get("categorie"):
                valeurs["categ_id"] = self._categorie_article(a["categorie"], env, caches["categ"]).id
            if a.get("marque"):
                valeurs["description_sale"] = f"Marque : {a['marque']}"
            unite = self._unite_article(a.get("unite"), env, caches["uom"])
            if unite:
                valeurs.update({"uom_id": unite.id, "uom_po_id": unite.id})
            if produit:
                if produit.uom_id and "uom_id" in valeurs:
                    valeurs.pop("uom_id"), valeurs.pop("uom_po_id")
                if not valeurs["barcode"]:
                    valeurs.pop("barcode")
                produit.write(valeurs)
                maj += 1
            elif valeurs["active"]:
                a_creer.append(valeurs)
        if a_creer:
            # un code-barres en double dans la base du site ferait tout rater : on le garde seulement s'il est unique
            vus = set()
            for v in a_creer:
                if v.get("barcode") in vus or (v.get("barcode") and Produit.search_count([("barcode", "=", v["barcode"])])):
                    v["barcode"] = False
                elif v.get("barcode"):
                    vus.add(v["barcode"])
            Produit.create(a_creer)
            crees += len(a_creer)
        return crees, maj

    def _categorie_article(self, nom, env, cache=None):
        cache = cache if cache is not None else {}
        cle = nom.strip()[:120].lower()
        if cle in cache:
            return cache[cle]
        Categ = env["product.category"]
        racine = cache.get("__racine__") or Categ.search([("name", "=", "Articles cultiveau.fr"), ("parent_id", "=", False)], limit=1) or Categ.create({"name": "Articles cultiveau.fr"})
        cache["__racine__"] = racine
        categ = Categ.search([("name", "=ilike", nom.strip()[:120]), ("parent_id", "=", racine.id)], limit=1) or Categ.create({"name": nom.strip()[:120], "parent_id": racine.id})
        cache[cle] = categ
        return categ

    def _unite_article(self, libelle, env, cache=None):
        if not libelle:
            return None
        cache = cache if cache is not None else {}
        cle = libelle.strip().lower()
        if cle in cache:
            return cache[cle]
        cache[cle] = self._unite_article_chercher(cle, libelle, env)
        return cache[cle]

    def _unite_article_chercher(self, cle, libelle, env):
        correspondances = {"m": "uom.product_uom_meter", "ml": "uom.product_uom_meter", "mètre": "uom.product_uom_meter", "metre": "uom.product_uom_meter",
                           "kg": "uom.product_uom_kgm", "l": "uom.product_uom_litre", "litre": "uom.product_uom_litre", "h": "uom.product_uom_hour", "heure": "uom.product_uom_hour",
                           "u": "uom.product_uom_unit", "unité": "uom.product_uom_unit", "unite": "uom.product_uom_unit", "pce": "uom.product_uom_unit", "pièce": "uom.product_uom_unit"}
        xmlid = correspondances.get(cle)
        if xmlid:
            return env.ref(xmlid, raise_if_not_found=False)
        return env["uom.uom"].search([("name", "=ilike", libelle.strip())], limit=1) or None

    # ---- bons d'intervention

    def _synchro_inventaires(self):
        """Un inventaire validé dans Mon Inventaire (cultiveau.fr) devient le stock de l'ERP : pour chaque article compté, la quantité en stock
        de l'entrepôt de la société est fixée à la quantité comptée (les lignes d'un même article s'additionnent : plusieurs zones). Ce qui
        n'a pas été compté ne bouge pas. Une référence inconnue de l'ERP est signalée, jamais inventée."""
        env = self._env()
        debut = fields.Datetime.now()
        depuis = self.curseur_inventaires and (self.curseur_inventaires - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%S")
        try:
            lots = self._pages("inventaires", "inventaires", {"updatedSince": depuis} if depuis else {}, taille=20)
        except UserError as e:
            texte = str(e.args[0] if e.args else e)
            if "404" in texte:
                return "inventaires : pas encore exposés par le site"
            if "403" in texte or "droit" in texte:
                return "inventaires : la clé du site n'a pas le droit « articles » (repassez par cultiveau.fr)"
            raise
        if not lots:
            self.curseur_inventaires = debut
            return "0 inventaire validé"
        emplacement = self.company_id.sudo().cultiveau_entrepot().lot_stock_id
        Produit = env["product.product"].with_context(active_test=False)
        Quant = env["stock.quant"].with_context(inventory_mode=True)
        appliques, lignes_ok, inconnues = 0, 0, []
        for inv in lots:
            quantites = {}
            for l in inv.get("lignes") or []:
                produit = self._produit_du_site(Produit, l)
                if not produit:
                    if l.get("reference") and l["reference"] not in inconnues:
                        inconnues.append(l["reference"])
                    continue
                try:
                    q = float(str(l.get("quantite") or "0").replace(",", "."))
                except ValueError:
                    continue
                quantites[produit] = quantites.get(produit, 0.0) + q
            for produit, q in quantites.items():
                if not produit.is_storable:
                    produit.product_tmpl_id.sudo().write({"is_storable": True})
                quant = Quant.create({"product_id": produit.id, "location_id": emplacement.id, "inventory_quantity": q})
                quant.action_apply_inventory()
                lignes_ok += 1
            appliques += 1
            self._acquis()
        self.curseur_inventaires = debut
        texte = f"{appliques} inventaire(s) validé(s) appliqué(s) au stock ({lignes_ok} article(s))"
        if inconnues:
            texte += f" ; {len(inconnues)} référence(s) inconnue(s) de l'ERP : {', '.join(inconnues[:5])}" + (" …" if len(inconnues) > 5 else "")
        return texte

    def _produit_du_site(self, Produit, ligne):
        """L'article de l'ERP qui répond à une ligne comptée : par son identifiant du site, sinon sa référence, sinon son code-barres."""
        if ligne.get("articleId"):
            p = Produit.search([("product_tmpl_id.cultiveau_site_ref", "=", self._ref(ligne["articleId"]))], limit=1)
            if p:
                return p
        ref = (ligne.get("reference") or "").strip()
        if ref:
            p = Produit.search([("default_code", "=", ref), ("company_id", "in", (self.company_id.id, False))], limit=1)
            if p:
                return p
        ean = (ligne.get("ean") or "").strip()
        if ean:
            return Produit.search([("barcode", "=", ean)], limit=1)
        return Produit.browse()

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
