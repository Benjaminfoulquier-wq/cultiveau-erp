from odoo import fields, models


class Registre(models.Model):
    """Le registre de maintenance (A1.8) : date, préventif / curatif, intervention ou relevé, intervenant."""

    _name = "cultiveau.registre"
    _description = "Registre de maintenance d'une installation (A1.8)"
    _order = "date desc, id desc"

    installation_id = fields.Many2one("cultiveau.installation", "Installation", required=True, ondelete="cascade", index=True)
    partner_id = fields.Many2one(related="installation_id.partner_id", store=True)
    company_id = fields.Many2one(related="installation_id.company_id", store=True)
    date = fields.Date(required=True, default=fields.Date.context_today)
    genre = fields.Selection([("preventif", "Préventif"), ("curatif", "Curatif (dépannage)"), ("releve", "Relevé (pressions, débits, compteur)"),
                              ("mise_en_service", "Mise en service"), ("remise_en_service", "Remise en service"), ("hivernage", "Hivernage"),
                              ("diagnostic", "Diagnostic (A1.7)"), ("modification", "Modification (A1.9)")], required=True, default="preventif")
    description = fields.Char("Intervention / relevé", required=True)
    releves = fields.Char("Valeurs relevées", help="Pressions, débits, kWh/m³, uniformité… à comparer au PV de mise en service.")
    intervenant = fields.Char("Intervenant")
    user_id = fields.Many2one("res.users", "Saisi par", default=lambda self: self.env.user)
    reference = fields.Char("Référence (intervention, appel, facture)")
