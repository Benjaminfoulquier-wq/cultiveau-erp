from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.exceptions import UserError

from odoo.addons.cultiveau_installation.models.installation import TYPES


class SaleOrder(models.Model):
    _inherit = "sale.order"

    cultiveau_installation_id = fields.Many2one("cultiveau.installation", "Installation", tracking=True,
                                                domain="[('partner_id', 'child_of', partner_id)]")
    cultiveau_type_systeme = fields.Selection(TYPES, "Type d'installation", compute="_compute_type_systeme", store=True, readonly=False)
    cultiveau_surface_ha = fields.Float(related="cultiveau_installation_id.surface_ha")
    cultiveau_analyse_validee = fields.Boolean("Analyse des besoins validée", compute="_compute_cultiveau")
    cultiveau_dimensionnement = fields.Char("Dimensionnement", compute="_compute_cultiveau")

    @api.depends("cultiveau_installation_id")
    def _compute_type_systeme(self):
        for o in self:
            i = o.cultiveau_installation_id
            if i and not o.cultiveau_type_systeme:
                o.cultiveau_type_systeme = i.type_systeme
            elif not o.cultiveau_type_systeme:
                o.cultiveau_type_systeme = False

    @api.depends("cultiveau_installation_id", "cultiveau_installation_id.analyse_validee_le", "cultiveau_installation_id.besoin_pointe_mm_j",
                 "cultiveau_installation_id.debit_equipement_m3_h", "cultiveau_installation_id.hmt_m", "cultiveau_installation_id.pompe")
    def _compute_cultiveau(self):
        for o in self:
            i = o.cultiveau_installation_id
            o.cultiveau_analyse_validee = bool(i and i.analyse_validee_le)
            o.cultiveau_dimensionnement = (f"Besoin de pointe {i.besoin_pointe_mm_j:g} mm/j · débit d'équipement {i.debit_equipement_m3_h:g} m³/h · "
                                           f"HMT {i.hmt_m:g} m · {i.pompe or 'pompe à définir'}") if i and i.besoin_pointe_mm_j else ""

    def action_confirm(self):
        for o in self:
            if o.cultiveau_installation_id and not o.cultiveau_analyse_validee:
                o.message_post(body="⚠ Commande confirmée sans analyse des besoins (A1.1) validée avec l'exploitant : "
                                    "le référentiel la demande avant tout dimensionnement (§ 3.2). À régulariser sur l'installation.")
        return super().action_confirm()

    # ---------------------------------------------------------------- les lots, les sous-lots et leurs sous-totaux
    cultiveau_recap_lots = fields.Html("Lots et sous-totaux", compute="_compute_recap_lots", sanitize=False)
    cultiveau_nb_lots = fields.Integer("Lots", compute="_compute_recap_lots")

    def cultiveau_lots(self):
        """La structure du devis : [{nom, montant, materiel, mo, sous: [{nom, montant}]}], dans l'ordre des lignes. Les lignes avant le
        premier lot vont dans « Hors lot »."""
        self.ensure_one()
        lots, courant, sous = [], None, None
        for l in self.order_line.sorted(lambda l: (l.sequence, l.id)):
            if l.display_type == "line_section":
                if l.cultiveau_sous_lot and courant is not None:
                    sous = {"nom": l.name, "montant": 0.0}
                    courant["sous"].append(sous)
                else:
                    courant = {"nom": l.name, "montant": 0.0, "materiel": 0.0, "mo": 0.0, "sous": []}
                    sous = None
                    lots.append(courant)
                continue
            if l.display_type or not l.product_id:
                continue
            if courant is None:
                courant = {"nom": "Hors lot", "montant": 0.0, "materiel": 0.0, "mo": 0.0, "sous": []}
                lots.append(courant)
            courant["montant"] += l.price_subtotal
            if l.product_id.type == "service":
                courant["mo"] += l.price_subtotal
            else:
                courant["materiel"] += l.price_subtotal
            if sous is not None:
                sous["montant"] += l.price_subtotal
        return lots

    @api.depends("order_line.price_subtotal", "order_line.name", "order_line.display_type", "order_line.cultiveau_sous_lot", "order_line.sequence", "order_line.product_id")
    def _compute_recap_lots(self):
        for o in self:
            lots = o.cultiveau_lots()
            o.cultiveau_nb_lots = len([x for x in lots if x["nom"] != "Hors lot"])
            total = sum(x["montant"] for x in lots) or 0.0
            if not lots:
                o.cultiveau_recap_lots = Markup("<p class='text-muted'>Pas encore de lignes. Ajoutez des lots (sections), des sous-lots, ou insérez une nomenclature.</p>")
                continue

            def eur(v):
                return f"{v:,.0f}".replace(",", " ") + " €"

            lignes = []
            for x in lots:
                part = (x["montant"] / total * 100) if total else 0
                lignes.append(f"<tr class='fw-bold'><td>{escape(x['nom'])}</td><td class='text-end'>{eur(x['materiel'])}</td><td class='text-end'>{eur(x['mo'])}</td>"
                              f"<td class='text-end'>{eur(x['montant'])}</td><td class='text-end text-muted'>{part:.0f} %</td></tr>")
                for s in x["sous"]:
                    lignes.append(f"<tr><td class='ps-4 fst-italic'>{escape(s['nom'])}</td><td></td><td></td><td class='text-end'>{eur(s['montant'])}</td><td></td></tr>")
            mat, mo = sum(x["materiel"] for x in lots), sum(x["mo"] for x in lots)
            lignes.append(f"<tr class='table-active fw-bold'><td>Total HT</td><td class='text-end'>{eur(mat)}</td><td class='text-end'>{eur(mo)}</td><td class='text-end'>{eur(total)}</td><td></td></tr>")
            o.cultiveau_recap_lots = Markup("<table class='table table-sm'><thead><tr><th>Lot</th><th class='text-end'>Matériel</th><th class='text-end'>Main-d'œuvre, prestations</th>"
                                            "<th class='text-end'>Sous-total HT</th><th class='text-end'>Part</th></tr></thead><tbody>" + "".join(lignes) + "</tbody></table>"
                                            "<p class='small text-muted mb-0'>Les sous-totaux par lot et par sous-lot s'impriment sur le devis. Un sous-lot se crée avec « Ajouter un sous-lot » "
                                            "sous les lignes, ou en insérant une nomenclature.</p>")

    def action_inserer_nomenclature(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "res_model": "cultiveau.nomenclature.inserer", "view_mode": "form", "target": "new", "name": "Insérer une nomenclature",
                "context": {"default_order_id": self.id, "active_model": "sale.order", "active_id": self.id}}

    def action_enregistrer_nomenclature(self):
        self.ensure_one()
        if not self.order_line.filtered(lambda l: l.display_type == "line_section"):
            raise UserError("Ce devis n'a pas de lot (section) : une nomenclature s'enregistre depuis un lot ou un sous-lot.")
        return {"type": "ir.actions.act_window", "res_model": "cultiveau.nomenclature.enregistrer", "view_mode": "form", "target": "new", "name": "Enregistrer en nomenclature",
                "context": {"default_order_id": self.id, "active_model": "sale.order", "active_id": self.id}}

    def action_creer_installation(self):
        """Depuis un devis sans installation : créer le site chez le client, pour y tenir le dossier."""
        self.ensure_one()
        inst = self.env["cultiveau.installation"].create({
            "name": self.cultiveau_type_systeme and dict(TYPES)[self.cultiveau_type_systeme] or f"Projet {self.name}",
            "partner_id": self.partner_id.commercial_partner_id.id if self.partner_id.is_company else self.partner_id.id,
            "type_systeme": self.cultiveau_type_systeme or "mixte", "etat": "projet", "company_id": self.company_id.id, "user_id": self.user_id.id})
        self.cultiveau_installation_id = inst
        return {"type": "ir.actions.act_window", "res_model": "cultiveau.installation", "res_id": inst.id, "view_mode": "form"}


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    cultiveau_sous_lot = fields.Boolean("Sous-lot", help="Une section de second niveau, dans le lot qui la précède : son sous-total s'imprime, puis le total du lot.")
    cultiveau_nomenclature_id = fields.Many2one("cultiveau.nomenclature", "Nomenclature", index=True, ondelete="set null", copy=True,
                                                help="La nomenclature dont cette ligne est issue.")
