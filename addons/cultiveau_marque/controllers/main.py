"""L'adresse de l'application est /app, jamais le nom de l'éditeur : les anciennes adresses y renvoient.

Le manifeste de l'application (écran d'accueil du téléphone, couleur de la barre du navigateur) et la page
hors ligne sont aux couleurs et au nom de Cultiveau.
"""
from odoo import http
from odoo.http import request
from odoo.tools import file_open

from odoo.addons.web.controllers.home import Home
from odoo.addons.web.controllers.webmanifest import WebManifest

PREFIXE = "/app"
COULEUR_FOND = "#183840"


def _vers_app(subpath=""):
    return PREFIXE + (f"/{subpath}" if subpath else "")


class HomeCultiveau(Home):
    @http.route("/", type="http", auth="none")
    def index(self, s_action=None, db=None, **kw):
        reponse = super().index(s_action=s_action, db=db, **kw)
        return _corriger_redirection(reponse)

    @http.route(["/web", PREFIXE, PREFIXE + "/<path:subpath>", "/scoped_app/<path:subpath>"], type="http", auth="none")
    def web_client(self, s_action=None, **kw):
        kw.pop("subpath", None)
        return _corriger_redirection(super().web_client(s_action=s_action, **kw))

    @http.route(["/odoo", "/odoo/<path:subpath>"], type="http", auth="none")
    def web_client_ancienne_adresse(self, subpath="", **kw):
        """L'adresse d'origine du client web renvoie, pour toujours, vers /app (liens, favoris, e-mails)."""
        return request.redirect_query(_vers_app(subpath), query=request.httprequest.args, code=301)


def _corriger_redirection(reponse):
    """Une redirection vers l'ancienne adresse part directement vers /app."""
    location = getattr(reponse, "headers", None) and reponse.headers.get("Location")
    if location and (location == "/odoo" or location.startswith(("/odoo/", "/odoo?"))):
        reponse.headers["Location"] = PREFIXE + location[len("/odoo"):]
    return reponse


class WebManifestCultiveau(WebManifest):
    def _get_webmanifest(self):
        manifest = super()._get_webmanifest()
        manifest.update({
            "name": request.env["ir.config_parameter"].sudo().get_param("web.web_app_name", "Cultiveau"),
            "scope": PREFIXE, "start_url": PREFIXE, "background_color": COULEUR_FOND, "theme_color": COULEUR_FOND,
            "icons": [{"src": f"/cultiveau_marque/static/src/img/icone-{t}.png", "sizes": f"{t}x{t}", "type": "image/png"} for t in (192, 512)],
        })
        for raccourci in manifest.get("shortcuts", []):
            raccourci["url"] = raccourci["url"].replace("/odoo", PREFIXE, 1)
        return manifest

    @http.route("/web/service-worker.js", type="http", auth="public", methods=["GET"], readonly=True)
    def service_worker(self):
        reponse = super().service_worker()
        reponse.headers["Service-Worker-Allowed"] = PREFIXE
        return reponse

    def _get_service_worker_content(self):
        return super()._get_service_worker_content().replace("/odoo", PREFIXE)

    def _icon_path(self):
        return "cultiveau_marque/static/src/img/icone-192.png"

    @http.route(PREFIXE + "/offline", type="http", auth="public", methods=["GET"], readonly=True)
    def offline(self):
        return super().offline()
