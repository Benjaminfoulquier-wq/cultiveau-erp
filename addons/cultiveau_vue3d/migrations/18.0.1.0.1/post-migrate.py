"""Le quai de livraison disparaît de tous les plans, y compris ceux retouchés dans l'éditeur (une fois, à cette mise à jour)."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for plan in env["cultiveau.plan"].search([]):
        layout = dict(plan.layout or {})
        objets = layout.get("objets") or []
        restants = [o for o in objets if o.get("type") != "quai"]
        if len(restants) != len(objets):
            layout["objets"] = restants
            plan.layout = layout
