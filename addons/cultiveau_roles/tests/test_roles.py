from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "cultiveau")
class TestRoles(TransactionCase):
    def _a(self, user, xmlid):
        return self.env.ref(xmlid) in user.groups_id

    def test_role_pose_les_droits(self):
        u = self.env["res.users"].create({"name": "Léa Technicienne", "login": "lea@example.test", "cultiveau_role": "technicien"})
        self.assertTrue(self._a(u, "cultiveau_base.group_adherent"))
        self.assertTrue(self._a(u, "stock.group_stock_user"))
        self.assertTrue(self._a(u, "project.group_project_user"))
        self.assertFalse(self._a(u, "account.group_account_invoice"))
        self.assertFalse(self._a(u, "sales_team.group_sale_manager"))
        u.cultiveau_role = "gerant"
        self.assertTrue(self._a(u, "sales_team.group_sale_manager"))
        self.assertTrue(self._a(u, "account.group_account_manager"))
        self.assertTrue(self._a(u, "stock.group_stock_manager"))
        u.cultiveau_role = "administratif"
        self.assertTrue(self._a(u, "account.group_account_invoice"))
        self.assertFalse(self._a(u, "sales_team.group_sale_manager"))
        self.assertFalse(self._a(u, "stock.group_stock_manager"))
        # un groupe hors des rôles, réglé à la main, survit au changement de rôle
        u.groups_id = [(4, self.env.ref("base.group_no_one").id)]
        u.cultiveau_role = "commercial"
        self.assertTrue(self._a(u, "base.group_no_one"))
        self.assertTrue(self._a(u, "sales_team.group_sale_salesman_all_leads"))

    def test_salarie_recoit_son_acces(self):
        e = self.env["hr.employee"].create({"name": "Paul Poseur", "work_email": "paul.poseur@example.test", "cultiveau_role_propose": "technicien", "company_id": self.env.company.id})
        e.action_creer_acces()
        self.assertTrue(e.user_id)
        self.assertEqual(e.user_id.login, "paul.poseur@example.test")
        self.assertEqual(e.user_id.cultiveau_role, "technicien")
        self.assertTrue(self._a(e.user_id, "project.group_project_user"))
        with self.assertRaises(UserError):
            e.action_creer_acces()
        sans = self.env["hr.employee"].create({"name": "Sans mail", "company_id": self.env.company.id})
        with self.assertRaises(UserError):
            sans.action_creer_acces()

    def test_aide_par_ecran(self):
        A = self.env["cultiveau.aide"]
        a = A.pour("cultiveau_vue3d.action_map", "cultiveau.map")
        self.assertEqual(a["nom"], "Map vivante")
        b = A.pour("sale.action_quotations_with_onboarding", "sale.order")
        self.assertEqual(b["nom"], "Devis")
        self.assertIn("nomenclature", b["texte"].lower())
        g = A.pour("x.y", "modele.inconnu")
        self.assertEqual(g["nom"], "Les gestes qui font gagner du temps")  # le repli : les gestes d'Odoo
