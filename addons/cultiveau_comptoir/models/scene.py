from odoo import models


class Scene(models.AbstractModel):
    _inherit = "cultiveau.scene"

    def _compteurs(self, company, taches):
        res = super()._compteurs(company, taches)
        res["comptoir"] = True  # la vue d'ensemble propose « Une vente au comptoir »
        return res
