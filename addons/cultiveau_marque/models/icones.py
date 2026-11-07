"""Les icônes des applications optionnelles (RH, flotte, sondages…) : posées si le module est là, à chaque mise à jour de la marque."""
from odoo import api, models

ICONES = {"project_todo.menu_todo_todos": "todo", "spreadsheet_dashboard.spreadsheet_dashboard_menu_root": "tableaux", "survey.menu_surveys": "sondages",
          "hr.menu_hr_root": "employes", "fleet.menu_root": "flotte", "hr_holidays.menu_hr_holidays_root": "conges", "hr_expense.menu_hr_expense_root": "depenses"}


class Menu(models.Model):
    _inherit = "ir.ui.menu"

    @api.model
    def cultiveau_poser_icones(self):
        n = 0
        for xmlid, nom in ICONES.items():
            m = self.env.ref(xmlid, raise_if_not_found=False)
            if m:
                m.web_icon = f"cultiveau_marque,static/src/img/apps/{nom}.png"
                n += 1
        return n
