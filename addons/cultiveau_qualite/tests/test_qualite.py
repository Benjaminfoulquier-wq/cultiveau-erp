from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "cultiveau")
class TestQualite(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        P = cls.env["res.partner"]
        cls.a = P.create({"name": "Earl Dupont", "city": "Alès", "phone": "06 11 22 33 44", "cultiveau_type": "agriculteur"})
        cls.b = P.create({"name": "EARL DUPONT", "city": "alès", "cultiveau_type": "agriculteur"})            # même nom, même commune
        cls.c = P.create({"name": "Mairie", "mobile": "+33 6 11 22 33 44", "cultiveau_type": "collectivite"})  # même téléphone que a
        cls.d = P.create({"name": "Paysages Verts", "cultiveau_type": "paysagiste", "email": "pv@example.test", "city": "Nîmes"})
        cls.sans_prix = cls.env["product.template"].create({"name": "Vanne sans prix", "list_price": 0, "type": "consu", "sale_ok": True, "company_id": cls.env.company.id, "is_storable": True})

    def test_controles(self):
        q = self.env["cultiveau.qualite"].create({"company_id": self.env.company.id})
        par_lib = {x[1]: x for x in q.controles()}
        doublons = next(v for k, v in par_lib.items() if k.startswith("Clients en doublon"))
        self.assertGreaterEqual(doublons[2], 3)
        ids = [t[2] for t in doublons[5] if t[0] == "id"][0]
        self.assertTrue({self.a.id, self.b.id, self.c.id} <= set(ids))
        sans_tel = next(v for k, v in par_lib.items() if k.startswith("Clients sans téléphone ni e-mail"))
        self.assertGreaterEqual(sans_tel[2], 1)
        sans_prix = next(v for k, v in par_lib.items() if k.startswith("Articles vendables sans prix"))
        self.assertGreaterEqual(sans_prix[2], 1)
        sans_fourn = next(v for k, v in par_lib.items() if k.startswith("Articles stockables sans fournisseur"))
        self.assertGreaterEqual(sans_fourn[2], 1)
        self.assertIn("/ 100", q.html)
        self.assertIn("Voir et corriger", q.html)
        self.assertGreater(q.nb_points, 0)

    def test_action_voir(self):
        q = self.env["cultiveau.qualite"].create({"company_id": self.env.company.id})
        ctrls = q.controles()
        i = next(i for i, x in enumerate(ctrls) if x[1].startswith("Articles vendables sans prix"))
        a = q.action_voir(i)
        self.assertEqual(a["res_model"], "product.template")
        self.assertIn(self.sans_prix, self.env["product.template"].search(a["domain"]))
        j = next(i for i, x in enumerate(ctrls) if x[0] == "Société")
        self.assertEqual(q.action_voir(j)["res_model"], "res.company")
        ouvert = self.env["cultiveau.qualite"].action_ouvrir()
        self.assertEqual(ouvert["res_model"], "cultiveau.qualite")
