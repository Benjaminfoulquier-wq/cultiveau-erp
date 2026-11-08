"""Entrer dans l'ERP depuis cultiveau.fr, sans deuxième mot de passe.

cultiveau.fr signe un laissez-passer (deux minutes, usage unique) qui dit qui entre, son entreprise et son rôle dans l'équipe.
L'ERP retrouve ou crée l'entreprise (res.company, reliée par l'identifiant cultiveau.fr) et l'utilisateur (login = son e-mail,
rôle Cultiveau), puis ouvre sa session par une vérification d'identité propre (type « cultiveau_site ») au lieu d'un mot de passe.
À la première entrée d'une entreprise, l'ERP demande aussi à cultiveau.fr sa clé d'accès aux données (clients, interventions,
chantiers, bons), de serveur à serveur : la synchronisation horaire démarre d'elle-même."""
import base64
import logging
import secrets
import time

import requests

from odoo import api, fields, models
from odoo.exceptions import AccessDenied

_logger = logging.getLogger(__name__)
ROLES_SITE = {"gerant", "administratif", "technicien", "magasinier", "commercial"}


class Company(models.Model):
    _inherit = "res.company"

    cultiveau_site_id = fields.Integer("Entreprise sur cultiveau.fr (id)", index=True, copy=False)
    cultiveau_site_logo_url = fields.Char("Logo repris de cultiveau.fr (adresse)", copy=False, readonly=True)
    cultiveau_erp_ouvert = fields.Boolean("Accès à l'ERP ouvert", default=False,
                                          help="Tout le monde n'a pas l'ERP : cochez pour que cette entreprise et son équipe puissent entrer depuis cultiveau.fr. Les comptes déjà créés entrent toujours.")

    @api.model
    def cultiveau_ouvrir_erp_existants(self):
        """À la mise à jour : les entreprises qui ont déjà des utilisateurs gardent l'accès."""
        self.env.cr.execute("SELECT DISTINCT company_id FROM res_users WHERE active AND share = false")
        ids = [r[0] for r in self.env.cr.fetchall()]
        if ids:
            self.sudo().browse(ids).filtered(lambda c: not c.cultiveau_erp_ouvert).write({"cultiveau_erp_ouvert": True})
        return True

    @api.model
    def cultiveau_erp_eligible(self, charge):
        """cultiveau.fr demande si cette personne peut entrer : son compte existe, ou son entreprise a l'accès ouvert."""
        email = (charge.get("email") or "").strip().lower()
        if email and self.env["res.users"].sudo().with_context(active_test=False).search_count([("login", "=ilike", email), ("share", "=", False)]):
            return True, "compte existant"
        e = charge.get("entreprise") or {}
        company = self._cultiveau_societe_site(e, creer=False)
        if company and company.cultiveau_erp_ouvert:
            return True, "entreprise ouverte"
        return False, "Votre entreprise n'a pas encore accès à l'ERP Cultiveau : demandez-le à Cultiveau."

    @api.model
    def _cultiveau_societe_site(self, e, creer=False):
        Company = self.sudo()
        site_id = int(e.get("id") or 0)
        nom = (e.get("nom") or "").strip()
        company = Company.search([("cultiveau_site_id", "=", site_id)], limit=1) if site_id else Company.browse()
        if not company and nom:
            company = Company.search([("name", "=ilike", nom)], limit=1)
        return company


class CompanyEntrepot(models.Model):
    _inherit = "res.company"

    def cultiveau_entrepot(self):
        """L'entrepôt de la société, créé s'il manque : sans entrepôt, aucun stock n'est possible (« le stock n'est toujours pas
        disponible », 08/11/2026 : les sociétés venues de cultiveau.fr n'en avaient pas)."""
        self.ensure_one()
        Entrepot = self.env["stock.warehouse"].sudo().with_context(active_test=False)
        entrepot = Entrepot.search([("company_id", "=", self.id)], limit=1)
        if entrepot:
            if not entrepot.active:
                entrepot.active = True
            if entrepot.name in ("My Company", "YourCompany") and self.name:
                entrepot.name = self.name[:255]
            return entrepot
        code = "".join(c for c in (self.name or "").upper() if c.isalnum())[:5] or f"ENT{self.id}"
        entrepot = Entrepot.with_company(self).create({"name": (self.name or f"Entrepôt {self.id}")[:255], "code": code[:5], "company_id": self.id})
        _logger.info("Entrepôt créé pour %s (%s)", self.name, entrepot.code)
        return entrepot

    @api.model
    def cultiveau_entrepots_manquants(self):
        """À chaque mise à jour : chaque société a son entrepôt, au nom de la société."""
        for company in self.sudo().search([]):
            company.cultiveau_entrepot()
        return True


class LaissezPasser(models.Model):
    _name = "cultiveau.site.laissez_passer"
    _description = "Laissez-passer reçu de cultiveau.fr (usage unique)"
    _rec_name = "login"

    nonce = fields.Char(required=True, index=True)
    login = fields.Char(required=True)
    expire_le = fields.Datetime(required=True)
    consomme = fields.Boolean(default=False)

    _sql_constraints = [("nonce_unique", "unique(nonce)", "Ce laissez-passer a déjà été présenté.")]

    @api.autovacuum
    def _gc(self):
        self.search([("expire_le", "<", fields.Datetime.subtract(fields.Datetime.now(), hours=1))]).unlink()


class Users(models.Model):
    _inherit = "res.users"

    def _check_credentials(self, credential, env):
        """Un laissez-passer de cultiveau.fr vaut mot de passe, une fois, pour le compte qu'il nomme."""
        if credential.get("type") != "cultiveau_site":
            return super()._check_credentials(credential, env)
        lp = self.env["cultiveau.site.laissez_passer"].sudo().browse(int(credential.get("laissez_passer") or 0)).exists()
        if not lp or lp.consomme or lp.expire_le < fields.Datetime.now() or (lp.login or "").lower() != (self.env.user.login or "").lower():
            raise AccessDenied()
        lp.consomme = True
        return {"uid": self.env.user.id, "auth_method": "cultiveau_site", "mfa": "default"}

    @api.model
    def cultiveau_depuis_site(self, charge):
        """Retrouve ou crée l'entreprise et l'utilisateur que décrit le laissez-passer. Renvoie l'utilisateur."""
        email = (charge.get("email") or "").strip().lower()
        if not email or "@" not in email:
            raise ValueError("laissez-passer sans e-mail")
        Users = self.sudo().with_context(active_test=False)
        user = Users.search([("login", "=ilike", email)], limit=1)
        if not user:
            ok, raison = self.env["res.company"].sudo().cultiveau_erp_eligible(charge)
            if not ok:
                raise PermissionError(raison)
        company = self._cultiveau_societe_depuis_site(charge.get("entreprise") or {}, charge)
        role = charge.get("role") if charge.get("role") in ROLES_SITE else "technicien"
        if user:
            vals = {}
            if not user.active:
                vals["active"] = True
            if company and company not in user.company_ids:
                vals["company_ids"] = [(4, company.id)]
            if company and user.share is False and user.company_id != company and len(user.company_ids) <= 1:
                vals["company_id"] = company.id
            if "cultiveau_role" in user._fields and user.cultiveau_role in (False, "libre") and user.login not in ("admin",):
                vals["cultiveau_role"] = role
            if vals:
                user.write(vals)
        else:
            vals = {"name": charge.get("nom") or email, "login": email, "email": email, "tz": "Europe/Paris",
                    "company_id": company.id, "company_ids": [(6, 0, [company.id])]}
            francais = self.env["res.lang"].sudo().search([("code", "=", "fr_FR"), ("active", "=", True)], limit=1)
            if francais:
                vals["lang"] = "fr_FR"
            if "cultiveau_role" in self._fields:
                vals["cultiveau_role"] = role
            user = Users.with_context(no_reset_password=True).create(vals)
            if charge.get("telephone"):
                user.partner_id.mobile = charge["telephone"]
            if charge.get("fonction"):
                user.partner_id.function = charge["fonction"]
            _logger.info("cultiveau.fr : accès ERP créé pour %s (%s, %s)", email, company.name, role)
        if company:
            self.env["cultiveau.site.connexion"].sudo()._cultiveau_relier_si_besoin(company, charge)
        return user

    @api.model
    def _cultiveau_societe_depuis_site(self, e, charge):
        Company = self.env["res.company"].sudo()
        site_id = int(e.get("id") or 0)
        nom = (e.get("nom") or charge.get("nom") or "").strip()
        company = Company.search([("cultiveau_site_id", "=", site_id)], limit=1) if site_id else Company.browse()
        if not company and nom:
            company = Company.search([("name", "=ilike", nom)], limit=1)
        vals = {"cultiveau_adherent": True} if "cultiveau_adherent" in Company._fields else {}
        if site_id:
            vals["cultiveau_site_id"] = site_id
        if not company:
            if "iap_enrich_auto_done" in Company._fields:
                vals["iap_enrich_auto_done"] = True  # pas d'appel en ligne à l'éditeur pour une entreprise qui vient de cultiveau.fr
            company = Company.create(dict(vals, name=nom or f"Adhérent {site_id}"))
            company.cultiveau_entrepot()
            _logger.info("cultiveau.fr : entreprise créée dans l'ERP : %s", company.name)
        elif vals:
            company.write({k: v for k, v in vals.items() if company[k] != v})
        partenaire = company.partner_id
        coord = {}
        if e.get("telephone") and not partenaire.phone:
            coord["phone"] = e["telephone"]
        if e.get("email") and not partenaire.email:
            coord["email"] = e["email"]
        if e.get("site") and not partenaire.website:
            coord["website"] = e["site"]
        if e.get("adresse") and not partenaire.street:
            coord["street"] = e["adresse"][:128]
        if coord:
            partenaire.write(coord)
        self._cultiveau_logo_depuis_site(company, e.get("logo_url"))
        return company

    @api.model
    def _cultiveau_logo_depuis_site(self, company, url):
        """Le logo de l'entreprise est celui de son espace cultiveau.fr : repris à l'entrée, et à chaque fois qu'il change là-bas."""
        if not url or not str(url).startswith("http") or company.cultiveau_site_logo_url == url and company.logo:
            return False
        try:
            r = requests.get(url, timeout=20)
            if r.status_code != 200 or not r.content or len(r.content) > 5_000_000 or not (r.headers.get("Content-Type") or "").startswith("image/"):
                return False
            company.sudo().write({"logo": base64.b64encode(r.content), "cultiveau_site_logo_url": url})  # un logo choisi : la règle du logo Cultiveau ne le touche plus
            _logger.info("cultiveau.fr : logo de %s repris dans l'ERP", company.name)
            return True
        except Exception as e:  # noqa: BLE001 — image illisible, site injoignable : le logo attend, l'entrée ne bloque pas
            _logger.info("cultiveau.fr : logo de %s non repris (%s)", company.name, e)
            return False


class Connexion(models.Model):
    _inherit = "cultiveau.site.connexion"

    @api.model
    def _cultiveau_relier_si_besoin(self, company, charge, forcer=False):
        """Pas encore de clé d'accès aux données de cette entreprise, ou une clé qui ne sait pas écrire ? L'ERP en demande une à cultiveau.fr,
        signé avec le secret partagé. La clé reçue depuis le 07/11/2026 sait aussi créer des chantiers (appli Mon Chantier)."""
        existante = self.sudo().with_context(active_test=False).search([("company_id", "=", company.id)], limit=1)
        if existante and not forcer:
            vals = {}
            if charge.get("cultiveau_id") and not existante.cultiveau_site_adherent_id:
                vals["cultiveau_site_adherent_id"] = charge["cultiveau_id"]
            if vals:
                existante.write(vals)
            if existante.cultiveau_site_ecriture:
                return False
            forcer = True  # clé ancienne, en lecture seule : on la remplace
        P = self.env["ir.config_parameter"].sudo()
        secret = P.get_param("cultiveau.erp_lien_secret")
        site = (P.get_param("cultiveau.url_site") or "https://cultiveau.fr").rstrip("/")
        cultiveau_id = charge.get("cultiveau_id")
        if not (secret and cultiveau_id):
            return False
        from ..controllers.ecran import fabriquer_jeton  # noqa: PLC0415 — même format que l'écran
        jeton = fabriquer_jeton({"v": 1, "outil": "cultiveau", "source": "erp", "action": "lier", "cultiveau_id": cultiveau_id,
                                 "exp": int(time.time()) + 120, "n": secrets.token_hex(12)}, secret)
        try:
            r = requests.post(f"{site}/api/erp/lier", json={"t": jeton}, timeout=15)
            if r.status_code != 200:
                _logger.info("cultiveau.fr : clé d'accès refusée pour %s (%s %s)", company.name, r.status_code, r.text[:120])
                return False
            cle = (r.json() or {}).get("cle")
        except (requests.RequestException, ValueError) as e:
            _logger.info("cultiveau.fr : clé d'accès non obtenue pour %s (%s)", company.name, e)
            return False
        if not cle:
            return False
        vals = {"company_id": company.id, "url": site, "cle": cle, "cultiveau_site_adherent_id": cultiveau_id, "cultiveau_site_ecriture": True, "active": True}
        if existante:
            existante.write(vals)
        else:
            self.sudo().create(vals)
        cron = self.env.ref("cultiveau_site.cron_synchro_site", raise_if_not_found=False)
        if cron:
            cron.sudo()._trigger()  # tout ce que l'adhérent a sur cultiveau.fr arrive dans la minute, pas dans une heure
        _logger.info("cultiveau.fr : données de %s reliées à l'ERP (clé reçue, première synchronisation lancée, chantiers vers Mon Chantier).", company.name)
        return True
