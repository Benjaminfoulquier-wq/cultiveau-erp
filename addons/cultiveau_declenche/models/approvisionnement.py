"""La liste de courses du devis : article par article, ce qu'il y a, ce qui arrive, ce qui manque, chez qui et à quel prix ; les
demandes de prix en un clic, groupées par fournisseur."""
from odoo import Command, api, fields, models
from odoo.exceptions import UserError


class Approvisionnement(models.TransientModel):
    _name = "cultiveau.approvisionnement"
    _description = "Approvisionnement d'un devis"

    order_id = fields.Many2one("sale.order", "Devis", required=True)
    ligne_ids = fields.One2many("cultiveau.approvisionnement.ligne", "appro_id", "Articles")
    tout = fields.Boolean("Commander tout le devis (pas seulement les manquants)", help="Pour un chantier livré directement du fournisseur, sans passer par le stock.")
    nb_manquants = fields.Integer("Articles manquants", compute="_compute_totaux")
    total_a_commander = fields.Monetary("Total à commander (HT, prix fournisseur)", compute="_compute_totaux", currency_field="currency_id")
    currency_id = fields.Many2one(related="order_id.currency_id")
    sans_fournisseur = fields.Char("Sans fournisseur connu", compute="_compute_totaux")

    @api.model
    def default_get(self, champs):
        valeurs = super().default_get(champs)
        order_id = valeurs.get("order_id") or self.env.context.get("default_order_id")
        if order_id and "ligne_ids" in champs:
            order = self.env["sale.order"].browse(order_id)
            lignes = []
            for b in order.cultiveau_besoins():
                p = b["product"]
                seller = p.with_company(order.company_id)._select_seller(quantity=max(b["manque"], 1.0), uom_id=p.uom_id)
                lignes.append(Command.create({
                    "product_id": p.id, "qte_devis": b["qte"], "en_stock": b["couvert_stock"], "en_commande": b["en_commande"], "manque": b["manque"], "a_commander": b["manque"],
                    "fournisseur_id": seller.partner_id.id if seller else False, "prix": seller.price if seller else p.standard_price, "delai": seller.delay if seller else 0,
                    "ref_fournisseur": seller.product_code if seller else ""}))
            valeurs["ligne_ids"] = lignes
        return valeurs

    @api.depends("ligne_ids.a_commander", "ligne_ids.prix", "ligne_ids.manque", "ligne_ids.fournisseur_id")
    def _compute_totaux(self):
        for w in self:
            w.nb_manquants = len(w.ligne_ids.filtered(lambda l: l.manque > 0))
            w.total_a_commander = sum(l.a_commander * l.prix for l in w.ligne_ids if l.a_commander > 0)
            sans = w.ligne_ids.filtered(lambda l: l.a_commander > 0 and not l.fournisseur_id)
            w.sans_fournisseur = ", ".join(sans.mapped("product_id.display_name")[:8]) + (" …" if len(sans) > 8 else "")

    @api.onchange("tout")
    def _onchange_tout(self):
        for l in self.ligne_ids:
            l.a_commander = l.qte_devis if self.tout else l.manque

    def action_commander(self):
        self.ensure_one()
        lignes = self.ligne_ids.filtered(lambda l: l.a_commander > 0 and l.fournisseur_id)
        if not lignes:
            raise UserError("Rien à commander : aucune quantité avec un fournisseur.")
        besoins = []
        Seller = self.env["product.supplierinfo"]
        for l in lignes:
            seller = l.product_id.with_company(self.order_id.company_id)._select_seller(partner_id=l.fournisseur_id, quantity=l.a_commander, uom_id=l.product_id.uom_id)
            if not seller:
                seller = Seller.new({"partner_id": l.fournisseur_id.id, "price": l.prix, "delay": l.delai, "product_tmpl_id": l.product_id.product_tmpl_id.id})
            besoins.append({"product": l.product_id, "qte": l.qte_devis, "manque": l.manque, "a_commander": l.a_commander, "seller": seller})
        crees, _sans = self.order_id._cultiveau_commander_manquants(besoins=besoins)
        self.order_id.message_post(body=f"Approvisionnement : {len(crees)} demande(s) de prix créée(s) ({len(lignes)} ligne(s), {self.total_a_commander:,.0f} € HT au prix fournisseur).".replace(",", " "))
        if len(crees) == 1:
            return {"type": "ir.actions.act_window", "res_model": "purchase.order", "res_id": crees.id, "view_mode": "form"}
        return {"type": "ir.actions.act_window", "name": "Demandes de prix", "res_model": "purchase.order", "view_mode": "list,form", "domain": [("id", "in", crees.ids)]}


class ApprovisionnementLigne(models.TransientModel):
    _name = "cultiveau.approvisionnement.ligne"
    _description = "Article à approvisionner"
    _order = "manque desc, id"

    appro_id = fields.Many2one("cultiveau.approvisionnement", required=True, ondelete="cascade")
    product_id = fields.Many2one("product.product", "Article", required=True)
    qte_devis = fields.Float("Au devis", digits="Product Unit of Measure")
    en_stock = fields.Float("Disponible", digits="Product Unit of Measure", help="En stock, moins ce que d'autres commandes attendent déjà.")
    en_commande = fields.Float("Arrive", digits="Product Unit of Measure", help="Déjà commandé chez un fournisseur, pas encore reçu.")
    manque = fields.Float("Manque", digits="Product Unit of Measure")
    a_commander = fields.Float("À commander", digits="Product Unit of Measure")
    fournisseur_id = fields.Many2one("res.partner", "Fournisseur", domain="[('is_company', '=', True)]")
    ref_fournisseur = fields.Char("Réf. fournisseur")
    prix = fields.Float("Prix d'achat", digits="Product Price")
    delai = fields.Integer("Délai (j)")
    montant = fields.Float("Montant", compute="_compute_montant")

    @api.depends("a_commander", "prix")
    def _compute_montant(self):
        for l in self:
            l.montant = l.a_commander * l.prix

    @api.onchange("fournisseur_id")
    def _onchange_fournisseur(self):
        if self.fournisseur_id and self.product_id:
            seller = self.product_id._select_seller(partner_id=self.fournisseur_id, quantity=max(self.a_commander, 1.0), uom_id=self.product_id.uom_id)
            if seller:
                self.prix, self.delai, self.ref_fournisseur = seller.price, seller.delay, seller.product_code or ""
