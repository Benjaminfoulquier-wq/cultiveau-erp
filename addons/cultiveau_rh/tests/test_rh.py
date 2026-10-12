import json
from datetime import date
from unittest import mock

from freezegun import freeze_time

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from ..models import frais as module_frais
from ..models.equipe import jours_feries, paques


def _reponse(donnees):
    return mock.Mock(status_code=200, json=lambda: donnees, raise_for_status=lambda: None)


@tagged("post_install", "-at_install")
class TestEquipe(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        groupe_user = cls.env.ref("base.group_user")
        cls.gerant = cls.env["res.users"].create({"name": "Gisèle Gérante", "login": "gerante-rh@test.fr", "email": "gerante-rh@test.fr",
                                                   "company_id": cls.company.id, "company_ids": [(6, 0, cls.company.ids)],
                                                   "groups_id": [(6, 0, [groupe_user.id, cls.env.ref("sales_team.group_sale_manager").id])]})
        cls.tech = cls.env["res.users"].create({"name": "Théo Technicien", "login": "tech-rh@test.fr", "email": "tech-rh@test.fr",
                                                 "company_id": cls.company.id, "company_ids": [(6, 0, cls.company.ids)],
                                                 "groups_id": [(6, 0, [groupe_user.id, cls.env.ref("project.group_project_user").id])]})
        cls.env["ir.config_parameter"].sudo().set_param("cultiveau.conges_jours_an", "25")
        with freeze_time("2026-10-14 08:00:00"):
            cls.env["cultiveau.equipe"].preparer(cls.company)

    # ---------------------------------------------------------------- la mise en place

    def test_jours_feries(self):
        self.assertEqual(paques(2026), date(2026, 4, 5))
        self.assertEqual(paques(2027), date(2027, 3, 28))
        feries = dict(jours_feries(2026))
        self.assertEqual(len(feries), 11)
        self.assertEqual(feries[date(2026, 4, 6)], "Lundi de Pâques")
        self.assertEqual(feries[date(2026, 5, 14)], "Ascension")
        self.assertEqual(feries[date(2026, 5, 25)], "Lundi de Pentecôte")
        poses = self.env["resource.calendar.leaves"].search([("company_id", "=", self.company.id), ("resource_id", "=", False), ("name", "=", "Armistice 1918")])
        self.assertTrue(poses, "les jours fériés sont posés sur l'agenda de la société")
        self.assertEqual(self.env["cultiveau.equipe"].poser_jours_feries(self.company, [2026]), 0, "pas de doublon")

    def test_preparation(self):
        Equipe = self.env["cultiveau.equipe"]
        e = Equipe.employe(self.tech, creer=False)
        self.assertTrue(e, "chaque personne a sa fiche salarié")
        self.assertEqual(e.leave_manager_id, self.gerant, "le gérant valide les congés")
        self.assertEqual(e.expense_manager_id, self.gerant, "et les notes de frais")
        self.assertTrue(self.gerant.has_group("hr_holidays.group_hr_holidays_user"))
        self.assertEqual(self.env.ref("hr_holidays.holiday_status_cl").with_context(lang="en_US").name, "Congés payés")
        with freeze_time("2026-10-14 08:00:00"):
            soldes = self.env["cultiveau.conges"].with_user(self.tech).soldes()
        cp = next(s for s in soldes if s["nom"] == "Congés payés")
        self.assertEqual(cp["acquis"], 25)
        # un nouvel utilisateur a sa fiche tout de suite
        nouveau = self.env["res.users"].create({"name": "Nina Nouvelle", "login": "nouvelle-rh@test.fr", "company_id": self.company.id,
                                                "company_ids": [(6, 0, self.company.ids)]})
        self.assertTrue(Equipe.employe(nouveau, creer=False))

    # ---------------------------------------------------------------- les congés

    @freeze_time("2026-10-14 08:00:00")
    def test_conge_demande_validation_map(self):
        Conges = self.env["cultiveau.conges"]
        # le technicien demande la semaine du 19 octobre
        c = Conges.with_user(self.tech).demander("conges_payes", "2026-10-19", "2026-10-23", motif="Vacances")
        self.assertEqual(c["jours"], 5)
        self.assertEqual(c["etat"], "confirm")
        evenement = self.env["cultiveau.evenement"].search([("genre", "=", "conge"), ("res_id", "=", c["id"])], limit=1)
        self.assertIn("Demande de congés", evenement.titre)
        # le gérant la voit et la valide en un clic
        a_valider = Conges.with_user(self.gerant).a_valider()
        self.assertIn(c["id"], [x["id"] for x in a_valider])
        res = Conges.with_user(self.gerant).decider(c["id"], True)
        self.assertEqual(res["conge"]["etat"], "validate")
        restant = next(s for s in Conges.with_user(self.tech).soldes() if s["nom"] == "Congés payés")["restant"]
        self.assertEqual(restant, 20)
        # un jour férié n'est pas décompté : le 11 novembre tombe un mercredi
        c2 = Conges.with_user(self.tech).demander("conges_payes", "2026-11-09", "2026-11-13")
        self.assertEqual(c2["jours"], 4)
        # les réunions évitent la semaine de congés
        creneaux = self.env["cultiveau.reunion"].with_user(self.gerant).creneaux([self.tech.id], 60, salle=False, jours=14, nombre=20)
        jours = {cr["debut"][:10] for cr in creneaux}
        self.assertFalse(jours & {"2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22", "2026-10-23"})

    @freeze_time("2026-10-14 08:00:00")
    def test_conge_en_cours_sur_la_map(self):
        Conges = self.env["cultiveau.conges"]
        c = Conges.with_user(self.tech).demander("conges_payes", "2026-10-14", "2026-10-16")
        Conges.with_user(self.gerant).decider(c["id"], True)
        v = self.env["cultiveau.map"].with_user(self.gerant).vivant()
        p = next(p for p in v["personnes"] if p["id"] == self.tech.id)
        self.assertEqual(p["statut"], "en_conges")
        self.assertIn("retour lundi 19 octobre", p["statut_nom"])
        fiche = self.env["cultiveau.map"].with_user(self.gerant).fiche("personne", self.tech.id)
        self.assertTrue(any(b["titre"] == "Congés" for b in fiche["blocs"]))

    @freeze_time("2026-10-14 08:00:00")
    def test_arret_maladie_reste_prive(self):
        Conges = self.env["cultiveau.conges"]
        c = Conges.with_user(self.tech).demander("maladie", "2026-10-15", "2026-10-15")
        Conges.with_user(self.gerant).decider(c["id"], True)
        collegue = self.env["res.users"].create({"name": "Colin Collègue", "login": "collegue-rh@test.fr", "company_id": self.company.id,
                                                 "company_ids": [(6, 0, self.company.ids)], "groups_id": [(6, 0, [self.env.ref("base.group_user").id])]})
        vu = Conges.with_user(collegue).absences("2026-10-15", "2026-10-15")
        ligne = next(x for x in vu if x["id"] == c["id"])
        self.assertEqual(ligne["type"], "Absence", "un collègue ne lit pas « arrêt maladie »")
        self.assertEqual(next(x for x in Conges.with_user(self.gerant).absences("2026-10-15") if x["id"] == c["id"])["type"], "Arrêt maladie")

    def test_demande_invalide(self):
        with freeze_time("2026-10-14 08:00:00"), self.assertRaises(UserError):
            self.env["cultiveau.conges"].with_user(self.tech).demander("conges_payes", "2026-10-17", "2026-10-18")  # un week-end

    # ---------------------------------------------------------------- les notes de frais

    def _lecture(self):
        ocr = _reponse({"pages": [{"index": 0, "markdown": "LE RELAIS DU MOULIN\n14/10/2026\n2 menus 23,50\nTVA 10% 2,14\nTOTAL TTC 23,50 EUR"}]})
        lu = {"date": "2026-10-14", "fournisseur": "Le Relais du Moulin", "total_ttc": 23.5, "devise": "EUR", "tva": [{"taux": 10, "montant": 2.14}],
              "categorie": "repas", "description": "Déjeuner 2 couverts", "confiance": "haute"}
        chat = _reponse({"choices": [{"message": {"content": json.dumps(lu)}}]})
        return [ocr, chat]

    @freeze_time("2026-10-14 08:00:00")
    def test_ticket_lu_envoye_valide(self):
        self.env["ir.config_parameter"].sudo().set_param("cultiveau.mistral_cle", "cle-test")
        Frais = self.env["cultiveau.frais"]
        with mock.patch.object(module_frais.requests, "post", side_effect=self._lecture()) as post:
            x = Frais.with_user(self.tech).depuis_photo("IMG_0042.jpg", b"\xff\xd8\xff photo", "image/jpeg")
        self.assertEqual(post.call_count, 2)
        self.assertIn("/ocr", post.call_args_list[0].args[0])
        self.assertEqual(x["lecture"], "lu")
        self.assertEqual(x["montant"], 23.5)
        self.assertEqual(x["cle"], "repas")
        self.assertEqual(x["date"], "2026-10-14")
        self.assertIn("Le Relais du Moulin", x["nom"])
        # l'envoi au gérant, puis la validation
        envoi = Frais.with_user(self.tech).envoyer()
        self.assertIn("23,50 €", envoi["message"])
        note = envoi["notes"][0]
        self.assertIn(note["id"], [f["id"] for f in Frais.with_user(self.gerant).a_valider()])
        res = Frais.with_user(self.gerant).decider(note["id"], True)
        self.assertEqual(res["note"]["etat"], "approve")
        self.assertTrue(self.env["cultiveau.evenement"].search_count([("genre", "=", "frais")]))

    def test_ticket_sans_cle_et_kilometres(self):
        self.env["ir.config_parameter"].sudo().set_param("cultiveau.mistral_cle", "")
        Frais = self.env["cultiveau.frais"]
        x = Frais.with_user(self.tech).depuis_photo("ticket.jpg", b"photo", "image/jpeg", montant="12,40", categorie="peage")
        self.assertEqual(x["montant"], 12.4)
        self.assertEqual(x["lecture"], "sans_cle")
        km = Frais.with_user(self.tech).depuis_photo(None, None, kilometres="100", note="Chantier Martin")
        self.assertEqual(km["cle"], "km")
        self.assertAlmostEqual(km["montant"], 63.6, places=1)

    # ---------------------------------------------------------------- Mathis et la page du téléphone

    @freeze_time("2026-10-14 08:00:00")
    def test_mathis_et_espace(self):
        Mathis = self.env["cultiveau.mathis"].with_user(self.tech)
        noms = {o["function"]["name"] for o in Mathis._outils()}
        self.assertTrue({"conges", "demander_conge", "decider_conge", "frais", "creer_frais", "envoyer_frais", "decider_frais"} <= noms)
        self.assertIn("demander_conge", Mathis._ecritures())
        res, action = Mathis._executer("demander_conge", {"type": "familial", "du": "2026-10-16"})
        self.assertEqual(action["modele"], "hr.leave")
        lecture, _a = Mathis._executer("conges", {})
        self.assertTrue(lecture["mes_demandes"])
        espace = self.env["cultiveau.equipe"].with_user(self.tech).espace()
        self.assertEqual(espace["prenom"], "Théo")
        self.assertFalse(espace["gerant"])
        self.assertTrue(espace["types"])
        gerant = self.env["cultiveau.equipe"].with_user(self.gerant).espace()
        self.assertTrue(gerant["gerant"])
        self.assertIn(res["id"], [c["id"] for c in gerant["a_valider"]["conges"]])
        portes = self.env["cultiveau.map"].with_user(self.gerant)._portes()
        self.assertIn("conges_a_valider", [p["cle"] for p in portes["administratif"]])
