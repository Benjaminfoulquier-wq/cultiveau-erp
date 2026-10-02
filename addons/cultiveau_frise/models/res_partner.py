from markupsafe import Markup, escape

from odoo import api, fields, models

from .culture import MOIS_COURTS, libelle_mois

FOND = ["#f5f3ef", "#dceef1", "#b8dde3", "#7fc3cf", "#2a7f8f"]  # repos → pointe


class ResPartner(models.Model):
    _inherit = "res.partner"

    cultiveau_culture_ids = fields.One2many("cultiveau.culture.client", "partner_id", string="Cultures")
    cultiveau_surface_ha = fields.Float("Surface irriguée (ha)", compute="_compute_surface", digits=(8, 2))
    cultiveau_frise_html = fields.Html("Frise culturale", compute="_compute_frise", sanitize=False)
    cultiveau_fenetres = fields.Char("Fenêtres commerciales", compute="_compute_frise")
    cultiveau_a_contacter = fields.Boolean("À contacter ce mois-ci", compute="_compute_a_contacter", search="_search_a_contacter")

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

    @api.model
    def _rendre_frise(self, lignes, mois_actuel):
        tete = "".join(f"<th style='text-align:center;padding:4px;font-weight:{'700' if m == mois_actuel else '500'};"
                       f"color:{'#1d3a52' if m == mois_actuel else '#5d6b78'}'>{MOIS_COURTS[m - 1]}</th>" for m in range(1, 13))
        corps = []
        for l in lignes:
            c, cc = l["culture"], l["cc"]
            cases = []
            for case in l["cases"]:
                s = case["stade"]
                titre = (f"{s.name} ({s.periode}) — Kc {s.kc_min:g}–{s.kc_max:g}, besoin {s.besoin_min}–{s.besoin_max} % ETP, "
                         f"ETP {s.etp_min:g}–{s.etp_max:g} mm/j. Irrigation : {s.irrigation or '—'}") if s else "Hors cycle"
                marques = ("<span style='position:absolute;left:3px;top:1px;font-size:10px;font-weight:700;color:#1d3a52'>P</span>" if case["projet"] else "") + \
                          ("<span style='position:absolute;right:3px;top:1px;font-size:10px;font-weight:700;color:#8a5e3c'>A</span>" if case["achat"] else "")
                bord = "outline:2px solid #1d3a52;outline-offset:-2px;" if case["mois"] == mois_actuel else ""
                cases.append(f"<td title=\"{escape(titre)}\" style='position:relative;height:30px;background:{FOND[case['intensite']]};"
                             f"border:1px solid #fff;{bord}'>{marques}</td>")
            surface = f" · {cc.surface_ha:g} ha" if cc.surface_ha else ""
            corps.append(f"<tr><th style='text-align:left;padding:4px 8px;white-space:nowrap;border-left:6px solid {escape(c.couleur or '#2a7f8f')}'>"
                         f"{escape(c.name)}<span style='font-weight:400;color:#5d6b78'>{surface}</span></th>{''.join(cases)}"
                         f"<td style='padding:4px 8px;white-space:nowrap;font-size:12px'>Projet <b>{libelle_mois(l['projet'])}</b> · Achat <b>{libelle_mois(l['achat'])}</b></td></tr>")
        legende = ("<p style='font-size:12px;color:#5d6b78;margin-top:6px'>Teinte = besoin en eau du stade (Kc). "
                   "<b>P</b> fenêtre projet (étude, conseil), <b>A</b> fenêtre achat (commande, livraison). Survolez une case pour le stade.</p>")
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
