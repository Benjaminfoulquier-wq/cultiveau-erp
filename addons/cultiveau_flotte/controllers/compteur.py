"""Le relevé du compteur depuis la page du téléphone (/moi)."""
from odoo import http
from odoo.exceptions import UserError
from odoo.http import request

from odoo.addons.cultiveau_rh.controllers.moi import _faire


class Compteur(http.Controller):

    @http.route("/moi/compteur", type="http", auth="user", methods=["POST"])
    def compteur(self, km="", **kw):
        def faire():
            v = request.env["fleet.vehicle"].du_conducteur(request.env.user)
            if not v:
                raise UserError("Aucun camion ne vous est attribué.")
            try:
                valeur = float((km or "").replace(" ", "").replace("\u202f", "").replace(",", "."))
            except ValueError:
                raise UserError("Indiquez le kilométrage en chiffres.") from None
            return v.relever_compteur(valeur, request.env.user)["message"]
        return _faire(faire, "camion")
