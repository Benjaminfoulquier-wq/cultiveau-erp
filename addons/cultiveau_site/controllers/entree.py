"""``/cultiveau/entree?t=…`` : l'entrée dans l'ERP depuis cultiveau.fr, avec le laissez-passer signé par le site."""
import base64
import hashlib
import logging
import hmac
import json
import re
import time
from datetime import datetime

from markupsafe import escape

from odoo import SUPERUSER_ID, http
from odoo.http import request

_logger = logging.getLogger(__name__)
DESTINATION = re.compile(r"^/app(/[A-Za-z0-9/_\-?=&.%]*)?$")


def lire_jeton(jeton, secret):
    """Vérifie base64url(JSON).base64url(HMAC-SHA256) et rend la charge ; lève ValueError sinon."""
    try:
        corps, signature = (jeton or "").split(".")
    except ValueError as e:
        raise ValueError("laissez-passer illisible") from e
    attendu = base64.urlsafe_b64encode(hmac.new(secret.encode(), corps.encode(), hashlib.sha256).digest()).rstrip(b"=").decode()
    if not hmac.compare_digest(attendu, signature):
        raise ValueError("signature invalide")
    charge = json.loads(base64.urlsafe_b64decode(corps + "=" * (-len(corps) % 4)))
    if int(charge.get("exp") or 0) < time.time():
        raise ValueError("laissez-passer expiré")
    return charge


class Entree(http.Controller):

    @http.route("/cultiveau/entree", type="http", auth="none", methods=["GET"], csrf=False, readonly=False)
    def entree(self, t="", **_kw):
        # auth="none" : pas d'utilisateur dans l'environnement ; tout ce qui suit se fait en administrateur, avec sa société
        env = request.env(user=SUPERUSER_ID)
        P = env["ir.config_parameter"].sudo()
        secret = P.get_param("cultiveau.erp_lien_secret")
        if not secret:
            return self._message("Le lien avec cultiveau.fr n'est pas encore réglé dans l'ERP (secret partagé absent).")
        try:
            charge = lire_jeton(t, secret)
        except (ValueError, TypeError) as e:
            return self._message(f"Laissez-passer refusé : {e}. Repassez par cultiveau.fr.")
        if charge.get("v") != 1 or charge.get("outil") != "erp" or charge.get("source") != "cultiveau":
            return self._message("Laissez-passer inattendu.")
        email = (charge.get("email") or "").strip().lower()
        LP = env["cultiveau.site.laissez_passer"].sudo()
        if not charge.get("n") or LP.search_count([("nonce", "=", charge["n"])]):
            return self._message("Laissez-passer déjà utilisé : repassez par cultiveau.fr.")
        lp = LP.create({"nonce": charge["n"], "login": email, "expire_le": datetime.utcfromtimestamp(int(charge["exp"]))})
        try:
            user = env["res.users"].sudo().cultiveau_depuis_site(charge)
        except PermissionError as e:
            request.env.cr.rollback()
            return self._message(str(e))
        except Exception as e:  # noqa: BLE001 — on explique plutôt qu'une page d'erreur
            _logger.exception("cultiveau.fr : entrée impossible pour %s", email)
            request.env.cr.rollback()
            return self._message(f"Impossible de préparer votre accès : {e}")
        request.env.cr.commit()  # l'utilisateur et le laissez-passer doivent exister pour le curseur d'authentification
        try:
            request.session.authenticate(request.db, {"type": "cultiveau_site", "login": user.login, "laissez_passer": lp.id})
        except Exception as e:  # noqa: BLE001
            return self._message(f"Connexion refusée : {e}")
        vers = charge.get("vers") or "/app"
        if not DESTINATION.match(vers) or "//" in vers or ".." in vers:
            vers = "/app"
        reponse = request.redirect(vers)
        reponse.headers["Cache-Control"] = "no-store"
        return reponse

    @http.route("/cultiveau/entree/eligible", type="http", auth="none", methods=["GET"], csrf=False)
    def eligible(self, t="", **_kw):
        """cultiveau.fr demande, signé, si cette personne peut entrer dans l'ERP : tout le monde n'a pas l'ERP."""
        env = request.env(user=SUPERUSER_ID)
        secret = env["ir.config_parameter"].sudo().get_param("cultiveau.erp_lien_secret")
        reponse = {"eligible": False}
        if secret:
            try:
                charge = lire_jeton(t, secret)
                if charge.get("v") == 1 and charge.get("outil") == "erp" and charge.get("action") == "eligible":
                    ok, raison = env["res.company"].sudo().cultiveau_erp_eligible(charge)
                    reponse = {"eligible": ok, "raison": raison}
            except (ValueError, TypeError) as e:
                reponse = {"eligible": False, "raison": str(e)}
        return request.make_response(json.dumps(reponse), headers=[("Content-Type", "application/json"), ("Cache-Control", "no-store")])

    def _message(self, texte):
        return request.make_response(
            f"<!doctype html><html lang='fr'><head><meta charset='utf-8'><title>Cultiveau</title></head><body style='font-family:sans-serif;"
            f"display:flex;align-items:center;justify-content:center;min-height:90vh;color:#15283a'><p>{escape(texte)}</p></body></html>",
            headers=[("Content-Type", "text/html; charset=utf-8")])
