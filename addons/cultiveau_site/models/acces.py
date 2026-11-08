"""« Si pas ERP dans l'admin, pas d'accès » (Benjamin, 08/11/2026) : l'ERP ne laisse entrer que ce que l'admin de cultiveau.fr a ouvert.

Toutes les portes : le laissez-passer de cultiveau.fr (déjà filtré là-bas), la connexion par mot de passe sur erp.cultiveau.fr, et les
sessions déjà ouvertes. Passent toujours : l'administrateur et les comptes de la société Cultiveau elle-même. Un compte venu du site qui
a été décoché est désactivé (``/cultiveau/entree/personne``) : il ne peut plus se connecter de toute façon.
"""
from odoo import SUPERUSER_ID, http, models
from odoo.exceptions import AccessDenied
from odoo.http import request

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
