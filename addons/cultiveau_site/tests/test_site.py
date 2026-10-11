from unittest.mock import patch

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


def faux_site(appels):
    def _appeler(self, chemin, params=None):
        appels.append((chemin, dict(params or {})))
        return {"clients": CLIENTS, "interventions": INTERVENTIONS, "chantiers": CHANTIERS, "bons-intervention": BONS,
                "bons-intervention/501": BON}[chemin]
    return _appeler


@tagged("post_install", "-at_install", "cultiveau")
class TestSite(TransactionCase):
    def test_synchronisation(self):
        societe = self.env.company
        connexion = self.env["cultiveau.site.connexion"].create({"company_id": societe.id, "cle": "cle-de-test"})
        appels = []
        with patch.object(type(connexion), "_appeler", faux_site(appels)):
            connexion._synchroniser()
        self.assertFalse(connexion.en_erreur, connexion.resultat)
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
        self.assertTrue(connexion.curseur_clients and connexion.curseur_bons)
        # une seconde passe ne crée rien en double, et ne relit que depuis le curseur
        avant = (Partner.search_count([("name", "like", "-Site")]), self.env["project.task"].search_count([("cultiveau_site_ref", "!=", False)]))
        with patch.object(type(connexion), "_appeler", faux_site(appels)):
            connexion._synchroniser()
        apres = (Partner.search_count([("name", "like", "-Site")]), self.env["project.task"].search_count([("cultiveau_site_ref", "!=", False)]))
        self.assertEqual(avant, apres)
        self.assertEqual(self.env["cultiveau.site.bon"].search_count([("connexion_id", "=", connexion.id)]), 1)
        self.assertTrue(any(c == "clients" and p.get("updatedSince") for c, p in appels))

    def test_erreur_notee(self):
        connexion = self.env["cultiveau.site.connexion"].create({"company_id": self.env.company.id})
        connexion._synchroniser()
        self.assertTrue(connexion.en_erreur)
        self.assertIn("clé", connexion.resultat)
