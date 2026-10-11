"""Ce que le client voit sur le devis et la facture : l'adhérent choisit le niveau de détail, l'ERP garde tout."""

from odoo import api, fields, models

NIVEAUX = [("complet", "Détail complet (chaque article)"), ("lots", "Par lot (un montant par lot)"), ("forfait", "Forfait (une seule ligne)"),
           ("materiel_mo", "Matériel et main-d'œuvre séparés")]
LIBELLE_FORFAIT = "Fourniture et pose de l'installation d'irrigation"
LIBELLE_HORS_LOT = "Fournitures et prestations"
LIBELLE_MASQUE = "Fournitures diverses et petites pièces"


def _est_service(produit):
    return bool(produit) and produit.type == "service"


class Company(models.Model):
    _inherit = "res.company"

    cultiveau_detail_devis = fields.Selection(NIVEAUX, "Présentation des devis", default="complet", required=True)
    cultiveau_detail_facture = fields.Selection(NIVEAUX, "Présentation des factures", default="complet", required=True)


class Settings(models.TransientModel):
    _inherit = "res.config.settings"

    cultiveau_detail_devis = fields.Selection(related="company_id.cultiveau_detail_devis", readonly=False)
    cultiveau_detail_facture = fields.Selection(related="company_id.cultiveau_detail_facture", readonly=False)


def regrouper(lignes, niveau, champs):
    """Les lignes à montrer, d'après le niveau de détail. `champs` dit comment lire une ligne (nom, qté, unité, pu, remise, taxes, sous-total, section, note, masquée, produit).
    Renvoie une liste de dicts prêts pour des enregistrements virtuels."""
    def groupe(nom, membres, qte=1.0, unite=None):
        total = sum(champs["sous_total"](l) for l in membres)
        taxes = next((champs["taxes"](l) for l in membres if champs["taxes"](l)), None)
        return {"name": nom, "qte": qte, "unite": unite or (champs["unite"](membres[0]) if membres and qte != 1.0 else None), "pu": total / qte if qte else total,
                "remise": 0.0, "taxes": taxes, "sous_total": total, "section": False, "note": False}

    def simple(l):
        return {"name": champs["nom"](l), "qte": champs["qte"](l), "unite": champs["unite"](l), "pu": champs["pu"](l), "remise": champs["remise"](l), "taxes": champs["taxes"](l),
                "sous_total": champs["sous_total"](l), "section": champs["section"](l), "note": champs["note"](l)}

    reelles = [l for l in lignes if not champs["section"](l) and not champs["note"](l)]
    if niveau == "forfait":
        return [groupe(LIBELLE_FORFAIT, reelles)] if reelles else []
    if niveau == "materiel_mo":
        materiel = [l for l in reelles if not _est_service(champs["produit"](l))]
        mo = [l for l in reelles if _est_service(champs["produit"](l))]
        resultat = []
        if materiel:
            resultat.append(groupe("Matériel et fournitures", materiel))
        if mo:
            resultat.append(groupe("Main-d'œuvre, pose et prestations", mo))
        return resultat
    if niveau == "lots":
        resultat, courant, membres, notes = [], None, [], []

        def fermer():
            if membres:
                resultat.append(groupe(courant or LIBELLE_HORS_LOT, membres))
            resultat.extend(notes)  # les notes d'un lot viennent sous son montant
        for l in lignes:
            if champs["section"](l):
                fermer()
                courant, membres, notes = champs["nom"](l), [], []
            elif champs["note"](l):
                notes.append(simple(l))
            else:
                membres.append(l)
        fermer()
        return resultat
    # complet : les lignes masquées se fondent en une seule, à la fin
    resultat = [simple(l) for l in lignes if not champs["masquee"](l)]
    masquees = [l for l in reelles if champs["masquee"](l)]
    if masquees:
        resultat.append(groupe(LIBELLE_MASQUE, masquees))
    return resultat


class SaleOrder(models.Model):
    _inherit = "sale.order"

    cultiveau_detail = fields.Selection(NIVEAUX, "Présentation du devis", compute="_compute_detail", store=True, readonly=False, precompute=True)

    @api.depends("company_id")
    def _compute_detail(self):
        for o in self:
            o.cultiveau_detail = o.cultiveau_detail or o.company_id.cultiveau_detail_devis or "complet"

    def _create_invoices(self, grouped=False, final=False, date=None):
        factures = super()._create_invoices(grouped=grouped, final=final, date=date)
        factures._cultiveau_copier_presentation()
        return factures

    def _get_order_lines_to_report(self):
        lignes = super()._get_order_lines_to_report()
        niveau = self.cultiveau_detail or "complet"
        if niveau == "complet" and not any(lignes.mapped("cultiveau_masque")):
            return lignes
        champs = {"nom": lambda l: l.name, "qte": lambda l: l.product_uom_qty, "unite": lambda l: l.product_uom, "pu": lambda l: l.price_unit, "remise": lambda l: l.discount,
                  "taxes": lambda l: l.tax_id, "sous_total": lambda l: l.price_subtotal, "section": lambda l: l.display_type == "line_section",
                  "note": lambda l: l.display_type == "line_note", "masquee": lambda l: l.cultiveau_masque, "produit": lambda l: l.product_id}
        Ligne = self.env["sale.order.line"]
        virtuelles = Ligne
        for i, d in enumerate(regrouper(lignes, niveau, champs)):
            virtuelles |= Ligne.new({"order_id": self.id, "name": d["name"], "product_uom_qty": d["qte"], "product_uom": d["unite"].id if d["unite"] else False,
                                     "price_unit": d["pu"], "discount": d["remise"], "tax_id": [(6, 0, d["taxes"].ids)] if d["taxes"] else False,
                                     "price_subtotal": d["sous_total"], "price_total": d["sous_total"], "sequence": i,
                                     "display_type": "line_section" if d["section"] else ("line_note" if d["note"] else False)})
        return virtuelles


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    cultiveau_masque = fields.Boolean("Masquer sur le document", help="La ligne n'apparaît pas au client : son montant se fond dans « Fournitures diverses » (ou dans son lot).")


class AccountMove(models.Model):
    _inherit = "account.move"

    cultiveau_detail = fields.Selection(NIVEAUX, "Présentation de la facture", compute="_compute_detail", store=True, readonly=False, precompute=True)

    @api.depends("company_id", "move_type")
    def _compute_detail(self):
        for m in self:
            m.cultiveau_detail = m.cultiveau_detail or m.company_id.cultiveau_detail_facture or "complet"

    def cultiveau_lignes_presentees(self):
        """Les lignes de facture à montrer, selon le niveau choisi ; les vraies lignes si le détail est complet et rien n'est masqué."""
        self.ensure_one()
        lignes = self.invoice_line_ids.sorted(key=lambda l: (-l.sequence, l.date, l.move_name, -l.id), reverse=True)
        niveau = self.cultiveau_detail or "complet"
        if self.move_type not in ("out_invoice", "out_refund") or (niveau == "complet" and not any(lignes.mapped("cultiveau_masque"))):
            return lignes
        champs = {"nom": lambda l: l.name, "qte": lambda l: l.quantity, "unite": lambda l: l.product_uom_id, "pu": lambda l: l.price_unit, "remise": lambda l: l.discount,
                  "taxes": lambda l: l.tax_ids, "sous_total": lambda l: l.price_subtotal, "section": lambda l: l.display_type == "line_section",
                  "note": lambda l: l.display_type == "line_note", "masquee": lambda l: l.cultiveau_masque, "produit": lambda l: l.product_id}
        Ligne = self.env["account.move.line"]
        virtuelles = Ligne
        for i, d in enumerate(regrouper(lignes, niveau, champs)):
            virtuelles |= Ligne.new({"move_id": self.id, "name": d["name"], "quantity": d["qte"], "product_uom_id": d["unite"].id if d["unite"] else False,
                                     "price_unit": d["pu"], "discount": d["remise"], "tax_ids": [(6, 0, d["taxes"].ids)] if d["taxes"] else False,
                                     "price_subtotal": d["sous_total"], "price_total": d["sous_total"], "sequence": i,
                                     "display_type": "line_section" if d["section"] else ("line_note" if d["note"] else "product")})
        return virtuelles

    def _cultiveau_copier_presentation(self):
        for m in self:
            commandes = m.invoice_line_ids.sale_line_ids.order_id
            if m.move_type in ("out_invoice", "out_refund") and m.company_id.cultiveau_detail_facture == "complet" and commandes and len(commandes) == 1 and commandes.cultiveau_detail != "complet":
                m.cultiveau_detail = commandes.cultiveau_detail  # sans réglage particulier pour les factures, la facture suit le devis


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    cultiveau_masque = fields.Boolean("Masquer sur le document")

    @api.model_create_multi
    def create(self, vals_list):
        lignes = super().create(vals_list)
        for l in lignes.filtered(lambda l: l.sale_line_ids and l.sale_line_ids[0].cultiveau_masque):
            l.cultiveau_masque = True
        return lignes
