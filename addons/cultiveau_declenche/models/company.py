from odoo import fields, models


class Societe(models.Model):
    _inherit = "res.company"

    cultiveau_decl_chantier = fields.Boolean("Créer le chantier à la confirmation", default=True)
    cultiveau_decl_acompte = fields.Boolean("Préparer la facture d'acompte à la confirmation", default=True)
    cultiveau_decl_achats = fields.Boolean("Préparer les demandes de prix des manquants à la confirmation", default=True)
    cultiveau_decl_mise_en_service = fields.Boolean("Créer l'intervention de mise en service à la confirmation", default=True)


class Reglages(models.TransientModel):
    _inherit = "res.config.settings"

    cultiveau_decl_chantier = fields.Boolean(related="company_id.cultiveau_decl_chantier", readonly=False)
    cultiveau_decl_acompte = fields.Boolean(related="company_id.cultiveau_decl_acompte", readonly=False)
    cultiveau_decl_achats = fields.Boolean(related="company_id.cultiveau_decl_achats", readonly=False)
    cultiveau_decl_mise_en_service = fields.Boolean(related="company_id.cultiveau_decl_mise_en_service", readonly=False)
