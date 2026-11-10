from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

CLIENTS = {"success": True, "total": 2, "clients": [
    {"id": 101, "civilite": "M.", "nom": "Dupont-Site", "prenom": "Jean", "entreprise": "EARL Exemple Site", "adresse": "1 chemin des Vergers",
     "codePostal": "30100", "ville": "Alès", "telephonePortable": "0698761101", "email": "jean.site@exemple.fr", "isActive": 1},
    {"id": 102, "nom": "Martin-Site", "prenom": "Paul", "telephone": "0466000102", "isActive": 1},
]}
INTERVENTIONS = {"success": True, "total": 1, "limit": 200, "offset": 0, "interventions": [
    {"id": 2001, "reference": "FI-2001", "clientName": "Jean Dupont-Site", "clientPhone": "06 98 76 11 01", "equipmentType": "Pompe",
     "equipmentBrand": "MarqueX", "interventionType": "depannage", "priority": "urgente", "status": "planifiee", "scheduledDate": "2026-10-20 08:00:00",
     "symptoms": "Baisse de pression", "workPerformed": None, "technicianName": "Technicien Exemple",
     "validationToken": "secret-a-ne-pas-garder", "ratingToken": "secret-2", "shortCode": "XYZ"}]}
CHANTIERS = {"success": True, "chantiers": [
    {"id": 31, "reference": "CH-31", "nom": "Goutte à goutte vigne", "clientName": "Paul Martin-Site", "clientPhone": "0466000102",
     "statut": "en_cours", "dateDebutPrevue": "2026-10-13", "dateFinPrevue": "2026-10-17", "adresseChantier": "Lieu-dit Exemple"}]}
BONS = {"success": True, "total": 1, "limit": 200, "offset": 0, "bons": [{"id": 501}]}
BON = {"success": True, "bon": {
    "id": 501, "numero": "BI-2026-0501", "dateIntervention": "2026-10-20", "statut": "valide", "clientId": 101, "clientNom": "Jean Dupont-Site",
    "ficheInterventionId": 2001, "chantierId": 31, "technicienNom": "Technicien Exemple", "totalArticlesHT": "120.00", "totalMOHT": "90.00",
    "totalDeplacementHT": "30.00", "totalHT": "240.00", "totalTVA": "48.00", "totalTTC": "288.00", "signeParLeClient": True, "signeParLeTechnicien": True,
    "exporte": False, "updatedAt": "2026-10-20 18:00:00",
    "articles": [{"reference": "REF-SITE-001", "designation": "Raccord exemple", "quantite": "2", "unite": "u", "prixUnitaireHT": "60.00", "remise": "0",
                  "tvaRate": "20", "totalHT": "120.00"}],
    "mainOeuvre": [{"description": "Dépannage", "dureeMinutes": 90, "tauxHoraire": "60.00", "uniteFacturation": "heure", "quantite": "1.5", "totalHT": "90.00"}],
    "heuresMachines": []}}


ARTICLES = {"success": True, "total": 2, "limit": 500, "offset": 0, "articles": [
    {"id": 9001, "reference": "REF-SITE-001", "ean": "3000000000011", "designation": "Raccord exemple 32 mm", "categorie": "Raccords", "marque": "Plasson",
     "prixUnitaireHT": "60.00", "unite": "u", "tvaRate": "20", "isActive": 1, "createdAt": "2026-10-01 10:00:00", "updatedAt": "2026-10-20 18:00:00"},
    {"id": 9002, "reference": "PE32-PN10", "ean": None, "designation": "Tube PE 32 PN10", "categorie": "Tubes", "marque": None,
     "prixUnitaireHT": "1.45", "unite": "m", "tvaRate": "20", "isActive": 1, "createdAt": "2026-10-01 10:00:00", "updatedAt": "2026-10-20 18:00:00"}]}


INVENTAIRES = {"success": True, "total": 1, "inventaires": [
    {"id": 5, "nom": "Inventaire de novembre", "validatedAt": "2026-11-07T10:00:00", "lignes": [
        {"articleId": 9001, "reference": "REF-SITE-001", "quantite": "12"},
        {"articleId": 9001, "reference": "REF-SITE-001", "quantite": "3", "zoneId": 2},  # le même article compté dans une autre zone : ça s'additionne
        {"reference": "PE32-PN10", "quantite": "250,5"},
        {"reference": "INCONNUE-XYZ", "quantite": "1"}]}]}


def faux_site(appels):
    def _appeler(self, chemin, params=None):
        appels.append((chemin, dict(params or {})))
        return {"clients": CLIENTS, "interventions": INTERVENTIONS, "chantiers": CHANTIERS, "bons-intervention": BONS,
                "bons-intervention/501": BON, "articles": ARTICLES, "entreprise": ENTREPRISE, "inventaires": INVENTAIRES}[chemin]
    return _appeler


ENTREPRISE = {"success": True, "entreprise": {"id": 120004, "nom": "Irrigation Sud", "logo_url": "https://site.test/api/adherent-image/77/logo"}}
PNG_1x1 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="


@tagged("post_install", "-at_install", "cultiveau")
class TestSite(TransactionCase):
    def test_synchronisation(self):
        societe = self.env.company
        connexion = self.env["cultiveau.site.connexion"].create({"company_id": societe.id, "cle": "cle-de-test"})
        appels = []
        with patch.object(type(connexion), "_appeler", faux_site(appels)):
            connexion._synchroniser()
        self.assertFalse(connexion.en_erreur, connexion.resultat)
        # l'inventaire validé sur cultiveau.fr est devenu le stock : 12 + 3 raccords, 250,5 m de tube ; la référence inconnue est signalée
        raccord = self.env["product.product"].search([("product_tmpl_id.cultiveau_site_ref", "=", f"{connexion.id}:9001")])
        tube = self.env["product.product"].search([("product_tmpl_id.cultiveau_site_ref", "=", f"{connexion.id}:9002")])
        self.assertEqual((raccord.qty_available, tube.qty_available), (15.0, 250.5))
        self.assertIn("1 inventaire(s) validé(s)", connexion.resultat)
        self.assertIn("INCONNUE-XYZ", connexion.resultat)
        self.assertTrue(connexion.curseur_inventaires)
        Partner = self.env["res.partner"]
        jean = Partner.search([("cultiveau_site_ref", "=", f"{connexion.id}:101")])
        self.assertEqual((jean.name, jean.exploitation, jean.city, jean.company_id), ("Jean Dupont-Site", "EARL Exemple Site", "Alès", societe))
        # l'intervention : retrouvée par la référence du site, rattachée au client par son téléphone, sans les jetons du site
        t = self.env["project.task"].search([("cultiveau_site_ref", "=", f"{connexion.id}:2001")])
        self.assertEqual((t.partner_id, t.cultiveau_nature, t.cultiveau_urgence, t.stage_id.name), (jean, "depannage", "immediate", "Planifiée"))
        self.assertIn("Baisse de pression", t.description)
        self.assertNotIn("secret-a-ne-pas-garder", t.description or "")
        # le chantier, avec son installation créée pour le client
        ch = self.env["cultiveau.chantier"].search([("cultiveau_site_ref", "=", f"{connexion.id}:31")])
        self.assertEqual((ch.etat, ch.partner_id.name, str(ch.date_debut)), ("en_cours", "Paul Martin-Site", "2026-10-13"))
        # le bon : client, intervention, chantier, montants et lignes
        bon = self.env["cultiveau.site.bon"].search([("connexion_id", "=", connexion.id)])
        self.assertEqual((bon.numero, bon.partner_id, bon.task_id, bon.chantier_id, bon.total_ttc), ("BI-2026-0501", jean, t, ch, 288.0))
        self.assertEqual(sorted(bon.ligne_ids.mapped("genre")), ["article", "mo"])
        self.assertTrue(connexion.curseur_clients and connexion.curseur_bons and connexion.curseur_articles)
        # les articles de « Clients & Articles » : dans le catalogue de la société, avec leur référence, prix, unité et famille
        Produit = self.env["product.template"]
        raccord = Produit.search([("cultiveau_site_ref", "=", f"{connexion.id}:9001")])
        self.assertEqual((raccord.default_code, raccord.list_price, raccord.company_id, raccord.categ_id.name, raccord.barcode), ("REF-SITE-001", 60.0, societe, "Raccords", "3000000000011"))
        tube = Produit.search([("cultiveau_site_ref", "=", f"{connexion.id}:9002")])
        self.assertEqual((tube.uom_id, tube.cultiveau_source), (self.env.ref("uom.product_uom_meter"), "site"))
        # le premier passage ne doit pas envoyer « updatedSince=False » (le site répondait 422 et rien n'arrivait)
        self.assertFalse([p for c, p in appels if p.get("updatedSince") is False])
        # une seconde passe ne crée rien en double, et ne relit que depuis le curseur
        avant = (Partner.search_count([("name", "like", "-Site")]), self.env["project.task"].search_count([("cultiveau_site_ref", "!=", False)]))
        with patch.object(type(connexion), "_appeler", faux_site(appels)):
            connexion._synchroniser()
        apres = (Partner.search_count([("name", "like", "-Site")]), self.env["project.task"].search_count([("cultiveau_site_ref", "!=", False)]))
        self.assertEqual(avant, apres)
        self.assertEqual(self.env["cultiveau.site.bon"].search_count([("connexion_id", "=", connexion.id)]), 1)
        self.assertTrue(any(c == "clients" and p.get("updatedSince") for c, p in appels))

    def test_le_logo_suit_l_espace_cultiveau_fr(self):
        """Un logo posé sur cultiveau.fr après la première entrée arrive quand même : la fiche est relue à chaque passage."""
        import base64
        import requests as req

        class Reponse:
            status_code = 200
            headers = {"Content-Type": "image/png"}
            content = base64.b64decode(PNG_1x1)
        images = []

        def get(url, timeout=20, **kw):
            images.append(url)
            return Reponse()
        societe = self.env["res.company"].create({"name": "Irrigation Sud (test logo)", "iap_enrich_auto_done": True})
        connexion = self.env["cultiveau.site.connexion"].create({"company_id": societe.id, "cle": "cle-de-test", "clients": False, "interventions": False,
                                                                  "chantiers": False, "bons": False, "articles": False})
        with patch.object(type(connexion), "_appeler", faux_site([])), patch.object(req, "get", get):
            connexion._synchroniser()
        self.assertFalse(connexion.en_erreur, connexion.resultat)
        self.assertEqual(images, ["https://site.test/api/adherent-image/77/logo"])
        self.assertEqual(societe.cultiveau_site_logo_url, "https://site.test/api/adherent-image/77/logo")
        self.assertTrue(societe.cultiveau_logo_choisi)
        # même adresse au passage suivant : l'image n'est pas redemandée
        with patch.object(type(connexion), "_appeler", faux_site([])), patch.object(req, "get", get):
            connexion._synchroniser()
        self.assertEqual(len(images), 1)

    def test_chaque_societe_a_son_entrepot(self):
        """Une société venue de cultiveau.fr n'avait pas d'entrepôt : aucun stock possible. Maintenant il est créé, au nom de la société."""
        societe = self.env["res.company"].create({"name": "Irrigation du Tarn (test entrepôt)", "iap_enrich_auto_done": True})
        self.env["stock.warehouse"].sudo().with_context(active_test=False).search([("company_id", "=", societe.id)]).write({"active": False})
        entrepot = societe.cultiveau_entrepot()
        self.assertTrue(entrepot.active and entrepot.lot_stock_id)
        self.assertEqual((entrepot.company_id, entrepot.name), (societe, "Irrigation du Tarn (test entrepôt)"))
        self.assertEqual(societe.cultiveau_entrepot(), entrepot)  # pas de doublon au passage suivant
        self.env["res.company"].cultiveau_entrepots_manquants()
        self.assertEqual(len(self.env["stock.warehouse"].search([("company_id", "=", societe.id)])), 1)

    def test_un_article_cree_dans_l_erp_arrive_dans_la_base(self):
        """Un article créé ou dont le prix de vente change dans l'ERP part dans la base Clients & Articles de cultiveau.fr ; le prix d'achat
        et ce que la synchronisation du site écrit ne repartent pas."""
        from ..models.chantier_site import Connexion as CxEnvoi
        societe = self.env.company
        cx = self.env["cultiveau.site.connexion"].create({"company_id": societe.id, "url": "https://site.test", "cle": "cle-de-test", "cultiveau_site_ecriture": True})
        envois = []

        def poster(self_, chemin, d):
            envois.append(("POST", chemin, d))
            return 201, {"success": True, "created": True, "article": {"id": 777, "reference": d["reference"]}}

        def modifier(self_, chemin, d):
            envois.append(("PATCH", chemin, d))
            return 200, {"success": True, "article": {"id": 777}}
        with patch.object(CxEnvoi, "_poster", poster), patch.object(type(cx), "_modifier", modifier):
            vanne = self.env["product.template"].create({"name": "Vanne 2 pouces", "default_code": "VAN-2", "list_price": 45.0, "standard_price": 30.0})
            self.assertEqual(vanne.company_id, societe, "l'article d'un adhérent relié est à lui")
            self.assertTrue(vanne.cultiveau_site_a_envoyer)
            self.assertEqual(vanne.cultiveau_envoyer_vers_site(), 1)
            self.assertEqual(vanne.cultiveau_site_ref, f"{cx.id}:777")
            self.assertFalse(vanne.cultiveau_site_a_envoyer)
            genre, chemin, d = envois[0]
            self.assertEqual((genre, chemin, d["reference"], d["designation"], d["prixUnitaireHT"]), ("POST", "articles", "VAN-2", "Vanne 2 pouces", 45.0))
            self.assertNotIn("standard_price", str(d))
            vanne.list_price = 49.0
            self.assertTrue(vanne.cultiveau_site_a_envoyer)
            self.assertEqual(vanne.cultiveau_envoyer_vers_site(), 1)
            self.assertEqual((envois[-1][0], envois[-1][1], envois[-1][2]["prixUnitaireHT"]), ("PATCH", "articles/777", 49.0))
            vanne.standard_price = 32.0  # le prix d'achat : affaire de l'ERP seulement
            self.assertFalse(vanne.cultiveau_site_a_envoyer)
            sans_ref = self.env["product.template"].create({"name": "Collier sans référence", "list_price": 3.0})
            sans_ref.cultiveau_envoyer_vers_site()
            self.assertEqual((sans_ref.default_code, envois[-1][2]["reference"]), (f"ERP-{sans_ref.id}", f"ERP-{sans_ref.id}"))
        # ce que la synchronisation du site écrit ne repart pas vers le site
        with patch.object(type(cx), "_appeler", faux_site([])):
            cx._synchroniser()
        raccord = self.env["product.template"].search([("cultiveau_site_ref", "=", f"{cx.id}:9001")])
        self.assertTrue(raccord)
        self.assertFalse(raccord.cultiveau_site_a_envoyer)

    def test_la_base_articles_montre_les_articles_de_la_societe(self):
        """L'écran Base articles s'ouvre sur les articles de la société (pas le catalogue commun à 1 €) ; les filtres existent."""
        action = self.env.ref("cultiveau_site.action_base_articles")
        self.assertEqual(action.context.get("search_default_mes_articles") if isinstance(action.context, dict) else eval(action.context).get("search_default_mes_articles"), 1)
        arch = self.env.ref("cultiveau_site.view_base_articles_search").arch
        self.assertIn("allowed_company_ids", arch)
        self.assertIn("catalogue_commun", arch)

    def test_la_fiche_du_site_nee_d_un_appel_rejoint_l_intervention_de_l_erp(self):
        """L'assistant a créé l'intervention dans l'ERP (réf. APL) et une fiche sur cultiveau.fr qui porte la même réf. : la synchro les rapproche."""
        societe = self.env.company
        if "cultiveau_reference_appel" not in self.env["project.task"]._fields:
            self.skipTest("module connecteurs absent")
        connexion = self.env["cultiveau.site.connexion"].create({"company_id": societe.id, "cle": "cle-de-test", "clients": False, "chantiers": False, "bons": False, "articles": False, "inventaires": False})
        projet = self.env["project.project"].cultiveau_projet_interventions(societe)
        tache = self.env["project.task"].create({"name": "Baisse de pression — appel", "project_id": projet.id, "company_id": societe.id, "cultiveau_reference_appel": "APL-abc123def4"})
        inter = dict(INTERVENTIONS["interventions"][0], problemDescription="[À VALIDER — assistant téléphonique · réf. APL-abc123def4] Baisse de pression")
        appels = []

        def _appeler(self_, chemin, params=None):
            appels.append(chemin)
            return {"interventions": {**INTERVENTIONS, "interventions": [inter]}, "entreprise": ENTREPRISE}[chemin]
        with patch.object(type(connexion), "_appeler", _appeler):
            connexion._synchroniser()
        self.assertFalse(connexion.en_erreur, connexion.resultat)
        self.assertIn("1 rapprochée(s)", connexion.resultat)
        tache.invalidate_recordset()
        self.assertEqual(tache.cultiveau_site_ref, f"{connexion.id}:{inter['id']}")
        self.assertEqual(self.env["project.task"].search_count([("cultiveau_site_ref", "=", f"{connexion.id}:{inter['id']}")]), 1)

    def test_sans_cle_rien_ne_casse(self):
        connexion = self.env["cultiveau.site.connexion"].create({"company_id": self.env.company.id})
        connexion._synchroniser()
        self.assertFalse(connexion.en_erreur)
        self.assertIn("clé", connexion.resultat)

    def test_erreur_notee(self):
        connexion = self.env["cultiveau.site.connexion"].create({"company_id": self.env.company.id, "cle": "cle-test"})

        def _appeler(self_, chemin, params=None):
            from odoo.exceptions import UserError
            raise UserError("Le site refuse la clé (absente, invalide ou révoquée).")
        with patch.object(type(connexion), "_appeler", _appeler):
            connexion._synchroniser()
        self.assertTrue(connexion.en_erreur)
        self.assertIn("refuse la clé", connexion.resultat)


    def test_cle_sans_droit_articles_remplacee(self):
        societe = self.env.company
        connexion = self.env["cultiveau.site.connexion"].create({"company_id": societe.id, "cle": "vieille", "cultiveau_site_adherent_id": 77,
                                                                 "clients": False, "interventions": False, "chantiers": False, "bons": False})
        etat = {"cle": "vieille"}

        def _appeler(self_, chemin, params=None):
            if etat["cle"] == "vieille":
                from odoo.exceptions import UserError
                raise UserError("La clé n'a pas le droit nécessaire (articles) : 403")
            return ARTICLES

        def redemander(self_):
            etat["cle"] = "neuve"
            return True
        with patch.object(type(connexion), "_appeler", _appeler), patch.object(type(connexion), "_cultiveau_redemander_cle", redemander):
            connexion._synchroniser()
        self.assertFalse(connexion.en_erreur, connexion.resultat)
        self.assertIn("2 article(s) lus", connexion.resultat)


class TestFacturerBonDuSite(TransactionCase):
    def _bon(self, **v):
        societe = self.env.company
        connexion = self.env["cultiveau.site.connexion"].search([("company_id", "=", societe.id)], limit=1) or self.env["cultiveau.site.connexion"].create(
            {"company_id": societe.id, "cle": "cle-de-test"})
        client = self.env["res.partner"].create({"name": "Client du bon"})
        return self.env["cultiveau.site.bon"].create({
            "connexion_id": connexion.id, "ref": v.pop("ref", "b1"), "numero": "BI-TEST-1", "date": "2026-11-03", "partner_id": client.id, "signe_client": True,
            "total_ht": 250.0, "total_deplacement_ht": 30.0, "statut": "signe",
            "ligne_ids": [(0, 0, {"genre": "article", "reference": "R1", "designation": "Vanne", "quantite": 2, "prix_unitaire_ht": 60.0, "remise": 0, "tva": 20, "total_ht": 120.0}),
                          (0, 0, {"genre": "mo", "designation": "Main-d'œuvre", "quantite": 2, "prix_unitaire_ht": 50.0, "total_ht": 100.0}),
                          (0, 0, {"genre": "machine", "designation": "Mini-pelle", "duree_minutes": 60})], **v})

    def test_un_bon_signe_devient_une_facture_brouillon(self):
        bon = self._bon()
        self.assertTrue(bon.a_facturer)
        bon.action_facturer()
        f = bon.invoice_id
        self.assertEqual((f.state, f.move_type, f.partner_id, f.amount_untaxed), ("draft", "out_invoice", bon.partner_id, 250.0))
        self.assertEqual(len(f.invoice_line_ids.filtered(lambda l: l.display_type == "product")), 3)  # vanne, main-d'œuvre, déplacement
        self.assertFalse(bon.a_facturer)
        with self.assertRaises(UserError):
            bon.action_facturer()  # jamais deux fois

    def test_un_bon_exporte_en_compta_n_est_pas_refacture_par_megarde(self):
        bon = self._bon(ref="b2", exporte=True)
        self.assertFalse(bon.a_facturer)
        with self.assertRaises(UserError):
            bon.action_facturer()
        bon.action_facturer_malgre_export()
        self.assertTrue(bon.invoice_id)

    def test_un_bon_non_signe_ne_se_facture_pas(self):
        bon = self._bon(ref="b3", signe_client=False)
        with self.assertRaises(UserError):
            bon.action_facturer()
