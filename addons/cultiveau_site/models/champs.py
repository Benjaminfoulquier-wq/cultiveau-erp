"""La référence de l'élément d'origine sur cultiveau.fr : « <connexion>:<identifiant du site> »."""
from odoo import fields, models


class Partner(models.Model):
    _inherit = "res.partner"

    cultiveau_site_ref = fields.Char("Référence cultiveau.fr", index=True, copy=False, readonly=True)


class Task(models.Model):
    _inherit = "project.task"

    cultiveau_site_ref = fields.Char("Référence cultiveau.fr", index=True, copy=False, readonly=True)
    cultiveau_site_bon_ids = fields.One2many("cultiveau.site.bon", "task_id", string="Bons du site")


class Chantier(models.Model):
    _inherit = "cultiveau.chantier"

    cultiveau_site_ref = fields.Char("Référence cultiveau.fr", index=True, copy=False, readonly=True)
    cultiveau_site_bon_ids = fields.One2many("cultiveau.site.bon", "chantier_id", string="Bons du site")


class Installation(models.Model):
    _inherit = "cultiveau.installation"

    cultiveau_site_ref = fields.Char("Référence cultiveau.fr", index=True, copy=False, readonly=True)
