"""Augmenter ou baisser les prix en un clic : une variation en pourcentage sur toute une liste, une famille ou un fournisseur,
soit sur le prix d'achat (le prix de vente suit la marge), soit sur le prix de vente catalogue. Le pendant manuel de l'import
d'un tarif fournisseur, pour le « je rajoute 20 % sur tout d'un coup »."""

from odoo import api, fields, models
from odoo.exceptions import UserError


class HaussePrix(models.TransientModel):
    _name = "cultiveau.hausse.prix"
    _description = "Augmenter ou baisser les prix en un clic"

    cible = fields.Selection([("achat", "Le prix d'achat"), ("vente", "Le prix de vente")], "Sur quel prix", required=True, default="achat")
    perimetre = fields.Selection([("tout", "Tous mes articles"), ("famille", "Une famille"), ("fournisseur", "Un fournisseur")], "Sur quels articles", required=True, default="tout")
    categ_id = fields.Many2one("product.category", "Famille")
    fournisseur_id = fields.Many2one("res.partner", "Fournisseur", domain=[("is_company", "=", True)])
    pct = fields.Float("Variation (%)", required=True, help="+20 pour augmenter de 20 %, -5 pour baisser de 5 %.")
    repercuter = fields.Boolean("Répercuter sur mes prix de vente", default=True,
                                help="Après la hausse du prix d'achat, la liste de prix de vente est recalculée avec votre marge.")
    nb = fields.Integer("Articles concernés", compute="_compute_nb")

    @api.depends("perimetre", "categ_id", "fournisseur_id", "cible")
    def _compute_nb(self):
        for w in self:
            try:
                w.nb = len(w._articles())
            except UserError:
                w.nb = 0

    def _articles(self):
        self.ensure_one()
        company = self.env.company
        if self.cible == "vente":
            # le prix de vente catalogue est partagé entre les sociétés : on ne touche qu'aux propres articles de l'adhérent
            domaine = [("company_id", "=", company.id), ("sale_ok", "=", True)]
        else:
            domaine = ["|", ("company_id", "=", False), ("company_id", "=", company.id), ("purchase_ok", "=", True)]
        if self.perimetre == "famille":
            if not self.categ_id:
                raise UserError("Choisissez la famille.")
            familles = self.env["product.category"].search([("id", "child_of", self.categ_id.id)])
            domaine += [("categ_id", "in", familles.ids)]
        elif self.perimetre == "fournisseur":
            if not self.fournisseur_id:
                raise UserError("Choisissez le fournisseur.")
            domaine += [("seller_ids.partner_id", "=", self.fournisseur_id.id)]
        return self.env["product.template"].with_company(company).search(domaine)

    def action_appliquer(self):
        self.ensure_one()
        if not self.pct:
            raise UserError("Indiquez de combien augmenter ou baisser, en pourcentage.")
        facteur = 1 + self.pct / 100.0
        if facteur <= 0:
            raise UserError("Une baisse de 100 % ou plus n'est pas possible.")
        articles = self._articles()
        if not articles:
            raise UserError("Aucun article ne correspond à ce choix.")
        company = self.env.company
        champ = "standard_price" if self.cible == "achat" else "list_price"
        n = 0
        for p in articles.with_company(company):
            ancien = p[champ]
            if not ancien:
                continue
            nouveau = round(ancien * facteur, 2)
            if nouveau != ancien:
                p[champ] = nouveau
                n += 1
        quoi = "prix d'achat" if self.cible == "achat" else "prix de vente"
        message = f"{n} article(s) à jour : {quoi} {self.pct:+.1f} %."
        if self.cible == "achat" and self.repercuter and company.cultiveau_tarif_vente_id:
            company.cultiveau_appliquer_marges()
            message += " Vos prix de vente ont suivi avec votre marge."
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"title": "Prix mis à jour", "message": message, "type": "success", "sticky": False,
                           "next": {"type": "ir.actions.act_window_close"}}}
