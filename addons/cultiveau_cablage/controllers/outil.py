"""L'outil de câblage (cablage.cultiveau.fr) affiché dans le cadre de l'ERP, sans nouvelle connexion.

Le cadre ouvre ``/cultiveau/cablage/ouvrir`` : l'ERP fabrique un laissez-passer signé pour l'utilisateur connecté (son e-mail,
sa société, valable deux minutes, à usage unique) et renvoie vers ``<outil>/sso/erp/?t=…``. Ouvert depuis un dossier d'armoire
(``armoire=<id>``), le laissez-passer emporte la description du dossier : l'outil la pose dans sa zone de saisie.
Secret partagé : paramètre système ``cultiveau.cablage_secret`` = « SSO_ERP » de l'outil. Adresse : ``cultiveau.url_cablage``.
"""
import base64
import hashlib
import hmac
import json
import secrets
import time
from urllib.parse import quote

from markupsafe import escape

from odoo import http
from odoo.http import request

ADRESSE = "https://cablage.cultiveau.fr"


def _b64(octets):
    return base64.urlsafe_b64encode(octets).rstrip(b"=").decode()


def fabriquer_jeton(charge, secret):
    """base64url(JSON).base64url(HMAC-SHA256 du premier morceau) : le format lu par l'outil."""
    corps = _b64(json.dumps(charge, separators=(",", ":")).encode())
    return f"{corps}.{_b64(hmac.new(secret.encode(), corps.encode(), hashlib.sha256).digest())}"


class OutilCablage(http.Controller):

    @http.route("/cultiveau/cablage/ouvrir", type="http", auth="user", methods=["GET"])
    def ouvrir(self, armoire=None, **_kw):
        parametres = request.env["ir.config_parameter"].sudo()
        secret = parametres.get_param("cultiveau.cablage_secret")
        outil = (parametres.get_param("cultiveau.url_cablage") or ADRESSE).rstrip("/")
        if not secret:
            return self._message("L'outil de câblage n'est pas encore relié à l'ERP (secret partagé absent).")
        utilisateur = request.env.user
        charge = {"v": 1, "outil": "cablage", "source": "erp", "email": (utilisateur.email or utilisateur.login or "").strip().lower(),
                  "entreprise": request.env.company.name or "", "exp": int(time.time()) + 120, "n": secrets.token_hex(12)}
        if armoire and str(armoire).isdigit():
            # la lecture passe par les droits de l'utilisateur : un dossier d'une autre société ne part pas
            dossier = request.env["cultiveau.armoire"].search([("id", "=", int(armoire))], limit=1)
            if dossier:
                charge.update(ref=dossier.name or "", texte=(dossier.cahier_des_charges or "").strip()[:3000])
        reponse = request.redirect(f"{outil}/sso/erp/?t={quote(fabriquer_jeton(charge, secret))}", local=False)
        reponse.headers["Cache-Control"] = "no-store"
        reponse.headers["Referrer-Policy"] = "no-referrer"
        return reponse

    def _message(self, texte):
        return request.make_response(
            f"<!doctype html><html lang='fr'><head><meta charset='utf-8'></head><body style='font-family:sans-serif;"
            f"display:flex;align-items:center;justify-content:center;min-height:90vh;color:#183840'><p>{escape(texte)}</p></body></html>",
            headers=[("Content-Type", "text/html; charset=utf-8")])
