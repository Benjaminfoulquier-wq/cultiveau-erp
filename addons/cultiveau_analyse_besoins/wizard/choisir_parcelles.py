"""Choisir, parmi les parcelles déclarées par le client, celles que le projet doit arroser."""
from odoo import api, fields, models


class ChoisirParcelles(models.TransientModel):
    _name = "cultiveau.installation.parcelles"
    _description = "Les parcelles du client à reprendre dans le projet"

    installation_id = fields.Many2one("cultiveau.installation", required=True, ondelete="cascade")
    partner_id = fields.Many2one(related="installation_id.partner_id")
    campagne = fields.Integer("Campagne PAC", default=lambda self: self._campagne_defaut())
    parcelle_ids = fields.Many2many("cultiveau.parcelle", string="Parcelles à arroser", default=lambda self: self._parcelles_defaut(),
                                    domain="[('partner_id', '=', partner_id), ('campagne', '=', campagne)]")
    surface_ha = fields.Float("Surface retenue (ha)", compute="_compute_surface", digits=(8, 2))

    def _campagne_defaut(self):
        inst = self.env["cultiveau.installation"].browse(self.env.context.get("default_installation_id"))
        return inst.campagne_client or fields.Date.context_today(self).year

    def _parcelles_defaut(self):
        inst = self.env["cultiveau.installation"].browse(self.env.context.get("default_installation_id"))
        if inst.parcelle_ids:
            return inst.parcelle_ids.ids
        campagne = inst.campagne_client
        return inst.partner_id.cultiveau_parcelle_ids.filtered(lambda p: p.campagne == campagne and p.irriguee and p.culture_id).ids

    @api.depends("parcelle_ids")
    def _compute_surface(self):
        for w in self:
            w.surface_ha = sum(w.parcelle_ids.mapped("surface_ha"))

    def action_appliquer(self):
        self.ensure_one()
        self.installation_id.appliquer_parcelles(self.parcelle_ids)
        return {"type": "ir.actions.client", "tag": "soft_reload"}
