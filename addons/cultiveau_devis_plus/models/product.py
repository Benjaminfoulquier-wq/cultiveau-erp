"""Ce que le référentiel dit d'un article : les avis « présence » dont les mots se retrouvent dans sa désignation, sa référence ou sa famille,
affichés sur la fiche de l'article (qu'il vienne du stock de l'adhérent, du réseau ou de la logistique)."""
from markupsafe import Markup, escape

from odoo import api, fields, models

from .avis import NIVEAUX, contient, mots, plat


class Produit(models.Model):
    _inherit = "product.template"

    cultiveau_referentiel_html = fields.Html("Ce que dit le référentiel", compute="_compute_referentiel", sanitize=False)
    cultiveau_nb_avis = fields.Integer("Avis du référentiel", compute="_compute_referentiel")

    def cultiveau_avis(self):
        """Les avis « présence » que cet article déclenche à lui seul."""
        self.ensure_one()
        corpus = plat(" ".join(filter(None, [self.name, self.default_code or "", self.categ_id.complete_name or "", self.description_sale or ""])))
        Avis = self.env["cultiveau.referentiel.avis"]
        return Avis.search([("genre", "=", "presence"), ("company_id", "in", [False, self.env.company.id])]).filtered(lambda a: contient(corpus, mots(a.mots_cles)))

    @api.depends("name", "default_code", "categ_id", "description_sale")
    def _compute_referentiel(self):
        for p in self:
            avis = p.cultiveau_avis() if p.name else self.env["cultiveau.referentiel.avis"]
            p.cultiveau_nb_avis = len(avis)
            if not avis:
                p.cultiveau_referentiel_html = False
                continue
            items = []
            for a in avis:
                niveau = dict(NIVEAUX)[a.niveau]
                items.append(Markup("<div class='cv-avis-article'><div class='cv-avis-titre'><b>%s</b> <span class='badge rounded-pill text-bg-light'>§ %s%s · %s</span></div><div>%s</div></div>") % (
                    escape(a.name), escape(a.section), escape(f", p. {a.page}" if a.page else ""), escape(niveau), escape(a.texte.strip())))
            p.cultiveau_referentiel_html = Markup("<div class='cv-avis-articles'>%s</div>") % Markup("").join(items)
