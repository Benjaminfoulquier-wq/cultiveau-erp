"""La remise à zéro de la démonstration de la map : les pointages et événements joués disparaissent."""
from odoo import api, fields, models
from odoo.exceptions import UserError


class Map(models.AbstractModel):
    _inherit = "cultiveau.map"

    @api.model
    def reinitialiser_demo(self, regenerer_plan=False):
        """Efface ce que la démonstration a joué pour la société (pointages « démonstration », événements marqués démo) ;
        avec regenerer_plan, le plan revient au plan généré. Pour le gérant."""
        if not (self.env.user.has_group("sales_team.group_sale_manager") or self.env.user.has_group("base.group_system")):
            raise UserError("Seul le gérant remet la démonstration à zéro.")
        company = self.env.company
        pointages = self.env["cultiveau.pointage"].sudo().search([("company_id", "=", company.id), ("source", "=", "demo")])
        evenements = self.env["cultiveau.evenement"].sudo().search([("company_id", "=", company.id), "|", ("demo", "=", True), ("id", "in", pointages.evenement_id.ids)])
        n_p, n_e = len(pointages), len(evenements)
        pointages.unlink()
        evenements.unlink()
        if regenerer_plan:
            Plan = self.env["cultiveau.plan"].sudo()
            plan = Plan.search([("company_id", "=", company.id)], limit=1) if "company_id" in Plan._fields else Plan.browse()
            if plan and hasattr(plan, "action_regenerer"):
                plan.action_regenerer()
        self.env["cultiveau.audit"].noter(company, "suppression", resume=f"Démonstration remise à zéro : {n_p} pointage(s), {n_e} événement(s)")
        return {"message": f"Démonstration remise à zéro : {n_p} pointage(s) et {n_e} événement(s) effacés.", "pointages": n_p, "evenements": n_e}


class Settings(models.TransientModel):
    _inherit = "res.config.settings"

    def action_cultiveau_reinitialiser_demo(self):
        r = self.env["cultiveau.map"].reinitialiser_demo()
        return {"type": "ir.actions.client", "tag": "display_notification", "params": {"title": "Démonstration", "message": r["message"], "type": "success", "sticky": False}}


class SettingsAudit(models.TransientModel):
    _inherit = "res.config.settings"

    cultiveau_audit_annees = fields.Integer("Conserver le journal (années)", config_parameter="cultiveau.audit_annees", default=3)
