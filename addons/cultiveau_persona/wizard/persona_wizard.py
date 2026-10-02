from odoo import api, fields, models
from odoo.exceptions import UserError

from ..models.questionnaire import QUESTIONS, scorer, selection


class PersonaWizard(models.TransientModel):
    """Huit questions, et le persona apparaît."""

    _name = "cultiveau.persona.wizard"
    _description = "Questionnaire de persona"

    partner_id = fields.Many2one("res.partner", "Agriculteur", required=True)
    probleme = fields.Selection(selection=lambda self: selection("probleme"), string="Face à un problème technique, la première chose qu'il fait")
    achat = fields.Selection(selection=lambda self: selection("achat"), string="Pour un achat courant")
    relation = fields.Selection(selection=lambda self: selection("relation"), string="La relation qu'il attend de son fournisseur")
    strategie = fields.Selection(selection=lambda self: selection("strategie"), string="S'il devait choisir")
    moral = fields.Selection(selection=lambda self: selection("moral"), string="Son état d'esprit face à l'avenir")
    engagement = fields.Selection(selection=lambda self: selection("engagement"), string="L'exploitation")
    techno = fields.Selection(selection=lambda self: selection("techno"), string="Face aux nouvelles technologies")
    info = fields.Selection(selection=lambda self: selection("info"), string="Où il s'informe avant d'investir")
    persona_id = fields.Many2one("cultiveau.persona", "Persona", compute="_compute_persona")
    apercu = fields.Char("Aperçu", compute="_compute_persona")

    @api.model
    def default_get(self, champs):
        valeurs = super().default_get(champs)
        partner = self.env["res.partner"].browse(valeurs.get("partner_id") or self.env.context.get("default_partner_id"))
        derniere = partner.cultiveau_persona_evaluation_ids[:1] if partner else None
        if derniere and derniere.reponses:
            for q in QUESTIONS:
                if q["code"] in champs and derniere.reponses.get(q["code"]):
                    valeurs[q["code"]] = derniere.reponses[q["code"]]
        return valeurs

    def _reponses(self):
        return {q["code"]: self[q["code"]] for q in QUESTIONS if self[q["code"]]}

    @api.depends(*[q["code"] for q in QUESTIONS])
    def _compute_persona(self):
        personas = {p.code: p for p in self.env["cultiveau.persona"].search([])}
        for w in self:
            reponses = w._reponses()
            if len(reponses) < len(QUESTIONS):
                w.persona_id = False
                w.apercu = f"{len(reponses)} réponse(s) sur {len(QUESTIONS)}"
                continue
            code, scores = scorer(reponses)
            w.persona_id = personas.get(code)
            total = sum(scores.values()) or 1
            w.apercu = " · ".join(f"{personas[c].name if c in personas else c} {round(100 * n / total)} %" for c, n in scores.items())

    def action_valider(self):
        self.ensure_one()
        reponses = self._reponses()
        if len(reponses) < len(QUESTIONS):
            raise UserError("Répondez aux huit questions : le persona en dépend.")
        code, scores = scorer(reponses)
        persona = self.env["cultiveau.persona"].search([("code", "=", code)], limit=1)
        if not persona:
            raise UserError(f"Persona « {code} » introuvable : les données du module ne sont pas chargées.")
        evaluation = self.env["cultiveau.persona.evaluation"].create({
            "partner_id": self.partner_id.id, "persona_id": persona.id, "reponses": reponses, "scores": scores})
        self.partner_id.message_post(body=f"Persona évalué : <b>{persona.animal or ''} {persona.name}</b>, {persona.surnom or ''} — {persona.resume} ({evaluation.repartition}).")
        return {"type": "ir.actions.act_window", "res_model": "res.partner", "res_id": self.partner_id.id, "view_mode": "form"}
