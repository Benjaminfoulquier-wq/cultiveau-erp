import base64
from datetime import date

from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from ..models import formats

OFX = b"""OFXHEADER:100
DATA:OFXSGML
<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><BANKTRANLIST>
<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20260305120000<TRNAMT>1200.00<FITID>2026030501<NAME>VIR SEPA DUPONT<MEMO>FACTURE 12</STMTTRN>
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260306<TRNAMT>-12.50<FITID>2026030602<NAME>FRAIS TENUE DE COMPTE</STMTTRN>
</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>"""

CAMT = b"""<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.02"><BkToCstmrStmt><Stmt>
<Bal><Tp><CdOrPrtry><Cd>OPBD</Cd></CdOrPrtry></Tp><Amt Ccy="EUR">1000.00</Amt><CdtDbtInd>CRDT</CdtDbtInd></Bal>
<Bal><Tp><CdOrPrtry><Cd>CLBD</Cd></CdOrPrtry></Tp><Amt Ccy="EUR">2187.50</Amt><CdtDbtInd>CRDT</CdtDbtInd></Bal>
<Ntry><Amt Ccy="EUR">1200.00</Amt><CdtDbtInd>CRDT</CdtDbtInd><BookgDt><Dt>2026-03-05</Dt></BookgDt><AcctSvcrRef>REF001</AcctSvcrRef>
 <NtryDtls><TxDtls><RltdPties><Dbtr><Nm>SARL DUPONT IRRIGATION</Nm></Dbtr></RltdPties><RmtInf><Ustrd>FACTURE 12</Ustrd></RmtInf></TxDtls></NtryDtls></Ntry>
<Ntry><Amt Ccy="EUR">12.50</Amt><CdtDbtInd>DBIT</CdtDbtInd><BookgDt><Dt>2026-03-06</Dt></BookgDt><AcctSvcrRef>REF002</AcctSvcrRef><AddtlNtryInf>FRAIS TENUE DE COMPTE</AddtlNtryInf></Ntry>
</Stmt></BkToCstmrStmt></Document>"""

QIF = b"""!Type:Bank
D05/03/2026
T1200,00
PVIR SEPA DUPONT
MFACTURE 12
^
D06/03/2026
T-12.50
PFRAIS TENUE DE COMPTE
^
"""


@tagged("post_install", "-at_install")
class TestCompta(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.societe = cls.env["res.company"].create({"name": "Adhérent Compta Test", "company_registry": "123 456 789 00011"})
        cls.societe.cultiveau_mettre_en_place_compta()
        cls.env = cls.env(context={**cls.env.context, "allowed_company_ids": [cls.societe.id]})
        cls.env.user.company_ids |= cls.societe
        cls.client = cls.env["res.partner"].create({"name": "SARL Dupont Irrigation", "company_id": cls.societe.id})
        cls.fournisseur = cls.env["res.partner"].create({"name": "Fournisseur Tuyaux", "company_id": cls.societe.id})
        aujourdhui = fields.Date.today()
        cls.jour = aujourdhui.replace(day=10)
        cls.facture = cls._facture("out_invoice", cls.client, 1000, "Station de pompage")
        cls.achat = cls._facture("in_invoice", cls.fournisseur, 500, "Tuyau PE")

    @classmethod
    def _facture(cls, genre, tiers, ht, libelle, jour=None):
        societe = cls.societe
        taxe = societe.account_sale_tax_id if genre.startswith("out") else societe.account_purchase_tax_id
        facture = cls.env["account.move"].with_company(societe).create({
            "move_type": genre, "partner_id": tiers.id, "invoice_date": jour or cls.jour, "date": jour or cls.jour, "company_id": societe.id,
            "invoice_line_ids": [Command.create({"name": libelle, "quantity": 1, "price_unit": ht, "tax_ids": [Command.set(taxe.ids)]})]})
        facture.action_post()
        return facture

    def _csv(self, lignes):
        texte = "Date;Libellé;Montant\n" + "".join(f"{d:%d/%m/%Y};{lib};{m}\n" for d, lib, m in lignes)
        return texte.encode("cp1252")

    def _importer(self, contenu, nom="releve.csv"):
        banque = self.env["account.journal"].search([("company_id", "=", self.societe.id), ("type", "=", "bank"), ("code", "!=", "CHQ")], limit=1)
        assistant = self.env["cultiveau.import.releve"].with_company(self.societe).create({"journal_id": banque.id, "company_id": self.societe.id,
                                                                                          "fichier": base64.b64encode(contenu), "nom_fichier": nom})
        action = assistant.action_importer()
        return self.env["account.bank.statement.line"].search(action["domain"] + [("journal_id", "=", banque.id)]) | self.env["account.bank.statement.line"].search([("journal_id", "=", banque.id)])

    # ---------------------------------------------------------------- mise en place

    def test_mise_en_place(self):
        s = self.societe
        self.assertEqual(s.chart_template, "fr")
        self.assertEqual(s.account_sale_tax_id.amount, 20)
        journaux = {j.code: j for j in self.env["account.journal"].search([("company_id", "=", s.id)])}
        self.assertEqual(journaux["CHQ"].name, "Chèques")
        self.assertEqual(journaux["CHQ"].default_account_id.code, "511200")
        self.assertIn(journaux["INV"].name, ("Ventes", "Factures clients"))
        modeles = self.env["account.reconcile.model"].search([("company_id", "=", s.id), ("name", "=", "Frais bancaires")])
        self.assertEqual(modeles.line_ids.account_id.code, "627800")
        self.assertEqual(s.cultiveau_siren(), "123456789")
        # relancer ne crée rien en double
        s.cultiveau_mettre_en_place_compta()
        self.assertEqual(self.env["account.journal"].search_count([("company_id", "=", s.id), ("code", "=", "CHQ")]), 1)

    # ---------------------------------------------------------------- lecture des relevés

    def test_lecture_formats(self):
        for nom, contenu in (("releve.ofx", OFX), ("releve.xml", CAMT), ("releve.qif", QIF)):
            lignes, debut, fin = formats.lire(nom, contenu)
            self.assertEqual([l["montant"] for l in lignes], [1200.0, -12.5], nom)
            self.assertEqual(lignes[0]["date"], date(2026, 3, 5), nom)
            self.assertIn("DUPONT", lignes[0]["libelle"], nom)
            self.assertIn("FRAIS", lignes[1]["libelle"], nom)
        lignes, debut, fin = formats.lire("releve.xml", CAMT)
        self.assertEqual((debut, fin), (1000.0, 2187.5))
        # un CSV « débit / crédit » d'une autre banque, avec un préambule
        csv = "Relevé du compte 00012345\n\nDate opération;Date valeur;Libellé;Débit;Crédit\n05/03/2026;05/03/2026;VIR DUPONT;;1 200,00\n06/03/2026;06/03/2026;FRAIS;12,50;\n".encode("cp1252")
        lignes, _, _ = formats.lire("export.csv", csv)
        self.assertEqual([(l["montant"], l["libelle"]) for l in lignes], [(1200.0, "VIR DUPONT"), (-12.5, "FRAIS")])
        self.assertEqual(formats.lire_montant("(1.234,56)"), -1234.56)
        self.assertEqual(formats.lire_montant("1,234.56"), 1234.56)

    # ---------------------------------------------------------------- rapprochement

    def test_import_et_rapprochement(self):
        j = self.jour
        lignes = self._importer(self._csv([(j, "VIR SEPA SARL DUPONT IRRIGATION STATION", "1200,00"), (j, "FRAIS TENUE DE COMPTE", "-12,50"),
                                           (j, "PRLV SEPA FOURNISSEUR TUYAUX", "-600,00"), (j, "CB CARBURANT TOTAL", "-80,00")]))
        self.assertEqual(len(lignes), 4)
        par_libelle = {l.payment_ref: l for l in lignes}
        self.assertTrue(par_libelle["VIR SEPA SARL DUPONT IRRIGATION STATION"].is_reconciled, "le virement du client paie sa facture tout seul")
        self.assertEqual(self.facture.payment_state, "paid")
        self.assertEqual(self.achat.payment_state, "paid")
        frais = par_libelle["FRAIS TENUE DE COMPTE"]
        self.assertEqual((frais.is_reconciled, frais.cultiveau_confiance, frais.cultiveau_modele_id.name), (False, "probable", "Frais bancaires"))
        frais.action_valider_proposition()
        self.assertTrue(frais.is_reconciled)
        self.assertIn("627800", frais.move_id.line_ids.mapped("account_id.code"))
        carburant = par_libelle["CB CARBURANT TOTAL"]
        self.assertEqual(carburant.cultiveau_confiance, "aucune")
        compte = self.env["account.account"].with_company(self.societe).search([("company_ids", "in", self.societe.id), ("code", "=", "606100")], limit=1)
        carburant.cultiveau_passer_sur_compte(compte, None, "Gazole", self.societe.account_purchase_tax_id, ttc=True)
        self.assertTrue(carburant.is_reconciled)
        codes = carburant.move_id.line_ids.mapped("account_id.code")
        self.assertIn("606100", codes)
        self.assertIn("445660", codes, "la TVA déductible est séparée")
        self.assertAlmostEqual(sum(carburant.move_id.line_ids.filtered(lambda l: l.account_id.code == "606100").mapped("debit")), 66.67, places=2)
        # le même fichier une seconde fois : rien n'est importé deux fois
        with self.assertRaises(UserError):
            self._importer(self._csv([(j, "VIR SEPA SARL DUPONT IRRIGATION STATION", "1200,00")]))
        # défaire remet la ligne en attente
        frais.action_defaire()
        self.assertFalse(frais.is_reconciled)
        self.assertEqual(frais.cultiveau_confiance, "probable")

    def test_choix_de_facture_et_acompte(self):
        j = self.jour
        autre = self._facture("out_invoice", self.client, 250, "Programmateur")
        lignes = self._importer(self._csv([(j, "VIR INCONNU", "1500,00"), (j, "VIR ACOMPTE NOUVEAU PROJET", "500,00")]))
        inconnu = lignes.filtered(lambda l: l.payment_ref == "VIR INCONNU")
        self.assertFalse(inconnu.is_reconciled)
        choix = self.env["cultiveau.rapprochement.choix"].create({"ligne_id": inconnu.id, "partner_id": self.client.id,
                                                                  "aml_ids": [Command.set((self.facture + autre).line_ids.filtered("cultiveau_a_lettrer").ids)]})
        self.assertAlmostEqual(choix.total, 1500)
        choix.action_rapprocher()
        self.assertTrue(inconnu.is_reconciled)
        self.assertEqual((self.facture.payment_state, autre.payment_state), ("paid", "paid"))
        acompte = lignes.filtered(lambda l: l.payment_ref == "VIR ACOMPTE NOUVEAU PROJET")
        acompte.partner_id = self.client
        acompte.action_acompte()
        self.assertTrue(acompte.is_reconciled)
        ligne_411 = acompte.move_id.line_ids.filtered(lambda l: l.account_id.account_type == "asset_receivable")
        self.assertEqual((ligne_411.partner_id, ligne_411.credit), (self.client, 500))
        self.assertTrue(ligne_411.cultiveau_a_lettrer)

    # ---------------------------------------------------------------- lettrage

    def test_lettrage_auto(self):
        f2 = self._facture("out_invoice", self.client, 250, "Programmateur")
        f3 = self._facture("out_invoice", self.client, 100, "Vanne")
        od = self.env["account.journal"].search([("company_id", "=", self.societe.id), ("type", "=", "general")], limit=1)
        banque = self.env["account.account"].with_company(self.societe).search([("company_ids", "in", self.societe.id), ("code", "=like", "512%")], limit=1)
        compte_client = self.client.with_company(self.societe).property_account_receivable_id

        def reglement(montant, libelle):
            m = self.env["account.move"].with_company(self.societe).create({"journal_id": od.id, "date": self.jour, "line_ids": [
                Command.create({"account_id": banque.id, "debit": montant, "name": libelle}),
                Command.create({"account_id": compte_client.id, "partner_id": self.client.id, "credit": montant, "name": libelle})]})
            m.action_post()
            return m
        reglement(1200, "REGLEMENT")                       # même montant que la facture de 1000 HT
        reglement(420, "VIREMENT " + f2.name + " " + f3.name)  # cite deux factures (300 + 120)
        n = self.env["account.move.line"].cultiveau_lettrer_auto(self.societe)
        self.assertEqual(n, 5)
        self.assertEqual((self.facture.payment_state, f2.payment_state, f3.payment_state), ("paid", "paid", "paid"))
        self.assertFalse(self.env["account.move.line"].search([("company_id", "=", self.societe.id), ("cultiveau_a_lettrer", "=", True), ("partner_id", "=", self.client.id)]))

    # ---------------------------------------------------------------- TVA

    def test_tva(self):
        debut, fin = self.jour.replace(day=1), (self.jour.replace(day=28) + __import__("datetime").timedelta(days=4)).replace(day=1) - __import__("datetime").timedelta(days=1)
        tva = self.env["cultiveau.tva"].with_company(self.societe).create({"company_id": self.societe.id, "date_debut": debut, "date_fin": fin})
        tva.action_calculer()
        cases = {l.code: l.montant for l in tva.ligne_ids}
        self.assertEqual((cases["box_A1"], cases["box_08_base"], cases["box_08_taxe"]), (1000, 1000, 200))
        self.assertEqual((cases["box_20"], cases["box_16"], cases["box_23"]), (100, 200, 100))
        self.assertEqual((cases["box_TD"], cases["box_28"], cases["box_32"], cases["box_25"]), (100, 100, 100, 0))
        self.assertEqual((tva.tva_due, tva.credit, tva.ca_ht), (100, 0, 1000))
        tva.action_valider()
        self.assertEqual(tva.etat, "validee")
        lignes = {l.account_id.code: (l.debit, l.credit) for l in tva.move_id.line_ids}
        self.assertEqual(lignes["445710"], (200, 0))
        self.assertEqual(lignes["445660"], (0, 100))
        self.assertEqual(lignes["445510"], (0, 100))
        self.assertEqual(self.societe.tax_lock_date, fin)
        # un crédit de TVA : gros achat, période suivante
        jour2 = fin + __import__("datetime").timedelta(days=3)
        self._facture("in_invoice", self.fournisseur, 2000, "Pompe", jour=jour2)
        tva2 = self.env["cultiveau.tva"].with_company(self.societe).create({"company_id": self.societe.id, "date_debut": jour2.replace(day=1),
                                                                             "date_fin": (jour2.replace(day=28) + __import__("datetime").timedelta(days=4)).replace(day=1) - __import__("datetime").timedelta(days=1)})
        tva2.action_calculer()
        self.assertEqual((tva2.tva_due, tva2.credit), (0, 400))
        tva2.action_valider()
        l2 = {l.account_id.code: (l.debit, l.credit) for l in tva2.move_id.line_ids}
        self.assertEqual(l2["445670"], (400, 0))
        # la période suivante reporte ce crédit
        tva3 = self.env["cultiveau.tva"].with_company(self.societe).create({"company_id": self.societe.id, "date_debut": tva2.date_fin + __import__("datetime").timedelta(days=1),
                                                                             "date_fin": tva2.date_fin + __import__("datetime").timedelta(days=28)})
        tva3.action_calculer()
        self.assertEqual(tva3.report_credit, 400)

    # ---------------------------------------------------------------- exports

    def test_fec_et_exports(self):
        Export = self.env["cultiveau.export.compta"]
        nom, contenu = Export.fec(self.societe, date(self.jour.year, 1, 1), date(self.jour.year, 12, 31))
        self.assertEqual(nom, f"123456789FEC{self.jour.year}1231.txt")
        lignes = contenu.decode().split("\r\n")
        self.assertEqual(lignes[0].split("|")[0:3], ["JournalCode", "JournalLib", "EcritureNum"])
        self.assertEqual(len(lignes[0].split("|")), 18)
        amls = self.env["account.move.line"].search([("company_id", "=", self.societe.id), ("parent_state", "=", "posted")])
        self.assertEqual(len(lignes) - 1, len(amls))
        debit = sum(float(l.split("|")[11].replace(",", ".")) for l in lignes[1:])
        credit = sum(float(l.split("|")[12].replace(",", ".")) for l in lignes[1:])
        self.assertAlmostEqual(debit, credit, places=2)
        self.assertTrue(any("C%d" % self.client.id in l for l in lignes[1:]), "le client est en compte auxiliaire")
        for genre in ("grand_livre", "balance", "journaux"):
            nom, contenu = getattr(Export, genre)(self.societe, date(self.jour.year, 1, 1), date(self.jour.year, 12, 31))
            self.assertTrue(nom.endswith(".csv") and len(contenu) > 50, genre)
        assistant = self.env["cultiveau.export.assistant"].create({"company_id": self.societe.id, "genre": "fec"})
        self.assertIn("/web/content/", assistant.action_exporter()["url"])

    def test_comptable(self):
        u = self.societe.cultiveau_inviter_comptable("cabinet@exemple.fr", "Cabinet Test")
        self.assertTrue(u.has_group("account.group_account_readonly"))
        self.assertFalse(u.has_group("account.group_account_invoice"))
        self.assertIn(self.societe, u.company_ids)
