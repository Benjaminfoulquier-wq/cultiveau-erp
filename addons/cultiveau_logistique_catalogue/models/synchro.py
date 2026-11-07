"""Les produits de logistique.cultiveau.fr dans l'ERP : lus toutes les heures, créés ou mis à jour dans le catalogue du réseau, avec
famille, fournisseur, prix, photo et fiches techniques ; archivés quand ils sont retirés là-bas."""
import base64
import logging
from datetime import datetime

import requests

from odoo import api, fields, models
from odoo.tools import config
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)
PARTENAIRE_LOGISTIQUE = "Cultiveau Logistique"


class Reglages(models.TransientModel):
    _inherit = "res.config.settings"

    cultiveau_logistique_url = fields.Char("Adresse de la logistique", config_parameter="cultiveau.logistique_url", default="https://logistique.cultiveau.fr")
    cultiveau_logistique_secret_pose = fields.Boolean("Secret posé", compute="_compute_logistique_etat")
    cultiveau_logistique_bilan = fields.Char("Dernière synchronisation", compute="_compute_logistique_etat")
    cultiveau_logistique_photos = fields.Boolean("Rapatrier les photos", config_parameter="cultiveau.logistique_photos", default=True)

    def _compute_logistique_etat(self):
        P = self.env["ir.config_parameter"].sudo()
        for r in self:
            r.cultiveau_logistique_secret_pose = bool(P.get_param("cultiveau.logistique_secret"))
            r.cultiveau_logistique_bilan = P.get_param("cultiveau.logistique_bilan") or "jamais"

    def action_synchroniser_logistique(self):
        bilan = self.env["product.template"].cultiveau_synchro_logistique(tout=True)
        return {"type": "ir.actions.client", "tag": "display_notification", "params": {"title": "Logistique", "message": bilan, "type": "success", "sticky": False}}


class Produit(models.Model):
    _inherit = "product.template"

    cultiveau_source = fields.Selection(selection_add=[("logistique", "Logistique Cultiveau")], ondelete={"logistique": "set null"})
    cultiveau_logistique_id = fields.Integer("Produit logistique (id)", index=True, copy=False)
    cultiveau_logistique_url = fields.Char("Fiche sur la logistique", copy=False)
    cultiveau_logistique_image_url = fields.Char("Photo (adresse logistique)", copy=False)
    cultiveau_logistique_maj = fields.Datetime("Mis à jour sur la logistique", copy=False)

    def action_ouvrir_logistique(self):
        self.ensure_one()
        return {"type": "ir.actions.act_url", "url": self.cultiveau_logistique_url or "https://logistique.cultiveau.fr", "target": "new"}

    # ---------------------------------------------------------------- la lecture
    @api.model
    def _logistique_page(self, page, depuis=None, taille=500):
        P = self.env["ir.config_parameter"].sudo()
        url = (P.get_param("cultiveau.logistique_url") or "https://logistique.cultiveau.fr").rstrip("/")
        secret = (P.get_param("cultiveau.logistique_secret") or "").strip()
        if not secret:
            raise UserError("Le secret partagé avec la logistique n'est pas réglé (paramètre cultiveau.logistique_secret).")
        params = {"page": page, "taille": taille}
        if depuis:
            params["depuis"] = depuis
        r = requests.get(f"{url}/api/erp/produits", params=params, headers={"X-Erp-Secret": secret}, timeout=60)
        if r.status_code == 401:
            raise UserError("La logistique refuse le secret partagé.")
        if r.status_code == 503:
            raise UserError("La logistique n'a pas son secret ERP (ERP_SYNC_SECRET) ou sa base est indisponible.")
        r.raise_for_status()
        return r.json()

    @api.model
    def _logistique_telecharger(self, url):
        try:
            r = requests.get(url, timeout=60)
            if r.status_code == 200 and r.content:
                return r.content
        except requests.RequestException as e:  # noqa: PERF203
            _logger.info("Logistique : fichier non rapatrié %s (%s)", url, e)
        return None

    # ---------------------------------------------------------------- la synchronisation
    @api.model
    def cultiveau_synchro_logistique(self, tout=False):
        """Lit les produits modifiés depuis la dernière fois (ou tous) et les pose dans le catalogue du réseau. Renvoie le bilan en une phrase."""
        P = self.env["ir.config_parameter"].sudo()
        if not (P.get_param("cultiveau.logistique_secret") or "").strip():
            texte = "Secret partagé avec la logistique non réglé : rien n'est synchronisé (équipe Cultiveau : script deploiement/publier-erp-export)."
            P.set_param("cultiveau.logistique_bilan", texte)
            _logger.info("Logistique → ERP : %s", texte)
            return texte
        depuis = None if tout else P.get_param("cultiveau.logistique_depuis")
        debut = fields.Datetime.now()
        page, bilan = 1, {"crees": 0, "maj": 0, "archives": 0, "fiches": 0, "photos": 0}
        while True:
            data = self._logistique_page(page, depuis)
            produits = data.get("produits") or []
            if not produits:
                break
            self._logistique_appliquer(produits, bilan)
            if not config["test_enable"]:
                self.env.cr.commit()  # chaque page est acquise : une coupure ne perd pas tout
            if page * data.get("taille", 500) >= data.get("total", 0):
                break
            page += 1
        P.set_param("cultiveau.logistique_depuis", fields.Datetime.to_string(debut))
        texte = f"{fields.Datetime.context_timestamp(self, fields.Datetime.now()):%d/%m %H:%M} : {bilan['crees']} créé(s), {bilan['maj']} mis à jour, {bilan['archives']} archivé(s), {bilan['fiches']} fiche(s), {bilan['photos']} photo(s)."
        P.set_param("cultiveau.logistique_bilan", texte)
        _logger.info("Logistique → ERP : %s", texte)
        return texte

    @api.model
    def _logistique_appliquer(self, produits, bilan):
        Fiche = self.env["cultiveau.fiche"].sudo()
        cache_f, cache_c = {}, {}
        avec_photos = (self.env["ir.config_parameter"].sudo().get_param("cultiveau.logistique_photos") or "True") not in ("False", "0", "")
        logistique = self._cultiveau_fournisseur(PARTENAIRE_LOGISTIQUE, cache_f)
        Produit = self.sudo().with_context(active_test=False)
        ids = [p["id"] for p in produits]
        refs = [p["reference"] for p in produits if p.get("reference")]
        existants = {p.cultiveau_logistique_id: p for p in Produit.search([("cultiveau_logistique_id", "in", ids)])}
        par_ref = {p.default_code: p for p in Produit.search([("default_code", "in", refs), ("company_id", "=", False), ("cultiveau_logistique_id", "=", False)])} if refs else {}
        for p in produits:
            fournisseur = self._cultiveau_fournisseur((p.get("fournisseur") or {}).get("nom"), cache_f)
            parent = self._cultiveau_categorie(p.get("famille") or "Autre", cache=cache_c)
            categorie = self._cultiveau_categorie(p["sous_famille"], parent, cache_c) if p.get("sous_famille") else parent
            description = (p.get("description") or "").strip()
            if p.get("argumentaire"):
                description = (description + "\n\n" if description else "") + f"Le mot de {(p.get('fournisseur') or {}).get('nom') or 'le fabricant'} : {p['argumentaire'].strip()}"
            maj = p.get("mis_a_jour")
            try:
                maj_dt = datetime.fromisoformat(maj.replace("Z", "+00:00")).replace(tzinfo=None) if maj else None
            except ValueError:
                maj_dt = None
            prix_achat = p.get("prix") if p.get("prix") is not None else 0.0
            prix_vente = p.get("prix_brut") if p.get("prix_brut") else (prix_achat * 1.3 if prix_achat else 0.0)
            valeurs = {
                "name": (p.get("nom") or p.get("reference") or "Produit")[:255], "default_code": (p.get("reference") or f"LOG-{p['id']}")[:64], "type": "consu", "is_storable": True,
                "categ_id": categorie.id, "description_sale": description or False, "weight": p.get("poids") or 0.0,
                "list_price": prix_vente, "standard_price": prix_achat, "cultiveau_conditionnement": (p.get("conditionnement") or "")[:120] or False,
                "cultiveau_source": "logistique", "cultiveau_reseau": True, "sale_ok": True, "purchase_ok": True, "company_id": False,
                "cultiveau_logistique_id": p["id"], "cultiveau_logistique_url": p.get("url") or False, "cultiveau_logistique_maj": maj_dt, "active": bool(p.get("actif", True)),
            }
            fiches = p.get("fiches") or []
            if fiches:
                valeurs["cultiveau_fiche_url"] = (fiches[0].get("url") or "")[:500] or False
            produit = existants.get(p["id"]) or par_ref.get(valeurs["default_code"])
            if produit:
                etait_actif = produit.active
                produit.write(valeurs)
                if valeurs["active"]:
                    bilan["maj"] += 1
                elif etait_actif:
                    bilan["archives"] += 1
            else:
                if not valeurs["active"]:
                    continue  # un produit retiré qu'on ne connaissait pas : rien à créer
                produit = Produit.create(valeurs)
                bilan["crees"] += 1
                existants[p["id"]] = produit
            # le fournisseur réel (prix et référence), et la logistique comme canal d'achat
            if fournisseur:
                self._cultiveau_fournisseur_prix(produit, fournisseur, prix=None, reference=p.get("reference"))
            if prix_achat:
                self._cultiveau_fournisseur_prix(produit, logistique, prix=prix_achat, reference=p.get("reference"))
            # les fiches techniques dans la bibliothèque, reliées à l'article
            for f in fiches:
                if not f.get("url"):
                    continue
                cle = f"logistique:{f.get('id')}"
                doc = Fiche.search([("drive_id", "=", cle)], limit=1)
                vals_f = {"name": (f.get("titre") or f"Fiche {p.get('reference') or p['id']}")[:255], "url": f["url"][:500], "type_doc": "fiche", "fournisseur_nom": (p.get("fournisseur") or {}).get("nom") or False,
                          "fournisseur_id": fournisseur.id if fournisseur else False, "famille": p.get("famille") or False, "sous_famille": p.get("sous_famille") or False, "source": "logistique.cultiveau.fr",
                          "mime": "application/pdf" if (f.get("type") or "pdf") == "pdf" else False}
                if doc:
                    doc.write(vals_f)
                else:
                    doc = Fiche.create({**vals_f, "drive_id": cle})
                    bilan["fiches"] += 1
                if not produit.cultiveau_fiche_id:
                    produit.cultiveau_fiche_id = doc
            # la photo, une fois par adresse
            if avec_photos and p.get("image_url") and p["image_url"] != produit.cultiveau_logistique_image_url:
                contenu = self._logistique_telecharger(p["image_url"])
                if contenu and len(contenu) < 8_000_000:
                    try:
                        produit.write({"image_1920": base64.b64encode(contenu), "cultiveau_logistique_image_url": p["image_url"]})
                        bilan["photos"] += 1
                    except Exception as e:  # noqa: BLE001 : une image illisible n'arrête pas la synchronisation
                        _logger.info("Logistique : photo refusée pour %s (%s)", produit.default_code, e)
        return bilan
