"""Les soldes des comptes sur une période, et les regroupements du plan comptable général pour le bilan et le compte de résultat."""

from odoo import models


def soldes(env, societe, debut, fin, codes=None):
    """{code de compte: solde (débit − crédit)} des écritures validées de la période."""
    domaine = [("company_id", "=", societe.id), ("parent_state", "=", "posted"), ("date", "<=", fin)]
    if debut:
        domaine.append(("date", ">=", debut))
    if codes:
        domaine.append(("account_id.code", "=like", codes))
    resultat = {}
    # le code d'un compte dépend de la société : on lit dans la sienne
    for compte, balance in env["account.move.line"].with_company(societe)._read_group(domaine, ["account_id"], ["balance:sum"]):
        code = compte.with_company(societe).code or ""
        resultat[code] = resultat.get(code, 0.0) + balance
    return resultat


def somme(soldes_, prefixes, signe=1):
    """La somme des soldes des comptes dont le code commence par l'un des préfixes (× signe : −1 pour lire un crédit en positif)."""
    return signe * sum(v for c, v in soldes_.items() if any(c.startswith(p) for p in prefixes))


def somme_si(soldes_, prefixes, debiteur=True):
    """Les comptes de tiers se lisent à l'actif s'ils sont débiteurs, au passif s'ils sont créditeurs : on trie compte par compte."""
    total = 0.0
    for c, v in soldes_.items():
        if any(c.startswith(p) for p in prefixes) and ((v > 0) if debiteur else (v < 0)):
            total += abs(v)
    return total


# Le compte de résultat (liasse simplifiée), ligne par ligne : (libellé, préfixes, produit ?)
COMPTE_DE_RESULTAT = [
    ("Ventes de marchandises", ("707",), True),
    ("Production vendue : biens", ("701", "702", "703", "704", "705"), True),
    ("Production vendue : services et travaux", ("706", "708"), True),
    ("Rabais, remises accordés", ("709",), True),
    ("Subventions, autres produits d'exploitation", ("71", "72", "74", "75", "781", "791"), True),
    ("Achats de marchandises et variation de stock", ("607", "6087", "6097", "6037"), False),
    ("Achats de matières, fournitures et variation de stock", ("601", "602", "6081", "6082", "6091", "6092", "6031", "6032"), False),
    ("Autres achats et charges externes", ("604", "605", "606", "6084", "6085", "6086", "6094", "6095", "6096", "61", "62"), False),
    ("Impôts et taxes", ("63",), False),
    ("Salaires", ("641", "644"), False),
    ("Charges sociales", ("645", "646", "647", "648"), False),
    ("Dotations aux amortissements et provisions", ("681",), False),
    ("Autres charges d'exploitation", ("65",), False),
]
FINANCIER = [("Produits financiers", ("76", "786", "796"), True), ("Charges financières", ("66", "686"), False)]
EXCEPTIONNEL = [("Produits exceptionnels", ("77", "787", "797"), True), ("Charges exceptionnelles", ("67", "687"), False)]
IMPOT = [("Impôt sur les bénéfices", ("69",), False)]


class Outils(models.AbstractModel):
    _name = "cultiveau.comptes"
    _description = "Outils de lecture des comptes"
