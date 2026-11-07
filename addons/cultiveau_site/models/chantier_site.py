"""Un chantier né dans l'ERP (une commande confirmée, un devis lancé) tombe dans l'appli Mon Chantier de cultiveau.fr.

Quand l'entreprise est reliée au site (clé d'accès obtenue à son entrée dans l'ERP), chaque chantier créé dans l'ERP est envoyé
à cultiveau.fr une fois la transaction acquise (phases comprises) : client, objet, dates, phases avec leurs heures. Le site
rend son identifiant, gardé dans ``cultiveau_site_ref`` : la synchronisation horaire (site → ERP) reconnaît alors le même chantier
et ne le recrée pas. Si la clé n'a pas le droit d'écrire (clé remise avant le 07/11/2026), l'ERP en redemande une."""
import logging
from functools import partial

import requests

from odoo import SUPERUSER_ID, api, fields, models
from odoo.tools import config

_logger = logging.getLogger(__name__)
ETAT_SITE = {"brouillon": "brouillon", "planifie": "planifie", "en_cours": "en_cours", "termine": "termine", "annule": "annule"}


class Connexion(models.Model):
    _inherit = "cultiveau.site.connexion"

    cultiveau_site_adherent_id = fields.Integer("Compte cultiveau.fr qui a remis la clé", readonly=True, copy=False)
    cultiveau_site_ecriture = fields.Boolean("La clé peut écrire (chantiers)", readonly=True, copy=False)

    def _poster(self, chemin, donnees):
        """Un POST sur l'API externe du site ; renvoie (code, JSON). Isolé pour les tests."""
        self.ensure_one()
        cle = self.sudo().cle
        url = f"{self.url.rstrip('/')}/api/external/{chemin.lstrip('/')}"
        r = requests.post(url, json=donnees, headers={"X-API-Key": cle, "Accept": "application/json", "Idempotency-Key": donnees.get("idempotence", "")}, timeout=30)
        try:
            return r.status_code, r.json()
        except ValueError:
            return r.status_code, {"erreur": r.text[:200]}

    def _cultiveau_redemander_cle(self):
        """La clé en place ne sait pas écrire : on en redemande une à cultiveau.fr, pour le même compte."""
        self.ensure_one()
        if not self.cultiveau_site_adherent_id:
            return False
        return self._cultiveau_relier_si_besoin(self.company_id, {"cultiveau_id": self.cultiveau_site_adherent_id}, forcer=True)


class Chantier(models.Model):
    _inherit = "cultiveau.chantier"

    cultiveau_site_a_envoyer = fields.Boolean("À envoyer dans Mon Chantier", default=False, copy=False, index=True)
    cultiveau_site_envoye_le = fields.Datetime("Envoyé dans Mon Chantier le", readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        chantiers = super().create(vals_list)
        a_envoyer = chantiers.filtered(lambda c: not c.cultiveau_site_ref and c._cultiveau_site_connexion())
        if a_envoyer:
            a_envoyer.write({"cultiveau_site_a_envoyer": True})
            a_envoyer._cultiveau_site_programmer_envoi()
        return chantiers

    def _cultiveau_site_connexion(self):
        self.ensure_one()
        return self.env["cultiveau.site.connexion"].sudo().search([("company_id", "=", self.company_id.id), ("active", "=", True)], limit=1)

    def _cultiveau_site_programmer_envoi(self):
        """L'envoi part une fois la transaction acquise : les phases et le matériel du chantier sont alors là."""
        if config["test_enable"]:
            return  # dans les tests, on appelle l'envoi à la main
        ids, dbname = self.ids, self.env.cr.dbname
        self.env.cr.postcommit.add(partial(self._cultiveau_site_envoyer_apres_commit, dbname, ids))

    @staticmethod
    def _cultiveau_site_envoyer_apres_commit(dbname, ids):
        from odoo.modules.registry import Registry  # noqa: PLC0415
        with Registry(dbname).cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            try:
                env["cultiveau.chantier"].browse(ids).exists().cultiveau_envoyer_vers_site()
            except Exception:  # noqa: BLE001 — jamais bloquer la confirmation d'une commande pour le site
                _logger.exception("Mon Chantier : envoi impossible pour les chantiers %s", ids)

    def action_envoyer_vers_site(self):
        n = self.cultiveau_envoyer_vers_site()
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"title": "Mon Chantier", "message": f"{n} chantier(s) envoyé(s) dans l'appli Mon Chantier de cultiveau.fr." if n else "Rien envoyé : entreprise non reliée, chantier déjà présent, ou site injoignable.",
                           "type": "success" if n else "warning", "sticky": False, "next": {"type": "ir.actions.client", "tag": "soft_reload"}}}

    def _cultiveau_site_charge(self):
        """Ce que l'ERP dit du chantier à cultiveau.fr."""
        self.ensure_one()
        partner = self.partner_id
        phases = []
        for ph in self.phase_ids.sorted(lambda p: (p.sequence, p.id)):
            phase = {"name": ph.name}
            if ph.heures_prevues:
                phase["estimatedHours"] = ph.heures_prevues
            if ph.date_debut:
                phase["startDate"] = fields.Date.to_string(ph.date_debut)
            if ph.date_fin:
                phase["endDate"] = fields.Date.to_string(ph.date_fin)
            phases.append(phase)
        adresse = ", ".join(x for x in (partner.street, partner.street2) if x)
        notes = [f"Créé dans l'ERP Cultiveau : {self.name}"]
        if self.sale_order_id:
            notes.append(f"Commande {self.sale_order_id.name}")
        if self.notes:
            notes.append(self.notes)
        charge = {
            "name": (self.titre or self.name)[:255], "clientName": (partner.name or "Client")[:255],
            "clientPhone": partner.mobile or partner.phone or None, "clientEmail": partner.email or None,
            "clientAddress": adresse or None, "clientCity": partner.city or None, "clientPostalCode": partner.zip or None,
            "siteAddress": (self.acces or adresse or None), "description": (self.installation_id.name or "")[:10000] or None,
            "status": ETAT_SITE.get(self.etat, "brouillon"), "priority": "normale",
            "estimatedHours": sum(self.phase_ids.mapped("heures_prevues")) or None,
            "notes": "\n".join(notes)[:10000], "phases": phases, "idempotence": f"erp-chantier-{self.id}",
        }
        if self.date_debut:
            charge["startDate"] = fields.Date.to_string(self.date_debut)
        if self.date_fin:
            charge["endDate"] = fields.Date.to_string(self.date_fin)
        return {k: v for k, v in charge.items() if v is not None}

    def cultiveau_envoyer_vers_site(self):
        """Envoie les chantiers pas encore connus du site. Renvoie le nombre envoyé."""
        envoyes = 0
        for ch in self.filtered(lambda c: not c.cultiveau_site_ref):
            cx = ch._cultiveau_site_connexion()
            if not cx:
                continue
            charge = ch._cultiveau_site_charge()
            try:
                code, rep = cx._poster("chantiers", charge)
                if code == 403 and cx._cultiveau_redemander_cle():
                    code, rep = cx._poster("chantiers", charge)
            except requests.RequestException as e:
                _logger.info("Mon Chantier : site injoignable pour %s (%s)", ch.name, e)
                continue
            if code != 201 or not rep.get("chantierId"):
                _logger.info("Mon Chantier : chantier %s refusé par le site (%s %s)", ch.name, code, rep)
                ch.message_post(body=f"Envoi dans Mon Chantier refusé par cultiveau.fr ({code}) : {rep.get('message') or rep.get('error') or rep.get('erreur') or ''}", subtype_xmlid="mail.mt_note")
                continue
            ch.write({"cultiveau_site_ref": cx._ref(rep["chantierId"]), "cultiveau_site_a_envoyer": False, "cultiveau_site_envoye_le": fields.Datetime.now()})
            ch.message_post(body=f"Chantier créé dans l'appli Mon Chantier de cultiveau.fr : {rep.get('reference') or rep['chantierId']}" + (f", {len(rep.get('phases') or [])} phase(s)" if rep.get("phases") else "") + ".", subtype_xmlid="mail.mt_note")
            envoyes += 1
        return envoyes

    @api.model
    def _cron_envoyer_vers_site(self):
        """Filet de sécurité : ce qui n'est pas parti tout de suite (site injoignable) part au passage suivant."""
        self.search([("cultiveau_site_a_envoyer", "=", True), ("cultiveau_site_ref", "=", False)], limit=50).cultiveau_envoyer_vers_site()
