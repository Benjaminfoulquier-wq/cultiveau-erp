from markupsafe import Markup, escape

from odoo import api, fields, models

from .agent import recommander


class ResPartner(models.Model):
    _inherit = "res.partner"

    cultiveau_persona_evaluation_ids = fields.One2many("cultiveau.persona.evaluation", "partner_id", string="Évaluations de persona")
    cultiveau_persona_id = fields.Many2one("cultiveau.persona", "Persona", compute="_compute_persona", store=True)
    cultiveau_persona_date = fields.Datetime("Persona évalué le", compute="_compute_persona", store=True)
    cultiveau_persona_animal = fields.Char(related="cultiveau_persona_id.animal")
    cultiveau_persona_surnom = fields.Char(related="cultiveau_persona_id.surnom")
    cultiveau_persona_resume = fields.Char(related="cultiveau_persona_id.resume")
    cultiveau_persona_maslow = fields.Selection(related="cultiveau_persona_id.maslow")
    cultiveau_persona_approche = fields.Text(related="cultiveau_persona_id.approche")
    cultiveau_persona_arguments = fields.Html(related="cultiveau_persona_id.arguments")
    cultiveau_persona_canal = fields.Char(related="cultiveau_persona_id.canal")
    cultiveau_persona_moment = fields.Char(related="cultiveau_persona_id.moment")
    cultiveau_persona_pieges = fields.Html(related="cultiveau_persona_id.pieges")
    cultiveau_persona_couleur = fields.Char(related="cultiveau_persona_id.couleur")
    cultiveau_agent_html = fields.Html("L'Agent", compute="_compute_agent", sanitize=False,
                                       help="La recommandation du mois : persona × frise × cours.")

    @api.depends("cultiveau_persona_evaluation_ids.persona_id", "cultiveau_persona_evaluation_ids.date")
    def _compute_persona(self):
        for p in self:
            derniere = p.cultiveau_persona_evaluation_ids.sorted(lambda e: (e.date, e.id), reverse=True)[:1]
            p.cultiveau_persona_id = derniere.persona_id
            p.cultiveau_persona_date = derniere.date

    def cultiveau_recommandation(self, mois=None):
        """Ce que l'Agent conseille ce mois-ci pour ce client : timing, ton, approche, pièges."""
        self.ensure_one()
        situation = self.cultiveau_situation(mois) if self.cultiveau_culture_ids else {}
        persona = self.cultiveau_persona_id.pour_agent() if self.cultiveau_persona_id else None
        reco = recommander(persona, situation)
        reco["situation"] = situation
        return reco

    @api.depends("cultiveau_persona_id", "cultiveau_culture_ids", "cultiveau_culture_ids.culture_id.cours_tendance")
    def _compute_agent(self):
        for p in self:
            r = p.cultiveau_recommandation()
            if not p.cultiveau_culture_ids and not p.cultiveau_persona_id:
                p.cultiveau_agent_html = Markup("<p class='text-muted'>L'Agent n'a rien à dire tant qu'il ne connaît ni le persona ni les cultures.</p>")
                continue
            lignes = [f"<p style='margin:0 0 4px'><b>{escape(r['resume'])}</b></p>",
                      f"<p style='margin:0 0 4px'>⏱ <b>Quand</b> : {escape(r['timing'])}</p>"]
            if not p.cultiveau_culture_ids:
                lignes.append("<p style='margin:0 0 4px;color:#8a5e3c'>Sans culture renseignée, le moment est celui du calendrier, pas de sa frise.</p>")
            if r["ton"]:
                lignes.append(f"<p style='margin:0 0 4px'>🎯 <b>Le ton</b> : {escape(r['ton'])}</p>")
            if r["approche"]:
                lignes.append(f"<p style='margin:0 0 4px'>🧭 <b>L'approche</b> : {escape(r['approche'])}</p>")
            if r["eviter"]:
                lignes.append("<p style='margin:0'>⛔ <b>Éviter</b> : " + " · ".join(escape(e) for e in r["eviter"]) + "</p>")
            p.cultiveau_agent_html = Markup("".join(lignes))

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
        return {"code": p.code, "nom": p.name, "animal": p.animal or "", "surnom": p.surnom or "", "resume": p.resume or "",
                "maslow": p.maslow or "", "approche": p.approche or "", "canal": p.canal or "", "moment": p.moment or ""}

    def cultiveau_agent_pour_api(self):
        """La recommandation de l'Agent pour l'assistant : il adapte son ton et sait s'il doit déranger."""
        self.ensure_one()
        r = self.cultiveau_recommandation()
        return {"resume": r["resume"], "quand": r["timing"], "ton": r["ton"], "approche": r["approche"], "eviter": r["eviter"],
                "posture": r["posture"], "periode_critique": r["critique"], "cours": r["cours"]}
