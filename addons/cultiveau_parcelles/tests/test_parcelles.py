import io
import struct
import zipfile
from datetime import date, timedelta
from unittest import mock

from odoo import Command

from odoo.tests import TransactionCase, tagged

from ..models import geo, irrigation, meteo, sentinel, telepac

# Deux parcelles au sud d'Auch (Gers), en Lambert 93, comme dans un export Telepac
CARRE = "502000,6280000 502300,6280000 502300,6280400 502000,6280400 502000,6280000"
CARRE2 = "502400,6280000 502600,6280000 502600,6280200 502400,6280200 502400,6280000"
XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<producteurs xmlns:gml="http://www.opengis.net/gml">
  <producteur numero-pacage="032123456">
    <rpg>
      <ilot numero-ilot="1">
        <commune>32013</commune>
        <parcelles>
          <parcelle>
            <descriptif-parcelle numero-parcelle="1">
              <culture-principale><code-culture>MIS</code-culture><precision>Grain</precision></culture-principale>
            </descriptif-parcelle>
            <geometrie><gml:Polygon><gml:outerBoundaryIs><gml:LinearRing><gml:coordinates>{CARRE}</gml:coordinates></gml:LinearRing></gml:outerBoundaryIs></gml:Polygon></geometrie>
          </parcelle>
          <parcelle>
            <descriptif-parcelle numero-parcelle="2">
              <culture-principale><code-culture>ZZZ</code-culture></culture-principale>
            </descriptif-parcelle>
            <geometrie><gml:Polygon><gml:exterior><gml:LinearRing><gml:posList>{CARRE2.replace(",", " ")}</gml:posList></gml:LinearRing></gml:exterior></gml:Polygon></geometrie>
          </parcelle>
        </parcelles>
      </ilot>
    </rpg>
  </producteur>
</producteurs>""".encode()

# La forme réelle de l'export Telepac 2026 (données inventées) : espace de noms, ISO-8859-1, îlot numéroté et référencé,
# surface admissible en ares, surfaces non agricoles (haies, arbres) mêlées aux parcelles, jachère
EXPORT_2026 = f"""<?xml version="1.0" encoding="ISO-8859-1"?>
<producteurs xmlns="urn:x-telepac:fr.gouv.agriculture.telepac:echange-producteur" xmlns:gml="http://www.opengis.net/gml">
<producteur numero-pacage="040999999" campagne="Courante" fichier-xsd="Echanges-producteur-export-2026-V1">
 <demandeur><identification-societe><exploitation>GAEC DES LANDES ESSAI</exploitation></identification-societe>
  <siret>12345678900011</siret><courriel>gaec.essai@exemple.fr</courriel></demandeur>
 <rpg>
  <ilot numero-ilot-reference="040012345678" numero-ilot="3">
   <commune>40309</commune>
   <geometrie><gml:Polygon><gml:outerBoundaryIs><gml:LinearRing><gml:coordinates>{CARRE}</gml:coordinates></gml:LinearRing></gml:outerBoundaryIs></gml:Polygon></geometrie>
   <parcelles>
    <parcelle>
     <descriptif-parcelle numero-parcelle="1">
      <culture-principale culture-secondaire="CPL"><code-culture>MIS</code-culture><precision>001</precision></culture-principale>
     </descriptif-parcelle>
     <geometrie><gml:Polygon><gml:outerBoundaryIs><gml:LinearRing><gml:coordinates>{CARRE}</gml:coordinates></gml:LinearRing></gml:outerBoundaryIs></gml:Polygon></geometrie>
     <surface-admissible>1195</surface-admissible>
    </parcelle>
    <parcelle>
     <descriptif-parcelle numero-parcelle="2"><culture-principale><code-culture>JAC</code-culture><precision>001</precision></culture-principale></descriptif-parcelle>
     <geometrie><gml:Polygon><gml:outerBoundaryIs><gml:LinearRing><gml:coordinates>{CARRE2}</gml:coordinates></gml:LinearRing></gml:outerBoundaryIs></gml:Polygon></geometrie>
     <surface-admissible>400</surface-admissible>
    </parcelle>
   </parcelles>
   <intersectionsSnaParcelles><intersectionSnaParcelle><numeroSna>7</numeroSna><numeroParcelle>1</numeroParcelle></intersectionSnaParcelle></intersectionsSnaParcelles>
  </ilot>
  <sna-declaree><numeroSna>7</numeroSna><typeSna>HAI</typeSna><geometrie><gml:Point><gml:coordinates>502100,6280100</gml:coordinates></gml:Point></geometrie></sna-declaree>
 </rpg>
</producteur>
</producteurs>""".encode("iso-8859-1")


def _shapefile(polygones, attributs):
    """Un petit shapefile (polygones) et son dbf, comme ceux que Telepac fournit en ZIP."""
    enregs = b""
    for i, pts in enumerate(polygones, start=1):
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        corps = struct.pack("<i4d2i", 5, min(xs), min(ys), max(xs), max(ys), 1, len(pts)) + struct.pack("<i", 0)
        corps += b"".join(struct.pack("<2d", *p) for p in pts)
        enregs += struct.pack(">2i", i, len(corps) // 2) + corps
    shp = struct.pack(">7i", 9994, 0, 0, 0, 0, 0, 50 + len(enregs) // 2) + struct.pack("<2i4d4d", 1000, 5, 0, 0, 0, 0, 0, 0, 0, 0) + enregs
    champs = [("NUM_ILOT", 5), ("NUM_PARCEL", 5), ("CODE_CULTU", 5), ("SURF_ADM", 10)]
    entete = 32 + 32 * len(champs) + 1
    taille = 1 + sum(l for _, l in champs)
    dbf = struct.pack("<B3BIHH20x", 3, 26, 1, 1, len(attributs), entete, taille)
    for nom, longueur in champs:
        dbf += nom.encode().ljust(11, b"\x00") + b"C" + b"\x00" * 4 + bytes([longueur, 0]) + b"\x00" * 14
    dbf += b"\x0d"
    for a in attributs:
        dbf += b" " + b"".join(str(a[i]).encode().ljust(l)[:l] for i, (_, l) in enumerate(champs))
    return shp, dbf + b"\x1a"


@tagged("post_install", "-at_install")
class TestParcelles(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.agri = cls.env["res.partner"].create({"name": "EARL des Parcelles", "zip": "32000", "cultiveau_type": "agriculteur", "email": "earl@exemple.fr"})
        cls.mais = cls.env.ref("cultiveau_frise.culture_mais_grain")
        cls.Parcelle = cls.env["cultiveau.parcelle"]

    def test_lambert93_vers_gps(self):
        self.assertEqual(tuple(round(v, 4) for v in geo.lambert93_vers_wgs84(700000, 6600000)), (3.0, 46.5))
        lon, lat = geo.lambert93_vers_wgs84(652469.02, 6862035.26)
        self.assertAlmostEqual(lon, 2.3522, places=3)
        self.assertAlmostEqual(lat, 48.8566, places=3)

    def test_import_xml_telepac(self):
        bilan = self.Parcelle.importer(self.agri, "declaration.xml", XML, 2026)
        self.assertEqual((bilan["parcelles"], bilan["codes_inconnus"]), (2, ["ZZZ"]))
        p1 = self.agri.cultiveau_parcelle_ids.filtered(lambda p: p.numero == "1")
        self.assertEqual((p1.ilot, p1.pacage, p1.culture_id, p1.precision), ("1", "032123456", self.mais, "Grain"))
        self.assertAlmostEqual(p1.surface_ha, 12.0, delta=0.05)  # 300 m × 400 m
        self.assertTrue(43.4 < p1.latitude < 43.8 and 0.4 < p1.longitude < 0.8, (p1.latitude, p1.longitude))
        self.assertIn("<polygon", p1.carte)
        # ses cultures se remplissent : le maïs avec la surface de la parcelle
        cc = self.agri.cultiveau_culture_ids.filtered(lambda c: c.culture_id == self.mais)
        self.assertAlmostEqual(cc.surface_ha, p1.surface_ha, places=2)
        self.assertGreater(cc.besoin_pointe_mm, 5)
        # relier le code inconnu à une culture met à jour la parcelle et ses cultures
        tournesol = self.env.ref("cultiveau_frise.culture_tournesol")
        self.env["cultiveau.code.pac"].search([("code", "=", "ZZZ")]).culture_id = tournesol
        self.assertIn(tournesol, self.agri.cultiveau_culture_ids.culture_id)
        # réimporter ne duplique pas
        self.Parcelle.importer(self.agri, "declaration.xml", XML, 2026)
        self.assertEqual(len(self.agri.cultiveau_parcelle_ids), 2)

    def test_export_telepac_2026(self):
        client = self.env["res.partner"].create({"name": "M. Essai", "cultiveau_type": "agriculteur"})
        bilan = self.Parcelle.importer(client, "Dossier-PAC-2026_dossier.xml", EXPORT_2026, 2026)
        self.assertEqual((bilan["parcelles"], bilan["codes_inconnus"]), (2, []), "la jachère n'est pas un code à relier")
        mais, jachere = client.cultiveau_parcelle_ids.sorted("numero")
        self.assertEqual((mais.ilot, mais.numero, mais.commune, mais.pacage), ("3", "1", "40309", "040999999"))
        self.assertEqual(mais.surface_ha, 11.95, "surface admissible en ares")
        self.assertEqual((jachere.surface_ha, jachere.suivi, jachere.culture_id.id), (4.0, False, False))
        # la fiche du client se complète d'après la déclaration
        self.assertEqual((client.email, client.departement, client.exploitation), ("gaec.essai@exemple.fr", "40", "GAEC DES LANDES ESSAI"))
        self.assertEqual(client.company_registry, "12345678900011")
        self.assertEqual(client.cultiveau_culture_ids.culture_id, self.mais)

    def test_import_zip_shapefile(self):
        carre = [(502000, 6280000), (502000, 6280400), (502300, 6280400), (502300, 6280000), (502000, 6280000)]
        shp, dbf = _shapefile([carre], [("4", "7", "BTH", "11.95")])
        tampon = io.BytesIO()
        with zipfile.ZipFile(tampon, "w") as z:
            z.writestr("parcelles_2026.shp", shp)
            z.writestr("parcelles_2026.dbf", dbf)
        lues = telepac.lire("telepac.zip", tampon.getvalue())
        self.assertEqual((lues[0]["ilot"], lues[0]["numero"], lues[0]["code"], lues[0]["surface_ha"]), ("4", "7", "BTH", 11.95))
        self.assertEqual(len(lues[0]["anneau"]), 5)

    def _mesures(self, points):
        reponses = [mock.Mock(status_code=200, json=lambda: {"access_token": "jeton"}),
                    mock.Mock(status_code=200, json=lambda: sentinel.exemple_reponse(points))]
        return mock.patch("requests.post", side_effect=reponses)

    def test_satellite_et_alertes(self):
        self.Parcelle.importer(self.agri, "declaration.xml", XML, 2026)
        p1 = self.agri.cultiveau_parcelle_ids.filtered(lambda p: p.numero == "1")
        self.env["ir.config_parameter"].sudo().set_param("cultiveau.copernicus_id", "id")
        self.env["ir.config_parameter"].sudo().set_param("cultiveau.copernicus_secret", "secret")
        # juillet, maïs en floraison : la vigueur chute, l'eau des feuilles baisse, la parcelle devient hétérogène
        points = [("2026-07-01", 0.82, 0.42, 0.05), ("2026-07-06", 0.83, 0.41, 0.06), ("2026-07-11", 0.80, 0.38, 0.08),
                  ("2026-07-16", 0.62, 0.24, 0.19)]
        with self._mesures(points) as post:
            n = p1.actualiser_satellite(forcer=True, aujourdhui=date(2026, 7, 20))
        self.assertEqual(n, 4)
        self.assertEqual(post.call_args.args[0], sentinel.ADRESSE_STATISTIQUES)
        corps = post.call_args.kwargs["json"]
        self.assertEqual(corps["input"]["data"][0]["type"], "sentinel-2-l2a")
        self.assertIn("B11", corps["aggregation"]["evalscript"])
        self.assertEqual(p1.dernier_ndvi, 0.62)
        genres = set(p1.alerte_ids.mapped("genre"))
        self.assertEqual(genres, {"vigueur", "stress", "heterogene"})
        self.assertEqual(p1.etat, "alerte")
        self.assertTrue(self.agri.activity_ids.filtered(lambda a: "Satellite" in (a.summary or "")), "le commercial a une activité")
        self.assertIn("<polyline", p1.courbe)
        # on prévient le client en un clic
        alerte = p1.alerte_ids.filtered(lambda a: a.genre == "stress")
        alerte.action_prevenir_client()
        self.assertEqual(alerte.etat, "client_prevenu")
        self.assertTrue(alerte.message_ids.filtered(lambda m: "à vérifier sur votre parcelle" in (m.subject or "")))
        # pas de doublon d'alerte deux semaines durant
        p1.analyser(date(2026, 7, 21))
        self.assertEqual(len(p1.alerte_ids), 3)

    def test_pas_d_alerte_a_la_recolte(self):
        self.Parcelle.importer(self.agri, "declaration.xml", XML, 2026)
        p1 = self.agri.cultiveau_parcelle_ids.filtered(lambda p: p.numero == "1")
        self.env["ir.config_parameter"].sudo().set_param("cultiveau.copernicus_id", "id")
        self.env["ir.config_parameter"].sudo().set_param("cultiveau.copernicus_secret", "secret")
        # fin septembre, maïs en maturation : le vert qui baisse, c'est normal
        points = [("2026-09-10", 0.70, 0.30, 0.05), ("2026-09-20", 0.45, 0.10, 0.06)]
        with self._mesures(points):
            p1.actualiser_satellite(forcer=True, aujourdhui=date(2026, 9, 25))
        self.assertFalse(p1.alerte_ids)
        self.assertEqual(p1.etat, "ok")


    # ---------------------------------------------------------------- conseil d'irrigation

    def _meteo(self, aujourdhui, eto=6.0, pluie=0.0, pluie_prevue=0.0):
        jours = [aujourdhui + timedelta(days=i) for i in range(-meteo.JOURS_PASSES, meteo.JOURS_A_VENIR)]
        donnees = {"daily": {"time": [j.isoformat() for j in jours], "et0_fao_evapotranspiration": [eto] * len(jours),
                             "precipitation_sum": [pluie if j < aujourdhui else pluie_prevue for j in jours]}}
        return mock.patch.object(meteo.requests, "get", return_value=mock.Mock(status_code=200, json=lambda: donnees, raise_for_status=lambda: None))

    def test_conseil_irrigation(self):
        self.Parcelle.importer(self.agri, "declaration.xml", XML, 2026)
        p1 = self.agri.cultiveau_parcelle_ids.filtered(lambda p: p.numero == "1")
        cc = p1._culture_client()
        self.assertGreater(cc.kc_a_la_date(date(2026, 7, 15)), 0.8, "maïs en juillet dans le Gers : pleine évapotranspiration")
        self.assertEqual(cc.kc_a_la_date(date(2026, 1, 15)), 0.0)
        ete = date(2026, 7, 15)
        # trois semaines sans pluie, 6 mm d'ETo par jour : la réserve est vide, il faut arroser
        with self._meteo(ete) as get:
            n = self.Parcelle._cron_irrigation(ete)
        self.assertGreaterEqual(n, 1)
        self.assertEqual(get.call_args.kwargs["params"]["daily"], "et0_fao_evapotranspiration,precipitation_sum")
        self.assertEqual(p1.etat_eau, "arroser")
        self.assertAlmostEqual(p1.deficit_mm, p1.rfu_mm, delta=1)
        self.assertIn("Apporter", p1.conseil)
        self.assertIn("<table", p1.bilan_eau)
        alerte = p1.alerte_ids.filtered(lambda a: a.genre == "irrigation")
        self.assertEqual(len(alerte), 1)
        self.assertTrue(self.agri.activity_ids, "le commercial est prévenu")
        alerte.action_prevenir_client()
        self.assertTrue(alerte.message_ids.filtered(lambda m: "tour d'eau" in (m.subject or "")))
        # le lendemain, pas de seconde alerte ; l'arrosage noté remet la réserve à niveau
        with self._meteo(ete + timedelta(days=1)):
            self.Parcelle._cron_irrigation(ete + timedelta(days=1))
        self.assertEqual(len(p1.alerte_ids.filtered(lambda a: a.genre == "irrigation")), 1)
        self.env["cultiveau.apport.assistant"].create({"partner_id": self.agri.id, "parcelle_ids": [Command.set(p1.ids)], "date": ete + timedelta(days=1), "mm": p1.rfu_mm}).action_noter()
        p1.calculer_bilan(ete + timedelta(days=1))
        self.assertIn(p1.etat_eau, ("ok", "bientot"))
        self.assertLess(p1.deficit_mm, 10)
        # un été pluvieux : rien à faire ; janvier : hors saison
        with self._meteo(ete, eto=3.0, pluie=8.0):
            p1.action_actualiser_eau()
            p1.calculer_bilan(ete)
        self.assertEqual(p1.etat_eau, "ok")
        with self._meteo(date(2026, 1, 15), eto=0.5):
            self.env["cultiveau.meteo.jour"].actualiser({p1._station()}, date(2026, 1, 15))
        p1.calculer_bilan(date(2026, 1, 15))
        self.assertEqual(p1.etat_eau, "hors_saison")
        self.assertIn("Hors saison", str(self.agri.cultiveau_conseil_eau))
