"""La grille de remises : qui achète quoi, à quel prix. La ligne la plus précise l'emporte."""

from odoo import api, fields, models
from odoo.exceptions import UserError


class Remise(models.Model):
    _name = "cultiveau.remise"
    _description = "Ligne de la grille de remises"
    _order = "company_id, cultiveau_type, categ_id, quantite_min"

    company_id = fields.Many2one("res.company", "Société", default=lambda self: self.env.company, index=True, help="Vide : la grille proposée par le réseau.")
    cultiveau_type = fields.Selection(lambda self: [(t, l) for t, l in self.env["res.partner"]._fields["cultiveau_type"].selection if t != "adherent"], "Typologie de client",
                                      help="Vide : tous les clients.")
    partner_id = fields.Many2one("res.partner", "Client précis", help="Une remise négociée avec ce client seul.")
    categ_id = fields.Many2one("product.category", "Famille / sous-famille", help="Vide : toutes les familles. Une sous-famille l'emporte sur sa famille.")
    product_id = fields.Many2one("product.template", "Article précis")
    quantite_min = fields.Float("À partir de (quantité)", digits="Product Unit of Measure", default=0.0)
    remise_pct = fields.Float("Remise (%)", digits=(5, 2), required=True)
    note = fields.Char("Remarque")

    @api.constrains("remise_pct")
    def _check_remise(self):
        for r in self:
            if not -50 <= r.remise_pct <= 100:
                raise UserError("Une remise va de 0 à 100 % (ou jusqu'à −50 % pour une majoration).")

    def _precision(self, categ):
        """Plus la ligne est précise, plus elle pèse : client > article > sous-famille > typologie > famille > tout."""
        self.ensure_one()
        poids = 0
        if self.partner_id:
            poids += 1000
        if self.product_id:
            poids += 500
        if self.categ_id:
            poids += 100 + (self.categ_id.parent_path or "").count("/") * 10  # une sous-famille est plus profonde qu'une famille
        if self.cultiveau_type:
            poids += 50
        if self.quantite_min:
            poids += 1
        return poids

    @api.model
    def pour(self, societe, partner, produit, quantite=1.0):
        """La remise (%) qui s'applique à cet article pour ce client, dans cette société ; 0 sans ligne."""
        client = (partner.commercial_partner_id or partner) if partner else partner
        genre = client.cultiveau_type if client else False
        categ = produit.categ_id if produit else self.env["product.category"]
        ancetres = self.env["product.category"]
        c = categ
        while c:
            ancetres |= c
            c = c.parent_id
        candidates = self.search([("company_id", "=", societe.id), ("quantite_min", "<=", quantite or 0.0),
                                  "|", ("partner_id", "=", False), ("partner_id", "in", [client.id, partner.id] if client else []),
                                  "|", ("cultiveau_type", "=", False), ("cultiveau_type", "=", genre or "__aucun__"),
                                  "|", ("categ_id", "=", False), ("categ_id", "in", ancetres.ids),
                                  "|", ("product_id", "=", False), ("product_id", "=", produit.product_tmpl_id.id if produit else 0)])
        if not candidates:
            return 0.0
        meilleure = max(candidates, key=lambda r: (r._precision(categ), r.quantite_min))
        return meilleure.remise_pct

    @api.model
    def copier_grille_reseau(self, societe):
        """La grille proposée par le réseau devient celle de la société (sans écraser ses lignes existantes)."""
        reseau = self.search([("company_id", "=", False)])
        existantes = self.search([("company_id", "=", societe.id)])
        cles = {(r.cultiveau_type, r.categ_id.id, r.product_id.id, r.partner_id.id, r.quantite_min) for r in existantes}
        n = 0
        for r in reseau:
            cle = (r.cultiveau_type, r.categ_id.id, r.product_id.id, r.partner_id.id, r.quantite_min)
            if cle in cles:
                continue
            r.copy({"company_id": societe.id, "note": "Grille réseau"})
            n += 1
        return n


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    cultiveau_remise_grille = fields.Float("Remise de la grille (%)", digits=(5, 2), compute="_compute_remise_grille")

    @api.depends("product_id", "product_uom_qty", "order_id.partner_id", "order_id.company_id")
    def _compute_remise_grille(self):
        Remise = self.env["cultiveau.remise"]
        for l in self:
            l.cultiveau_remise_grille = Remise.pour(l.company_id or l.order_id.company_id, l.order_id.partner_id, l.product_id, l.product_uom_qty) if l.product_id and not l.display_type else 0.0

    @api.depends("product_id", "product_uom", "product_uom_qty", "order_id.partner_id")
    def _compute_discount(self):
        super()._compute_discount()
        for l in self:
            if l.product_id and not l.display_type and not l.combo_item_id:
                grille = self.env["cultiveau.remise"].pour(l.company_id or l.order_id.company_id, l.order_id.partner_id, l.product_id, l.product_uom_qty)
                if grille:
                    l.discount = grille


class Company(models.Model):
    _inherit = "res.company"

    cultiveau_nb_remises = fields.Integer("Lignes de la grille", compute="_compute_nb_remises")

    def _compute_nb_remises(self):
        for c in self:
            c.cultiveau_nb_remises = self.env["cultiveau.remise"].search_count([("company_id", "=", c.id)])


class Settings(models.TransientModel):
    _inherit = "res.config.settings"

    cultiveau_nb_remises = fields.Integer(related="company_id.cultiveau_nb_remises")

    def action_cultiveau_grille(self):
        return {"type": "ir.actions.act_window", "name": "Ma grille de remises", "res_model": "cultiveau.remise", "view_mode": "list",
                "domain": [("company_id", "=", self.company_id.id)], "context": {"default_company_id": self.company_id.id, "search_default_par_type": 1}, "target": "current"}

    def action_cultiveau_copier_grille(self):
        n = self.env["cultiveau.remise"].copier_grille_reseau(self.company_id)
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"title": "Grille réseau", "message": f"{n} ligne(s) copiée(s) dans votre grille : ajustez-les à votre guise.", "sticky": False,
                           "next": {"type": "ir.actions.client", "tag": "reload"}}}
