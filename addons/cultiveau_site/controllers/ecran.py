"""Les écrans de cultiveau.fr et de la logistique affichés dans le cadre de l'ERP, sans nouvelle connexion.

Le cadre de l'ERP ouvre ``/cultiveau/ecran?vers=…`` : l'ERP fabrique un laissez-passer signé pour l'utilisateur connecté
(son e-mail, valable une minute, à usage unique) et renvoie vers ``<site>/api/erp/entree?t=…``. Le site ouvre la session
adhérent puis affiche l'écran demandé ; avec ``vers=logistique``, il passe la main à la connexion unique de la logistique.
Secret partagé : paramètre système ``cultiveau.erp_lien_secret`` = « ERP_LIEN_SECRET » sur cultiveau.fr.
"""
import base64
import hashlib
import hmac
import json
import re
import secrets
import time
from urllib.parse import quote

from markupsafe import escape

from odoo import http
from odoo.http import request

# Seules ces destinations partent de l'ERP : un chemin de l'espace adhérent, la logistique, ou un écran de l'assistant téléphonique (assistant:/moi/reglages/)
DESTINATION = re.compile(r"^(logistique|assistant:/[A-Za-z0-9/_\-?=&.%]*|/adherent/[A-Za-z0-9/_\-?=&.%]*)$")


def _b64(octets):
    return base64.urlsafe_b64encode(octets).rstrip(b"=").decode()


def fabriquer_jeton(charge, secret):
    """Même format que le site : base64url(JSON).base64url(HMAC-SHA256 du premier morceau)."""
    corps = _b64(json.dumps(charge, separators=(",", ":")).encode())
    return f"{corps}.{_b64(hmac.new(secret.encode(), corps.encode(), hashlib.sha256).digest())}"


class Ecran(http.Controller):

    @http.route("/cultiveau/ecran", type="http", auth="user", methods=["GET"])
    def ecran(self, vers="/adherent/espace", **_kw):
        parametres = request.env["ir.config_parameter"].sudo()
        secret = parametres.get_param("cultiveau.erp_lien_secret")
        site = (parametres.get_param("cultiveau.url_site") or "https://cultiveau.fr").rstrip("/")
        if not secret:
            return self._message("Le lien avec cultiveau.fr n'est pas encore réglé (secret partagé absent).")
        if not DESTINATION.match(vers or "") or "//" in vers or ".." in vers:
            vers = "/adherent/espace"
        utilisateur = request.env.user
        email = (utilisateur.email or utilisateur.login or "").strip().lower()
        jeton = fabriquer_jeton({"v": 1, "outil": "cultiveau", "source": "erp", "email": email, "vers": vers,
                                 "exp": int(time.time()) + 60, "n": secrets.token_hex(12)}, secret)
        reponse = request.redirect(f"{site}/api/erp/entree?t={quote(jeton)}", local=False)
        reponse.headers["Cache-Control"] = "no-store"
        reponse.headers["Referrer-Policy"] = "no-referrer"
        return reponse

    def _message(self, texte):
        return request.make_response(
            f"<!doctype html><html lang='fr'><head><meta charset='utf-8'></head><body style='font-family:sans-serif;"
            f"display:flex;align-items:center;justify-content:center;min-height:90vh;color:#183840'><p>{escape(texte)}</p></body></html>",
            headers=[("Content-Type", "text/html; charset=utf-8")])
