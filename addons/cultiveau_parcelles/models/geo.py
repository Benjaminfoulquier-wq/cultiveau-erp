"""Géométrie des parcelles : Lambert 93 (celui de Telepac et du RPG) vers GPS (WGS84), surface, contour simplifié pour la carte.

Projection inverse Lambert-93 d'après l'algorithme de l'IGN (ALG0004, NTG_71) sur l'ellipsoïde GRS80 ; précision bien meilleure
que le mètre, largement assez pour situer une parcelle et l'envoyer au satellite.
"""
import math

E = 0.0818191910428158  # excentricité GRS80
N = 0.7256077650532670
C = 11754255.4261
XS, YS = 700000.0, 12655612.0499
LAMBDA0 = math.radians(3.0)


def lambert93_vers_wgs84(x, y):
    """(x, y) en Lambert 93 → (longitude, latitude) en degrés."""
    dx, dy = x - XS, y - YS
    r = math.hypot(dx, dy)
    gamma = math.atan(dx / -dy)
    longitude = LAMBDA0 + gamma / N
    l_iso = -1.0 / N * math.log(abs(r / C))
    phi = 2 * math.atan(math.exp(l_iso)) - math.pi / 2
    for _ in range(20):
        suivant = 2 * math.atan(((1 + E * math.sin(phi)) / (1 - E * math.sin(phi))) ** (E / 2) * math.exp(l_iso)) - math.pi / 2
        if abs(suivant - phi) < 1e-12:
            phi = suivant
            break
        phi = suivant
    return math.degrees(longitude), math.degrees(phi)


def est_lambert93(x, y):
    return 50_000 <= x <= 1_300_000 and 6_000_000 <= y <= 7_200_000


def est_wgs84(x, y):
    return -180 <= x <= 180 and -90 <= y <= 90


def vers_wgs84(anneau):
    """Un anneau de points, en Lambert 93 ou déjà en degrés, rendu en (lon, lat). None si le système n'est pas reconnu."""
    if not anneau:
        return None
    x, y = anneau[0]
    if est_lambert93(x, y):
        return [lambert93_vers_wgs84(a, b) for a, b in anneau]
    if est_wgs84(x, y):
        return [(float(a), float(b)) for a, b in anneau]
    return None


def surface_ha(anneau_wgs84):
    """Surface d'un anneau (lon, lat) en hectares : projection locale équirectangulaire, puis formule du lacet."""
    if not anneau_wgs84 or len(anneau_wgs84) < 3:
        return 0.0
    lat0 = math.radians(sum(p[1] for p in anneau_wgs84) / len(anneau_wgs84))
    rayon = 6_371_008.8
    pts = [(math.radians(lon) * rayon * math.cos(lat0), math.radians(lat) * rayon) for lon, lat in anneau_wgs84]
    aire = 0.0
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        aire += x1 * y2 - x2 * y1
    return abs(aire) / 2 / 10_000


def centre(anneau_wgs84):
    if not anneau_wgs84:
        return 0.0, 0.0
    return sum(p[0] for p in anneau_wgs84) / len(anneau_wgs84), sum(p[1] for p in anneau_wgs84) / len(anneau_wgs84)


def fermer(anneau):
    if anneau and anneau[0] != anneau[-1]:
        return anneau + [anneau[0]]
    return anneau
