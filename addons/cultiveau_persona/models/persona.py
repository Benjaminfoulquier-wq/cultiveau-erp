from odoo import fields, models

from .questionnaire import ORDRE, QUESTIONS, scorer


class Persona(models.Model):
    _name = "cultiveau.persona"
    _description = "Persona client"
    _order = "sequence, name"

    code = fields.Char(required=True)
    name = fields.Char("Persona", required=True)
    couleur = fields.Char(default="#1d3a52")
    sequence = fields.Integer(default=10)
    resume = fields.Char("En une phrase")
    signes = fields.Html("Comment on le reconnaît", sanitize=True)
    approche = fields.Text("Comment l'aborder")
    arguments = fields.Html("Les arguments qui portent", sanitize=True)
    canal = fields.Char("Le bon canal")
    moment = fields.Char("Le bon moment")
    pieges = fields.Html("Les pièges", sanitize=True)
    nb_clients = fields.Integer("Clients", compute="_compute_nb_clients")

    _sql_constraints = [("code_unique", "unique(code)", "Ce code de persona existe déjà.")]

    def _compute_nb_clients(self):
        groupes = self.env["res.partner"]._read_group([("cultiveau_persona_id", "in", self.ids)], ["cultiveau_persona_id"], ["__count"])
        compte = {p.id: n for p, n in groupes}
        for p in self:
            p.nb_clients = compte.get(p.id, 0)

    @classmethod
    def questionnaire(cls):
        return QUESTIONS

    @classmethod
    def scorer(cls, reponses):
        return scorer(reponses)

    def action_clients(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "name": f"Clients « {self.name} »", "res_model": "res.partner",
                "view_mode": "list,kanban,form", "domain": [("cultiveau_persona_id", "=", self.id)]}


class PersonaEvaluation(models.Model):
    _name = "cultiveau.persona.evaluation"
    _description = "Évaluation du persona d'un client"
    _order = "date desc, id desc"
    _rec_name = "persona_id"

    partner_id = fields.Many2one("res.partner", "Agriculteur", required=True, ondelete="cascade", index=True)
    persona_id = fields.Many2one("cultiveau.persona", "Persona", required=True, ondelete="restrict")
    date = fields.Datetime(default=fields.Datetime.now, required=True)
    user_id = fields.Many2one("res.users", "Évalué par", default=lambda self: self.env.user)
    reponses = fields.Json("Réponses")
    scores = fields.Json("Scores")
    repartition = fields.Char("Répartition", compute="_compute_repartition")
    company_id = fields.Many2one(related="partner_id.company_id", store=True)

    def _compute_repartition(self):
        noms = {p.code: p.name for p in self.env["cultiveau.persona"].search([])}
        for e in self:
            scores = e.scores or {}
            total = sum(scores.values()) or 1
            e.repartition = " · ".join(f"{noms.get(c, c)} {round(100 * scores.get(c, 0) / total)} %" for c in ORDRE if c in scores)
