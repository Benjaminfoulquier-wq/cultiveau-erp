from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "cultiveau")
class TestTableaux(TransactionCase):
    def test_action_interventions_par_technicien(self):
        T = self.env["cultiveau.tableau.demande"]
        a = T.action("interventions", "nombre", "technicien", None, "ce_mois", "barres")
        self.assertEqual(a["res_model"], "project.task")
        self.assertEqual(a["views"][0][1], "graph")
        self.assertEqual(a["context"]["graph_groupbys"], ["user_ids"])
        self.assertEqual(a["context"]["graph_mode"], "bar")
        self.assertTrue(any(d[0] == "cultiveau_debut" and d[1] == ">=" for d in a["domain"] if isinstance(d, tuple)))
        self.assertIn("Interventions", a["name"])
        self.assertIn("technicien", a["name"].lower())

    def test_mesure_et_groupe_invalides_retombent(self):
        T = self.env["cultiveau.tableau.demande"]
        a = T.action("devis", "kilometres", "technicien", "nature", "tout", "camembert")  # ni kilomètres ni technicien sur un devis
        self.assertEqual(a["context"]["graph_measure"], "__count__")
        self.assertEqual(a["context"]["graph_groupbys"], ["user_id"])  # le premier regroupement du sujet
        self.assertEqual(a["context"]["graph_mode"], "pie")
        with self.assertRaises(UserError):
            T.action("licornes")

    def test_tableau_croise_et_periode(self):
        T = self.env["cultiveau.tableau.demande"]
        a = T.action("factures", "montant", "client", "mois", "annee", "tableau")
        self.assertEqual(a["views"][0][1], "pivot")
        self.assertEqual(a["context"]["pivot_measures"], ["amount_untaxed_signed"])
        self.assertEqual(a["context"]["pivot_row_groupby"], ["partner_id"])
        self.assertEqual(a["context"]["pivot_column_groupby"], ["invoice_date:month"])
        self.assertTrue(any(d[0] == "invoice_date" for d in a["domain"] if isinstance(d, tuple)))

    def test_favori_et_mathis(self):
        res, action = self.env["cultiveau.mathis"]._executer("tableau", {"sujet": "commandes", "mesure": "montant", "regrouper_par": "mois", "periode": "12_mois", "graphique": "courbe", "enregistrer": True})
        self.assertEqual(action["type"], "action")
        self.assertEqual(action["action"]["res_model"], "sale.order")
        self.assertTrue(res.get("enregistre_dans_mes_tableaux"))
        f = self.env["cultiveau.tableau.favori"].browse(res["enregistre_dans_mes_tableaux"])
        self.assertEqual(f.user_id, self.env.user)
        a = f.action_ouvrir()
        self.assertEqual(a["context"]["graph_mode"], "line")
        self.assertIn("tableau", [o["function"]["name"] for o in self.env["cultiveau.mathis"]._outils()])
