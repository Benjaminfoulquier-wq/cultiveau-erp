from markupsafe import Markup, escape

from odoo import api, fields, models

from .culture import COURS, MOIS, MOIS_COURTS, POSTURE_INFOS, POSTURES, TON_COURS, combiner_postures, libelle_mois

FOND = ["#f5f3ef", "#dceef1", "#b8dde3", "#7fc3cf", "#2a7f8f"]  # repos → pointe


class ResPartner(models.Model):
    _inherit = "res.partner"

    cultiveau_culture_ids = fields.One2many("cultiveau.culture.client", "partner_id", string="Cultures")
    cultiveau_surface_ha = fields.Float("Surface irriguée (ha)", compute="_compute_surface", digits=(8, 2))
    cultiveau_frise_html = fields.Html("Frise culturale", compute="_compute_frise", sanitize=False)
    cultiveau_fenetres = fields.Char("Fenêtres commerciales", compute="_compute_frise")
    cultiveau_a_contacter = fields.Boolean("À contacter ce mois-ci", compute="_compute_a_contacter", search="_search_a_contacter")
    cultiveau_posture = fields.Selection(POSTURES, "Posture du mois", compute="_compute_posture",
                                         help="Ce que l'agriculteur attend de nous ce mois-ci, d'après le stade de ses cultures.")
    cultiveau_posture_detail = fields.Char("Pourquoi", compute="_compute_posture")
    cultiveau_periode_critique = fields.Boolean("Période critique", compute="_compute_posture")
    cultiveau_cours = fields.Selection(COURS, "Cours de ses cultures", compute="_compute_posture",
                                       help="En baisse dès qu'une de ses cultures l'est : la prudence l'emporte.")
    cultiveau_cours_ton = fields.Char("Le ton", compute="_compute_posture")

    @api.depends("cultiveau_culture_ids.surface_ha")
    def _compute_surface(self):
        for p in self:
            p.cultiveau_surface_ha = sum(p.cultiveau_culture_ids.mapped("surface_ha"))

    @api.depends("cultiveau_culture_ids", "cultiveau_culture_ids.departement", "departement")
    def _compute_frise(self):
        mois_actuel = fields.Date.context_today(self).month
        for p in self:
            lignes = [dict(cc.culture_id.ligne_frise(cc.departement), cc=cc) for cc in p.cultiveau_culture_ids]
            p.cultiveau_fenetres = " · ".join(
                f"{l['culture'].name} : projet {libelle_mois(l['projet'])}, achat {libelle_mois(l['achat'])}" for l in lignes)
            p.cultiveau_frise_html = self._rendre_frise(lignes, mois_actuel) if lignes else Markup(
                "<p class='text-muted'>Aucune culture renseignée : ajoutez les cultures de l'exploitation dans l'onglet.</p>")

    def cultiveau_situation(self, mois=None):
        """La situation du mois pour l'Agent : posture combinée, cultures critiques, cours, stades.

        {"mois", "posture", "critique", "critiques": [noms], "stades": [(culture, stade, posture)], "cours", "ton"}
        """
        self.ensure_one()
        mois = mois or fields.Date.context_today(self).month
        postures, critiques, stades = set(), [], []
        for cc in self.cultiveau_culture_ids:
            posture, critique, stade = cc.posture_du_mois(mois)
            postures.add(posture)
            stades.append((cc.culture_id.name, stade.name if stade else "hors cycle", posture))
            if critique:
                critiques.append(f"{cc.culture_id.name} ({stade.name.lower()})" if stade else cc.culture_id.name)
        tendances = set(self.cultiveau_culture_ids.mapped("culture_id.cours_tendance"))
        cours = "baisse" if "baisse" in tendances else "hausse" if "hausse" in tendances else "stable"
        return {"mois": MOIS[mois - 1][1], "numero_mois": mois, "posture": combiner_postures(postures, bool(critiques)),
                "critique": bool(critiques), "critiques": critiques, "stades": stades, "cours": cours, "ton": TON_COURS[cours]}

    @api.depends("cultiveau_culture_ids", "cultiveau_culture_ids.departement", "cultiveau_culture_ids.culture_id.cours_tendance")
    def _compute_posture(self):
        for p in self:
            if not p.cultiveau_culture_ids:
                p.cultiveau_posture = False
                p.cultiveau_posture_detail = "Pas de culture renseignée : la posture du mois ne peut pas être déduite."
                p.cultiveau_periode_critique = False
                p.cultiveau_cours = False
                p.cultiveau_cours_ton = ""
                continue
            s = p.cultiveau_situation()
            p.cultiveau_posture = s["posture"]
            p.cultiveau_periode_critique = s["critique"]
            p.cultiveau_cours = s["cours"]
            p.cultiveau_cours_ton = s["ton"]
            if s["critique"]:
                p.cultiveau_posture_detail = f"Période critique : {', '.join(s['critiques'])}. {POSTURE_INFOS['discret']['consigne']}"
            else:
                detail = ", ".join(f"{c} en {st.lower()}" for c, st, _ in s["stades"])
                p.cultiveau_posture_detail = f"{detail}. {POSTURE_INFOS[s['posture']]['consigne']}"

    @api.model
    def _rendre_frise(self, lignes, mois_actuel):
        tete = "".join(f"<th style='text-align:center;padding:4px;font-weight:{'700' if m == mois_actuel else '500'};"
                       f"color:{'#1d3a52' if m == mois_actuel else '#5d6b78'}'>{MOIS_COURTS[m - 1]}</th>" for m in range(1, 13))
        corps = []
        postures_mois = [set() for _ in range(12)]
        critiques_mois = [False] * 12
        for l in lignes:
            c, cc = l["culture"], l["cc"]
            cases = []
            for case in l["cases"]:
                s = case["stade"]
                posture = POSTURE_INFOS[case["posture"]]
                titre = (f"{s.name} ({s.periode}) — Kc {s.kc_min:g}–{s.kc_max:g}, besoin {s.besoin_min}–{s.besoin_max} % ETP, "
                         f"ETP {s.etp_min:g}–{s.etp_max:g} mm/j. Irrigation : {s.irrigation or '—'}. ") if s else "Hors cycle. "
                titre += f"Posture : {posture['saison'].lower()}, {dict(POSTURES)[case['posture']].lower()}" + (" — période critique, ne pas déranger." if case["critique"] else ".")
                postures_mois[case["mois"] - 1].add(case["posture"])
                critiques_mois[case["mois"] - 1] = critiques_mois[case["mois"] - 1] or case["critique"]
                marques = ("<span style='position:absolute;left:3px;top:1px;font-size:10px;font-weight:700;color:#1d3a52'>P</span>" if case["projet"] else "") + \
                          ("<span style='position:absolute;right:3px;top:1px;font-size:10px;font-weight:700;color:#8a5e3c'>A</span>" if case["achat"] else "") + \
                          ("<span style='position:absolute;left:0;right:0;bottom:0;text-align:center;font-size:10px;color:#b23a3a'>✖</span>" if case["critique"] else "")
                bord = "outline:2px solid #1d3a52;outline-offset:-2px;" if case["mois"] == mois_actuel else ""
                cases.append(f"<td title=\"{escape(titre)}\" style='position:relative;height:30px;background:{FOND[case['intensite']]};"
                             f"border:1px solid #fff;{bord}'>{marques}</td>")
            surface = f" · {cc.surface_ha:g} ha" if cc.surface_ha else ""
            cours = {"hausse": " ▲", "baisse": " ▼"}.get(c.cours_tendance, "")
            corps.append(f"<tr><th style='text-align:left;padding:4px 8px;white-space:nowrap;border-left:6px solid {escape(c.couleur or '#2a7f8f')}'>"
                         f"{escape(c.name)}<span style='font-weight:400;color:#5d6b78'>{surface}{cours}</span></th>{''.join(cases)}"
                         f"<td style='padding:4px 8px;white-space:nowrap;font-size:12px'>Projet <b>{libelle_mois(l['projet'])}</b> · Achat <b>{libelle_mois(l['achat'])}</b></td></tr>")
        # La ligne des postures : la saison émotionnelle du client, mois par mois, toutes cultures confondues.
        ligne_postures = []
        for i in range(12):
            p = combiner_postures(postures_mois[i], critiques_mois[i])
            info = POSTURE_INFOS[p]
            bord = "outline:2px solid #1d3a52;outline-offset:-2px;" if i + 1 == mois_actuel else ""
            ligne_postures.append(f"<td title=\"{escape(info['consigne'])}\" style='text-align:center;font-size:11px;background:{info['couleur']};border:1px solid #fff;padding:3px;{bord}'>"
                                  f"{info['icone']} {dict(POSTURES)[p]}</td>")
        corps.append(f"<tr><th style='text-align:left;padding:4px 8px;white-space:nowrap;color:#1d3a52'>Posture</th>{''.join(ligne_postures)}<td></td></tr>")
        legende = ("<p style='font-size:12px;color:#5d6b78;margin-top:6px'>Teinte = besoin en eau du stade (Kc). "
                   "<b>P</b> fenêtre projet (étude, conseil), <b>A</b> fenêtre achat (commande, livraison), <span style='color:#b23a3a'>✖</span> période critique (on ne dérange pas). "
                   "Posture : ❄ écoute, 🌱 support, ☀ discret, 🍂 proposition. ▲▼ cours de la culture. Survolez une case pour le stade.</p>")
        return Markup(f"<table style='border-collapse:collapse;width:100%;font-size:13px'><thead><tr><th></th>{tete}<th></th></tr></thead>"
                      f"<tbody>{''.join(corps)}</tbody></table>{legende}")

    def _compute_a_contacter(self):
        mois = fields.Date.context_today(self).month
        for p in self:
            p.cultiveau_a_contacter = any(cc.fenetres_du_mois(mois) for cc in p.cultiveau_culture_ids)

    def _search_a_contacter(self, operateur, valeur):
        mois = fields.Date.context_today(self).month
        ids = [p.id for p in self.env["cultiveau.culture.client"].partenaires_a_contacter(mois)]
        vrai = (operateur == "=" and valeur) or (operateur == "!=" and not valeur)
        return [("id", "in" if vrai else "not in", ids)]

    def action_frise_cultures(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "name": f"Cultures — {self.display_name}", "res_model": "cultiveau.culture.client",
                "view_mode": "list,form", "domain": [("partner_id", "=", self.id)], "context": {"default_partner_id": self.id}}

    def cultiveau_frise_pour_api(self, mois=None):
        """La frise résumée pour l'assistant : posture, période critique, cours, et le stade de chaque culture."""
        self.ensure_one()
        if not self.cultiveau_culture_ids:
            return None
        s = self.cultiveau_situation(mois)
        return {"mois": s["mois"], "posture": s["posture"], "posture_libelle": dict(POSTURES)[s["posture"]],
                "consigne": POSTURE_INFOS[s["posture"]]["consigne"], "periode_critique": s["critique"], "critiques": s["critiques"],
                "stades": [{"culture": c, "stade": st, "posture": p} for c, st, p in s["stades"]], "cours": s["cours"], "ton": s["ton"]}
