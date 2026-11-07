"""Le logo d'une société n'est jamais celui de l'éditeur : une société sans logo porte celui de Cultiveau (en attendant le sien, repris de
son espace cultiveau.fr), sur le portail client, les devis, les factures et les courriels."""
import base64
import logging

from odoo import api, fields, models
from odoo.tools import file_open

_logger = logging.getLogger(__name__)


def logo_cultiveau():
    with file_open("cultiveau_marque/static/src/img/logo.png", "rb") as f:
        return base64.b64encode(f.read())


class Company(models.Model):
    _inherit = "res.company"

    cultiveau_logo_choisi = fields.Boolean("Logo choisi par l'entreprise", default=False, copy=False,
                                           help="Coché dès qu'un logo est posé à la main ou repris de cultiveau.fr. Sinon, la société porte le logo Cultiveau.")

    @api.model
    def _get_logo(self):
        return logo_cultiveau()

    def write(self, vals):
        if "logo" in vals and not self.env.context.get("cultiveau_logo_auto"):
            vals = dict(vals, cultiveau_logo_choisi=bool(vals["logo"]))
        return super().write(vals)

    def _compute_uses_default_logo(self):
        """Odoo sert une image « Your logo » dès qu'il juge le logo « par défaut » : jamais ici, le vrai logo s'affiche toujours."""
        for c in self:
            c.uses_default_logo = False

    @api.model
    def cultiveau_logo_par_defaut(self):
        """À chaque mise à jour : toute société dont le logo n'a pas été choisi (à la main ou repris de cultiveau.fr) porte celui de Cultiveau.
        On ne cherche pas à reconnaître l'image « Your logo » de l'éditeur : elle change d'une version à l'autre."""
        n = 0
        for c in self.sudo().with_context(active_test=False).search([]):
            if c.cultiveau_logo_choisi or ("cultiveau_site_logo_url" in c._fields and c.cultiveau_site_logo_url):
                continue
            c.with_context(cultiveau_logo_auto=True).write({"logo": logo_cultiveau()})
            n += 1
        self.env.cr.execute("UPDATE res_company SET uses_default_logo = false WHERE uses_default_logo IS DISTINCT FROM false")
        self.env.registry.clear_cache()
        _logger.info("Cultiveau : logo Cultiveau posé sur %s société(s) sans logo choisi ; plus aucune société en « logo par défaut ».", n)
        return n
