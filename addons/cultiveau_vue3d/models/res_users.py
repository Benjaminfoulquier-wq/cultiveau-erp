from odoo import api, fields, models


class ResUsers(models.Model):
    """La vue d'ensemble est la page d'accueil de l'ERP : chaque utilisateur y arrive à la connexion."""

    _inherit = "res.users"

    action_id = fields.Many2one(default=lambda self: self.env.ref("cultiveau_vue3d.action_vue3d", raise_if_not_found=False))

    @api.model
    def _cultiveau_page_accueil_pour_tous(self):
        action = self.env.ref("cultiveau_vue3d.action_vue3d", raise_if_not_found=False)
        if action:
            self.sudo().with_context(active_test=False).search([("share", "=", False), ("action_id", "=", False)]).write({"action_id": action.id})
