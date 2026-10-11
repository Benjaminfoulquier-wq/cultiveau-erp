"""La marge de chaque adhérent, par famille s'il veut : sa liste de prix de vente se construit seule à partir du prix d'achat."""

from odoo import api, fields, models


class Marge(models.Model):
    _name = "cultiveau.marge"
    _description = "Marge par famille d'articles"
    _order = "company_id, categ_id"

    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, ondelete="cascade")
    categ_id = fields.Many2one("product.category", "Famille", required=True)
    marge_pct = fields.Float("Marge sur le prix de vente (%)", digits=(5, 1), required=True, help="30 % : un article acheté 10 € se vend 14,29 € HT.")

    _sql_constraints = [("famille_unique", "unique(company_id, categ_id)", "Une seule marge par famille et par société.")]


def remise_pour_marge(marge_pct):
    """La « remise » négative qu'une liste de prix applique au prix d'achat pour obtenir la marge voulue sur le prix de vente."""
    m = max(0.0, min(marge_pct or 0.0, 95.0)) / 100
    return -100 * m / (1 - m) if m else 0.0


class Company(models.Model):
    _inherit = "res.company"

    cultiveau_marge_pct = fields.Float("Marge cible (%)", digits=(5, 1), default=30.0, help="Sur le prix de vente HT, pour tout ce qui n'a pas de marge par famille.")
    cultiveau_marge_ids = fields.One2many("cultiveau.marge", "company_id", "Marges par famille")
    cultiveau_tarif_vente_id = fields.Many2one("product.pricelist", "Liste de prix de vente", readonly=True)

    def cultiveau_appliquer_marges(self):
        """(Re)construit la liste de prix de la société : prix d'achat × coefficient, par famille puis pour le reste ; elle devient celle par défaut."""
        Pricelist = self.env["product.pricelist"].sudo()
        for societe in self:
            liste = societe.cultiveau_tarif_vente_id
            if not liste:
                liste = Pricelist.search([("company_id", "=", societe.id), ("name", "=like", "Tarif de vente —%")], limit=1) or Pricelist.create(
                    {"name": f"Tarif de vente — {societe.name}", "company_id": societe.id, "currency_id": societe.currency_id.id})
                societe.cultiveau_tarif_vente_id = liste
            liste.sequence = 1  # la première liste de la société : celle que prennent ses clients par défaut
            liste.item_ids.unlink()
            items = [{"pricelist_id": liste.id, "applied_on": "2_product_category", "categ_id": m.categ_id.id, "compute_price": "formula", "base": "standard_price",
                      "price_discount": remise_pour_marge(m.marge_pct), "price_round": 0.01} for m in societe.cultiveau_marge_ids]
            items.append({"pricelist_id": liste.id, "applied_on": "3_global", "compute_price": "formula", "base": "standard_price",
                          "price_discount": remise_pour_marge(societe.cultiveau_marge_pct), "price_round": 0.01})
            self.env["product.pricelist.item"].sudo().create(items)
            self.env["ir.config_parameter"].sudo().set_param(f"res.partner.property_product_pricelist_{societe.id}", str(liste.id))
        return True

    def cultiveau_mettre_en_place_compta(self):
        res = super().cultiveau_mettre_en_place_compta()
        for societe in self.filtered(lambda s: s.chart_template == "fr" and not s.cultiveau_tarif_vente_id):
            societe.cultiveau_appliquer_marges()
        return res


class PricelistItem(models.Model):
    _inherit = "product.pricelist.item"

    def _compute_price(self, product, quantity, uom, date, currency=None):
        """Un article sans prix d'achat (le propre article de l'adhérent, saisi avec son prix de vente) garde son prix catalogue."""
        prix = super()._compute_price(product, quantity, uom, date, currency=currency)
        if self.compute_price == "formula" and self.base == "standard_price" and prix <= 0:
            return product.lst_price if hasattr(product, "lst_price") else product.list_price
        return prix


class Settings(models.TransientModel):
    _inherit = "res.config.settings"

    cultiveau_marge_pct = fields.Float(related="company_id.cultiveau_marge_pct", readonly=False)
    cultiveau_tarif_vente_id = fields.Many2one(related="company_id.cultiveau_tarif_vente_id")

    def action_cultiveau_appliquer_marges(self):
        self.ensure_one()
        self.company_id.cultiveau_marge_pct = self.cultiveau_marge_pct
        self.company_id.cultiveau_appliquer_marges()
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"title": "Marges appliquées", "message": "Votre liste de prix de vente est à jour : prix d'achat × coefficient, par famille puis pour le reste.", "sticky": False,
                           "next": {"type": "ir.actions.client", "tag": "reload"}}}

    def action_cultiveau_marges_familles(self):
        return {"type": "ir.actions.act_window", "name": "Marges par famille", "res_model": "cultiveau.marge", "view_mode": "list",
                "domain": [("company_id", "=", self.company_id.id)], "context": {"default_company_id": self.company_id.id}, "target": "current"}
