import base64
import json

from odoo.tests import TransactionCase, tagged


def etude(avec_nomenclature=True):
    """Une étude minimale au format d'échange Cultiveau, comme Réseau 3D l'exporte (schéma 1.2.0)."""
    vq = lambda v, o="declaration", s="Saisie", u=None: {"valeur": v, "origine": o, "source": s, **({"unite": u} if u else {})}  # noqa: E731
    d = {
        "entete": {"schema": "cultiveau-echange", "schema_version": "1.2.0", "exporte_le": "2026-11-07T10:00:00Z", "type_document": "etude", "document_uid": "doc-1", "installation_uid": "inst-1",
                   "emetteur": {"logiciel": "Cultiveau Réseau 3D", "version": "108"}},
        "acteurs": [{"id": "act-exploitant", "role": "exploitant", "nom": "Earl des Oliviers · Goutte à goutte oliviers"}, {"id": "act-concepteur", "role": "installateur", "nom": "Irrigation Sud"}],
        "installation": {"objets": [
            {"uid": "p1", "type": "pompe", "libelle": "Caprari MEC-A 2/80", "caracteristiques": {"modele": vq("MEC-A 2/80", "constructeur")}},
            {"uid": "c1", "type": "canalisation", "libelle": "Conduite 1 Ø110", "caracteristiques": {"dn_mm": vq(110, "conception", u="mm"), "materiau": vq("PE", "conception"), "longueur_m": vq(240, "calcul", u="m"), "perte_de_charge_m": vq(3.2, "calcul", u="m")}},
            {"uid": "c2", "type": "canalisation", "libelle": "Conduite 2 Ø63", "caracteristiques": {"dn_mm": vq(63, "conception", u="mm"), "materiau": vq("PE", "conception"), "longueur_m": vq(60, "calcul", u="m")}},
            {"uid": "f1", "type": "filtration", "libelle": "Filtre à disques 3\"", "caracteristiques": {"reference": vq("FD-3-130", "constructeur"), "designation": vq("Filtre à disques 3\" 130 µm", "constructeur"), "fournisseur": vq("ODIS", "constructeur")}},
        ]},
        "conception": {
            "analyse_des_besoins": {"surface_ha": vq(8, u="ha"), "nature_ressource": vq("Forage"), "debit_mobilisable_pointe_m3h": vq(45, u="m³/h"), "volume_autorise_m3_an": vq(30000, u="m³/an"),
                                    "energie_puissance_disponible": vq("Réseau électrique ; 36 kVA"), "acces_niveau_automatisme": vq("Programmateur"), "hierarchie_eau_energie_rendement": vq("L'eau d'abord")},
            "note_dimensionnement": {"besoin_pointe_mm_j": vq(5.5, "conception", u="mm/j"), "debit_fictif_continu_l_s_ha": vq(0.64, "calcul", u="l/s/ha"), "temps_fonctionnement_h_j": vq(18, u="h/j"),
                                     "debit_equipement_m3h": vq(40, u="m³/h"), "pression_service_bar": vq(2.5, u="bar"), "bilan_pression_hmt_m": vq(48.6, "calcul", u="m"),
                                     "pompe_point_fonctionnement": vq("Caprari MEC-A 2/80 à 40 m³/h × 48,6 m", "calcul"), "filtration_type_finesse": vq("Filtre à disques 3\" 130 µm", "constructeur"),
                                     "diametres_vitesses": vq("Ø110, Ø63 ; vitesse maximale 1,2 m/s", "calcul"), "technique_organes": vq("Goutte à goutte de surface")},
            "resultats": [{"code": "hmt", "valeur": "48.6", "unite": "m"}, {"code": "vitesse_ecoulement", "valeur": "1.2", "unite": "m/s", "dans_tolerance": True, "reference": {"valeur": "2.0", "unite": "m/s", "source": "13.1.5"}}],
            "hypotheses": []},
        "conformite": [{"exigence": "PRE-clapet", "statut": "non_conforme", "motif": "Pas de clapet anti-retour"}, {"exigence": "PRE-vitesse", "statut": "conforme"}],
        "pieces": [], "avertissements": ["Les valeurs de contexte sont déclaratives."],
    }
    if avec_nomenclature:
        d["nomenclature"] = {"longueur_conduites_m": 300, "lignes": [
            {"libelle": "Tube PE Ø110 PN10", "type": "pipe", "quantite": 240, "unite": "m", "reference": "PE110-10", "designation": "Tube PE100 Ø110 PN10", "fournisseur": "SYSTEM GROUP", "famille": "Tuyaux et raccords (réseau)", "dn_mm": 100, "materiau": "PE"},
            {"libelle": "Tube PE Ø63 PN10", "type": "pipe", "quantite": 60, "unite": "m", "famille": "Tuyaux et raccords (réseau)", "dn_mm": 50, "materiau": "PE"},
            {"libelle": "Coude 90° Ø110 — ATUSA IC341110", "type": "fit", "quantite": 3, "unite": "u", "reference": "IC341110", "designation": "Coude 90°", "fournisseur": "ATUSA", "famille": "Tuyaux et raccords (réseau)", "dn_mm": 100},
            {"libelle": "Filtre à disques 3\" 130 µm", "type": "equip", "quantite": 1, "unite": "u", "reference": "FD-3-130", "fournisseur": "ODIS", "famille": "Filtration"},
            {"libelle": "Caprari MEC-A 2/80 — groupe de pompage 15 kW", "type": "equip", "quantite": 1, "unite": "u", "famille": "Pompage"},
            {"libelle": "Programmateur 8 voies", "type": "equip", "quantite": 1, "unite": "u", "famille": "Automatisme et pilotage"},
            {"libelle": "Tube goutteur Ø16, 1,6 l/h tous les 0,5 m", "type": "pipe", "quantite": 4800, "unite": "m", "famille": "Goutte à goutte / micro-irrigation"},
        ]}
    return base64.b64encode(json.dumps(d).encode()).decode()


@tagged("post_install", "-at_install", "cultiveau")
class TestImportSchema3d(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.agri = cls.env["res.partner"].create({"name": "Earl des Oliviers", "zip": "30250", "cultiveau_type": "agriculteur"})
        cls.tube = cls.env["product.product"].create({"name": "Tube PE100 Ø110 PN10", "default_code": "PE110-10", "list_price": 4.2, "type": "consu", "sale_ok": True})
        cls.filtre = cls.env["product.product"].create({"name": "Filtre à disques 3\" 130 µm", "default_code": "FD-3-130", "list_price": 850.0, "type": "consu", "sale_ok": True})

    def test_import_complet(self):
        w = self.env["cultiveau.schema3d.import"].create({"partner_id": self.agri.id, "fichier": etude(), "fichier_nom": "oliviers.echange.json"})
        self.assertIn("7 lignes", w.resume)
        self.assertIn("1 non-conformité", w.resume)
        action = w.action_importer()
        devis = self.env["sale.order"].browse(action["res_id"])
        inst = devis.cultiveau_installation_id
        # l'installation est née de l'étude et porte A1.1 / A1.2
        self.assertEqual(inst.partner_id, self.agri)
        self.assertEqual(inst.type_systeme, "goutte_surface")
        self.assertEqual(inst.surface_ha, 8)
        self.assertEqual(inst.ressource, "forage")
        self.assertEqual(inst.energie, "reseau")
        self.assertEqual(inst.puissance_souscrite_kva, 36)
        self.assertEqual(inst.niveau_automatisme, "programmateur")
        self.assertEqual(inst.hmt_m, 48.6)
        self.assertEqual(inst.debit_equipement_m3_h, 40)
        self.assertAlmostEqual(inst.pertes_charge_m, 3.2)
        self.assertEqual(inst.schema3d_uid, "inst-1")
        self.assertTrue(self.env["ir.attachment"].search([("res_model", "=", "cultiveau.installation"), ("res_id", "=", inst.id), ("name", "=", "oliviers.echange.json")]))
        # le devis par lots : articles reconnus par référence, le reste à préciser, conduites au mètre, lot pose
        self.assertTrue(devis.cultiveau_schema3d)
        sections = [l.name for l in devis.order_line if l.display_type == "line_section"]
        self.assertEqual([s for s in sections if s.startswith("Lot")], ["Lot 1 — Station de pompage et énergie", "Lot 2 — Filtration et protection sanitaire", "Lot 3 — Réseau principal, vannes, raccords",
                                                                        "Lot 4 — Secteurs : conduites, rampes, organes", "Lot 5 — Automatisme et pilotage", "Lot 6 — Pose, mise en service, réception et formation"])
        self.assertIn("Conduites", sections)
        lignes = {l.name: l for l in devis.order_line if l.product_id}
        tube = next(l for n, l in lignes.items() if "PE110-10" in n or "Tube PE100 Ø110" in n)
        self.assertEqual(tube.product_id, self.tube)
        self.assertEqual(tube.product_uom_qty, 240)
        self.assertEqual(tube.product_uom, self.env.ref("uom.product_uom_meter"))
        self.assertEqual(tube.price_unit, 4.2)
        filtre = next(l for n, l in lignes.items() if "Filtre à disques" in n)
        self.assertEqual(filtre.product_id, self.filtre)
        pompe = next(l for n, l in lignes.items() if "Caprari" in n)
        self.assertEqual(pompe.product_id.default_code, "A-PRECISER")
        self.assertIn("à préciser", pompe.name)
        tranchee = next(l for n, l in lignes.items() if n.startswith("Tranchée"))
        self.assertEqual(tranchee.product_uom_qty, 300)
        self.assertTrue(any("A1.3" in n for n in lignes))
        lots = devis.cultiveau_lots()
        self.assertEqual(lots[2]["sous"][0]["nom"], "Conduites")
        self.assertEqual(inst.schema3d_nb_devis, 1)
        # le fil raconte : résultats, non-conformité
        corps = " ".join(inst.message_ids.mapped("body"))
        self.assertIn("PRE-clapet", corps)
        self.assertIn("Surface irriguée", corps)

    def test_sans_nomenclature_on_reconstitue(self):
        w = self.env["cultiveau.schema3d.import"].create({"partner_id": self.agri.id, "fichier": etude(avec_nomenclature=False)})
        self.assertIn("reconstituée", w.resume)
        action = w.action_importer()
        devis = self.env["sale.order"].browse(action["res_id"])
        noms = [l.name for l in devis.order_line if l.product_id]
        self.assertTrue(any("Ø 110" in n for n in noms))
        self.assertTrue(any("Filtre" in n for n in noms))

    def test_ne_pas_ecraser(self):
        inst = self.env["cultiveau.installation"].create({"name": "Oliviers", "partner_id": self.agri.id, "type_systeme": "goutte_surface", "surface_ha": 12})
        w = self.env["cultiveau.schema3d.import"].create({"partner_id": self.agri.id, "installation_id": inst.id, "fichier": etude(), "creer_devis": False})
        w.action_importer()
        self.assertEqual(inst.surface_ha, 12)
        self.assertEqual(inst.hmt_m, 48.6)
        w2 = self.env["cultiveau.schema3d.import"].create({"partner_id": self.agri.id, "installation_id": inst.id, "fichier": etude(), "creer_devis": False, "ecraser": True})
        w2.action_importer()
        self.assertEqual(inst.surface_ha, 8)

    def test_mauvais_fichier(self):
        w = self.env["cultiveau.schema3d.import"].create({"partner_id": self.agri.id, "fichier": base64.b64encode(json.dumps({"v": 1, "app": "Cultiveau Réseau 3D", "state": {}, "project": {}}).encode()).decode()})
        self.assertIn("sauvegarde de projet", w.resume)
