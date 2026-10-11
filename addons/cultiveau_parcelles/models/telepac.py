"""Lire une déclaration PAC : l'export XML de Telepac, un ZIP (XML ou shapefile des parcelles) ou un GeoJSON.

Le schéma de l'export Telepac n'est pas publié et varie selon les campagnes : la lecture est tolérante. Une parcelle est un élément
dont le nom contient « parcelle » et qui porte un code culture (élément ou attribut « code-culture », « code_culture », « CODE_CULTU »…) ;
son contour est la première géométrie GML trouvée dessous (gml:coordinates, gml:posList, gml:pos) ; l'îlot est son ancêtre « ilot ».

Renvoie une liste de dictionnaires : {pacage, ilot, numero, code, precision, surface_ha, anneau (liste de (x, y)), commune}.
"""
import io
import json
import re
import struct
import zipfile
from xml.etree import ElementTree

CLES_CODE = ("code-culture", "code_culture", "codeculture", "code_cultu", "culture", "code")
CLES_SURFACE = ("surface-admissible", "surface_admissible", "surf_adm", "surface", "surf_parc", "surface-graphique", "surf_graph")


def _nom(tag):
    """Le nom d'un élément sans espace de noms, en minuscules."""
    return tag.rsplit("}", 1)[-1].lower() if isinstance(tag, str) else ""


def _nombre(texte):
    try:
        return float(str(texte).strip().replace(",", "."))
    except (TypeError, ValueError):
        return None


def _points(texte, couples=True):
    """« x,y x,y » (gml:coordinates) ou « x y x y » (gml:posList)."""
    texte = (texte or "").strip()
    if not texte:
        return []
    if "," in texte and couples:
        pts = []
        for morceau in texte.split():
            v = [float(a) for a in morceau.split(",")[:2]]
            if len(v) == 2:
                pts.append(tuple(v))
        return pts
    valeurs = [float(a) for a in texte.replace(",", " ").split()]
    return list(zip(valeurs[0::2], valeurs[1::2]))


def _anneau(element):
    """Le premier contour extérieur sous l'élément."""
    for e in element.iter():
        n = _nom(e.tag)
        if n in ("coordinates", "poslist"):
            pts = _points(e.text, couples=(n == "coordinates"))
            if len(pts) >= 3:
                return pts
    pos = [e for e in element.iter() if _nom(e.tag) == "pos"]
    if len(pos) >= 3:
        return [p for e in pos for p in _points(e.text, couples=False)][: len(pos)]
    return []


def _valeur(element, cles):
    for cle in cles:
        for attr, v in element.attrib.items():
            if _nom(attr) == cle and v.strip():
                return v.strip()
    for e in element.iter():
        if e is element:
            continue
        n = _nom(e.tag)
        if n in cles and (e.text or "").strip() and len(e) == 0:
            return e.text.strip()
        # <culture-principale><code-culture>MIS</code-culture>…
    return None


def lire_xml(contenu):
    racine = ElementTree.fromstring(contenu)
    parents = {enfant: parent for parent in racine.iter() for enfant in parent}
    pacage = None
    for e in racine.iter():
        for attr, v in e.attrib.items():
            if "pacage" in _nom(attr):
                pacage = v
        if "pacage" in _nom(e.tag) and (e.text or "").strip():
            pacage = e.text.strip()
        if pacage:
            break
    parcelles = []
    for e in racine.iter():
        n = _nom(e.tag)
        if "parcelle" not in n or n.startswith("descriptif") or n.endswith("parcelles"):
            continue
        code = None
        for sous in e.iter():
            sn = _nom(sous.tag)
            if sn in ("code-culture", "code_culture", "codeculture", "code_cultu") and (sous.text or "").strip():
                code = sous.text.strip()
                break
            for attr, v in sous.attrib.items():
                if _nom(attr) in ("code-culture", "code_culture", "code_cultu") and v.strip():
                    code = v.strip()
            if code:
                break
        if not code:
            continue
        numero = next((v for sous in e.iter() for attr, v in sous.attrib.items() if _nom(attr) in ("numero-parcelle", "numero_parcelle", "num_parcel", "numero")), None)
        # l'îlot et sa commune sont portés par l'élément <ilot numero-ilot="1" numero-ilot-reference="040012127686"> qui l'englobe
        ilot, commune, p = None, None, parents.get(e)
        while p is not None and ilot is None:
            if "ilot" in _nom(p.tag):
                attrs = {_nom(a): v for a, v in p.attrib.items()}
                ilot = next((attrs[c] for c in ("numero-ilot", "numero_ilot", "num_ilot", "ilot", "numero") if attrs.get(c)), None)
                ilot = ilot or next((v for a, v in attrs.items() if "numero" in a), None)
                commune = next((c.text.strip() for c in p if _nom(c.tag) in ("commune", "code-insee", "insee") and (c.text or "").strip()), None)
            p = parents.get(p)
        precision = None
        for sous in e.iter():
            if _nom(sous.tag) == "precision" and (sous.text or "").strip():
                precision = sous.text.strip()
                break
        surface = _nombre(_valeur(e, CLES_SURFACE))
        commune = _valeur(e, ("commune", "code-insee", "insee")) or commune
        parcelles.append({"pacage": pacage, "ilot": ilot, "numero": numero, "code": code.upper()[:3], "precision": precision,
                          "surface_ha": surface, "anneau": _anneau(e), "commune": commune})
    return parcelles


def lire_entete(contenu):
    """Qui est l'exploitant d'après l'export XML : {pacage, exploitation, siret, courriel}, les clés absentes sont omises."""
    try:
        racine = ElementTree.fromstring(contenu)
    except ElementTree.ParseError:
        return {}
    entete = {}
    for e in racine.iter():
        n = _nom(e.tag)
        for attr, v in e.attrib.items():
            if "pacage" in _nom(attr) and v.strip():
                entete.setdefault("pacage", v.strip())
        texte = (e.text or "").strip()
        if texte and len(e) == 0 and n in ("exploitation", "raison-sociale", "siret", "courriel"):
            entete.setdefault(n if n != "raison-sociale" else "exploitation", texte)
    return entete


# ---------------------------------------------------------------- shapefile (polygones) + dbf, sans bibliothèque

def lire_dbf(contenu):
    nb, entete, taille = struct.unpack("<xxxxIHH", contenu[:12])
    champs, pos = [], 32
    while contenu[pos] != 0x0D:
        nom = contenu[pos:pos + 11].split(b"\x00")[0].decode("latin-1")
        longueur = contenu[pos + 16]
        champs.append((nom, longueur))
        pos += 32
    lignes, pos = [], entete
    for _ in range(nb):
        enreg = contenu[pos:pos + taille]
        pos += taille
        if not enreg or enreg[:1] == b"*":
            lignes.append(None)
            continue
        i, ligne = 1, {}
        for nom, longueur in champs:
            ligne[nom.lower()] = enreg[i:i + longueur].decode("latin-1", "replace").strip()
            i += longueur
        lignes.append(ligne)
    return lignes


def lire_shp(contenu):
    """Les contours extérieurs (premier anneau) de chaque enregistrement polygone."""
    formes, pos = [], 100
    while pos + 8 <= len(contenu):
        _num, longueur = struct.unpack(">ii", contenu[pos:pos + 8])
        corps = contenu[pos + 8:pos + 8 + longueur * 2]
        pos += 8 + longueur * 2
        type_forme = struct.unpack("<i", corps[:4])[0] if len(corps) >= 4 else 0
        if type_forme not in (5, 15, 25):
            formes.append([])
            continue
        nb_parties, nb_points = struct.unpack("<ii", corps[36:44])
        parties = struct.unpack(f"<{nb_parties}i", corps[44:44 + 4 * nb_parties])
        debut = 44 + 4 * nb_parties
        points = [struct.unpack("<dd", corps[debut + 16 * i:debut + 16 * i + 16]) for i in range(nb_points)]
        fin = parties[1] if nb_parties > 1 else nb_points
        formes.append(points[parties[0]:fin])
    return formes


def _depuis_attributs(attrs, anneau):
    a = {k.lower(): v for k, v in (attrs or {}).items()}
    code = next((a[k] for k in ("code_cultu", "code_culture", "code-culture", "codeculture", "culture", "cult_princ") if a.get(k)), None)
    if not code:
        return None
    return {"pacage": a.get("pacage") or a.get("num_pacage"), "ilot": a.get("num_ilot") or a.get("ilot") or a.get("numero_ilot"),
            "numero": a.get("num_parcel") or a.get("num_parcelle") or a.get("numero") or a.get("id_parcel"),
            "code": str(code).upper()[:3], "precision": a.get("precision") or a.get("code_preci"),
            "surface_ha": _nombre(next((a[k] for k in ("surf_adm", "surf_parc", "surface", "surf_graph", "surface_ha") if a.get(k)), None)),
            "anneau": anneau, "commune": a.get("commune") or a.get("insee")}


def lire_shapefile(shp, dbf):
    return [p for p in (_depuis_attributs(attrs, anneau) for attrs, anneau in zip(lire_dbf(dbf), lire_shp(shp)) if attrs) if p]


def lire_geojson(contenu):
    donnees = json.loads(contenu)
    parcelles = []
    for f in donnees.get("features", []):
        g = f.get("geometry") or {}
        coords = g.get("coordinates") or []
        anneau = coords[0] if g.get("type") == "Polygon" and coords else coords[0][0] if g.get("type") == "MultiPolygon" and coords else []
        p = _depuis_attributs(f.get("properties") or {}, [tuple(pt[:2]) for pt in anneau])
        if p:
            parcelles.append(p)
    return parcelles


def lire(nom_fichier, contenu):
    """Le bon lecteur selon le fichier. Lève ValueError si rien n'est reconnu."""
    nom = (nom_fichier or "").lower()
    if nom.endswith(".zip") or contenu[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(contenu)) as z:
            noms = z.namelist()
            xml = [n for n in noms if n.lower().endswith(".xml")]
            if xml:
                return [p for n in xml for p in lire_xml(z.read(n))]
            shps = [n for n in noms if n.lower().endswith(".shp")]
            # le shapefile des parcelles (pas celui des îlots), sinon le seul présent
            for shp in sorted(shps, key=lambda n: not re.search(r"parcel", n, re.I)):
                dbf = next((n for n in noms if n.lower() == (shp[:-4] + ".dbf").lower()), None)
                if dbf and (re.search(r"parcel", shp, re.I) or len(shps) == 1):
                    return lire_shapefile(z.read(shp), z.read(dbf))
            geo = [n for n in noms if n.lower().endswith((".geojson", ".json"))]
            if geo:
                return lire_geojson(z.read(geo[0]))
        raise ValueError("Archive sans XML Telepac, sans shapefile de parcelles et sans GeoJSON.")
    if nom.endswith((".geojson", ".json")) or contenu.lstrip()[:1] == b"{":
        return lire_geojson(contenu)
    if contenu.lstrip()[:1] == b"<":
        return lire_xml(contenu)
    raise ValueError("Format non reconnu : envoyez l'export XML de Telepac, ou le ZIP des parcelles (shapefile).")
