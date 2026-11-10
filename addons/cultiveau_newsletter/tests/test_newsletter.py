from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "cultiveau")
class TestNewsletter(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.mais = cls.env["cultiveau.culture"].search([("name", "ilike", "Maïs grain")], limit=1) or cls.env["cultiveau.culture"].create(
            {"name": "Maïs grain", "categorie": "grandes_cultures", "kc_mi": 1.2, "racines_max": 1.7, "p_tarissement": 0.55,
             "duree_ini": 20, "duree_dev": 35, "duree_mi": 40, "duree_fin": 30})
        cls.agri = cls.env["res.partner"].create({"name": "Ferme du Maïs", "cultiveau_type": "agriculteur", "email": "ferme.mais@exemple.fr", "company_id": cls.company.id})
        cls.env["cultiveau.culture.client"].create({"partner_id": cls.agri.id, "culture_id": cls.mais.id, "surface_ha": 20})

    def _creer(self, **vals):
        wiz = self.env["cultiveau.newsletter"].create(vals)
        action = wiz.action_creer()
        return self.env["mailing.mailing"].browse(action["res_id"])

    def test_newsletter_culture_ciblee_et_ancree(self):
        m = self._creer(genre="culture", culture_id=self.mais.id, titre="Vos besoins en eau : Maïs grain", cibler=True)
        self.assertEqual(m.state, "draft")  # brouillon, jamais envoyé
        self.assertIn("Membre du réseau Cultiveau", m.body_arch)
        self.assertIn("A2.1", m.body_arch)          # ancrage référentiel
        self.assertIn("6 à 8 mm/j", m.body_arch)     # besoin de pointe du maïs
        self.assertIn("16.2.1", m.body_arch)         # pilotage par bilan hydrique
        self.assertIn(str(self.mais.id), m.mailing_domain)  # ciblé sur les agriculteurs de cette culture
        # l'agriculteur du maïs est bien dans la cible
        partenaires = self.env["res.partner"].search(eval(m.mailing_domain))  # noqa: S307 — domaine que l'on vient d'écrire
        self.assertIn(self.agri, partenaires)

    def test_newsletter_famille(self):
        m = self._creer(genre="famille", categorie="grandes_cultures")
        self.assertIn("Membre du réseau Cultiveau", m.body_arch)
        self.assertIn("grandes_cultures", m.mailing_domain)

    def test_newsletter_saison_hivernage(self):
        m = self._creer(genre="saison", theme="hivernage")
        self.assertIn("18.5", m.body_arch)   # § hivernage du référentiel
        self.assertIn("hivern", m.body_arch.lower())

    def test_newsletter_vierge_pour_la_sienne(self):
        m = self._creer(genre="vierge", titre="Ma newsletter de novembre")
        self.assertIn("Canva", m.body_arch)
        self.assertIn("Membre du réseau Cultiveau", m.body_arch)
