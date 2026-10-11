from datetime import date

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPilotage(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.s = cls.env["res.company"].with_context(chart_template_load=True).create({"name": "Adhérent Pilotage", "cultiveau_adherent": True})
        cls.s.cultiveau_mettre_en_place_compta()
        cls.env.user.company_ids |= cls.s
        cls.env = cls.env(context={**cls.env.context, "allowed_company_ids": [cls.s.id]})
        cls.client = cls.env["res.partner"].create({"name": "Client P", "company_id": cls.s.id})
        cls.four = cls.env["res.partner"].create({"name": "Fournisseur P", "company_id": cls.s.id})
        cls.annee = fields.Date.today().year
        cls.jour = date(cls.annee, 3, 10)

    def _facture(self, genre, tiers, ht, jour=None, compte=None):
        taxe = self.s.account_sale_tax_id if genre.startswith("out") else self.s.account_purchase_tax_id
        ligne = {"name": "Ligne", "quantity": 1, "price_unit": ht, "tax_ids": [Command.set(taxe.ids)]}
        if compte:
            ligne["account_id"] = compte.id
        f = self.env["account.move"].with_company(self.s).create({"move_type": genre, "partner_id": tiers.id, "invoice_date": jour or self.jour, "date": jour or self.jour,
                                                                   "company_id": self.s.id, "invoice_line_ids": [Command.create(ligne)]})
        f.action_post()
        return f

    def test_etats_et_cloture(self):
        self._facture("out_invoice", self.client, 10000)
        self._facture("in_invoice", self.four, 4000)
        etats = self.env["cultiveau.etats"].create({"company_id": self.s.id, "date_debut": date(self.annee, 1, 1), "date_fin": date(self.annee, 12, 31)})
        etats.action_calculer()
        self.assertEqual((etats.chiffre_affaires, etats.resultat_net), (10000, 6000))
        b = etats.bilan(self.s, date(self.annee, 12, 31), 6000)
        self.assertAlmostEqual(b["total_actif"], b["total_passif"], places=2)
        self.assertAlmostEqual(dict(b["actif"])["Créances clients"], 12000)
        self.assertAlmostEqual(dict(b["passif"])["Dettes fournisseurs"], 4800)
        self.assertIn("Résultat net", etats.resultat_html)
        cloture = self.env["cultiveau.cloture"].create({"company_id": self.s.id, "date_debut": date(self.annee, 1, 1), "date_fin": date(self.annee, 12, 31)})
        cloture.action_cloturer()
        self.assertEqual((cloture.etat, cloture.resultat), ("cloturee", 6000))
        lignes = {l.account_id.code[:3]: (l.debit, l.credit) for l in cloture.move_id.line_ids}
        self.assertEqual(lignes["120"], (0, 6000))
        self.assertEqual(self.s.fiscalyear_lock_date, date(self.annee, 12, 31))
        # après clôture, les charges et produits de l'exercice sont à zéro
        from ..models.comptes import soldes, somme
        s = soldes(self.env, self.s, date(self.annee, 1, 1), date(self.annee, 12, 31))
        self.assertAlmostEqual(somme(s, ("6", "7")), 0.0, places=2)
        cloture.action_rouvrir()
        self.assertEqual(cloture.etat, "brouillon")

    def test_immobilisation(self):
        compte_215 = self.env["account.account"].with_company(self.s).search([("company_ids", "in", self.s.id), ("code", "=like", "2154%")], limit=1)
        facture = self._facture("in_invoice", self.four, 12000, jour=date(self.annee, 1, 15), compte=compte_215)
        self.assertTrue(facture.cultiveau_a_immobiliser)
        action = facture.action_cultiveau_immobiliser()
        immo = self.env["cultiveau.immobilisation"].search(action["domain"])
        self.assertEqual((len(immo), immo.valeur, immo.etat, immo.compte_id), (1, 12000, "en_cours", compte_215))
        self.assertTrue(immo.compte_amortissement_id.code.startswith("2815") and immo.compte_dotation_id.code.startswith("6811"))
        self.assertEqual(len(immo.ligne_ids), 61)  # 60 mois + le prorata du premier
        self.assertAlmostEqual(sum(immo.ligne_ids.mapped("montant")), 12000, places=2)
        self.assertAlmostEqual(immo.ligne_ids[1].montant, 200.0)
        immo.action_passer_dotations(date(self.annee, 4, 30))
        passees = immo.ligne_ids.filtered("move_id")
        self.assertEqual(len(passees), 4)
        self.assertTrue(all(m.state == "posted" for m in passees.move_id))
        self.assertAlmostEqual(immo.valeur_nette, 12000 - sum(passees.mapped("montant")), places=2)
        immo.action_sortir()
        self.assertEqual(immo.etat, "cedee")

    def test_tableau(self):
        self._facture("out_invoice", self.client, 2500, jour=fields.Date.today())
        tableau = self.env["cultiveau.tableau"].create({"company_id": self.s.id})
        html = str(tableau.html)
        self.assertIn("Chiffre d'affaires", html)
        self.assertIn("2 500 €", html)
        self.assertIn("<svg", html)
        self.env.user.groups_id |= self.env.ref("cultiveau_base.group_equipe")
        tableau.reseau = True
        self.assertIn("Le réseau", str(tableau.html))
