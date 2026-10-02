from odoo import api, fields, models

ETAPES = ["À planifier", "Planifiée", "En cours", "Terminée"]


class Project(models.Model):
    _inherit = "project.project"

    cultiveau_interventions = fields.Boolean("Projet des interventions Cultiveau", help="Le projet qui reçoit les interventions de cet adhérent.")

    @api.model
    def cultiveau_projet_interventions(self, company=None):
        """Le projet « Interventions » de la société (créé au besoin, avec ses étapes)."""
        company = company or self.env.company
        projet = self.sudo().search([("cultiveau_interventions", "=", True), ("company_id", "=", company.id)], limit=1)
        if projet:
            return projet
        Etape = self.env["project.task.type"].sudo()
        etapes = Etape.browse()
        for i, nom in enumerate(ETAPES):
            etape = Etape.search([("name", "=", nom), ("project_ids.cultiveau_interventions", "=", True), ("project_ids.company_id", "=", company.id)], limit=1)
            etapes |= etape or Etape.create({"name": nom, "sequence": (i + 1) * 10, "fold": nom == "Terminée"})
        return self.sudo().create({"name": "Interventions", "company_id": company.id, "cultiveau_interventions": True,
                                   "type_ids": [(6, 0, etapes.ids)], "privacy_visibility": "employees"})
