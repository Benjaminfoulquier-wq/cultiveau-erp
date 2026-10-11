"""Sentinel-2 par le Copernicus Data Space Ecosystem (gratuit) : NDVI et NDWI moyens de chaque parcelle, tous les 5 jours.

On crée un compte gratuit sur dataspace.copernicus.eu, puis un « client OAuth » (identifiant + secret) dans le tableau de bord
Sentinel Hub ; l'ERP demande un jeton, puis interroge l'API statistique sur le contour de la parcelle. Les pixels de nuage, d'ombre,
de neige ou sans donnée sont écartés grâce à la classification de scène (SCL) de Sentinel-2 L2A.

NDVI = (B08 − B04) / (B08 + B04) : la vigueur de la végétation (0,2 sol nu → 0,8–0,9 couvert dense en pleine croissance).
NDWI (Gao, 1996) = (B08 − B11) / (B08 + B11) : l'eau contenue dans les feuilles ; il baisse quand la culture manque d'eau.
"""
import json

import requests

ADRESSE_JETON = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
ADRESSE_STATISTIQUES = "https://sh.dataspace.copernicus.eu/api/v1/statistics"

EVALSCRIPT = """//VERSION=3
function setup() {
  return {
    input: [{bands: ["B04", "B08", "B11", "SCL", "dataMask"]}],
    output: [{id: "ndvi", bands: 1, sampleType: "FLOAT32"}, {id: "ndwi", bands: 1, sampleType: "FLOAT32"}, {id: "dataMask", bands: 1}]
  };
}
function evaluatePixel(s) {
  // 0 sans donnée, 1 saturé, 3 ombre de nuage, 8 et 9 nuages, 10 cirrus, 11 neige : écartés
  const ecarte = [0, 1, 3, 8, 9, 10, 11].indexOf(s.SCL) >= 0;
  const ok = (s.dataMask === 1 && !ecarte) ? 1 : 0;
  return {
    ndvi: [(s.B08 - s.B04) / (s.B08 + s.B04 + 1e-6)],
    ndwi: [(s.B08 - s.B11) / (s.B08 + s.B11 + 1e-6)],
    dataMask: [ok]
  };
}"""


class ErreurSatellite(Exception):
    pass


def jeton(client_id, secret):
    try:
        r = requests.post(ADRESSE_JETON, data={"grant_type": "client_credentials", "client_id": client_id, "client_secret": secret}, timeout=30)
    except requests.RequestException as e:
        raise ErreurSatellite(f"Copernicus injoignable : {e}")
    if r.status_code != 200:
        raise ErreurSatellite(f"Identifiants Copernicus refusés (HTTP {r.status_code}) : vérifier le client OAuth dans les réglages.")
    return r.json()["access_token"]


def statistiques(acces, anneau_wgs84, debut, fin, intervalle="P5D"):
    """[{date, ndvi, ndwi, ndvi_ecart, couverture}] pour chaque intervalle où la parcelle était visible (au moins 30 % de pixels clairs)."""
    geometrie = {"type": "Polygon", "coordinates": [[list(p) for p in anneau_wgs84]]}
    corps = {
        "input": {"bounds": {"geometry": geometrie, "properties": {"crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84"}},
                  "data": [{"type": "sentinel-2-l2a", "dataFilter": {"maxCloudCoverage": 80}}]},
        "aggregation": {"timeRange": {"from": f"{debut}T00:00:00Z", "to": f"{fin}T23:59:59Z"},
                        "aggregationInterval": {"of": intervalle}, "evalscript": EVALSCRIPT,
                        "resx": 0.0001, "resy": 0.0001},  # ≈ 10 m, la résolution des bandes rouge et proche infrarouge
        "calculations": {"default": {}},
    }
    try:
        r = requests.post(ADRESSE_STATISTIQUES, json=corps, headers={"Authorization": f"Bearer {acces}"}, timeout=90)
    except requests.RequestException as e:
        raise ErreurSatellite(f"Copernicus injoignable : {e}")
    if r.status_code == 429:
        raise ErreurSatellite("Quota Copernicus du mois atteint : les calculs reprendront le mois prochain.")
    if r.status_code != 200:
        raise ErreurSatellite(f"Copernicus a refusé la demande (HTTP {r.status_code}) : {r.text[:300]}")
    return lire_statistiques(r.json())


def lire_statistiques(reponse):
    mesures = []
    for intervalle in reponse.get("data") or []:
        sorties = intervalle.get("outputs") or {}
        try:
            s_ndvi = sorties["ndvi"]["bands"]["B0"]["stats"]
            s_ndwi = sorties["ndwi"]["bands"]["B0"]["stats"]
        except (KeyError, TypeError):
            continue
        total = (s_ndvi.get("sampleCount") or 0)
        valides = total - (s_ndvi.get("noDataCount") or 0)
        couverture = valides / total if total else 0.0
        if couverture < 0.3 or s_ndvi.get("mean") in (None, "NaN") or s_ndwi.get("mean") in (None, "NaN"):
            continue  # parcelle trop couverte de nuages ce jour-là
        mesures.append({"date": (intervalle.get("interval") or {}).get("from", "")[:10], "ndvi": round(float(s_ndvi["mean"]), 3),
                        "ndwi": round(float(s_ndwi["mean"]), 3), "ndvi_ecart": round(float(s_ndvi.get("stDev") or 0.0), 3),
                        "couverture": round(couverture, 2)})
    return mesures


def exemple_reponse(points):
    """Une réponse de l'API au format réel, pour les essais : points = [(date, ndvi, ndwi, ecart)]."""
    return json.loads(json.dumps({"data": [{"interval": {"from": f"{d}T00:00:00Z", "to": f"{d}T23:59:59Z"}, "outputs": {
        "ndvi": {"bands": {"B0": {"stats": {"min": 0, "max": 1, "mean": v, "stDev": e, "sampleCount": 400, "noDataCount": 20}}}},
        "ndwi": {"bands": {"B0": {"stats": {"min": -1, "max": 1, "mean": w, "stDev": 0.05, "sampleCount": 400, "noDataCount": 20}}}}}}
        for d, v, w, e in points]}))
