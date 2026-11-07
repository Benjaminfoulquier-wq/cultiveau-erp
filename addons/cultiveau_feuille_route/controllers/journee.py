"""La page du téléphone : /journee/<jeton>, sans mot de passe, la journée d'un salarié."""
from datetime import date

from odoo import http
from odoo.http import request


class Journee(http.Controller):
    @http.route("/journee/<string:jeton>", type="http", auth="public", methods=["GET"], csrf=False, sitemap=False)
    def journee(self, jeton, date=None, **_kw):
        if not jeton or len(jeton) < 16:
            return request.not_found()
        employe = request.env["hr.employee"].sudo().search([("cultiveau_jeton", "=", jeton), ("active", "=", True)], limit=1)
        if not employe:
            return request.not_found()
        F = request.env["cultiveau.feuille.route"].sudo()
        jour = None
        if date:
            try:
                jour = _date(date)
            except ValueError:
                jour = None
        if not jour:
            jour = F.prochain_jour(employe.company_id) if _apres_midi(F, employe.company_id) else _aujourdhui(F, employe.company_id)
        html = F.page(employe, jour)
        return request.make_response(html, headers=[("Content-Type", "text/html; charset=utf-8"), ("Cache-Control", "no-store"), ("X-Robots-Tag", "noindex")])


def _date(texte):
    a, m, j = (int(x) for x in texte.split("-"))
    return date(a, m, j)


def _aujourdhui(F, company):
    from datetime import datetime
    return datetime.now(F._tz(company)).date()


def _apres_midi(F, company):
    from datetime import datetime
    return datetime.now(F._tz(company)).hour >= 17
