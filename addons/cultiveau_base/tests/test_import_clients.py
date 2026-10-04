from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "cultiveau")
class TestImportClients(TransactionCase):
    def test_import_csv_colonnes_libres(self):
        Moteur = self.env["cultiveau.import.clients.moteur"]
        csv = ("Liste clients 2026\n"
               "Client;Société;Tél. portable;Fixe;Mail;Adresse;CP;Ville;Statut;Surface ha;Suivi par;Remarque\n"
               "Durand Paul;EARL des Oliviers;06 12 34 56 78;04 66 00 00 00;Paul.Durand@exemple.fr;12 chemin des Prés;30100;Alès;client;35;;Rappeler\n"
               "Martin Jean;;0612345679;;;;30 000;Nîmes;prospect;;;\n"
               ";;;;;;;;;;;\n"
               "Pompes du Gard;;04 66 11 22 33;;;;30900;Nîmes;fournisseur;;;\n").encode("cp1252")
        bilan = Moteur.importer("clients.csv", csv)
        self.assertEqual((bilan["crees"], bilan["maj"], bilan["ignores"]), (3, 0, 0), bilan)
        self.assertEqual(bilan["inconnus"], [])
        Partner = self.env["res.partner"]
        paul = Partner.search([("name", "=", "Durand Paul")])
        self.assertEqual((paul.exploitation, paul.mobile, paul.phone, paul.email, paul.zip, paul.city),
                         ("EARL des Oliviers", "+33612345678", "+33466000000", "paul.durand@exemple.fr", "30100", "Alès"))
        self.assertEqual((paul.cultiveau_type, paul.company_id, paul.country_id.code, paul.departement), ("agriculteur", self.env.company, "FR", "30"))
        self.assertIn("Surface (ha) : 35", paul.comment)
        jean = Partner.search([("name", "=", "Martin Jean")])
        self.assertEqual((jean.zip, jean.cultiveau_type), ("30000", "agriculteur"))
        self.assertIn("Prospect", jean.category_id.mapped("name"))
        pompes = Partner.search([("name", "=", "Pompes du Gard")])
        self.assertEqual((pompes.cultiveau_type, pompes.supplier_rank), ("fournisseur", 1))
        # Relancé : même numéro → mis à jour, pas dupliqué ; l'e-mail complète la fiche.
        csv2 = "Nom;Portable;E-mail\nPaul Durand;+33 6 12 34 56 78;paul@oliviers.fr\nMartin Jean;06 12 34 56 79;\n".encode()
        bilan = Moteur.importer("clients.csv", csv2)
        self.assertEqual((bilan["crees"], bilan["maj"]), (0, 2))
        self.assertEqual(paul.email, "paul@oliviers.fr")
        self.assertEqual(Partner.search_count([("numero_court", "=", "33612345678")]), 1)
        bilan = Moteur.importer("clients.csv", csv2, mettre_a_jour=False)
        self.assertEqual((bilan["crees"], bilan["maj"], bilan["ignores"]), (0, 0, 2))

    def test_import_xlsx_et_fichier_illisible(self):
        import io

        import openpyxl

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Nom", "Prénom", "Téléphone", "Commune"])
        ws.append(["Durand (exemple)", "Paul", "0612345678", "Alès"])
        ws.append(["Roux", "Marie", 612345680, "Uzès"])  # Excel a mangé le 0
        sortie = io.BytesIO()
        wb.save(sortie)
        bilan = self.env["cultiveau.import.clients.moteur"].importer("clients.xlsx", sortie.getvalue())
        self.assertEqual((bilan["crees"], bilan["ignores"]), (1, 1))
        marie = self.env["res.partner"].search([("name", "=", "Marie Roux")])
        self.assertEqual((marie.mobile, marie.city), ("+33612345680", "Uzès"))
        with self.assertRaises(ValueError):
            self.env["cultiveau.import.clients.moteur"].importer("x.csv", b"Ville;Pays\nAles;France\n")
