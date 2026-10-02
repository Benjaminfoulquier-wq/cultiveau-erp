"""Des quatre personas de la première version aux cinq animaux de l'étude PRISM.

Bâtisseur → Lion, Pilote → Jaguar, Fidèle → Tortue, Pragmatique → Chat ; les évaluations existantes
suivent (leurs scores restent ceux de l'ancien questionnaire : à refaire quand l'occasion se présente),
puis les anciens personas disparaissent.
"""
from odoo import SUPERUSER_ID, api

CORRESPONDANCE = {"batisseur": "lion", "pilote": "jaguar", "fidele": "tortue", "pragmatique": "chat"}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Persona = env["cultiveau.persona"]
    nouveaux = {p.code: p for p in Persona.search([("code", "in", list(CORRESPONDANCE.values()))])}
    for ancien_code, nouveau_code in CORRESPONDANCE.items():
        ancien = Persona.search([("code", "=", ancien_code)], limit=1)
        if not ancien or nouveau_code not in nouveaux:
            continue
        env["cultiveau.persona.evaluation"].search([("persona_id", "=", ancien.id)]).write({"persona_id": nouveaux[nouveau_code].id})
        env["ir.model.data"].search([("model", "=", "cultiveau.persona"), ("res_id", "=", ancien.id)]).unlink()
        ancien.unlink()
    env["res.partner"].search([("cultiveau_persona_evaluation_ids", "!=", False)])._compute_persona()
