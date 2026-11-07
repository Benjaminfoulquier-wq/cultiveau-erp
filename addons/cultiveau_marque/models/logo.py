"""Le logo d'une société n'est jamais celui de l'éditeur : une société sans logo porte celui de Cultiveau (en attendant le sien, repris de
son espace cultiveau.fr), sur le portail client, les devis, les factures et les courriels."""
import base64
import logging

from odoo import api, models
from odoo.tools import file_open, image_process

_logger = logging.getLogger(__name__)


def logo_cultiveau():
    with file_open("cultiveau_marque/static/src/img/logo.png", "rb") as f:
        return base64.b64encode(f.read())


class Company(models.Model):
    _inherit = "res.company"

    @api.model
    def _get_logo(self):
        return logo_cultiveau()

    def _compute_uses_default_logo(self):
        """Odoo sert une image « Your logo » dès qu'il juge le logo « par défaut » : jamais ici, le vrai logo s'affiche toujours."""
        for c in self:
            c.uses_default_logo = False

    @api.model
    def cultiveau_logo_par_defaut(self):
        """À chaque mise à jour : les sociétés sans logo, ou avec le logo de l'éditeur, reçoivent celui de Cultiveau."""
        # l'image « Your logo » de l'éditeur, telle quelle et telle qu'Odoo la range (retaillée) dans la fiche de la société
        editeur = set()
        try:
            with file_open("base/static/img/res_company_logo.png", "rb") as f:
                brut = f.read()
            editeur.add(base64.b64encode(brut))
            for taille in ((1920, 1920), (1024, 1024)):
                try:
                    editeur.add(base64.b64encode(image_process(brut, size=taille)))
                except Exception:  # noqa: BLE001
                    pass
        except OSError:
            pass
        n = 0
        for c in self.sudo().with_context(active_test=False).search([]):
            logo = c.logo or b""
            if not logo or logo in editeur or (c.partner_id.image_1920 or b"") in editeur:
                c.write({"logo": logo_cultiveau()})
                n += 1
        self.env.cr.execute("UPDATE res_company SET uses_default_logo = false WHERE uses_default_logo IS DISTINCT FROM false")
        self.env.registry.clear_cache()
        _logger.info("Cultiveau : logo posé sur %s société(s) qui n'en avaient pas ; plus aucune société en « logo par défaut ».", n)
        return n
