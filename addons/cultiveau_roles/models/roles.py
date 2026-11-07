"""Les rôles : un mot sur l'utilisateur, les bons droits dans les bonnes applications."""
from odoo import api, fields, models
from odoo.exceptions import UserError

ROLES = [("gerant", "Gérant"), ("administratif", "Administratif"), ("technicien", "Technicien / poseur"), ("magasinier", "Magasinier"), ("commercial", "Commercial"), ("libre", "Réglage à la main")]

# rôle -> groupes (identifiants externes) ; un groupe absent (module non installé) est ignoré
GROUPES = {
    "gerant": ["cultiveau_base.group_adherent", "sales_team.group_sale_manager", "account.group_account_manager", "account.group_account_invoice", "purchase.group_purchase_manager",
               "stock.group_stock_manager", "project.group_project_manager", "hr.group_hr_user", "hr_holidays.group_hr_holidays_manager", "hr_expense.group_hr_expense_manager",
               "base.group_partner_manager"],
    "administratif": ["cultiveau_base.group_adherent", "sales_team.group_sale_salesman_all_leads", "account.group_account_invoice", "purchase.group_purchase_user", "stock.group_stock_user",
                      "project.group_project_user", "hr.group_hr_user", "base.group_partner_manager"],
    "technicien": ["cultiveau_base.group_adherent", "sales_team.group_sale_salesman", "stock.group_stock_user", "project.group_project_user", "hr_expense.group_hr_expense_user"],
    "magasinier": ["cultiveau_base.group_adherent", "stock.group_stock_manager", "purchase.group_purchase_user", "sales_team.group_sale_salesman", "project.group_project_user"],
    "commercial": ["cultiveau_base.group_adherent", "sales_team.group_sale_salesman_all_leads", "project.group_project_user", "stock.group_stock_user", "base.group_partner_manager"],
}


class Users(models.Model):
    _inherit = "res.users"

    cultiveau_role = fields.Selection(ROLES, "Rôle Cultiveau", default="libre", help="Le rôle règle les droits dans les applications d'un coup. « Réglage à la main » ne touche à rien.")

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS

    def _cultiveau_groupes_roles(self):
        """Tous les groupes que les rôles manipulent : on ne retire que ceux-là, jamais un groupe réglé à la main hors de cet ensemble."""
        tous = set()
        for xmlids in GROUPES.values():
            for x in xmlids:
                g = self.env.ref(x, raise_if_not_found=False)
                if g:
                    tous.add(g.id)
        return self.env["res.groups"].browse(list(tous))

    def cultiveau_appliquer_role(self):
        for u in self.filtered(lambda u: u.cultiveau_role and u.cultiveau_role != "libre"):
            voulus = self.env["res.groups"]
            for x in GROUPES[u.cultiveau_role]:
                g = self.env.ref(x, raise_if_not_found=False)
                if g:
                    voulus |= g
            tous = self._cultiveau_groupes_roles()
            garder = u.groups_id - tous
            u.sudo().write({"groups_id": [(6, 0, (garder | voulus | self.env.ref("base.group_user")).ids)]})
        return True

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        users.cultiveau_appliquer_role()
        return users

    def write(self, vals):
        res = super().write(vals)
        if "cultiveau_role" in vals:
            self.cultiveau_appliquer_role()
        return res


class Employee(models.Model):
    _inherit = "hr.employee"

    cultiveau_role_propose = fields.Selection(ROLES, "Rôle pour son accès", default="technicien")

    def action_creer_acces(self):
        """Un salarié sans accès reçoit son utilisateur, avec son rôle, et l'invitation par e-mail."""
        self.ensure_one()
        if self.user_id:
            raise UserError(f"{self.name} a déjà un accès ({self.user_id.login}).")
        courriel = self.work_email or self.private_email
        if not courriel:
            raise UserError("Renseignez son e-mail professionnel : c'est son identifiant et l'invitation part dessus.")
        if self.env["res.users"].sudo().with_context(active_test=False).search_count([("login", "=", courriel)]):
            raise UserError(f"Un utilisateur existe déjà avec l'identifiant {courriel} : reliez-le à la fiche (champ Utilisateur).")
        role = self.cultiveau_role_propose if self.cultiveau_role_propose != "libre" else "technicien"
        # create_employee_id : le module RH relie l'utilisateur à cette fiche au lieu d'en créer une seconde
        user = self.env["res.users"].sudo().with_context(no_reset_password=True).create({
            "name": self.name, "login": courriel, "email": courriel, "company_id": self.company_id.id, "company_ids": [(6, 0, [self.company_id.id])], "cultiveau_role": role,
            "create_employee_id": self.id})
        if self.user_id != user:
            self.user_id = user
        try:
            user.sudo().action_reset_password()
            envoi = "invitation envoyée par e-mail"
        except Exception as e:  # noqa: BLE001 : sans serveur de courriel, l'accès existe quand même
            envoi = f"invitation non envoyée ({e}) : utilisez « Envoyer une invitation » sur l'utilisateur"
        self.message_post(body=f"Accès créé : {courriel}, rôle {dict(ROLES)[role]}, {envoi}.")
        return {"type": "ir.actions.act_window", "res_model": "res.users", "res_id": user.id, "view_mode": "form"}
