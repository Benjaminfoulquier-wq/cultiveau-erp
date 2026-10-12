"""« Mon espace » : la page du téléphone. Badger, demander un congé, photographier un ticket, valider (pour le gérant).

Une page simple, sans application à installer : elle s'ouvre dans le navigateur du téléphone (et s'ajoute à l'écran d'accueil).
Chaque formulaire revient sur la page avec un message.
"""
import logging

from werkzeug.urls import url_encode

from odoo import http
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)

TAILLE_MAX = 15 * 1024 * 1024
GENRES_BADGE = {"arrivee", "pause_debut", "pause_fin", "depart_intervention", "retour_intervention", "depart"}


def _retour(message=None, erreur=None, ancre=""):
    params = {k: v for k, v in (("message", message), ("erreur", erreur)) if v}
    return request.redirect("/moi" + (("?" + url_encode(params)) if params else "") + (f"#{ancre}" if ancre else ""), local=True)


def _faire(fonction, ancre=""):
    """Exécute dans un point de sauvegarde : une erreur métier revient à la page, lisible, sans casser la transaction."""
    try:
        with request.env.cr.savepoint():
            message = fonction()
        return _retour(message=message, ancre=ancre)
    except (UserError, ValidationError, AccessError) as e:
        return _retour(erreur=str(e.args[0] if e.args else e), ancre=ancre)


class Moi(http.Controller):

    @http.route("/moi", type="http", auth="user", methods=["GET"])
    def moi(self, message=None, erreur=None, **kw):
        if request.env.user.share:
            return request.redirect("/my", local=True)
        d = request.env["cultiveau.equipe"].espace()
        return request.render("cultiveau_rh.moi", {"d": d, "message": message, "erreur": erreur})

    @http.route("/moi/badger", type="http", auth="user", methods=["POST"])
    def badger(self, genre=None, **kw):
        if genre not in GENRES_BADGE:
            return _retour(erreur="Pointage inconnu.")

        def faire():
            request.env["cultiveau.pointage"].badger(genre, user=request.env.user, source="erp", note="depuis le téléphone")
            return "Pointage enregistré."
        return _faire(faire)

    @http.route("/moi/conge", type="http", auth="user", methods=["POST"])
    def conge(self, type_conge="conges_payes", du=None, au=None, demi="", motif="", **kw):
        def faire():
            c = request.env["cultiveau.conges"].demander(type_conge, du, au or du, demi or False, motif)
            return f"Demande envoyée : {c['type'].lower()} {c['periode']} ({c['jours']:g} j)."
        return _faire(faire, "conges")

    @http.route("/moi/frais", type="http", auth="user", methods=["POST"])
    def frais(self, montant="", categorie="", kilometres="", note="", **kw):
        fichier = request.httprequest.files.get("ticket")
        contenu = fichier.read(TAILLE_MAX + 1) if fichier and fichier.filename else b""
        if len(contenu) > TAILLE_MAX:
            return _retour(erreur="Photo trop lourde (15 Mo au plus).", ancre="frais")
        if not contenu and not kilometres and not montant:
            return _retour(erreur="Prenez le ticket en photo, ou indiquez un montant ou des kilomètres.", ancre="frais")

        def faire():
            x = request.env["cultiveau.frais"].depuis_photo(fichier.filename if contenu else None, contenu or None, fichier.mimetype if contenu else None,
                                                            montant=montant, categorie=categorie or None, kilometres=kilometres, note=note)
            if x["lecture"] == "lu":
                return f"Ticket lu : {x['montant_texte']} · {x['categorie']}. Vérifiez puis envoyez."
            if x["lecture_message"] and x["lecture"] == "echec":
                return f"Dépense ajoutée, mais le ticket est illisible : indiquez le montant dans l'ERP. ({x['nom']})"
            return f"Dépense ajoutée : {x['montant_texte']} · {x['categorie']}."
        return _faire(faire, "frais")

    @http.route("/moi/frais/envoyer", type="http", auth="user", methods=["POST"])
    def envoyer(self, **kw):
        return _faire(lambda: request.env["cultiveau.frais"].envoyer()["message"], "frais")

    @http.route("/moi/frais/supprimer", type="http", auth="user", methods=["POST"])
    def supprimer(self, expense_id=0, **kw):
        def faire():
            x = request.env["hr.expense"].browse(int(expense_id or 0)).exists()
            e = request.env["cultiveau.equipe"].employe(creer=False)
            if not x or x.employee_id != e or x.state not in ("draft", "reported"):
                raise UserError("Cette dépense ne peut plus être supprimée.")
            x.unlink()
            return "Dépense supprimée."
        return _faire(faire, "frais")

    @http.route("/moi/decider", type="http", auth="user", methods=["POST"])
    def decider(self, genre="", res_id=0, oui="1", motif="", **kw):
        modele = {"conge": "cultiveau.conges", "frais": "cultiveau.frais"}.get(genre)
        if not modele:
            return _retour(erreur="Demande inconnue.")
        return _faire(lambda: request.env[modele].decider(int(res_id or 0), oui == "1", motif)["message"], "valider")
