from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    cultiveau_persona_evaluation_ids = fields.One2many("cultiveau.persona.evaluation", "partner_id", string="Évaluations de persona")
    cultiveau_persona_id = fields.Many2one("cultiveau.persona", "Persona", compute="_compute_persona", store=True)
    cultiveau_persona_date = fields.Datetime("Persona évalué le", compute="_compute_persona", store=True)
    cultiveau_persona_resume = fields.Char(related="cultiveau_persona_id.resume")
    cultiveau_persona_approche = fields.Text(related="cultiveau_persona_id.approche")
    cultiveau_persona_arguments = fields.Html(related="cultiveau_persona_id.arguments")
    cultiveau_persona_canal = fields.Char(related="cultiveau_persona_id.canal")
    cultiveau_persona_moment = fields.Char(related="cultiveau_persona_id.moment")
    cultiveau_persona_pieges = fields.Html(related="cultiveau_persona_id.pieges")
    cultiveau_persona_couleur = fields.Char(related="cultiveau_persona_id.couleur")

    @api.depends("cultiveau_persona_evaluation_ids.persona_id", "cultiveau_persona_evaluation_ids.date")
    def _compute_persona(self):
        for p in self:
            derniere = p.cultiveau_persona_evaluation_ids.sorted(lambda e: (e.date, e.id), reverse=True)[:1]
            p.cultiveau_persona_id = derniere.persona_id
            p.cultiveau_persona_date = derniere.date

    def action_evaluer_persona(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "name": f"Persona — {self.display_name}", "res_model": "cultiveau.persona.wizard",
                "view_mode": "form", "target": "new", "context": {"default_partner_id": self.id}}

    def cultiveau_persona_pour_api(self):
        """Ce que l'assistant téléphonique a besoin de savoir avant de parler au client."""
        self.ensure_one()
        p = self.cultiveau_persona_id
        if not p:
            return None
        return {"code": p.code, "nom": p.name, "resume": p.resume, "approche": p.approche, "canal": p.canal, "moment": p.moment}
