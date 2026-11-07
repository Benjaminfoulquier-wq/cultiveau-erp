"""Le devis : ses marges par lot, ses fiches techniques jointes à l'envoi, ses notes techniques tirées du référentiel."""
import base64
import logging
from collections import OrderedDict
from markupsafe import Markup, escape

import requests

from odoo import api, fields, models

from .avis import plat

_logger = logging.getLogger(__name__)
TITRE_NOTES = "Notes techniques (référentiel Cultiveau V4)"


class Devis(models.Model):
    _inherit = "sale.order"

    cultiveau_marges_html = fields.Html("Marges par lot", compute="_compute_marges", sanitize=False)
    cultiveau_marge_alerte = fields.Char("Repère de marge", compute="_compute_marges")
    cultiveau_fiche_ids = fields.Many2many("cultiveau.fiche", string="Fiches techniques des matériels", compute="_compute_fiches")
    cultiveau_nb_fiches = fields.Integer("Fiches techniques", compute="_compute_fiches")
    cultiveau_nb_avis = fields.Integer("Notes du référentiel", compute="_compute_avis")
    cultiveau_avis_html = fields.Html("Ce que dirait le référentiel", compute="_compute_avis", sanitize=False)

    # ---------------------------------------------------------------- les marges
    @api.depends("order_line.price_subtotal", "order_line.purchase_price", "order_line.product_uom_qty", "order_line.display_type", "order_line.cultiveau_sous_lot",
                 "margin", "margin_percent")
    def _compute_marges(self):
        for o in self:
            lots, courant = [], None
            for l in o.order_line.sorted(lambda l: (l.sequence, l.id)):
                if l.display_type == "line_section" and not l.cultiveau_sous_lot:
                    courant = {"nom": l.name, "vente": 0.0, "cout": 0.0}
                    lots.append(courant)
                    continue
                if l.display_type or not l.product_id:
                    continue
                if courant is None:
                    courant = {"nom": "Hors lot", "vente": 0.0, "cout": 0.0}
                    lots.append(courant)
                courant["vente"] += l.price_subtotal
                courant["cout"] += (l.purchase_price or 0.0) * l.product_uom_qty
            mini = o.company_id.cultiveau_marge_mini_pct or 0.0
            lignes = []
            for lot in lots:
                marge = lot["vente"] - lot["cout"]
                pct = marge / lot["vente"] * 100 if lot["vente"] else 0.0
                couleur = "#1a7f4b" if pct >= mini else "#b23b3b"
                lignes.append(Markup("<tr><td>%s</td><td style='text-align:right'>%s</td><td style='text-align:right'>%s</td><td style='text-align:right;color:%s;font-weight:600'>%s %%</td></tr>") % (
                    escape(lot["nom"]), f"{lot['vente']:,.0f}".replace(",", " "), f"{marge:,.0f}".replace(",", " "), couleur, f"{pct:.0f}"))
            if len(lots) > 1 and lignes:
                o.cultiveau_marges_html = Markup("<table class='table table-sm cv-marges'><thead><tr><th>Lot</th><th style='text-align:right'>Vente HT</th><th style='text-align:right'>Marge</th><th style='text-align:right'>Taux</th></tr></thead><tbody>%s</tbody></table>") % Markup("").join(lignes)
            else:
                o.cultiveau_marges_html = False
            pct_total = (o.margin_percent or 0.0) * 100
            if not o.amount_untaxed:
                o.cultiveau_marge_alerte = False
            elif pct_total < mini:
                o.cultiveau_marge_alerte = f"Marge {pct_total:.0f} %, sous le minimum de {mini:.0f} % de l'entreprise."
            else:
                o.cultiveau_marge_alerte = False

    # ---------------------------------------------------------------- les fiches techniques
    @api.depends("order_line.product_id")
    def _compute_fiches(self):
        for o in self:
            fiches = o.order_line.product_id.product_tmpl_id.cultiveau_fiche_id.filtered(lambda f: f.fichier or f.url)
            o.cultiveau_fiche_ids = fiches
            o.cultiveau_nb_fiches = len(fiches)

    def cultiveau_fiches_jointes(self):
        """Les fiches techniques du devis en pièces jointes (ir.attachment), rapatriées depuis leur lien si besoin. Une fiche illisible est passée."""
        self.ensure_one()
        Attachment = self.env["ir.attachment"].sudo()
        pieces = Attachment.browse()
        for fiche in self.cultiveau_fiche_ids:
            if not fiche.fichier and fiche.url:
                try:
                    r = requests.get(fiche.url, timeout=30)
                    if r.status_code == 200 and r.content and len(r.content) < 20_000_000 and (r.content[:5] == b"%PDF-" or "pdf" in (r.headers.get("Content-Type") or "")):
                        fiche.sudo().cultiveau_joindre(r.content, (fiche.fichier_nom or f"{fiche.name}.pdf")[:120], propager=False)
                except requests.RequestException as e:  # noqa: PERF203
                    _logger.info("Fiche %s non rapatriée (%s)", fiche.name, e)
            if not fiche.fichier:
                continue
            nom = fiche.fichier_nom or f"{fiche.name}.pdf"
            if not nom.lower().endswith(".pdf"):
                nom += ".pdf"
            piece = Attachment.search([("res_model", "=", "sale.order"), ("res_id", "=", self.id), ("name", "=", nom)], limit=1)
            if not piece:
                piece = Attachment.create({"name": nom, "datas": fiche.fichier, "res_model": "sale.order", "res_id": self.id, "mimetype": "application/pdf"})
            pieces |= piece
        return pieces

    def action_quotation_send(self):
        action = super().action_quotation_send()
        if len(self) != 1 or self.env.context.get("proforma") or not isinstance(action, dict):
            return action
        if self.company_id.cultiveau_devis_avis_auto and self.state in ("draft", "sent"):
            self.action_relire_referentiel()
        if self.company_id.cultiveau_devis_fiches:
            pieces = self.cultiveau_fiches_jointes()
            if pieces:
                ctx = dict(action.get("context") or {})
                ctx["default_attachment_ids"] = [(6, 0, pieces.ids)]
                action["context"] = ctx
        return action

    def action_voir_fiches(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "name": "Fiches techniques du devis", "res_model": "cultiveau.fiche", "view_mode": "list,form",
                "domain": [("id", "in", self.cultiveau_fiche_ids.ids)]}

    # ---------------------------------------------------------------- le référentiel
    def cultiveau_lots_corpus(self):
        """Pour chaque lot du devis, le texte de ses lignes (désignation, référence, famille, ligne), aplati pour la recherche de mots."""
        self.ensure_one()
        lots, courant = OrderedDict(), None
        for l in self.order_line.sorted(lambda l: (l.sequence, l.id)):
            if l.display_type == "line_section" and not l.cultiveau_sous_lot:
                courant = l.name or "Lot"
                lots.setdefault(courant, "")
                continue
            if l.display_type or not l.product_id or l.cultiveau_avis_id:
                continue
            if courant is None:
                courant = "Hors lot"
                lots.setdefault(courant, "")
            p = l.product_id
            lots[courant] += " " + plat(" ".join(filter(None, [p.name, p.default_code or "", p.categ_id.complete_name or "", l.name or ""])))
        return lots

    @api.depends("order_line.product_id", "order_line.name", "cultiveau_type_systeme")
    def _compute_avis(self):
        Avis = self.env["cultiveau.referentiel.avis"]
        for o in self:
            resultats = Avis.pour_devis(o) if o.order_line else []
            o.cultiveau_nb_avis = len(resultats)
            if not resultats:
                o.cultiveau_avis_html = Markup("<p class='text-muted'>Rien à signaler avec les règles en place : ajoutez des lignes, ou complétez les règles dans Réglages › Cultiveau.</p>") if o.order_line else False
                continue
            items = []
            for a, lots in resultats:
                ou = Markup(" <span class='text-muted'>(%s)</span>") % escape(", ".join(lots)) if lots else ""
                items.append(Markup("<li><b>%s</b>%s<br/><span style='font-size:92%%'>%s</span></li>") % (escape(a.name), ou, escape(a.libelle())))
            o.cultiveau_avis_html = Markup("<ul class='cv-avis'>%s</ul>") % Markup("").join(items)

    def action_relire_referentiel(self):
        """(Re)génère la section « Notes techniques » en fin de devis : une note par avis déclenché. Les notes précédentes sont remplacées."""
        Ligne = self.env["sale.order.line"]
        for o in self:
            anciennes = o.order_line.filtered(lambda l: l.cultiveau_avis_id or (l.display_type == "line_section" and l.name == TITRE_NOTES))
            anciennes.unlink()
            resultats = self.env["cultiveau.referentiel.avis"].pour_devis(o)
            if not resultats:
                continue
            seq = max(o.order_line.mapped("sequence") or [0]) + 10
            Ligne.create({"order_id": o.id, "display_type": "line_section", "name": TITRE_NOTES, "sequence": seq})
            for a, lots in resultats:
                seq += 1
                texte = a.libelle()
                if lots and len(o.cultiveau_lots_corpus()) > 1:
                    texte = f"{', '.join(lots)} : {texte}"
                Ligne.create({"order_id": o.id, "display_type": "line_note", "name": texte, "sequence": seq, "cultiveau_avis_id": a.id})
            o.message_post(body=Markup("<p>Devis relu avec le référentiel : %s note(s) technique(s) ajoutée(s).</p>") % len(resultats), subtype_xmlid="mail.mt_note")
        return True

    def action_retirer_notes_referentiel(self):
        for o in self:
            o.order_line.filtered(lambda l: l.cultiveau_avis_id or (l.display_type == "line_section" and l.name == TITRE_NOTES)).unlink()
        return True


class Ligne(models.Model):
    _inherit = "sale.order.line"

    cultiveau_avis_id = fields.Many2one("cultiveau.referentiel.avis", "Avis du référentiel", index=True, ondelete="set null", copy=False)
