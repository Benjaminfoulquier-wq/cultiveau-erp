"""Les clés d'API : une par outil, montrée une seule fois, conservée sous forme d'empreinte."""
import hashlib
import hmac
import secrets

from odoo import api, fields, models

USAGES = [("site", "Site cultiveau.fr"), ("appli", "Application mobile"), ("claude", "Claude (connecteur)"), ("assistant", "Assistant téléphonique"), ("autre", "Autre outil")]


def empreinte(cle):
    return hashlib.sha256((cle or "").encode()).hexdigest()


class CleApi(models.Model):
    _name = "cultiveau.cle.api"
    _description = "Clé d'API"
    _order = "active desc, name"

    name = fields.Char("Outil", required=True, help="Ex. « Site cultiveau.fr », « Claude », « Appli des techniciens ».")
    usage = fields.Selection(USAGES, "Usage", default="site", required=True)
    droits = fields.Selection([("lecture", "Lecture seule"), ("ecriture", "Lecture et écriture")], "Droits", default="lecture", required=True,
                              help="L'écriture permet de créer des clients, des interventions, des opportunités et d'ajouter des notes.")
    company_ids = fields.Many2many("res.company", "cultiveau_cle_api_societe_rel", "cle_id", "company_id", string="Adhérents",
                                   help="Vide : tout le réseau. Sinon, la clé ne voit que les données de ces adhérents.")
    prefixe = fields.Char("Début de la clé", readonly=True)
    empreinte = fields.Char(readonly=True, index=True, copy=False)
    cle_a_copier = fields.Char("Clé (à copier maintenant)", readonly=True, copy=False,
                               help="Montrée une seule fois : copiez-la dans l'outil, puis cliquez sur « J'ai copié la clé ».")
    adresse_mcp = fields.Char("Adresse du connecteur Claude", compute="_compute_adresses")
    adresse_api = fields.Char("Adresse de l'API", compute="_compute_adresses")
    expire_le = fields.Date("Expire le")
    derniere_utilisation = fields.Datetime("Dernière utilisation", readonly=True)
    nb_appels = fields.Integer("Appels", readonly=True)
    active = fields.Boolean(default=True)
    notes = fields.Text("Notes")

    def _compute_adresses(self):
        base = (self.env["ir.config_parameter"].sudo().get_param("web.base.url") or "").rstrip("/")
        for c in self:
            c.adresse_api = f"{base}/cultiveau/api/v1"
            c.adresse_mcp = f"{base}/cultiveau/mcp/{c.cle_a_copier}" if c.cle_a_copier else f"{base}/cultiveau/mcp/<la clé>"

    @api.model_create_multi
    def create(self, vals_list):
        cles = []
        for vals in vals_list:
            cle = "cv_" + secrets.token_urlsafe(32)
            vals.update({"empreinte": empreinte(cle), "prefixe": cle[:10] + "…", "cle_a_copier": cle})
            cles.append(cle)
        return super().create(vals_list)

    def action_regenerer(self):
        """Une nouvelle clé : l'ancienne cesse aussitôt de fonctionner."""
        for c in self:
            cle = "cv_" + secrets.token_urlsafe(32)
            c.write({"empreinte": empreinte(cle), "prefixe": cle[:10] + "…", "cle_a_copier": cle})

    def action_cle_copiee(self):
        self.write({"cle_a_copier": False})

    @api.model
    def authentifier(self, cle):
        """La clé active qui correspond, ou rien. Compte l'appel."""
        if not cle or not cle.startswith("cv_"):
            return self.browse()
        trouvee = self.sudo().search([("empreinte", "=", empreinte(cle)), ("active", "=", True)], limit=1)
        if not trouvee or not hmac.compare_digest(trouvee.empreinte, empreinte(cle)):
            return self.browse()
        if trouvee.expire_le and trouvee.expire_le < fields.Date.context_today(trouvee):
            return self.browse()
        maintenant = fields.Datetime.now()
        # le compteur s'écrit à part : les lectures (GET) tournent dans une transaction en lecture seule
        try:
            if getattr(self.env.cr, "readonly", False) or self.env.context.get("cultiveau_cle_curseur_separe"):
                with self.env.registry.cursor() as cr:
                    cr.execute("UPDATE cultiveau_cle_api SET derniere_utilisation = %s, nb_appels = COALESCE(nb_appels, 0) + 1 WHERE id = %s", (maintenant, trouvee.id))
            else:
                with self.env.cr.savepoint():
                    self.env.cr.execute("UPDATE cultiveau_cle_api SET derniere_utilisation = %s, nb_appels = COALESCE(nb_appels, 0) + 1 WHERE id = %s",
                                        (maintenant, trouvee.id))
        except Exception:  # noqa: BLE001 — un compteur qui ne s'écrit pas ne bloque pas l'appel
            pass
        return trouvee
