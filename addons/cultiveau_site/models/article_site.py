"""Les articles créés ou modifiés dans l'ERP arrivent dans la base Clients & Articles de cultiveau.fr.

« Il faut que les articles créés soient disponibles dans la base » (08/11/2026). Jusque-là la base du site ne descendait que vers
l'ERP. Maintenant, pour une société reliée (clé du site qui sait écrire) : un article créé dans l'ERP est créé sur le site
(``POST /api/external/articles``), un article dont la désignation, la référence, le prix de vente, l'unité, la TVA, la famille ou
le code-barres change y est mis à jour (``PATCH /api/external/articles/<id>``). Le prix d'achat et le stock restent l'affaire de
l'ERP seul : ils ne partent pas. Ce que la synchronisation site → ERP écrit ne repart jamais (contexte ``cultiveau_depuis_site``).
L'envoi part une fois la transaction acquise ; ce qui n'est pas parti (site injoignable) part au passage suivant du robot.
"""
import logging
from functools import partial

import requests

from odoo import SUPERUSER_ID, api, fields, models
from odoo.tools import config

_logger = logging.getLogger(__name__)
CHAMPS_SUIVIS = {"name", "default_code", "list_price", "barcode", "categ_id", "uom_id", "taxes_id", "active", "description_sale", "sale_ok"}
RACINE_SITE = "Articles cultiveau.fr"


class Connexion(models.Model):
    _inherit = "cultiveau.site.connexion"

    def _modifier(self, chemin, donnees):
        """Un PATCH sur l'API externe du site ; renvoie (code, JSON). Isolé pour les tests."""
        self.ensure_one()
        url = f"{self.url.rstrip('/')}/api/external/{chemin.lstrip('/')}"
        r = requests.patch(url, json=donnees, headers={"X-API-Key": self.sudo().cle, "Accept": "application/json"}, timeout=30)
        try:
            return r.status_code, r.json()
        except ValueError:
            return r.status_code, {"erreur": r.text[:200]}


class ProductTemplate(models.Model):
    _inherit = "product.template"

    cultiveau_site_a_envoyer = fields.Boolean("À envoyer sur cultiveau.fr", copy=False, index=True)
    cultiveau_site_envoye_le = fields.Datetime("Envoyé sur cultiveau.fr le", readonly=True, copy=False)

    @api.model
    def _cultiveau_connexion_de(self, company):
        if not company:
            return self.env["cultiveau.site.connexion"]
        cx = self.env["cultiveau.site.connexion"].sudo().search([("company_id", "=", company.id), ("active", "=", True)], limit=1)
        return cx if cx and cx.cle else self.env["cultiveau.site.connexion"]

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get("cultiveau_depuis_site") and self._cultiveau_connexion_de(self.env.company):
            for vals in vals_list:
                if not vals.get("company_id") and vals.get("sale_ok", True):
                    vals["company_id"] = self.env.company.id  # l'article créé par un adhérent relié est à lui : il part dans sa base
        produits = super().create(vals_list)
        if not self.env.context.get("cultiveau_depuis_site"):
            produits._cultiveau_marquer_a_envoyer()
        return produits

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get("cultiveau_depuis_site") and CHAMPS_SUIVIS & set(vals):
            self._cultiveau_marquer_a_envoyer()
        return res

    def _cultiveau_marquer_a_envoyer(self):
        connexions = {}
        a_envoyer = self.env["product.template"]
        for p in self:
            if not p.company_id or not p.sale_ok:
                continue
            if p.company_id.id not in connexions:
                connexions[p.company_id.id] = bool(self._cultiveau_connexion_de(p.company_id))
            if connexions[p.company_id.id]:
                a_envoyer |= p
        if a_envoyer:
            a_envoyer.with_context(cultiveau_depuis_site=True).write({"cultiveau_site_a_envoyer": True})
            if not config["test_enable"]:  # dans les tests, on appelle l'envoi à la main
                self.env.cr.postcommit.add(partial(self._cultiveau_site_envoyer_apres_commit, self.env.cr.dbname, a_envoyer.ids))
        return a_envoyer

    @staticmethod
    def _cultiveau_site_envoyer_apres_commit(dbname, ids):
        from odoo.modules.registry import Registry  # noqa: PLC0415
        with Registry(dbname).cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            try:
                env["product.template"].browse(ids).exists().cultiveau_envoyer_vers_site()
            except Exception:  # noqa: BLE001 — jamais bloquer la saisie d'un article pour le site
                _logger.exception("Base articles cultiveau.fr : envoi impossible pour les articles %s", ids)

    def _cultiveau_site_charge(self):
        self.ensure_one()
        taxe = self.taxes_id.filtered(lambda t: t.company_id == self.company_id)[:1] or self.taxes_id[:1]
        marque = ""
        if (self.description_sale or "").startswith("Marque : "):
            marque = self.description_sale[len("Marque : "):].strip()[:255]
        charge = {"reference": (self.default_code or "")[:100], "designation": (self.name or "")[:500], "ean": (self.barcode or "")[:20],
                  "categorie": self.categ_id.name[:255] if self.categ_id and self.categ_id.name != RACINE_SITE else "",
                  "marque": marque, "prixUnitaireHT": round(self.list_price or 0.0, 2), "unite": (self.uom_id.name or "")[:50],
                  "tvaRate": round(taxe.amount, 2) if taxe else "", "isActive": bool(self.active)}
        return {k: v for k, v in charge.items() if v not in ("", None)}

    def cultiveau_envoyer_vers_site(self):
        """Envoie les articles marqués ; renvoie le nombre envoyé. Le prix d'achat et le stock ne partent pas."""
        envoyes = 0
        for p in self.with_context(active_test=False).filtered("cultiveau_site_a_envoyer"):
            cx = self._cultiveau_connexion_de(p.company_id)
            if not cx:
                continue
            if not p.default_code:
                p.with_context(cultiveau_depuis_site=True).write({"default_code": f"ERP-{p.id}"})  # la base du site exige une référence
            charge = p._cultiveau_site_charge()
            try:
                code, rep = p._cultiveau_site_envoyer_un(cx, charge)
                if code == 403 and cx._cultiveau_redemander_cle():
                    code, rep = p._cultiveau_site_envoyer_un(cx, charge)
            except requests.RequestException as e:
                _logger.info("Base articles cultiveau.fr : site injoignable pour %s (%s)", p.display_name, e)
                continue
            article = (rep or {}).get("article") or {}
            if code not in (200, 201) or not article.get("id"):
                _logger.info("Base articles cultiveau.fr : article %s refusé par le site (%s %s)", p.display_name, code, rep)
                continue
            p.with_context(cultiveau_depuis_site=True).write({"cultiveau_site_ref": cx._ref(article["id"]), "cultiveau_site_a_envoyer": False,
                                                              "cultiveau_site_envoye_le": fields.Datetime.now()})
            envoyes += 1
        return envoyes

    def _cultiveau_site_envoyer_un(self, cx, charge):
        """Mise à jour si le site connaît déjà l'article (identifiant du site dans la référence), sinon création ; un identifiant périmé crée."""
        ref = self.cultiveau_site_ref or ""
        if ref.startswith(f"{cx.id}:") and ref.split(":")[-1].isdigit():
            code, rep = cx._modifier(f"articles/{ref.split(':')[-1]}", charge)
            if code != 404:
                return code, rep
        return cx._poster("articles", charge)

    @api.model
    def _cron_envoyer_vers_site(self):
        """Filet de sécurité : ce qui n'est pas parti tout de suite part au passage suivant."""
        self.with_context(active_test=False).search([("cultiveau_site_a_envoyer", "=", True)], limit=200).cultiveau_envoyer_vers_site()

    def action_envoyer_vers_site(self):
        n = self.with_context(cultiveau_depuis_site=True)._cultiveau_forcer_envoi()
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"title": "Base articles cultiveau.fr", "message": f"{n} article(s) envoyé(s).", "type": "success" if n else "warning"}}

    def _cultiveau_forcer_envoi(self):
        self.write({"cultiveau_site_a_envoyer": True})
        return self.cultiveau_envoyer_vers_site()
