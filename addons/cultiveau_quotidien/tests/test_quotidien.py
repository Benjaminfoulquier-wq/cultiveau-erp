from datetime import timedelta

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestQuotidien(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.s = cls.env.company
        groupes = [cls.env.ref("base.group_user").id, cls.env.ref("sales_team.group_sale_manager").id, cls.env.ref("project.group_project_user").id,
                   cls.env.ref("stock.group_stock_user").id, cls.env.ref("account.group_account_invoice").id, cls.env.ref("cultiveau_base.group_adherent").id]
        cls.gerant = cls.env["res.users"].create({"name": "Gaston Gérant", "login": "gaston-quot@test.fr", "email": "gaston-quot@test.fr", "company_id": cls.s.id,
                                                  "company_ids": [(6, 0, cls.s.ids)], "groups_id": [(6, 0, groupes)]})
        cls.chef = cls.env["res.users"].create({"name": "Charles Chef", "login": "charles-quot@test.fr", "company_id": cls.s.id, "company_ids": [(6, 0, cls.s.ids)],
                                                "groups_id": [(6, 0, [cls.env.ref("base.group_user").id, cls.env.ref("project.group_project_user").id])]})
        cls.client = cls.env["res.partner"].create({"name": "GAEC des Essais", "email": "gaec@essais-quot.fr"})
        cls.installation = cls.env["cultiveau.installation"].create({"name": "Pivot des Essais", "partner_id": cls.client.id, "type_systeme": "couverture_integrale", "company_id": cls.s.id})
        cls.chantier = cls.env["cultiveau.chantier"].create({"titre": "Pose pivot", "installation_id": cls.installation.id, "company_id": cls.s.id, "chef_id": cls.chef.id,
                                                             "etat": "en_cours", "phase_ids": [Command.create({"name": "Tranchée", "heures_prevues": 10})]})

    def _pointer(self, heures, user=None):
        self.env["cultiveau.chantier.pointage"].create({"chantier_id": self.chantier.id, "user_id": (user or self.chef).id, "heures": heures})

    def test_budget_d_heures(self):
        c = self.chantier
        self.assertEqual(c.budget_heures, 10)
        self._pointer(5)
        self.assertEqual((c.budget_pct, c.budget_palier, c.budget_etat), (50, 50, "ok"))
        self.assertTrue(self.env["cultiveau.evenement"].search_count([("genre", "=", "budget_chantier"), ("res_id", "=", c.id)]))
        self._pointer(3, self.gerant)
        self.assertEqual((c.budget_palier, c.budget_etat), (80, "attention"))
        self.assertIn(self.chef, c.activity_ids.user_id, "le chef de chantier est prévenu à 80 %")
        self._pointer(3)
        self.assertEqual((c.budget_palier, c.budget_etat), (100, "depasse"))
        poseurs = c.par_poseur()
        self.assertEqual(poseurs[0]["nom"], "Charles Chef")
        self.assertEqual(poseurs[0]["heures"], 8)
        self.assertEqual(poseurs[0]["part"], 80)
        fiche = self.env["cultiveau.map"].fiche("chantier", c.id)
        bloc = next(b for b in fiche["blocs"] if b["titre"] == "Budget d'heures")
        self.assertEqual(bloc["lignes"][0]["jauge"], 110)
        # l'écran « Aujourd'hui » du gérant le montre
        tuiles = self.env["cultiveau.aujourdhui"].with_user(self.gerant).tuiles()
        chantiers = next(t for t in tuiles if t["cle"] == "chantiers")
        self.assertEqual(chantiers["couleur"], "rouge")
        self.assertIn(c.id, [l["id"] for l in chantiers["lignes"]])

    def test_aujourdhui_devis_et_rapport(self):
        produit = self.env["product.product"].create({"name": "Vanne test", "list_price": 120})
        devis = self.env["sale.order"].create({"partner_id": self.client.id, "user_id": self.gerant.id, "order_line": [Command.create({"product_id": produit.id})]})
        devis.action_quotation_sent()
        self.env.flush_all()
        self.env.cr.execute("UPDATE sale_order SET write_date = %s WHERE id = %s", (fields.Datetime.now() - timedelta(days=10), devis.id))
        devis.invalidate_recordset()
        ecran = self.env["cultiveau.aujourdhui"].with_user(self.gerant).ecran()
        self.assertEqual(ecran["bonjour"], "Bonjour Gaston")
        tuile = next(t for t in ecran["tuiles"] if t["cle"] == "devis")
        self.assertIn(devis.id, [l["id"] for l in tuile["lignes"]])
        # le rapport du lundi
        n = self.env["cultiveau.rapport"].envoyer(self.s, self.gerant)
        self.assertEqual(n, 1)
        mail = self.env["mail.mail"].search([("email_to", "ilike", "gaston-quot@test.fr")], limit=1)
        self.assertIn("rapport du lundi", mail.subject)
        self.assertIn("Devis à relancer", str(mail.body_html))
        semaine = self.env["cultiveau.rapport"].semaine(self.s)
        self.assertIn("facture", semaine)

    def test_automatisations(self):
        Regle = self.env["cultiveau.regle"]
        Regle.preparer(self.s)
        regles = Regle.search([("company_id", "=", self.s.id)])
        self.assertEqual(len(regles), 10)
        self.assertFalse(any(regles.mapped("actif")), "rien ne s'active tout seul")
        relance = regles.filtered(lambda r: r.cle == "relance_devis")
        produit = self.env["product.product"].create({"name": "Goutteur test", "list_price": 1})
        devis = self.env["sale.order"].create({"partner_id": self.client.id, "user_id": self.chef.id, "order_line": [Command.create({"product_id": produit.id})]})
        devis.action_quotation_sent()
        self.env.flush_all()
        self.env.cr.execute("UPDATE sale_order SET write_date = %s WHERE id = %s", (fields.Datetime.now() - timedelta(days=10), devis.id))
        devis.invalidate_recordset()
        relance.actif = True
        self.assertEqual(relance._executer(), 1)
        self.assertIn(self.chef, devis.activity_ids.user_id)
        self.assertEqual(relance._executer(), 0, "une seule fois par devis")
        self.assertEqual(relance.trace_ids.res_id, devis.id)
        # l'envoi automatique au client
        devis2 = devis.copy({"user_id": self.chef.id})
        devis2.action_quotation_sent()
        self.env.flush_all()
        self.env.cr.execute("UPDATE sale_order SET write_date = %s WHERE id = %s", (fields.Datetime.now() - timedelta(days=10), devis2.id))
        devis2.invalidate_recordset()
        relance.envoi_auto = True
        relance._executer()
        self.assertTrue(any("Avez-vous pu le consulter" in (m.body or "") for m in devis2.message_ids))
        # un devis signé avec une installation devient un chantier
        if "cultiveau_installation_id" in devis._fields:
            commande = self.env["sale.order"].create({"partner_id": self.client.id, "cultiveau_installation_id": self.installation.id,
                                                      "order_line": [Command.create({"product_id": produit.id})]})
            commande.action_confirm()
            chantier_regle = regles.filtered(lambda r: r.cle == "devis_signe_chantier")
            if "cultiveau_heures_pose" in commande._fields:
                commande.cultiveau_heures_pose = 12
            chantier_regle._executer()
            self.assertTrue(commande.cultiveau_chantier_ids)

    def test_mathis(self):
        Mathis = self.env["cultiveau.mathis"].with_user(self.gerant)
        noms = {o["function"]["name"] for o in Mathis._outils()}
        self.assertTrue({"a_faire", "budget_chantiers"} <= noms)
        self._pointer(9)
        res, _a = Mathis._executer("budget_chantiers", {"chantier_id": self.chantier.id})
        self.assertEqual(res[0]["pct"], 90)
        portes = self.env["cultiveau.map"].with_user(self.gerant)._portes()
        self.assertEqual(portes["administratif"][0]["cle"], "aujourdhui")
