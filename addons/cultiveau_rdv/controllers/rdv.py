"""Les pages publiques de prise de rendez-vous : /rdv/<jeton> (une société : ses motifs ; un motif : ses créneaux)."""
from werkzeug.exceptions import NotFound
from werkzeug.urls import url_encode

from odoo import http
from odoo.exceptions import UserError, ValidationError
from odoo.http import request


class Rdv(http.Controller):

    def _trouver(self, jeton):
        env = request.env
        t = env["cultiveau.rdv.type"].sudo().search([("jeton", "=", jeton), ("active", "=", True)], limit=1)
        if t:
            return t.company_id, t
        c = env["res.company"].sudo().search([("cultiveau_rdv_jeton", "=", jeton)], limit=1)
        if c:
            return c, None
        raise NotFound()

    @http.route("/rdv/<string:jeton>", type="http", auth="public", methods=["GET"], sitemap=False)
    def page(self, jeton, erreur=None, **kw):
        societe, motif = self._trouver(jeton)
        valeurs = {"societe": societe, "motif": motif, "erreur": erreur, "jeton": jeton}
        if motif:
            valeurs["jours"] = motif.jours_creneaux()
            valeurs["choisi"] = kw.get("creneau")
            if valeurs["choisi"]:
                valeurs["creneau"] = next((c for j in valeurs["jours"] for c in j["creneaux"] if c["debut_utc"] == valeurs["choisi"]), None)
        else:
            valeurs["motifs"] = request.env["cultiveau.rdv.type"].sudo().search([("company_id", "=", societe.id), ("user_ids", "!=", False)])
        return request.render("cultiveau_rdv.page", valeurs)

    @http.route("/rdv/<string:jeton>/reserver", type="http", auth="public", methods=["POST"], sitemap=False)
    def reserver(self, jeton, debut_utc="", nom="", telephone="", email="", adresse="", message="", site_web="", **kw):
        societe, motif = self._trouver(jeton)
        if not motif:
            raise NotFound()
        if site_web:  # le champ piège que seuls les robots remplissent
            return request.redirect(f"/rdv/{jeton}", local=True)
        try:
            with request.env.cr.savepoint():
                evenement = motif.reserver(debut_utc, nom, telephone, email, adresse, message)
        except (UserError, ValidationError) as e:
            return request.redirect(f"/rdv/{jeton}?" + url_encode({"erreur": str(e.args[0] if e.args else e)}), local=True)
        return request.render("cultiveau_rdv.confirme", {"societe": societe, "motif": motif, "evenement": evenement.sudo(),
                                                         "quand": evenement.sudo()._cultiveau_quand(), "nom": nom})
