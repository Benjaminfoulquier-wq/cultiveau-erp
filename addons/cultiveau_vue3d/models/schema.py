"""Le schéma de câblage dessiné dans l'éditeur (armoire de l'atelier, Map vivante).

Le dessin vit dans un JSON : `composants` [{id, type, x, y, repere, nom, valeurs}] et `fils`
[{id, de: {c, b}, a: {c, b}, num, section, longueur}]. Le serveur ne fait que le garder, par société : la palette,
le tracé et les contrôles (référentiel § 11.2 et 11.3) sont dans `static/src/js/schema.js`.
"""
import json

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SchemaCablage(models.Model):
    _name = "cultiveau.schema.cablage"
    _description = "Schéma de câblage"
    _order = "write_date desc, id desc"

    name = fields.Char("Nom", required=True, default="Nouveau schéma")
    company_id = fields.Many2one("res.company", "Société", required=True, default=lambda self: self.env.company, index=True)
    partner_id = fields.Many2one("res.partner", "Client")
    donnees = fields.Text("Dessin (JSON)", default='{"composants": [], "fils": []}')
    nb_composants = fields.Integer("Appareils", compute="_compute_nb", store=True)
    active = fields.Boolean(default=True)

    @api.depends("donnees")
    def _compute_nb(self):
        for schema in self:
            try:
                schema.nb_composants = len(json.loads(schema.donnees or "{}").get("composants") or [])
            except (ValueError, AttributeError):
                schema.nb_composants = 0

    @api.constrains("donnees")
    def _verifier_donnees(self):
        for schema in self:
            try:
                dessin = json.loads(schema.donnees or "{}")
            except ValueError:
                raise ValidationError("Le dessin du schéma est illisible.")
            if not isinstance(dessin, dict) or not isinstance(dessin.get("composants", []), list) or not isinstance(dessin.get("fils", []), list):
                raise ValidationError("Le dessin du schéma est illisible.")
