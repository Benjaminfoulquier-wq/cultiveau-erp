"""« Si pas ERP dans l'admin, pas d'accès » (Benjamin, 08/11/2026) : l'ERP ne laisse entrer que ce que l'admin de cultiveau.fr a ouvert.

Toutes les portes : le laissez-passer de cultiveau.fr (déjà filtré là-bas), la connexion par mot de passe sur erp.cultiveau.fr, et les
sessions déjà ouvertes. Passent toujours : l'administrateur et les comptes de la société Cultiveau elle-même. Un compte venu du site qui
a été décoché est désactivé (``/cultiveau/entree/personne``) : il ne peut plus se connecter de toute façon.
"""
import logging

from odoo import SUPERUSER_ID, api, http, models
from odoo.exceptions import AccessDenied
from odoo.http import request

_logger = logging.getLogger(__name__)
REFUS = "Votre accès à l'ERP Cultiveau n'est pas ouvert : il se règle dans l'administration de cultiveau.fr."


class Users(models.Model):
    _inherit = "res.users"

    def _cultiveau_acces_permis(self):
        """Vrai si ce compte peut entrer : administrateur, compte de la société Cultiveau, ou société ouverte depuis l'admin de cultiveau.fr."""
        self.ensure_one()
        user = self.sudo()
        if user.share or user.id == SUPERUSER_ID or user.id == self.env.ref("base.user_admin").id:
            return True
        company = user.company_id
        return bool(company and (company == self.env.ref("base.main_company") or company.cultiveau_erp_ouvert))

    @api.model
    def cultiveau_cloisonner_societes(self):
        """Chaque compte ne voit que sa société (08/11/2026 : « depuis le compte contact@cultiveau.fr je peux avoir accès à l'ERP de Frédéric
        Honoré et ça, c'est pas bon »). Seul le compte technique « admin » garde toutes les sociétés. Rejoué à chaque mise à jour."""
        admin = self.env.ref("base.user_admin")
        n = 0
        for user in self.sudo().with_context(active_test=False).search([("share", "=", False), ("id", "not in", (SUPERUSER_ID, admin.id))]):
            if not user.company_id:
                continue
            if user.company_ids != user.company_id:
                user.write({"company_ids": [(6, 0, [user.company_id.id])]})
                n += 1
        if n:
            _logger.info("Cloisonnement : %s compte(s) ramené(s) à leur seule société.", n)
        return n

    def _cultiveau_confiner(self):
        """Personne n'obtient une autre société que la sienne par un réglage de compte ; seul admin garde tout."""
        admin = self.env.ref("base.user_admin")
        for user in self.sudo().filtered(lambda u: not u.share and u.id not in (SUPERUSER_ID, admin.id) and u.company_id and u.company_ids != u.company_id):
            user.with_context(cultiveau_cloisonnement=True).write({"company_ids": [(6, 0, [user.company_id.id])]})

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        if not self.env.context.get("cultiveau_cloisonnement"):
            users._cultiveau_confiner()
        return users

    def write(self, vals):
        res = super().write(vals)
        if ("company_ids" in vals or "company_id" in vals) and not self.env.context.get("cultiveau_cloisonnement"):
            self._cultiveau_confiner()
        return res

    def _check_credentials(self, credential, env):
        resultat = super()._check_credentials(credential, env)
        if not self.env.user._cultiveau_acces_permis():
            raise AccessDenied(REFUS)
        return resultat


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @classmethod
    def _auth_method_user(cls):
        super()._auth_method_user()
        if not request.env.user._cultiveau_acces_permis():
            # la société a été fermée pendant que la session était ouverte : elle se termine maintenant
            request.session.logout(keep_db=True)
            raise http.SessionExpiredException(REFUS)
