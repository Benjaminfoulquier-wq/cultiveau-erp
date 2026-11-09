"""La fusion des deux horloges : à accompagner, pourquoi, et comment.

Une horloge est agronomique : la frise culturale dit quand le client entre dans une fenêtre projet
(il a le temps d'étudier) ou achat (il va commander), et quand il est en période critique (on ne le
dérange pas). L'autre est comportementale : son persona et ses signaux (un appel de dépannage récent,
un projet ouvert, un devis en attente) disent comment l'aborder et s'il faut le faire maintenant.

Ce module les met ensemble en une seule liste priorisée « À accompagner », avec, pour chaque client,
pourquoi c'est le moment (horloge agronomique + signaux) et comment lui parler (persona + Agent).

Garde-fous : rien n'est automatique, c'est une liste de rappels pour l'adhérent ; la période critique
fait taire la relance commerciale mais pas une demande d'aide à laquelle il faut répondre ; le profilage
reste interne à l'adhérent.
"""
from markupsafe import Markup, escape

from odoo import api, fields, models

JOURS_APPEL = 30     # un appel entrant de moins d'un mois compte comme une demande vivante
JOURS_DEVIS = 45     # un devis envoyé il y a moins de 45 jours et non signé reste chaud
SEUIL_LISTE = 15     # en dessous, pas assez de raison pour figurer dans « À accompagner »


class ResPartnerAccompagnement(models.Model):
    _inherit = "res.partner"

    cultiveau_accompagner = fields.Boolean(
        "À accompagner", readonly=True, index=True,
        help="Les deux horloges concordent : c'est le moment de reprendre contact avec ce client.")
    cultiveau_accompagner_priorite = fields.Integer("Priorité", readonly=True)
    cultiveau_accompagner_motif = fields.Char("Pourquoi maintenant", readonly=True)
    cultiveau_accompagner_html = fields.Html(
        "À accompagner — le détail", compute="_compute_accompagner_html", sanitize=False)

    def _accompagnement_signaux(self, mois):
        """Renvoie (priorite, [raisons_now], critique_actif). Les raisons sont l'horloge qui sonne."""
        self.ensure_one()
        priorite = 0
        raisons = []
        critique = False

        # --- horloge agronomique : les fenêtres de la frise ce mois-ci -------------------
        genres = set()
        noms_critiques = []
        for cc in self.cultiveau_culture_ids:
            genres |= cc.fenetres_du_mois(mois)
            if cc.posture_du_mois(mois)[1]:
                critique = True
                noms_critiques.append(cc.culture_id.name)
        if "projet" in genres:
            priorite += 40
            raisons.append("Fenêtre projet ouverte : il a le temps d'étudier, c'est le moment de proposer l'analyse des besoins.")
        if "achat" in genres:
            priorite += 25
            raisons.append("Fenêtre d'achat ouverte : il va commander et se faire livrer.")

        # --- horloge comportementale : les signaux vivants -------------------------------
        maintenant = fields.Datetime.now()
        if "cultiveau.appel" in self.env:
            recents = self.env["cultiveau.appel"].sudo().search([
                ("partner_id", "child_of", self.id), ("sens", "=", "entrant"),
                ("date", ">=", fields.Datetime.subtract(maintenant, days=JOURS_APPEL))])
            aide = recents.filtered(
                lambda a: a.urgence in ("immediate", "journee")
                or any(m in ((a.categorie or "") + " " + (a.sujet or "")).lower()
                       for m in ("panne", "dépann", "depann", "fuite", "problème", "probleme", "conseil", "aide")))
            if aide:
                priorite += 30
                raisons.append(f"Il a appelé pour être aidé il y a moins d'un mois ({len(aide)} appel·s) : à rappeler, même en période critique.")
        if "crm.lead" in self.env:
            opps = self.env["crm.lead"].sudo().search_count([
                ("partner_id", "child_of", self.id), ("type", "=", "opportunity"), ("active", "=", True)])
            if opps:
                priorite += 20
                raisons.append(f"{opps} projet·s en cours à faire avancer.")
        if "sale.order" in self.env:
            attente = self.env["sale.order"].sudo().search_count([
                ("partner_id", "child_of", self.id), ("state", "=", "sent"),
                ("date_order", ">=", fields.Datetime.subtract(maintenant, days=JOURS_DEVIS))])
            if attente:
                priorite += 15
                raisons.append(f"{attente} devis envoyé·s et pas encore signé·s : une relance peut débloquer.")
        if self.cultiveau_persona_ecart:
            priorite += 5
            raisons.append("Il se décrit autrement qu'il ne se comporte : l'occasion de mieux le cerner.")

        return priorite, raisons, (critique, noms_critiques)

    def cultiveau_calculer_accompagnement(self, mois=None):
        """Écrit, pour chaque client, s'il est à accompagner, avec quelle priorité et quel motif."""
        mois = mois or fields.Date.context_today(self).month
        for p in self:
            if not p.cultiveau_est_client:
                p.cultiveau_accompagner = False
                p.cultiveau_accompagner_priorite = 0
                p.cultiveau_accompagner_motif = False
                continue
            priorite, raisons, (critique, noms) = p._accompagnement_signaux(mois)
            # La période critique fait taire la relance commerciale, pas une demande d'aide.
            demande_vivante = any("rappeler" in r for r in raisons)
            if critique and not demande_vivante:
                priorite = min(priorite, 10)
            p.cultiveau_accompagner_priorite = min(priorite, 100)
            p.cultiveau_accompagner = priorite >= SEUIL_LISTE
            p.cultiveau_accompagner_motif = raisons[0] if raisons else False
        return True

    def action_cultiveau_calculer_accompagnement(self):
        self.cultiveau_calculer_accompagnement()
        return True

    @api.model
    def cultiveau_accompagnement_cron(self, limite=600):
        self.search([("cultiveau_est_client", "=", True)], limit=limite).cultiveau_calculer_accompagnement()
        return True

    def _compute_accompagner_html(self):
        mois = fields.Date.context_today(self).month
        for p in self:
            if not p.cultiveau_est_client or not (p.cultiveau_culture_ids or p.cultiveau_persona_id):
                p.cultiveau_accompagner_html = Markup(
                    "<p class='text-muted'>Pas assez d'éléments pour dire s'il faut l'accompagner maintenant.</p>")
                continue
            priorite, raisons, (critique, noms) = p._accompagnement_signaux(mois)
            lignes = [f"<p style='margin:0 0 6px'><b>Priorité {min(priorite, 100)}/100</b></p>"]
            lignes.append("<p style='margin:0 0 2px'><b>Pourquoi maintenant</b></p>")
            if raisons:
                lignes.append("<ul style='margin:0 0 8px'>" + "".join(f"<li>{escape(r)}</li>" for r in raisons) + "</ul>")
            else:
                lignes.append("<p style='margin:0 0 8px;color:#5d6b78'>Aucune horloge ne sonne ce mois-ci.</p>")
            if critique:
                lignes.append(f"<p style='margin:0 0 8px;color:#b23a3a'>⚠ {', '.join(escape(n) for n in noms)} "
                              "en période critique : on ne relance pas, on répond seulement à une demande.</p>")
            # Comment l'aborder : le persona et l'Agent.
            reco = p.cultiveau_recommandation(mois)
            lignes.append("<p style='margin:0 0 2px'><b>Comment l'aborder</b></p>")
            if p.cultiveau_persona_id:
                src = "observé" if (p.cultiveau_persona_observe_id == p.cultiveau_persona_id
                                    and not p.cultiveau_persona_evaluation_ids) else "déclaré"
                lignes.append(f"<p style='margin:0 0 4px'>Profil {escape(p.cultiveau_persona_id.name)} ({src}) : "
                              f"{escape(reco['ton'] or reco['approche'] or '')}</p>")
            if reco.get("eviter"):
                lignes.append("<p style='margin:0'>⛔ Éviter : " + " · ".join(escape(e) for e in reco["eviter"]) + "</p>")
            p.cultiveau_accompagner_html = Markup("".join(lignes))
