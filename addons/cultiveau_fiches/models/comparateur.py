"""Deux à six articles côte à côte : les caractéristiques, les différences surlignées, les prix en regard, la fiche à portée de clic."""

from markupsafe import Markup, escape

from odoo import api, fields, models


def _euros(montant):
    """« 2 500,00 € » : l'espace pour les milliers, la virgule pour les centimes."""
    return f"{montant:,.2f}".replace(",", " ").replace(".", ",") + " €"


class Comparateur(models.TransientModel):
    _name = "cultiveau.comparateur"
    _description = "Comparateur d'articles"

    product_ids = fields.Many2many("product.template", string="Articles à comparer")
    html = fields.Html("Comparaison", compute="_compute_html", sanitize=False)

    @api.depends("product_ids")
    def _compute_html(self):
        societe = self.env.company
        for c in self:
            produits = c.product_ids
            if len(produits) < 2:
                c.html = Markup("<p class='text-muted'>Choisissez au moins deux articles.</p>")
                continue
            familles = produits.mapped("cultiveau_famille_carac_id")
            cles, libelles = [], {}
            for f in familles:
                for cle_, lib in f.liste():
                    if cle_ not in libelles:
                        cles.append(cle_)
                        libelles[cle_] = lib
            for p in produits:  # ce que les fiches ont donné hors liste
                for cle_ in (p.cultiveau_caracteristiques or {}):
                    if cle_ not in libelles:
                        cles.append(cle_)
                        libelles[cle_] = cle_.replace("_", " ")

            def valeur(p, cle_):
                v = (p.cultiveau_caracteristiques or {}).get(cle_)
                return (v.get("valeur"), v.get("page")) if isinstance(v, dict) else (v, None)

            entete = "".join(f"<th class='text-center'>{escape(p.name)}<br/><small class='text-muted'>{escape(p.default_code or '')}</small></th>" for p in produits)
            lignes = []
            for cle_ in cles:
                valeurs = [valeur(p, cle_) for p in produits]
                if all(v in (None, "") for v, _p in valeurs):
                    continue
                differe = len({str(v) for v, _p in valeurs}) > 1
                cellules = "".join(f"<td class='text-center{' fw-bold' if differe else ''}'>{escape(str(v)) if v not in (None, '') else '—'}"
                                   f"{f' <small class=text-muted>p.{p_}</small>' if p_ else ''}</td>" for v, p_ in valeurs)
                lignes.append(f"<tr{' class=table-warning' if differe else ''}><th>{escape(libelles[cle_])}</th>{cellules}</tr>")
            # les lignes fixes : DN, PN, matière, prix, fiche
            fixes = [("DN", lambda p: f"{p.cultiveau_dn:g}" if p.cultiveau_dn else ""), ("PN (bar)", lambda p: f"{p.cultiveau_pn:g}" if p.cultiveau_pn else ""),
                     ("Matière", lambda p: p.cultiveau_matiere or ""), ("Raccordement", lambda p: p.cultiveau_raccordement or ""), ("Fournisseur", lambda p: p.seller_ids[:1].partner_id.name or ""),
                     ("Prix d'achat net HT", lambda p: _euros(p.seller_ids[:1].price) if p.seller_ids[:1].price else ""),
                     ("Prix de vente HT", lambda p: _euros(p.with_company(societe).list_price))]
            for lib, f in fixes:
                vals = [f(p) for p in produits]
                if not any(vals):
                    continue
                differe = len(set(vals)) > 1
                lignes.append(f"<tr><th>{escape(lib)}</th>" + "".join(f"<td class='text-center{' fw-bold' if differe else ''}'>{escape(v) or '—'}</td>" for v in vals) + "</tr>")
            fiches = "".join(f"<td class='text-center'>" + (f"<a href='/web/content/cultiveau.fiche/{p.cultiveau_fiche_id.id}/fichier?download=false' target='_blank'>Fiche technique</a>" if p.cultiveau_fiche_id.fichier else
                                                      (f"<a href='{escape(p.cultiveau_fiche_url)}' target='_blank'>Fiche (lien)</a>" if p.cultiveau_fiche_url else "—")) + "</td>" for p in produits)
            lignes.append(f"<tr><th>Fiche</th>{fiches}</tr>")
            c.html = Markup(f"<table class='table table-sm table-bordered'><thead><tr><th></th>{entete}</tr></thead><tbody>{''.join(lignes)}</tbody></table>"
                            "<p class='text-muted small'>En gras, sur fond jaune : ce qui diffère. « p. » : la page de la fiche où la valeur a été lue.</p>")
