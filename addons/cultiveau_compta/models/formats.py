"""Lecture des relevés bancaires, sans bibliothèque : CSV de la banque, OFX, CAMT.053 / 052, QIF.

Chaque ligne lue : {"date": date, "libelle": str, "montant": float, "reference": str, "empreinte": str}.
L'empreinte sert à ne jamais importer deux fois la même opération.
"""

import csv
import hashlib
import io
import re
import unicodedata
from datetime import date, datetime
from xml.etree import ElementTree

MOTS_DATE = ("date op", "date d'op", "date de l'op", "date operation", "date", "booking", "posted")
MOTS_LIBELLE = ("libelle", "libellé", "label", "description", "intitule", "intitulé", "nature", "motif", "designation", "désignation", "memo", "communication", "detail")
MOTS_MONTANT = ("montant", "amount", "somme")
MOTS_DEBIT = ("debit", "débit")
MOTS_CREDIT = ("credit", "crédit")
MOTS_REF = ("reference", "référence", "ref", "numero", "n°", "id")


def normaliser(texte):
    """Sans accent, en majuscules, un seul espace : pour comparer des libellés de banque."""
    texte = unicodedata.normalize("NFKD", texte or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", texte).strip().upper()


def empreinte(d, montant, libelle, cle=None):
    base = cle or f"{d.isoformat()}|{montant:.2f}|{normaliser(libelle)[:80]}"
    return hashlib.sha1(base.encode()).hexdigest()[:32]


def lire_montant(texte):
    t = (texte or "").strip().replace(" ", "").replace("\xa0", "").replace(" ", "")
    if not t:
        return None
    t = t.replace("€", "").replace("EUR", "")
    negatif = t.startswith("-") or t.endswith("-") or (t.startswith("(") and t.endswith(")"))
    t = t.strip("-()+")
    if "," in t and "." in t:
        t = t.replace(".", "").replace(",", ".") if t.rfind(",") > t.rfind(".") else t.replace(",", "")
    elif "," in t:
        t = t.replace(",", ".")
    try:
        v = float(t)
    except ValueError:
        return None
    return -v if negatif else v


def lire_date(texte):
    t = (texte or "").strip()[:19]
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d", "%Y/%m/%d", "%d/%m/%y", "%Y%m%d", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(t if fmt != "%Y%m%d" else t[:8], fmt).date()
        except ValueError:
            continue
    return None


def decoder(contenu):
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return contenu.decode(enc)
        except UnicodeDecodeError:
            continue
    return contenu.decode("latin-1", "replace")


def lire(nom_fichier, contenu):
    """Devine le format et renvoie les lignes et, si le fichier les donne, les soldes : (lignes, solde_debut, solde_fin)."""
    texte = decoder(contenu)
    debut = texte.lstrip()[:400].upper()
    if "<DOCUMENT" in debut and "CAMT" in debut or "<BKTOCSTMRSTMT" in debut or "<BKTOCSTMRACCTRPT" in debut:
        return lire_camt(contenu)
    if "OFXHEADER" in debut or "<OFX>" in debut or nom_fichier.lower().endswith((".ofx", ".qfx")):
        return lire_ofx(texte), None, None
    if debut.startswith("!TYPE") or nom_fichier.lower().endswith(".qif"):
        return lire_qif(texte), None, None
    return lire_csv(texte), None, None


# ---------------------------------------------------------------- CSV

def _colonne(entetes, mots, exclure=()):
    for i, e in enumerate(entetes):
        n = normaliser(e).lower()
        if any(m in n for m in mots) and not any(x in n for x in exclure):
            return i
    return None


def lire_csv(texte):
    lignes = [l for l in texte.splitlines() if l.strip()]
    if not lignes:
        return []
    echantillon = "\n".join(lignes[:20])
    try:
        sep = csv.Sniffer().sniff(echantillon, delimiters=";,\t|").delimiter
    except csv.Error:
        sep = ";" if echantillon.count(";") >= echantillon.count(",") else ","
    tableau = list(csv.reader(lignes, delimiter=sep))
    # la ligne d'en-tête est la première qui nomme une date et un montant (les banques mettent parfois un préambule)
    i_entete, cols = None, None
    for i, ligne in enumerate(tableau[:15]):
        d = _colonne(ligne, MOTS_DATE, exclure=("valeur", "value"))
        m, deb, cre = _colonne(ligne, MOTS_MONTANT), _colonne(ligne, MOTS_DEBIT), _colonne(ligne, MOTS_CREDIT)
        if d is not None and (m is not None or deb is not None or cre is not None):
            i_entete = i
            cols = {"date": d, "montant": m, "debit": deb, "credit": cre,
                    "libelle": _colonne(ligne, MOTS_LIBELLE), "reference": _colonne(ligne, MOTS_REF, exclure=("date",))}
            break
    resultats = []
    if i_entete is None:  # pas d'en-tête : date, libellé, montant (ou débit, crédit) dans l'ordre
        for ligne in tableau:
            if len(ligne) < 3:
                continue
            d = lire_date(ligne[0])
            if not d:
                continue
            montants = [lire_montant(c) for c in ligne[1:]]
            nombres = [(k + 1, v) for k, v in enumerate(montants) if v is not None and not lire_date(ligne[k + 1])]
            if not nombres:
                continue
            i_montant, montant = nombres[-1] if len(nombres) == 1 else (nombres[0] if nombres[0][1] else nombres[1])
            if len(nombres) >= 2 and nombres[0][1] and nombres[1][1] is not None and nombres[0][0] + 1 == nombres[1][0] and not nombres[1][1]:
                montant = -abs(nombres[0][1])  # colonnes débit puis crédit
            libelle = " ".join(c for k, c in enumerate(ligne[1:], start=1) if k != i_montant and lire_montant(c) is None and not lire_date(c)).strip()
            resultats.append(_ligne(d, libelle, montant, ""))
        return resultats
    for ligne in tableau[i_entete + 1:]:
        if len(ligne) <= cols["date"]:
            continue
        d = lire_date(ligne[cols["date"]])
        if not d:
            continue
        montant = None
        if cols["montant"] is not None and cols["montant"] < len(ligne):
            montant = lire_montant(ligne[cols["montant"]])
        if montant is None and (cols["debit"] is not None or cols["credit"] is not None):
            deb = lire_montant(ligne[cols["debit"]]) if cols["debit"] is not None and cols["debit"] < len(ligne) else None
            cre = lire_montant(ligne[cols["credit"]]) if cols["credit"] is not None and cols["credit"] < len(ligne) else None
            if deb or cre:
                montant = (cre or 0.0) - abs(deb or 0.0)
        if montant is None:
            continue
        libelle = ligne[cols["libelle"]].strip() if cols["libelle"] is not None and cols["libelle"] < len(ligne) else ""
        if not libelle:
            libelle = " ".join(c for k, c in enumerate(ligne) if k not in cols.values() and c.strip())[:200]
        reference = ligne[cols["reference"]].strip() if cols["reference"] is not None and cols["reference"] < len(ligne) else ""
        resultats.append(_ligne(d, libelle, montant, reference))
    return resultats


def _ligne(d, libelle, montant, reference, cle=None):
    return {"date": d, "libelle": re.sub(r"\s+", " ", libelle or "").strip() or "Opération", "montant": round(montant, 2),
            "reference": reference or "", "empreinte": empreinte(d, montant, libelle, cle)}


# ---------------------------------------------------------------- OFX

def _ofx_champ(bloc, nom):
    m = re.search(rf"<{nom}>([^<\r\n]*)", bloc, re.I)
    return m.group(1).strip() if m else ""


def lire_ofx(texte):
    resultats = []
    for bloc in re.findall(r"<STMTTRN>(.*?)(?:</STMTTRN>|(?=<STMTTRN>))", texte, re.S | re.I):
        d = lire_date(_ofx_champ(bloc, "DTPOSTED")[:8])
        montant = lire_montant(_ofx_champ(bloc, "TRNAMT"))
        if not d or montant is None:
            continue
        libelle = " ".join(x for x in (_ofx_champ(bloc, "NAME"), _ofx_champ(bloc, "MEMO")) if x)
        fitid = _ofx_champ(bloc, "FITID")
        resultats.append(_ligne(d, libelle, montant, _ofx_champ(bloc, "CHECKNUM") or fitid, cle=("OFX|" + fitid) if fitid else None))
    return resultats


# ---------------------------------------------------------------- CAMT

def _local(tag):
    return tag.split("}")[-1]


def _texte(element, chemin):
    """Premier texte trouvé en descendant par noms locaux : 'NtryDtls/TxDtls/RmtInf/Ustrd'."""
    courant = [element]
    for nom in chemin.split("/"):
        suivant = []
        for e in courant:
            suivant.extend(c for c in e if _local(c.tag) == nom)
        courant = suivant
        if not courant:
            return ""
    return " ".join((c.text or "").strip() for c in courant if (c.text or "").strip())


def lire_camt(contenu):
    racine = ElementTree.fromstring(contenu)
    resultats, solde_debut, solde_fin = [], None, None
    for bal in racine.iter():
        if _local(bal.tag) != "Bal":
            continue
        code = _texte(bal, "Tp/CdOrPrtry/Cd")
        montant = lire_montant(_texte(bal, "Amt"))
        if montant is None:
            continue
        if _texte(bal, "CdtDbtInd") == "DBIT":
            montant = -montant
        if code == "OPBD":
            solde_debut = montant
        elif code == "CLBD":
            solde_fin = montant
    for ntry in racine.iter():
        if _local(ntry.tag) != "Ntry":
            continue
        montant = lire_montant(_texte(ntry, "Amt"))
        if montant is None:
            continue
        if _texte(ntry, "CdtDbtInd") == "DBIT":
            montant = -montant
        d = lire_date(_texte(ntry, "BookgDt/Dt") or _texte(ntry, "BookgDt/DtTm") or _texte(ntry, "ValDt/Dt"))
        if not d:
            continue
        tiers = _texte(ntry, "NtryDtls/TxDtls/RltdPties/Dbtr/Nm") if montant > 0 else _texte(ntry, "NtryDtls/TxDtls/RltdPties/Cdtr/Nm")
        if not tiers:
            tiers = _texte(ntry, "NtryDtls/TxDtls/RltdPties/Dbtr/Pty/Nm") if montant > 0 else _texte(ntry, "NtryDtls/TxDtls/RltdPties/Cdtr/Pty/Nm")
        motif = _texte(ntry, "NtryDtls/TxDtls/RmtInf/Ustrd") or _texte(ntry, "AddtlNtryInf")
        libelle = " ".join(x for x in (tiers, motif) if x) or _texte(ntry, "AddtlNtryInf")
        ref = _texte(ntry, "NtryDtls/TxDtls/Refs/EndToEndId") or _texte(ntry, "AcctSvcrRef")
        cle = _texte(ntry, "AcctSvcrRef") or _texte(ntry, "NtryDtls/TxDtls/Refs/AcctSvcrRef")
        resultats.append(_ligne(d, libelle, montant, ref, cle=("CAMT|" + cle) if cle else None))
    return resultats, solde_debut, solde_fin


# ---------------------------------------------------------------- QIF

def lire_qif(texte):
    resultats, courant = [], {}
    for brute in texte.splitlines():
        l = brute.rstrip("\r")
        if not l or l.startswith("!"):
            continue
        code, valeur = l[0], l[1:].strip()
        if code == "^":
            if courant.get("date") and courant.get("montant") is not None:
                resultats.append(_ligne(courant["date"], " ".join(x for x in (courant.get("P"), courant.get("M")) if x), courant["montant"], courant.get("N", "")))
            courant = {}
        elif code == "D":
            courant["date"] = lire_date(valeur.replace("'", "/"))
        elif code == "T" or code == "U":
            courant["montant"] = lire_montant(valeur)
        elif code in "PMN":
            courant[code] = valeur
    return resultats
