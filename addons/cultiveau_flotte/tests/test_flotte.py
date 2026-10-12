from datetime import timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestFlotte(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.s = cls.env.company
        cls.gerant = cls.env["res.users"].create({"name": "Gilles Gérant", "login": "gilles-flotte@test.fr", "email": "gilles-flotte@test.fr", "company_id": cls.s.id,
                                                  "company_ids": [(6, 0, cls.s.ids)],
                                                  "groups_id": [(6, 0, [cls.env.ref("base.group_user").id, cls.env.ref("sales_team.group_sale_manager").id])]})
        cls.tech = cls.env["res.users"].create({"name": "Tom Technicien", "login": "tom-flotte@test.fr", "company_id": cls.s.id, "company_ids": [(6, 0, cls.s.ids)],
                                                "groups_id": [(6, 0, [cls.env.ref("base.group_user").id, cls.env.ref("project.group_project_user").id])]})
        cls.env["fleet.vehicle"]._cultiveau_preparer()
        marque = cls.env["fleet.vehicle.model.brand"].create({"name": "Marque test"})
        modele = cls.env["fleet.vehicle.model"].create({"name": "Fourgon test", "brand_id": marque.id})
        aujourd_hui = fields.Date.context_today(cls.env["fleet.vehicle"])
        cls.camion = cls.env["fleet.vehicle"].create({"model_id": modele.id, "license_plate": "AB-123-CD", "company_id": cls.s.id, "cultiveau_user_id": cls.tech.id,
                                                      "cultiveau_ct_prochain": aujourd_hui + timedelta(days=10), "cultiveau_entretien_km": 60000,
                                                      "cultiveau_entretien_date": aujourd_hui + timedelta(days=200)})

    def test_echeances_et_alertes(self):
        c = self.camion
        self.assertTrue(self.gerant.has_group("fleet.fleet_group_manager"))
        self.assertEqual(c.cultiveau_alerte, "bientot")
        self.assertIn("Contrôle technique", c.cultiveau_prochaine)
        self.env["fleet.vehicle"]._cron_cultiveau_alertes()
        self.assertTrue(c.activity_ids, "le gérant est prévenu")
        self.assertTrue(self.env["cultiveau.evenement"].search_count([("genre", "=", "flotte"), ("res_id", "=", c.id)]))
        n = len(c.activity_ids)
        self.env["fleet.vehicle"]._cron_cultiveau_alertes()
        self.assertEqual(len(c.activity_ids), n, "une seule alerte par échéance")
        tuiles = self.env["cultiveau.aujourdhui"].with_user(self.gerant).tuiles()
        self.assertIn("flotte", [t["cle"] for t in tuiles])

    def test_compteur_entretien_et_ct(self):
        c = self.camion
        c.relever_compteur(59500, self.tech)
        self.assertEqual(c.odometer, 59500)
        km = next(e for e in c.echeances() if e["nom"] == "Entretien (kilométrage)")
        self.assertEqual(km["etat"], "bientot")
        with self.assertRaises(ValidationError):
            c.relever_compteur(1000, self.tech)
        # un entretien fait fixe le suivant, un contrôle technique aussi
        self.env["fleet.vehicle.log.services"].create({"vehicle_id": c.id, "service_type_id": self.env.ref("cultiveau_flotte.type_entretien").id, "odometer": 60100,
                                                       "date": fields.Date.context_today(c)})
        self.assertEqual(c.cultiveau_entretien_km, 80100)
        self.env["fleet.vehicle.log.services"].create({"vehicle_id": c.id, "service_type_id": self.env.ref("cultiveau_flotte.type_controle_technique").id,
                                                       "date": fields.Date.context_today(c)})
        self.assertEqual(c.cultiveau_ct_prochain.year, fields.Date.context_today(c).year + 2)
        self.assertEqual(c.cultiveau_alerte, "ok")

    def test_carburant_map_telephone_mathis(self):
        x = self.env["cultiveau.frais"].with_user(self.tech).depuis_photo(None, None, montant="80", categorie="carburant", note="Gazole")
        depense = self.env["hr.expense"].browse(x["id"])
        self.assertEqual(depense.cultiveau_vehicule_id, self.camion)
        self.camion.invalidate_recordset()
        self.assertEqual(self.camion.cultiveau_carburant_mois, 80)
        espace = self.env["cultiveau.equipe"].with_user(self.tech).espace()
        self.assertEqual(espace["camion"]["plaque"], "AB-123-CD")
        # la page du téléphone (et sa partie « Mon camion ») se compile
        self.env["ir.qweb"]._compile("cultiveau_rh.moi")
        fiche = self.env["cultiveau.map"].with_user(self.gerant).fiche("camion", self.tech.id)
        bloc = next(b for b in fiche["blocs"] if b["titre"] == "Le véhicule")
        self.assertIn("AB-123-CD", bloc["lignes"][0]["texte"])
        res, _a = self.env["cultiveau.mathis"].with_user(self.gerant)._executer("flotte", {})
        self.assertIn("AB-123-CD", [v["plaque"] for v in res])
