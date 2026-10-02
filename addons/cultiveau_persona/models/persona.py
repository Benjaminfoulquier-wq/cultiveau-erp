import re

from markupsafe import Markup

from odoo import api, fields, models

from .questionnaire import ORDRE, QUESTIONS, scorer

# La pyramide de Maslow de l'agriculteur (Cultiveau, 2025) : le besoin dominant que chaque persona cherche à satisfaire.
MASLOW = [
    ("1", "1. Viabilité économique — vivre de son travail, rentabilité immédiate, payer les factures"),
    ("2", "2. Sécurité — réduire l'incertitude et la charge mentale : fiabilité, visibilité, moins de risques"),
    ("3", "3. Appartenance — briser l'isolement du dirigeant : soutien humain, entraide entre pairs"),
    ("4", "4. Estime — être respecté et écouté : reconnaissance, fierté du métier"),
    ("5", "5. Accomplissement — transmettre et être maître de soi : autonomie, pérennité, laisser une exploitation saine"),
]


class Persona(models.Model):
    _name = "cultiveau.persona"
    _description = "Persona client"
    _order = "sequence, name"

    code = fields.Char(required=True)
    name = fields.Char("Persona", required=True)
    animal = fields.Char("Animal", help="L'animal de l'étude PRISM : 🦁 🐆 🐈 🐢 🐝.")
    surnom = fields.Char("En deux mots", help="Le leader, l'opportuniste, le routinier, le fidèle, le collaboratif.")
    couleur = fields.Char(default="#1d3a52")
    sequence = fields.Integer(default=10)
    resume = fields.Char("En une phrase")
    maslow = fields.Selection(MASLOW, "Besoin dominant (Maslow)", help="Le niveau de la pyramide de Maslow de l'agriculteur que ce persona cherche d'abord à satisfaire.")
    profil = fields.Html("Le profil dans l'étude", sanitize=True, help="Ce que l'étude PRISM 2023 dit de ce groupe : exploitation, âge, état d'esprit, pratiques.")
    signes = fields.Html("Comment on le reconnaît", sanitize=True)
    approche = fields.Text("Comment l'aborder")
    arguments = fields.Html("Les arguments qui portent", sanitize=True)
    canal = fields.Char("Le bon canal")
    moment = fields.Char("Le bon moment")
    pieges = fields.Html("Les pièges", sanitize=True)
    source = fields.Char("Source", default="Étude PRISM 2023 (BVA, Réussir, Agriconomie) · Journées Cultiveau 2025")
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

    def pour_agent(self):
        """Le persona sous forme de dictionnaire pour l'Agent et l'API."""
        self.ensure_one()
        morceaux = re.split(r"</li>|<br\s*/?>|\n", str(self.pieges or ""))
        pieges = [Markup(m).striptags().strip() for m in morceaux]
        return {"code": self.code, "name": self.name, "animal": self.animal or "", "surnom": self.surnom or "", "resume": self.resume or "",
                "maslow": self.maslow or "", "approche": self.approche or "", "canal": self.canal or "", "moment": self.moment or "",
                "pieges_texte": [p for p in pieges if p]}

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
