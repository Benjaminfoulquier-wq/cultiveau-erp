"""Le bilan et le compte de résultat, lus dans les écritures, avec l'exercice précédent en regard."""

import base64
from datetime import date, timedelta

from markupsafe import Markup, escape

from odoo import api, fields, models

from .comptes import COMPTE_DE_RESULTAT, EXCEPTIONNEL, FINANCIER, IMPOT, soldes, somme, somme_si


def _eur(v):
    return f"{v:,.0f} €".replace(",", " ").replace("-", "−")


class Etats(models.TransientModel):
    _name = "cultiveau.etats"
    _description = "Bilan et compte de résultat"

    company_id = fields.Many2one("res.company", "Société", required=True, default=lambda self: self.env.company)
    date_debut = fields.Date("Du", required=True, default=lambda self: date(fields.Date.context_today(self).year, 1, 1))
    date_fin = fields.Date("Au", required=True, default=lambda self: fields.Date.context_today(self))
    comparer = fields.Boolean("Comparer à l'exercice précédent", default=True)
    resultat_html = fields.Html("Compte de résultat", readonly=True, sanitize=False)
    bilan_html = fields.Html("Bilan", readonly=True, sanitize=False)
    chiffre_affaires = fields.Float("Chiffre d'affaires HT", readonly=True)
    resultat_net = fields.Float("Résultat net", readonly=True)
    total_bilan = fields.Float("Total du bilan", readonly=True)

    # ---------------------------------------------------------------- compte de résultat

    @api.model
    def compte_de_resultat(self, societe, debut, fin):
        """Les lignes du compte de résultat et ses soldes intermédiaires : liste de (libellé, montant, niveau)."""
        s = soldes(self.env, societe, debut, fin)
        lignes, produits, charges = [], 0.0, 0.0

        def bloc(definition):
            p = c = 0.0
            for libelle, prefixes, est_produit in definition:
                montant = somme(s, prefixes, -1 if est_produit else 1)
                lignes.append((libelle, montant, 1))
                if est_produit:
                    p += montant
                else:
                    c += montant
            return p, c

        ca = somme(s, ("70",), -1)
        p, c = bloc(COMPTE_DE_RESULTAT)
        exploitation = p - c
        lignes.append(("Résultat d'exploitation", exploitation, 0))
        pf, cf = bloc(FINANCIER)
        lignes.append(("Résultat financier", pf - cf, 0))
        lignes.append(("Résultat courant avant impôt", exploitation + pf - cf, 0))
        pe, ce = bloc(EXCEPTIONNEL)
        lignes.append(("Résultat exceptionnel", pe - ce, 0))
        _pi, ci = bloc(IMPOT)
        net = exploitation + pf - cf + pe - ce - ci
        lignes.append(("Résultat net", net, 0))
        return {"lignes": lignes, "ca": ca, "net": net, "produits": p + pf + pe, "charges": c + cf + ce + ci}

    # ---------------------------------------------------------------- bilan

    @api.model
    def bilan(self, societe, fin, resultat_net):
        """Le bilan au soir du `fin`, depuis l'origine des écritures ; le résultat de l'exercice en cours s'ajoute aux capitaux propres."""
        s = soldes(self.env, societe, None, fin)
        actif = [
            ("Immobilisations incorporelles", somme(s, ("20", "232", "237")) - somme(s, ("280", "290"), -1)),
            ("Immobilisations corporelles", somme(s, ("21", "22", "231", "238")) - somme(s, ("281", "282", "291"), -1)),
            ("Immobilisations financières", somme(s, ("26", "27")) - somme(s, ("296", "297"), -1)),
            ("Stocks et en-cours", somme(s, ("31", "32", "33", "34", "35", "36", "37")) - somme(s, ("39",), -1)),
            ("Avances versées aux fournisseurs", somme_si(s, ("4091",))),
            ("Créances clients", somme_si(s, ("411", "413", "416", "418")) - somme(s, ("491",), -1)),
            ("Autres créances (TVA, État, divers)", somme_si(s, ("40",), True) - somme_si(s, ("4091",)) + somme_si(s, ("42", "43", "44", "45", "46", "47"), True) - somme_si(s, ("419",), True)),
            ("Valeurs mobilières de placement", somme(s, ("50",))),
            ("Disponibilités (banques, caisse)", somme_si(s, ("51", "53", "54", "58"), True)),
            ("Charges constatées d'avance", somme(s, ("486",))),
        ]
        capitaux = somme(s, ("10", "11", "13", "14"), -1) + somme(s, ("12",), -1) + resultat_net
        passif = [
            ("Capitaux propres (dont résultat de l'exercice)", capitaux),
            ("Provisions", somme(s, ("15",), -1)),
            ("Emprunts et dettes financières (dont découverts)", somme(s, ("16", "17"), -1) + somme_si(s, ("51", "53", "54", "58"), False)),
            ("Avances reçues des clients", somme_si(s, ("419",), False)),
            ("Dettes fournisseurs", somme_si(s, ("40",), False) - somme_si(s, ("4091",), False)),
            ("Dettes fiscales et sociales", somme_si(s, ("42", "43", "44"), False)),
            ("Autres dettes", somme_si(s, ("45", "46", "47"), False) + somme_si(s, ("411", "413", "416", "418"), False)),
            ("Produits constatés d'avance", somme(s, ("487",), -1)),
        ]
        return {"actif": actif, "passif": passif, "total_actif": sum(m for _, m in actif), "total_passif": sum(m for _, m in passif)}

    # ---------------------------------------------------------------- écran

    def action_calculer(self):
        self.ensure_one()
        societe, debut, fin = self.company_id, self.date_debut, self.date_fin
        cr = self.compte_de_resultat(societe, debut, fin)
        precedent = None
        if self.comparer:
            d0, d1 = debut.replace(year=debut.year - 1), fin.replace(year=fin.year - 1) if not (fin.month == 2 and fin.day == 29) else fin.replace(year=fin.year - 1, day=28)
            precedent = self.compte_de_resultat(societe, d0, d1)
        lignes = []
        for i, (libelle, montant, niveau) in enumerate(cr["lignes"]):
            avant = precedent["lignes"][i][1] if precedent else None
            style = " class='fw-bold table-active'" if niveau == 0 else ""
            lignes.append(f"<tr{style}><td>{escape(libelle)}</td><td class='text-end'>{_eur(montant)}</td>" + (f"<td class='text-end text-muted'>{_eur(avant)}</td>" if precedent else "") + "</tr>")
        entete = f"<tr><th>Compte de résultat du {debut:%d/%m/%Y} au {fin:%d/%m/%Y}</th><th class='text-end'>Exercice</th>" + ("<th class='text-end'>Précédent</th>" if precedent else "") + "</tr>"
        self.resultat_html = Markup(f"<table class='table table-sm'>{entete}{''.join(lignes)}</table>")
        b = self.bilan(societe, fin, cr["net"])
        actif = "".join(f"<tr><td>{escape(l)}</td><td class='text-end'>{_eur(m)}</td></tr>" for l, m in b["actif"] if abs(m) >= 0.5)
        passif = "".join(f"<tr><td>{escape(l)}</td><td class='text-end'>{_eur(m)}</td></tr>" for l, m in b["passif"] if abs(m) >= 0.5)
        ecart = b["total_actif"] - b["total_passif"]
        note = "" if abs(ecart) < 1 else f"<p class='text-warning'>Écart actif − passif de {_eur(ecart)} : des écritures hors classes ou un exercice précédent non clôturé (résultat non affecté).</p>"
        self.bilan_html = Markup(
            f"<div class='row'><div class='col-md-6'><table class='table table-sm'><tr><th>Actif au {fin:%d/%m/%Y}</th><th></th></tr>{actif}"
            f"<tr class='fw-bold table-active'><td>Total actif</td><td class='text-end'>{_eur(b['total_actif'])}</td></tr></table></div>"
            f"<div class='col-md-6'><table class='table table-sm'><tr><th>Passif</th><th></th></tr>{passif}"
            f"<tr class='fw-bold table-active'><td>Total passif</td><td class='text-end'>{_eur(b['total_passif'])}</td></tr></table></div></div>{note}")
        self.write({"chiffre_affaires": cr["ca"], "resultat_net": cr["net"], "total_bilan": b["total_actif"]})
        return {"type": "ir.actions.act_window", "res_model": self._name, "res_id": self.id, "view_mode": "form", "target": "current"}

    def action_export_csv(self):
        self.ensure_one()
        cr = self.compte_de_resultat(self.company_id, self.date_debut, self.date_fin)
        b = self.bilan(self.company_id, self.date_fin, cr["net"])
        texte = "Compte de résultat;Montant\n" + "".join(f"{l};{m:.2f}\n".replace(".", ",") for l, m, _n in cr["lignes"])
        texte += "\nActif;Montant\n" + "".join(f"{l};{m:.2f}\n".replace(".", ",") for l, m in b["actif"]) + "\nPassif;Montant\n" + "".join(f"{l};{m:.2f}\n".replace(".", ",") for l, m in b["passif"])
        piece = self.env["ir.attachment"].create({"name": f"etats-{self.company_id.name}-{self.date_fin}.csv".replace(" ", "-"), "datas": base64.b64encode(texte.encode("utf-8-sig")), "mimetype": "text/csv"})
        return {"type": "ir.actions.act_url", "url": f"/web/content/{piece.id}?download=true", "target": "self"}
