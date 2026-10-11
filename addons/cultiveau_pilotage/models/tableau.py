"""Le tableau de bord : la semaine de l'adhérent en une page, et le réseau pour l'équipe Cultiveau."""

from datetime import date, timedelta

from markupsafe import Markup, escape

from odoo import api, fields, models

from .comptes import soldes, somme


def _eur(v):
    return f"{v:,.0f} €".replace(",", " ").replace("-", "−")


def _carte(titre, valeur, detail="", couleur="primary"):
    return (f"<div class='col-6 col-md-3 mb-3'><div class='card h-100 border-{couleur}'><div class='card-body p-3'><div class='text-muted small'>{escape(titre)}</div>"
            f"<div class='fs-3 fw-bold'>{escape(valeur)}</div><div class='small text-muted'>{escape(detail)}</div></div></div></div>")


def _barres(series, libelles, largeur=720, hauteur=180):
    """Deux séries côte à côte par mois (N et N−1), en SVG."""
    maxi = max([v for s in series for v in s] + [1.0])
    G, B, H = 40, 24, 10
    n = len(libelles)
    pas = (largeur - G - 10) / n
    svg = [f"<line x1='{G}' y1='{hauteur - B}' x2='{largeur - 10}' y2='{hauteur - B}' stroke='#c9d2d8'/>"]
    for k, (s, couleur) in enumerate(zip(series, ("#1d7a8c", "#c9d2d8"))):
        for i, v in enumerate(s):
            h = (hauteur - B - H) * v / maxi
            x = G + i * pas + 4 + k * (pas - 8) / 2
            svg.append(f"<rect x='{x:.1f}' y='{hauteur - B - h:.1f}' width='{(pas - 8) / 2 - 1:.1f}' height='{h:.1f}' fill='{couleur}' rx='2'><title>{v:,.0f} €</title></rect>")
    for i, l in enumerate(libelles):
        svg.append(f"<text x='{G + i * pas + pas / 2:.1f}' y='{hauteur - 8}' font-size='10' text-anchor='middle' fill='#4a5560'>{escape(l)}</text>")
    svg.append(f"<text x='{G - 4}' y='{H + 8}' font-size='9' text-anchor='end' fill='#6c7883'>{maxi / 1000:.0f} k€</text>")
    return f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {largeur} {hauteur}' style='width:100%;max-width:{largeur}px'>{''.join(svg)}</svg>"


class Tableau(models.TransientModel):
    _name = "cultiveau.tableau"
    _description = "Tableau de bord"

    company_id = fields.Many2one("res.company", "Société", required=True, default=lambda self: self.env.company)
    reseau = fields.Boolean("Vue réseau", default=False)
    html = fields.Html("Tableau de bord", compute="_compute_html", sanitize=False)

    @api.model
    def _ca_mensuel(self, societe, annee):
        """Le chiffre d'affaires HT facturé par mois (factures clients validées, avoirs déduits)."""
        groupes = self.env["account.move"]._read_group(
            [("company_id", "=", societe.id), ("state", "=", "posted"), ("move_type", "in", ("out_invoice", "out_refund")),
             ("invoice_date", ">=", date(annee, 1, 1)), ("invoice_date", "<=", date(annee, 12, 31))], ["invoice_date:month", "move_type"], ["amount_untaxed_signed:sum"])
        mois = [0.0] * 12
        for periode, _genre, montant in groupes:
            m = fields.Date.to_date(periode).month if not isinstance(periode, str) else int(periode[5:7])
            mois[m - 1] += montant
        return mois

    def _kpi_societe(self, societe, aujourdhui):
        Move, Vente = self.env["account.move"], self.env["sale.order"]
        annee = aujourdhui.year
        ca = self._ca_mensuel(societe, annee)
        ca_prec = self._ca_mensuel(societe, annee - 1)
        ca_annee, ca_mois = sum(ca), ca[aujourdhui.month - 1]
        ca_annee_prec_meme_date = sum(ca_prec[:aujourdhui.month])
        depuis = aujourdhui - timedelta(days=365)
        devis = Vente.search([("company_id", "=", societe.id), ("state", "in", ("draft", "sent"))])
        signees = Vente.search_count([("company_id", "=", societe.id), ("state", "=", "sale"), ("date_order", ">=", depuis)])
        perdues = Vente.search_count([("company_id", "=", societe.id), ("state", "=", "cancel"), ("date_order", ">=", depuis)])
        retards = Move.search([("company_id", "=", societe.id), ("move_type", "=", "out_invoice"), ("state", "=", "posted"), ("payment_state", "in", ("not_paid", "partial")),
                               ("invoice_date_due", "<", aujourdhui)])
        a_payer = Move.search([("company_id", "=", societe.id), ("move_type", "=", "in_invoice"), ("state", "=", "posted"), ("payment_state", "in", ("not_paid", "partial"))])
        s = soldes(self.env, societe, None, aujourdhui)
        tresorerie = somme(s, ("51", "53"))
        tva = somme(s, ("4457",), -1) - somme(s, ("4456",)) - somme(s, ("44567",)) + somme(s, ("44551",), -1)
        return {"ca": ca, "ca_prec": ca_prec, "ca_annee": ca_annee, "ca_mois": ca_mois, "ca_prec_meme_date": ca_annee_prec_meme_date, "devis": devis, "signees": signees, "perdues": perdues,
                "retards": retards, "a_payer": a_payer, "tresorerie": tresorerie, "tva": tva}

    @api.depends("company_id", "reseau")
    def _compute_html(self):
        aujourdhui = fields.Date.context_today(self)
        mois = ["jan", "fév", "mar", "avr", "mai", "juin", "juil", "août", "sep", "oct", "nov", "déc"]
        for t in self:
            if t.reseau and self.env.user.has_group("cultiveau_base.group_equipe"):
                t.html = t._html_reseau(aujourdhui)
                continue
            k = t._kpi_societe(t.company_id, aujourdhui)
            evolution = ((k["ca_annee"] - k["ca_prec_meme_date"]) / k["ca_prec_meme_date"] * 100) if k["ca_prec_meme_date"] else 0.0
            taux = (k["signees"] / (k["signees"] + k["perdues"]) * 100) if (k["signees"] + k["perdues"]) else 0.0
            cartes = [
                _carte(f"Chiffre d'affaires {aujourdhui.year}", _eur(k["ca_annee"]), f"{evolution:+.0f} % vs {aujourdhui.year - 1} à la même date" if k["ca_prec_meme_date"] else "", "primary"),
                _carte("Ce mois-ci", _eur(k["ca_mois"]), f"{mois[aujourdhui.month - 1]} {aujourdhui.year}", "primary"),
                _carte("Devis en cours", f"{len(k['devis'])}", _eur(sum(k["devis"].mapped("amount_untaxed"))) + " HT", "info"),
                _carte("Taux de signature", f"{taux:.0f} %", f"{k['signees']} signés, {k['perdues']} perdus sur 12 mois", "info"),
                _carte("Clients en retard", _eur(sum(k["retards"].mapped("amount_residual"))), f"{len(k['retards'])} facture(s) échue(s)", "danger" if k["retards"] else "success"),
                _carte("Fournisseurs à payer", _eur(sum(k["a_payer"].mapped("amount_residual"))), f"{len(k['a_payer'])} facture(s)", "warning" if k["a_payer"] else "success"),
                _carte("Trésorerie", _eur(k["tresorerie"]), "banques et caisse", "success" if k["tresorerie"] >= 0 else "danger"),
                _carte("TVA en cours", _eur(k["tva"]), "collectée − déductible, à décaisser", "secondary"),
            ]
            extra = []
            Chantier = self.env.get("cultiveau.chantier")
            if Chantier is not None and "etat" in Chantier._fields:
                en_cours = Chantier.search_count([("company_id", "=", t.company_id.id), ("etat", "not in", ("termine", "annule", "receptionne"))])
                extra.append(_carte("Chantiers en cours", str(en_cours), "", "info"))
            Parcelle = self.env.get("cultiveau.parcelle")
            if Parcelle is not None:
                arroser = Parcelle.search_count([("company_id", "=", t.company_id.id), ("etat_eau", "=", "arroser")]) if "etat_eau" in Parcelle._fields else 0
                alertes = self.env["cultiveau.parcelle.alerte"].search_count([("company_id", "=", t.company_id.id), ("etat", "=", "nouvelle")])
                extra.append(_carte("Parcelles à suivre", f"{alertes}", f"alertes à traiter, {arroser} parcelle(s) à arroser", "warning" if alertes else "success"))
            graphe = _barres([k["ca"], k["ca_prec"]], mois)
            t.html = Markup(f"<div class='row'>{''.join(cartes + extra)}</div><h5>Chiffre d'affaires facturé par mois — {aujourdhui.year} (bleu) et {aujourdhui.year - 1} (gris)</h5>{graphe}")

    def _html_reseau(self, aujourdhui):
        lignes = []
        total = 0.0
        for societe in self.env["res.company"].sudo().search([("cultiveau_adherent", "=", True)], order="name"):
            k = self._kpi_societe(societe, aujourdhui)
            derniere = max(self.env["res.users"].sudo().search([("company_id", "=", societe.id), ("share", "=", False)]).mapped("login_date") or [None])
            total += k["ca_annee"]
            lignes.append(f"<tr><td>{escape(societe.name)}</td><td class='text-end'>{_eur(k['ca_annee'])}</td><td class='text-end'>{len(k['devis'])}</td>"
                          f"<td class='text-end'>{_eur(sum(k['retards'].mapped('amount_residual')))}</td><td class='text-end'>{_eur(k['tresorerie'])}</td>"
                          f"<td>{derniere.strftime('%d/%m/%Y') if derniere else '—'}</td></tr>")
        return Markup(f"<h5>Le réseau — chiffre d'affaires {aujourdhui.year} : {_eur(total)}</h5><table class='table table-sm'><tr><th>Adhérent</th><th class='text-end'>CA {aujourdhui.year}</th>"
                      f"<th class='text-end'>Devis en cours</th><th class='text-end'>Retards clients</th><th class='text-end'>Trésorerie</th><th>Dernière connexion</th></tr>{''.join(lignes)}</table>")

    def action_ouvrir(self):
        return {"type": "ir.actions.act_window", "res_model": self._name, "res_id": self.id, "view_mode": "form", "target": "current"}
