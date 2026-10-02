"""L'API de l'ERP pour les outils du réseau, d'abord l'assistant téléphonique.

Authentification : l'en-tête ``X-Cultiveau-Cle`` doit valoir la clé réglée dans
Cultiveau → Réglages (paramètre ``cultiveau.cle_api``). Sans clé réglée, l'API est fermée.
Les réponses sont en JSON ; les erreurs portent un code HTTP parlant (401, 404, 400).
"""
import hmac
import json
import logging

from odoo import SUPERUSER_ID, fields, http
from odoo.http import request

from odoo.addons.cultiveau_base.models.res_partner import normaliser_telephone
from odoo.addons.cultiveau_frise.models.culture import MOIS

_logger = logging.getLogger(__name__)


def _json(donnees, statut=200):
    return request.make_response(json.dumps(donnees, ensure_ascii=False, default=str), headers=[("Content-Type", "application/json; charset=utf-8")], status=statut)


def _autorise():
    attendue = request.env["ir.config_parameter"].sudo().get_param("cultiveau.cle_api") or ""
    fournie = request.httprequest.headers.get("X-Cultiveau-Cle", "")
    return bool(attendue) and hmac.compare_digest(attendue, fournie)


def _societe(numero_dedie):
    """L'adhérent reconnu par son numéro dédié ; sinon la société principale."""
    Company = request.env["res.company"].sudo()
    n = normaliser_telephone(numero_dedie)
    if n:
        for c in Company.search([("cultiveau_numero_dedie", "!=", False)]):
            if normaliser_telephone(c.cultiveau_numero_dedie) == n:
                return c
    return Company.browse(1) if Company.browse(1).exists() else Company.search([], limit=1)


def _fiche_client(partner):
    mois = fields.Date.context_today(partner).month
    fenetres = [{"culture": cc.culture_id.name, "genre": g, "surface_ha": cc.surface_ha}
                for cc in partner.cultiveau_culture_ids for g in sorted(cc.fenetres_du_mois(mois))]
    return {
        "id": partner.id, "nom": partner.name, "exploitation": partner.exploitation or "", "commune": partner.city or "",
        "departement": partner.departement or "", "email": partner.email or "", "telephone": partner.mobile or partner.phone or "",
        "commercial": partner.user_id.name if partner.user_id else "",
        "persona": partner.cultiveau_persona_pour_api(),
        "cultures": [{"culture": cc.culture_id.name, "surface_ha": cc.surface_ha, "projet": cc.projet_mois, "achat": cc.achat_mois} for cc in partner.cultiveau_culture_ids],
        "fenetres_du_mois": fenetres, "mois": MOIS[mois - 1][1],
        "installations": partner.cultiveau_installation_ids.resume_pour_api(),
        "interventions_ouvertes": [{"id": t.id, "nom": t.name, "urgence": t.cultiveau_urgence, "etape": t.stage_id.name}
                                   for t in request.env["project.task"].sudo().search(
                                       [("partner_id", "=", partner.id), ("cultiveau_intervention", "=", True), ("is_closed", "=", False)], limit=5)],
        "url": f"/odoo/contacts/{partner.id}",
    }


class CultiveauApi(http.Controller):
    @http.route("/cultiveau/api/client", type="http", auth="none", methods=["GET"], csrf=False, save_session=False)
    def client(self, telephone=None, numero_dedie=None, **kw):
        if not _autorise():
            return _json({"erreur": "clé absente ou invalide"}, 401)
        request.update_env(user=SUPERUSER_ID)
        societe = _societe(numero_dedie)
        partner = request.env["res.partner"].with_company(societe).cultiveau_par_telephone(telephone, societe)
        if not partner:
            return _json({"trouve": False, "adherent": societe.name, "telephone": normaliser_telephone(telephone)})
        return _json({"trouve": True, "adherent": societe.name, "client": _fiche_client(partner)})

    @http.route("/cultiveau/api/appel", type="http", auth="none", methods=["POST"], csrf=False, save_session=False, readonly=False)
    def appel(self, **kw):
        if not _autorise():
            return _json({"erreur": "clé absente ou invalide"}, 401)
        try:
            donnees = json.loads(request.httprequest.get_data(as_text=True) or "{}")
        except ValueError:
            return _json({"erreur": "corps JSON illisible"}, 400)
        request.update_env(user=SUPERUSER_ID)
        societe = _societe(donnees.get("numero_dedie"))
        Partner = request.env["res.partner"].with_company(societe)
        client = donnees.get("client") or {}
        telephone = client.get("telephone") or donnees.get("telephone")
        partner = Partner.cultiveau_par_telephone(telephone, societe)
        cree = False
        if not partner:
            if not (client.get("nom") or telephone):
                return _json({"erreur": "client : nom ou téléphone requis"}, 400)
            partner = Partner.create({
                "name": client.get("nom") or f"Appelant {normaliser_telephone(telephone)}", "mobile": telephone or False,
                "email": client.get("email") or False, "city": client.get("commune") or False, "zip": client.get("code_postal") or False,
                "exploitation": client.get("exploitation") or False, "cultiveau_type": "agriculteur", "company_id": societe.id,
                "comment": "Créé par l'assistant téléphonique d'après la conversation : nom et commune à vérifier."})
            cree = True
        reference = donnees.get("reference") or ""
        # Un appel n'est déposé qu'une fois : la référence fait foi.
        if reference:
            Task, Lead = request.env["project.task"], request.env["crm.lead"]
            deja = Task.search([("cultiveau_reference_appel", "=", reference)], limit=1) or Lead.search([("cultiveau_reference_appel", "=", reference)], limit=1)
            if deja:
                return _json({"ok": True, "deja": True, "type": "intervention" if deja._name == "project.task" else "opportunite", "id": deja.id,
                              "client_id": partner.id, "url": f"/odoo/action-{'project.action_view_all_task' if deja._name == 'project.task' else 'crm.crm_lead_action_pipeline'}/{deja.id}"})
        categorie = (donnees.get("categorie") or "autre").lower()
        resume = donnees.get("resume") or donnees.get("symptome") or "Appel reçu par l'assistant"
        if categorie in ("panne", "depannage", "urgence", "intervention"):
            t = request.env["project.task"].cultiveau_creer_depuis_appel(societe, partner, donnees)
            return _json({"ok": True, "type": "intervention", "id": t.id, "client_id": partner.id, "client_cree": cree, "url": f"/odoo/action-project.action_view_all_task/{t.id}"})
        if categorie in ("devis", "projet", "prix", "demande_de_prix", "opportunite"):
            lead = request.env["crm.lead"].with_company(societe).create({
                "name": resume[:120], "type": "opportunity", "partner_id": partner.id, "company_id": societe.id,
                "description": donnees.get("transcription") or resume, "cultiveau_origine": "assistant", "cultiveau_reference_appel": reference,
                "cultiveau_urgence": donnees.get("urgence") if donnees.get("urgence") in ("immediate", "journee", "semaine", "non_urgent") else False,
                "cultiveau_surface_ha": float(donnees.get("surface_ha") or 0) or 0.0,
                "stage_id": request.env.ref("cultiveau_ventes.stage_demande", raise_if_not_found=False).id or False})
            return _json({"ok": True, "type": "opportunite", "id": lead.id, "client_id": partner.id, "client_cree": cree, "url": f"/odoo/action-crm.crm_lead_action_pipeline/{lead.id}"})
        activite = partner.activity_schedule("mail.mail_activity_data_call", summary=resume[:120], note=donnees.get("transcription") or resume,
                                             user_id=(partner.user_id or request.env.ref("base.user_admin")).id)
        return _json({"ok": True, "type": "activite", "id": activite.id, "client_id": partner.id, "client_cree": cree, "url": f"/odoo/contacts/{partner.id}"})
