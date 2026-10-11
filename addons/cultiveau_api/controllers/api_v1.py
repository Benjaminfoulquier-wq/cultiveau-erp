"""L'API REST v1 et le connecteur Claude (MCP) de l'ERP.

Authentification (au choix) :
- ``Authorization: Bearer cv_…`` — une clé créée dans Cultiveau → Réglages → Clés d'API ;
- ``X-Cultiveau-Cle: cv_…`` — la même, dans l'en-tête des outils du réseau (l'ancienne clé unique des réglages reste acceptée) ;
- pour le connecteur Claude, la clé dans l'adresse : ``/cultiveau/mcp/cv_…``.
"""
import json
import logging

from odoo import SUPERUSER_ID, http
from odoo.exceptions import AccessError, UserError
from odoo.http import request

from odoo.addons.cultiveau_connecteurs.controllers.api import _autorise as _ancienne_cle_valide
from odoo.addons.cultiveau_connecteurs.controllers.api import _json

_logger = logging.getLogger(__name__)
VERSION = "1.0.0"
PROTOCOLES_MCP = ("2025-06-18", "2025-03-26", "2024-11-05")


class _Refus(Exception):
    pass


def _cle(depuis_adresse=None):
    """La clé qui appelle (enregistrement), None pour l'ancienne clé unique ; _Refus sinon."""
    request.update_env(user=SUPERUSER_ID)
    Cle = request.env["cultiveau.cle.api"]
    entete = request.httprequest.headers.get("Authorization", "")
    fournie = depuis_adresse or (entete[7:].strip() if entete.lower().startswith("bearer ") else "") or request.httprequest.headers.get("X-Cultiveau-Cle", "")
    if fournie.startswith("cv_"):
        cle = Cle.authentifier(fournie)
        if cle:
            return cle
        raise _Refus()
    if fournie and _ancienne_cle_valide():
        return None
    raise _Refus()


def _corps():
    try:
        return json.loads(request.httprequest.get_data(as_text=True) or "{}")
    except ValueError:
        raise UserError("Le corps de la requête n'est pas du JSON lisible.") from None


def _executer(fonction):
    try:
        cle = _cle()
    except _Refus:
        return _json({"erreur": "clé absente ou invalide", "aide": "En-tête Authorization: Bearer cv_… (Cultiveau → Réglages → Clés d'API)"}, 401)
    moteur = request.env["cultiveau.api.moteur"]
    try:
        return _json(fonction(moteur, cle))
    except AccessError as e:
        return _json({"erreur": str(e.args[0] if e.args else e)}, 403)
    except UserError as e:
        message = str(e.args[0] if e.args else e)
        return _json({"erreur": message}, 404 if "introuvable" in message else 400)
    except (ValueError, TypeError) as e:
        return _json({"erreur": f"paramètre invalide : {e}"}, 400)


class CultiveauApiV1(http.Controller):
    # ---------------------------------------------------------------- REST

    @http.route("/cultiveau/api/v1", type="http", auth="none", methods=["GET"], csrf=False, save_session=False)
    def index(self, **kw):
        return _executer(lambda m, cle: {
            "api": "ERP Cultiveau", "version": VERSION, "cle": {"outil": cle.name, "droits": cle.droits, "adherents": [c.name for c in m._societes(cle)]} if cle else None,
            "ressources": m.ressources_publiques(), "documentation": "/cultiveau/api/v1/openapi.json"})

    @http.route("/cultiveau/api/v1/resume", type="http", auth="none", methods=["GET"], csrf=False, save_session=False)
    def resume(self, **kw):
        return _executer(lambda m, cle: m.resume(cle))

    @http.route("/cultiveau/api/v1/openapi.json", type="http", auth="none", methods=["GET"], csrf=False, save_session=False)
    def openapi(self, **kw):
        request.update_env(user=SUPERUSER_ID)
        return _json(_openapi(request.env["cultiveau.api.moteur"]))

    @http.route("/cultiveau/api/v1/<string:ressource>", type="http", auth="none", methods=["GET", "POST"], csrf=False, save_session=False, readonly=False)
    def collection(self, ressource, **params):
        if request.httprequest.method == "POST":
            return _executer(lambda m, cle: m.creer(ressource, _corps(), cle))
        return _executer(lambda m, cle: m.lister(ressource, params, cle))

    @http.route("/cultiveau/api/v1/<string:ressource>/<int:ident>", type="http", auth="none", methods=["GET"], csrf=False, save_session=False)
    def element(self, ressource, ident, **kw):
        return _executer(lambda m, cle: m.lire(ressource, ident, cle))

    @http.route("/cultiveau/api/v1/<string:ressource>/<int:ident>/notes", type="http", auth="none", methods=["POST"], csrf=False, save_session=False, readonly=False)
    def note(self, ressource, ident, **kw):
        def faire(m, cle):
            corps = _corps()
            return m.noter(ressource, ident, corps.get("texte") or corps.get("note"), cle, corps.get("auteur"))
        return _executer(faire)

    # ---------------------------------------------------------------- le connecteur Claude (MCP, HTTP « streamable », réponses JSON)

    @http.route(["/cultiveau/mcp", "/cultiveau/mcp/<string:cle_adresse>"], type="http", auth="none", methods=["GET", "POST", "DELETE"], csrf=False,
                save_session=False, readonly=False)
    def mcp(self, cle_adresse=None, **kw):
        if request.httprequest.method != "POST":
            return request.make_response("", status=405, headers=[("Allow", "POST")])
        try:
            cle = _cle(cle_adresse)
        except _Refus:
            return _json({"jsonrpc": "2.0", "id": None, "error": {"code": -32001, "message": "clé absente ou invalide"}}, 401)
        try:
            message = json.loads(request.httprequest.get_data(as_text=True) or "null")
        except ValueError:
            return _json({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "JSON illisible"}}, 400)
        lot = message if isinstance(message, list) else [message]
        reponses = [r for r in (_mcp_traiter(m, cle) for m in lot) if r is not None]
        if not reponses:
            return request.make_response("", status=202)
        return _json(reponses if isinstance(message, list) else reponses[0])


# -------------------------------------------------------------------- MCP

def _outils(moteur, cle):
    ressources = list(moteur._ressources())
    filtres = {
        "q": {"type": "string", "description": "Texte cherché (nom, référence, commune, téléphone…)"},
        "client_id": {"type": "integer", "description": "Seulement ce client"}, "installation_id": {"type": "integer"},
        "adherent_id": {"type": "integer", "description": "Seulement cet adhérent (société)"},
        "etat": {"type": "string", "description": "État (ex. en_cours, planifie, not_paid, sale…)"},
        "modifie_depuis": {"type": "string", "description": "AAAA-MM-JJ : modifiés depuis cette date"},
        "ouvertes": {"type": "boolean", "description": "interventions : seulement celles à faire"},
        "a_encaisser": {"type": "boolean", "description": "factures : seulement celles à encaisser"},
        "catalogue": {"type": "string", "enum": ["mien", "reseau"], "description": "articles : mon catalogue ou le catalogue Cultiveau"},
        "en_stock": {"type": "boolean"}, "limite": {"type": "integer", "description": "1 à 200 (50 par défaut)"}, "decalage": {"type": "integer"},
    }
    outils = [
        {"name": "resume", "title": "Tableau de bord", "description": "Ce qui attend, adhérent par adhérent : interventions ouvertes et urgences, devis, factures à encaisser, opportunités, chantiers.",
         "inputSchema": {"type": "object", "properties": {}}, "annotations": {"readOnlyHint": True}},
        {"name": "lister", "title": "Lister", "description": "Liste une ressource de l'ERP avec recherche et filtres. Ressources : " + ", ".join(ressources) + ".",
         "inputSchema": {"type": "object", "properties": {"ressource": {"type": "string", "enum": ressources}, **filtres}, "required": ["ressource"]},
         "annotations": {"readOnlyHint": True}},
        {"name": "lire", "title": "Lire une fiche", "description": "La fiche complète d'un élément (client, intervention, chantier, installation, devis, facture…).",
         "inputSchema": {"type": "object", "properties": {"ressource": {"type": "string", "enum": ressources}, "id": {"type": "integer"}}, "required": ["ressource", "id"]},
         "annotations": {"readOnlyHint": True}},
        {"name": "chercher", "title": "Chercher partout", "description": "Cherche un texte dans les clients, interventions, chantiers, installations, devis, commandes, factures et opportunités.",
         "inputSchema": {"type": "object", "properties": {"texte": {"type": "string"}}, "required": ["texte"]}, "annotations": {"readOnlyHint": True}},
    ]
    if cle is None or cle.droits == "ecriture":
        client = {"type": "object", "properties": {"nom": {"type": "string"}, "telephone": {"type": "string"}, "email": {"type": "string"},
                                                   "exploitation": {"type": "string"}, "commune": {"type": "string"}, "code_postal": {"type": "string"}}}
        outils += [
            {"name": "creer_client", "title": "Créer un client", "description": "Crée un agriculteur (ou complète la fiche s'il existe déjà, reconnu par son téléphone ou son e-mail).",
             "inputSchema": {"type": "object", "properties": {**client["properties"], "rue": {"type": "string"}, "notes": {"type": "string"}, "adherent_id": {"type": "integer"}},
                             "required": ["nom"]}},
            {"name": "creer_intervention", "title": "Créer une intervention", "description": "Dépose une intervention (dépannage par défaut) pour un client existant (client_id) ou nouveau (client).",
             "inputSchema": {"type": "object", "properties": {"titre": {"type": "string"}, "symptome": {"type": "string"}, "description": {"type": "string"},
                                                              "urgence": {"type": "string", "enum": ["immediate", "journee", "semaine", "non_urgent"]},
                                                              "nature": {"type": "string", "enum": ["depannage", "entretien", "remise_en_service", "hivernage", "mise_en_service", "diagnostic", "modification", "livraison", "autre"]},
                                                              "client_id": {"type": "integer"}, "client": client, "installation_id": {"type": "integer"}, "adherent_id": {"type": "integer"}},
                             "required": ["titre"]}},
            {"name": "creer_opportunite", "title": "Créer une opportunité", "description": "Dépose une demande (devis, projet) pour un client existant ou nouveau.",
             "inputSchema": {"type": "object", "properties": {"titre": {"type": "string"}, "description": {"type": "string"}, "montant_espere": {"type": "number"},
                                                              "surface_ha": {"type": "number"}, "client_id": {"type": "integer"}, "client": client, "adherent_id": {"type": "integer"}},
                             "required": ["titre"]}},
            {"name": "ajouter_note", "title": "Ajouter une note", "description": "Ajoute une note sur une fiche (visible de l'équipe dans l'historique).",
             "inputSchema": {"type": "object", "properties": {"ressource": {"type": "string", "enum": ressources}, "id": {"type": "integer"}, "texte": {"type": "string"}},
                             "required": ["ressource", "id", "texte"]}},
        ]
    return outils


def _appeler(moteur, cle, nom, a):
    if nom == "resume":
        return moteur.resume(cle)
    if nom == "lister":
        return moteur.lister(a.get("ressource"), {k: v for k, v in a.items() if k != "ressource"}, cle)
    if nom == "lire":
        return moteur.lire(a.get("ressource"), a.get("id"), cle)
    if nom == "chercher":
        texte = a.get("texte") or ""
        return {r: moteur.lister(r, {"q": texte, "limite": 5}, cle)["resultats"]
                for r in ("clients", "interventions", "chantiers", "installations", "devis", "commandes", "factures", "opportunites") if r in moteur._ressources()}
    if nom == "creer_client":
        return moteur.creer("clients", a, cle)
    if nom == "creer_intervention":
        return moteur.creer("interventions", a, cle)
    if nom == "creer_opportunite":
        return moteur.creer("opportunites", a, cle)
    if nom == "ajouter_note":
        return moteur.noter(a.get("ressource"), a.get("id"), a.get("texte"), cle, "Claude")
    raise UserError(f"Outil inconnu : {nom}")


def _mcp_traiter(m, cle):
    if not isinstance(m, dict) or m.get("jsonrpc") != "2.0":
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "requête JSON-RPC 2.0 attendue"}}
    ident, methode, params = m.get("id"), m.get("method"), m.get("params") or {}
    if ident is None:
        return None  # une notification (notifications/initialized…) : rien à répondre
    moteur = request.env["cultiveau.api.moteur"]
    if methode == "initialize":
        demande = params.get("protocolVersion")
        return {"jsonrpc": "2.0", "id": ident, "result": {
            "protocolVersion": demande if demande in PROTOCOLES_MCP else PROTOCOLES_MCP[0],
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "erp-cultiveau", "title": "ERP Cultiveau", "version": VERSION},
            "instructions": ("L'ERP du réseau Cultiveau (magasins d'irrigation agricole). Commencez par « resume » ou « chercher » ; "
                             "« lister » et « lire » donnent le détail des clients, interventions, chantiers, installations, devis, factures, articles."),
        }}
    if methode == "ping":
        return {"jsonrpc": "2.0", "id": ident, "result": {}}
    if methode == "tools/list":
        return {"jsonrpc": "2.0", "id": ident, "result": {"tools": _outils(moteur, cle)}}
    if methode == "tools/call":
        nom = params.get("name")
        try:
            with request.env.cr.savepoint():
                resultat = _appeler(moteur, cle, nom, params.get("arguments") or {})
            texte = json.dumps(resultat, ensure_ascii=False, default=str, indent=1)
            return {"jsonrpc": "2.0", "id": ident, "result": {"content": [{"type": "text", "text": texte}], "structuredContent": resultat, "isError": False}}
        except (UserError, AccessError, ValueError, TypeError) as e:
            return {"jsonrpc": "2.0", "id": ident, "result": {"content": [{"type": "text", "text": str(e.args[0] if e.args else e)}], "isError": True}}
    if methode in ("resources/list", "prompts/list"):
        return {"jsonrpc": "2.0", "id": ident, "result": {methode.split("/")[0]: []}}
    return {"jsonrpc": "2.0", "id": ident, "error": {"code": -32601, "message": f"méthode inconnue : {methode}"}}


# -------------------------------------------------------------------- OpenAPI

def _openapi(moteur):
    chemins = {
        "/resume": {"get": {"summary": "Tableau de bord par adhérent", "responses": {"200": {"description": "OK"}}}},
    }
    parametres = [{"name": n, "in": "query", "schema": {"type": t}, "description": d} for n, t, d in (
        ("q", "string", "Texte cherché"), ("limite", "integer", "1 à 200, 50 par défaut"), ("decalage", "integer", "Pour paginer"), ("page", "integer", "Ou par page"),
        ("modifie_depuis", "string", "AAAA-MM-JJ[ HH:MM:SS]"), ("client_id", "integer", ""), ("installation_id", "integer", ""), ("adherent_id", "integer", ""),
        ("etat", "string", ""), ("ouvertes", "boolean", "interventions"), ("a_encaisser", "boolean", "factures"), ("catalogue", "string", "articles : mien | reseau"),
        ("en_stock", "boolean", "articles"))]
    for r in moteur.ressources_publiques():
        op = {"get": {"summary": r["titre"], "parameters": parametres, "responses": {"200": {"description": "{ressource, total, limite, decalage, suivant, resultats[]}"}}}}
        if r["ecriture"]:
            op["post"] = {"summary": f"Créer ({r['nom']})", "requestBody": {"content": {"application/json": {"schema": {"type": "object"}}}},
                          "responses": {"200": {"description": "L'élément créé"}}}
        chemins[f"/{r['nom']}"] = op
        chemins[f"/{r['nom']}/{{id}}"] = {"get": {"summary": f"Une fiche ({r['nom']})", "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                                                  "responses": {"200": {"description": "La fiche complète"}, "404": {"description": "Introuvable"}}}}
        chemins[f"/{r['nom']}/{{id}}/notes"] = {"post": {"summary": "Ajouter une note", "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}],
                                                        "requestBody": {"content": {"application/json": {"schema": {"type": "object", "properties": {"texte": {"type": "string"}, "auteur": {"type": "string"}}}}}},
                                                        "responses": {"200": {"description": "OK"}}}}
    return {"openapi": "3.1.0", "info": {"title": "API de l'ERP Cultiveau", "version": VERSION,
                                         "description": "Clés : Cultiveau → Réglages → Clés d'API. En-tête Authorization: Bearer cv_…"},
            "servers": [{"url": "/cultiveau/api/v1"}], "components": {"securitySchemes": {"cle": {"type": "http", "scheme": "bearer"}}},
            "security": [{"cle": []}], "paths": chemins}
