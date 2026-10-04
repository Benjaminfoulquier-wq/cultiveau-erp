from odoo.tests import TransactionCase, tagged

RESEAU = {
    "reglages": {"cultiveau.url_assistant": "https://assistant.exemple.fr"},
    "groupe": [
        {"cle": "cultiveau", "principale": True, "name": "Réseau Essai", "forme": "SASU", "street": "1 rue du Réseau", "zip": "11000", "city": "Carcassonne",
         "siret": "939 408 449 00014", "vat": "FR66939408449", "email": "contact@exemple.fr", "website": "https://exemple.fr", "adherent": False},
        {"cle": "holding", "name": "Holding Essai", "cles": ["HOLDINGESSAI"], "street": "1 rue du Réseau", "zip": "11000", "city": "Carcassonne", "adherent": False, "note": "La holding."},
    ],
    "equipe": [
        {"email": "presidente@exemple.fr", "name": "Présidente Essai", "fonction": "Présidente", "mobile": "06 11 22 33 44", "societe": "cultiveau", "utilisateur": "equipe",
         "signature": "Présidente Essai · Réseau"},
        {"email": "informaticien@exemple.fr", "name": "Informaticien Essai", "fonction": "IA", "societe": "cultiveau", "utilisateur": None},
    ],
    "adherents": [
        {"name": "Irrigation du Sud Essai", "qualite": "Support", "secteur": "Sud-Est", "street": "2 ZI", "zip": "30800", "city": "Saint-Gilles", "email": "contact@sud-essai.fr",
         "phone": "04 66 00 00 00", "contacts": [{"name": "Laurent Dirigeant", "fonction": "Dirigeant", "email": "laurent@sud-essai.fr"}, {"name": "Rachid Achats", "fonction": "Achats"}]},
    ],
    "prospects": [{"name": "Prospect Essai", "zip": "13160", "city": "Châteaurenard", "contacts": [{"name": "Baptiste Prospect", "email": "b@prospect-essai.fr"}]}],
    "fournisseurs": [{"name": "Nelson Irrigation Essai", "cles": ["NELSONESSAI"], "country": "US", "website": "https://nelson.exemple",
                      "contacts": [{"name": "Guillaume Commercial", "fonction": "Responsable Europe", "email": "g@nelson.exemple", "mobile": "+33 6 35 72 23 36"}]}],
}


@tagged("post_install", "-at_install", "cultiveau")
class TestReseau(TransactionCase):
    def test_import_reseau_relancable(self):
        Moteur = self.env["cultiveau.reseau.moteur"]
        # Un fournisseur déjà créé par le catalogue, sous son nom court : il est reconnu, pas dupliqué.
        court = self.env["res.partner"].create({"name": "NELSONESSAI", "is_company": True, "supplier_rank": 1})
        # Une société créée par l'assistant sous son nom court : reconnue et renommée, pas doublée.
        self.env["res.company"].create({"name": "HOLDINGESSAI"})
        bilan = Moteur.importer(RESEAU)
        self.assertEqual((bilan["societes_odoo_creees"], bilan["societes_odoo_maj"]), (1, 2), bilan)
        self.assertEqual((bilan["utilisateurs_crees"], bilan["prospects"], bilan["erreurs"]), (1, 1, []))
        principale = self.env["res.company"].browse(1)
        self.assertEqual((principale.name, principale.partner_id.city, principale.partner_id.vat, principale.cultiveau_adherent), ("Réseau Essai", "Carcassonne", "FR66939408449", False))
        self.assertEqual(self.env["ir.config_parameter"].sudo().get_param("cultiveau.url_assistant"), "https://assistant.exemple.fr")
        holding = self.env["res.company"].search([("name", "=", "Holding Essai")])
        self.assertTrue(holding and not holding.cultiveau_adherent)
        self.assertFalse(self.env["res.company"].search([("name", "=", "HOLDINGESSAI")]))
        adherent = self.env["res.company"].search([("name", "=", "Irrigation du Sud Essai")])
        self.assertTrue(adherent.cultiveau_adherent)
        self.assertEqual((adherent.partner_id.cultiveau_type, adherent.partner_id.phone, adherent.partner_id.country_id.code), ("adherent", "+33466000000", "FR"))
        laurent = self.env["res.partner"].search([("email", "=", "laurent@sud-essai.fr")])
        self.assertEqual((laurent.parent_id, laurent.function, laurent.company_id.id), (adherent.partner_id, "Dirigeant", False))
        user = self.env["res.users"].search([("login", "=", "presidente@exemple.fr")])
        self.assertTrue(user and self.env.ref("cultiveau_base.group_equipe") in user.groups_id)
        self.assertEqual((user.partner_id.mobile, user.partner_id.function), ("+33611223344", "Présidente"))
        self.assertIn("Présidente Essai · Réseau", str(user.signature))
        self.assertTrue(holding in user.company_ids and adherent in user.company_ids)
        self.assertFalse(self.env["res.users"].search([("login", "=", "informaticien@exemple.fr")]))
        self.assertEqual(court.website, "https://nelson.exemple")
        self.assertEqual(court.child_ids.mapped("name"), ["Guillaume Commercial"])
        self.assertEqual(self.env["crm.lead"].search_count([("name", "=", "Adhésion — Prospect Essai")]), 1)
        # Relancé : rien n'est dupliqué.
        bilan = Moteur.importer(RESEAU)
        self.assertEqual((bilan["societes_odoo_creees"], bilan["contacts_crees"], bilan["utilisateurs_crees"], bilan["prospects"]), (0, 0, 0, 0), bilan)
        self.assertEqual(self.env["res.partner"].search_count([("name", "=", "Guillaume Commercial")]), 1)
        self.assertEqual(self.env["res.company"].search_count([("name", "=", "Irrigation du Sud Essai")]), 1)
