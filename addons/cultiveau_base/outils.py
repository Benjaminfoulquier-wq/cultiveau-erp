"""Lecture d'un fichier tabulaire (Excel .xlsx/.xls, CSV) et reconnaissance des colonnes par leur intitulé.

Les adhérents arrivent avec le fichier de leur ancien logiciel, de leur comptable ou un export de leur
téléphone : les colonnes s'appellent comme elles veulent. On les reconnaît par synonymes, après avoir
retiré accents, majuscules et ponctuation ; l'en-tête peut être n'importe où dans les premières lignes.
"""
import csv
import io
import re
import unicodedata


def normaliser(texte):
    """« Téléphone (portable) * » → « telephone portable »."""
    s = unicodedata.normalize("NFKD", str(texte or "")).encode("ascii", "ignore").decode().lower()
    s = s.replace("€", " eur ").replace("°", " ").replace("'", " ").replace("’", " ")
    s = re.sub(r"[*()\[\]:;,./\\%-]", " ", s)
    return " ".join(s.replace("_", " ").split())


def nombre(valeur):
    """« 1 250,50 € » → 1250.5 ; None si ce n'est pas un nombre."""
    if valeur in (None, "", False):
        return None
    if isinstance(valeur, (int, float)):
        return float(valeur)
    s = re.sub(r"[^0-9.,\-]", "", str(valeur).replace(" ", "").replace(" ", ""))
    if s.count(",") and s.count("."):
        s = s.replace(".", "") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    s = s.replace(",", ".")
    try:
        return float(s) if s not in ("", "-", ".") else None
    except ValueError:
        return None


def texte(valeur):
    if valeur in (None, False):
        return ""
    if isinstance(valeur, float) and valeur.is_integer():
        return str(int(valeur))
    return " ".join(str(valeur).split())


def lire_tableau(nom_fichier, contenu):
    """Renvoie les lignes (listes de valeurs) du fichier, vides retirées. Lève ValueError si illisible."""
    nom = (nom_fichier or "").lower()
    if nom.endswith((".xlsx", ".xlsm")) or contenu[:4] == b"PK\x03\x04":
        import openpyxl

        try:
            wb = openpyxl.load_workbook(io.BytesIO(contenu), read_only=True, data_only=True)
        except Exception as e:  # noqa: BLE001 — classeur corrompu, protégé…
            raise ValueError(f"classeur Excel illisible ({e})") from e
        lignes = [list(row) for row in wb.active.iter_rows(values_only=True)]
    elif nom.endswith(".xls") or contenu[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        try:
            import xlrd

            wb = xlrd.open_workbook(file_contents=contenu)
            feuille = wb.sheet_by_index(0)
            lignes = [feuille.row_values(i) for i in range(feuille.nrows)]
        except Exception as e:  # noqa: BLE001
            raise ValueError(f"classeur Excel (.xls) illisible ({e})") from e
    else:
        brut = None
        for codage in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                brut = contenu.decode(codage)
                break
            except UnicodeDecodeError:
                continue
        if brut is None or "\x00" in brut[:2000]:
            raise ValueError("ce fichier n'est ni un classeur Excel ni un CSV")
        try:
            dialecte = csv.Sniffer().sniff(brut[:5000], delimiters=";,\t|") if brut.strip() else csv.excel
        except csv.Error:
            dialecte = csv.excel
            dialecte.delimiter = ";" if brut.count(";") >= brut.count(",") else ","
        lignes = list(csv.reader(io.StringIO(brut), dialecte))
    return [l for l in lignes if any(v not in (None, "") and str(v).strip() for v in l)]


def reconnaitre(lignes, colonnes, obligatoires=()):
    """Trouve la ligne d'en-tête (celle qui contient le plus de colonnes connues, dont les obligatoires) ;
    renvoie (correspondance {champ: index}, en-tête brut, lignes de données, intitulés inconnus)."""
    synonymes = {}
    for champ, noms in colonnes.items():
        for n in noms:
            synonymes.setdefault(normaliser(n), champ)
    meilleur = None
    for i, ligne in enumerate(lignes[:20]):
        trouve, inconnus = {}, []
        for j, cellule in enumerate(ligne):
            cle = normaliser(cellule)
            if not cle:
                continue
            champ = synonymes.get(cle)
            if champ and champ not in trouve:
                trouve[champ] = j
            elif not champ:
                inconnus.append(texte(cellule))
        score = len(trouve)
        if score and all(o in trouve for o in obligatoires) and (meilleur is None or score > meilleur[0]):
            meilleur = (score, i, trouve, inconnus)
    if meilleur is None:
        return {}, [], [], []
    _, i, trouve, inconnus = meilleur
    return trouve, lignes[i], lignes[i + 1:], inconnus


def valeur(ligne, correspondance, champ):
    i = correspondance.get(champ)
    if i is None or i >= len(ligne):
        return ""
    return texte(ligne[i])
