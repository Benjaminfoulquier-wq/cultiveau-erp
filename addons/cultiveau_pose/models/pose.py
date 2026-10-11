"""La matrice de pose : chaque geste a son temps ; le devis la lit, le chantier la corrige."""

import re
import unicodedata

from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.exceptions import UserError

COEFFICIENTS = {"cultiveau_terrain_caillouteux": ("terrain caillouteux ou argileux", 1.3), "cultiveau_terrain_pente": ("forte pente", 1.2),
                "cultiveau_terrain_acces": ("accès difficile", 1.15), "cultiveau_terrain_hiver": ("pose en hiver ou par temps humide", 1.1)}
UNITES = [("unite", "par unité posée"), ("metre", "par mètre"), ("forfait", "forfait par article")]


def _plat(texte):
    return re.sub(r"[^a-z0-9]+", " ", unicodedata.normalize("NFKD", texte or "").encode("ascii", "ignore").decode().lower()).strip()


class Geste(models.Model):
    _name = "cultiveau.geste"
    _description = "Geste de pose"
    _order = "company_id, sequence, name"

    name = fields.Char("Geste", required=True)
    company_id = fields.Many2one("res.company", "Société", default=lambda self: self.env.company, index=True, help="Vide : la matrice proposée par le réseau.")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    unite = fields.Selection(UNITES, "Compté", default="unite", required=True)
    minutes = fields.Float("Minutes", digits=(8, 1), required=True, help="Pour une unité, un mètre ou l'article entier, à une personne.")
    personnes = fields.Float("Personnes", digits=(3, 1), default=1.0, help="Deux personnes sur un geste de 20 minutes : 40 minutes de main-d'œuvre.")
    categ_ids = fields.Many2many("product.category", string="Familles d'articles", help="Les articles de ces familles (et sous-familles) déclenchent ce geste.")
    mots = fields.Char("Mots-clés", help="Dans le nom de l'article, séparés par des virgules : « asperseur, turbine ». Un mot précédé de − exclut.")
    minutes_constatees = fields.Float("Minutes constatées", digits=(8, 1), compute="_compute_constatees")
    nb_retours = fields.Integer("Chantiers", compute="_compute_constatees")
    retour_ids = fields.One2many("cultiveau.geste.retour", "geste_id", "Retours des chantiers")
    note = fields.Char("Remarque")

    @api.depends("retour_ids.reel_min", "retour_ids.quantite")
    def _compute_constatees(self):
        for g in self:
            retours = g.retour_ids.filtered(lambda r: r.quantite > 0)
            total_qte = sum(retours.mapped("quantite"))
            g.nb_retours = len(retours.chantier_id)
            g.minutes_constatees = (sum(retours.mapped("reel_min")) / total_qte) if total_qte else 0.0

    def _correspond(self, produit):
        self.ensure_one()
        categs = produit.categ_id
        c = produit.categ_id
        while c.parent_id:
            c = c.parent_id
            categs |= c
        if self.categ_ids and (self.categ_ids & categs):
            return True
        nom = _plat(produit.name)
        mots = [m.strip() for m in (self.mots or "").split(",") if m.strip()]

        def present(m):  # un mot entier ; au-delà de deux lettres, le début d'un mot suffit (« tube » trouve « tubes »)
            m = _plat(m)
            return bool(m) and bool(re.search(r"\b" + re.escape(m) + (r"\b" if len(m) <= 2 else ""), nom))
        if any(m.startswith("-") and present(m[1:]) for m in mots):
            return False
        return any(not m.startswith("-") and present(m) for m in mots)

    @api.model
    def pour_produit(self, produit, societe):
        """Le geste de la société pour cet article, sinon celui du réseau ; rien pour un service ou un article sans geste."""
        if not produit or produit.type == "service":
            return self.browse()
        for domaine in ([("company_id", "=", societe.id)], [("company_id", "=", False)]):
            for g in self.search(domaine):
                if g._correspond(produit):
                    return g
        return self.browse()

    def action_adopter_constate(self):
        """Le temps constaté sur les chantiers devient le temps standard (dans la matrice de la société, copiée du réseau au besoin)."""
        for g in self:
            if not g.minutes_constatees:
                raise UserError(f"{g.name} : aucun chantier terminé n'a encore donné de temps constaté.")
            cible = g
            if not g.company_id:
                cible = g.copy({"company_id": self.env.company.id, "note": "Copié de la matrice réseau"})
            cible.minutes = round(g.minutes_constatees, 1)
        return True

    @api.model
    def copier_matrice_reseau(self, societe):
        noms = set(self.search([("company_id", "=", societe.id)]).mapped("name"))
        n = 0
        for g in self.search([("company_id", "=", False)]):
            if g.name not in noms:
                g.copy({"company_id": societe.id})
                n += 1
        return n


class Retour(models.Model):
    _name = "cultiveau.geste.retour"
    _description = "Temps constaté d'un geste sur un chantier"
    _order = "date desc"

    geste_id = fields.Many2one("cultiveau.geste", required=True, ondelete="cascade", index=True)
    chantier_id = fields.Many2one("cultiveau.chantier", required=True, ondelete="cascade")
    company_id = fields.Many2one(related="chantier_id.company_id", store=True)
    date = fields.Date(default=fields.Date.context_today)
    quantite = fields.Float("Quantité", digits=(10, 2))
    prevu_min = fields.Float("Prévu (min)", digits=(10, 1))
    reel_min = fields.Float("Constaté (min)", digits=(10, 1))
    ratio = fields.Float("Réel / prévu", digits=(4, 2))


class Company(models.Model):
    _inherit = "res.company"

    cultiveau_taux_horaire_vente = fields.Float("Main-d'œuvre facturée (€/h HT)", default=48.0)

    def cultiveau_produit_mo(self):
        self.ensure_one()
        Produit = self.env["product.product"].with_company(self)
        p = Produit.search([("default_code", "=", "MO-POSE"), ("company_id", "in", [self.id, False])], limit=1)
        if not p:
            p = Produit.create({"name": "Main-d'œuvre de pose", "default_code": "MO-POSE", "type": "service", "list_price": self.cultiveau_taux_horaire_vente, "sale_ok": True,
                               "purchase_ok": False, "company_id": self.id, "uom_id": self.env.ref("uom.product_uom_hour").id, "uom_po_id": self.env.ref("uom.product_uom_hour").id})
        return p


class SaleOrder(models.Model):
    _inherit = "sale.order"

    cultiveau_terrain_caillouteux = fields.Boolean("Terrain caillouteux / argileux")
    cultiveau_terrain_pente = fields.Boolean("Forte pente")
    cultiveau_terrain_acces = fields.Boolean("Accès difficile")
    cultiveau_terrain_hiver = fields.Boolean("Pose en hiver / temps humide")
    cultiveau_heures_pose = fields.Float("Heures de pose calculées", digits=(8, 2), readonly=True)
    cultiveau_detail_pose = fields.Html("Détail du calcul", readonly=True, sanitize=False)

    def cultiveau_coefficient(self):
        self.ensure_one()
        coef = 1.0
        for champ, (_libelle, valeur) in COEFFICIENTS.items():
            if self[champ]:
                coef *= valeur
        return coef

    def _cultiveau_gestes(self):
        """[(ligne, geste, quantité, minutes)] pour chaque ligne de matériel du devis qui a un geste."""
        self.ensure_one()
        Geste = self.env["cultiveau.geste"]
        resultat = []
        for l in self.order_line.filtered(lambda l: l.product_id and not l.display_type and not l.cultiveau_ligne_pose):
            g = Geste.pour_produit(l.product_id, self.company_id)
            if not g:
                continue
            qte = 1.0 if g.unite == "forfait" else l.product_uom_qty
            resultat.append((l, g, qte, qte * g.minutes * (g.personnes or 1.0)))
        return resultat

    def action_calculer_pose(self):
        """La main-d'œuvre d'après la nomenclature et la matrice : une ligne « Main-d'œuvre de pose » au taux de la société."""
        for o in self:
            gestes = o._cultiveau_gestes()
            coef = o.cultiveau_coefficient()
            minutes = sum(m for _l, _g, _q, m in gestes)
            heures = round(minutes / 60 * coef, 2)
            lignes = "".join(f"<tr><td>{escape(l.product_id.display_name)}</td><td>{escape(g.name)}</td><td class='text-end'>{q:g}</td><td class='text-end'>{g.minutes:g} × {g.personnes:g}</td>"
                             f"<td class='text-end'>{m / 60:.2f} h</td></tr>" for l, g, q, m in gestes)
            sans = [l.product_id.display_name for l in o.order_line.filtered(lambda l: l.product_id and not l.display_type and not l.cultiveau_ligne_pose and l.product_id.type != "service")
                    if l not in [x[0] for x in gestes]]
            coefs = [lib for champ, (lib, _v) in COEFFICIENTS.items() if o[champ]]
            detail = (f"<table class='table table-sm'><tr><th>Article</th><th>Geste</th><th class='text-end'>Quantité</th><th class='text-end'>min × pers.</th><th class='text-end'>Temps</th></tr>{lignes}"
                      f"<tr class='fw-bold'><td colspan='4'>Total ({minutes / 60:.2f} h) × coefficient {coef:.2f}" + (f" ({', '.join(coefs)})" if coefs else "") + f"</td><td class='text-end'>{heures:.2f} h</td></tr></table>")
            if sans:
                detail += "<p class='text-muted small'>Sans geste dans la matrice (à compléter si la pose compte) : " + escape(", ".join(sans[:20])) + "</p>"
            o.write({"cultiveau_heures_pose": heures, "cultiveau_detail_pose": Markup(detail)})
            if heures:
                produit = o.company_id.cultiveau_produit_mo()
                ligne = o.order_line.filtered("cultiveau_ligne_pose")[:1]
                valeurs = {"product_id": produit.id, "name": f"Main-d'œuvre de pose — {heures:g} h (matrice de pose" + (", " + ", ".join(coefs) if coefs else "") + ")",
                           "product_uom_qty": heures, "price_unit": o.company_id.cultiveau_taux_horaire_vente, "product_uom": produit.uom_id.id, "cultiveau_ligne_pose": True}
                if ligne:
                    ligne.write(valeurs)
                else:
                    valeurs["sequence"] = max(o.order_line.mapped("sequence") or [0]) + 1
                    o.order_line = [(0, 0, valeurs)]
        return True


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    cultiveau_ligne_pose = fields.Boolean("Ligne de main-d'œuvre calculée", copy=False)


class Chantier(models.Model):
    _inherit = "cultiveau.chantier"

    cultiveau_heures_devis = fields.Float(related="sale_order_id.cultiveau_heures_pose", string="Heures de pose au devis")
    cultiveau_ecart_pct = fields.Float("Écart au devis (%)", compute="_compute_ecart")
    cultiveau_retour_ids = fields.One2many("cultiveau.geste.retour", "chantier_id", "Retours à la matrice")

    @api.depends("heures_reelles", "sale_order_id.cultiveau_heures_pose")
    def _compute_ecart(self):
        for c in self:
            prevu = c.sale_order_id.cultiveau_heures_pose
            c.cultiveau_ecart_pct = ((c.heures_reelles - prevu) / prevu * 100) if prevu else 0.0

    def action_terminer(self):
        res = super().action_terminer()
        self.cultiveau_retour_matrice()
        return res

    def cultiveau_retour_matrice(self):
        """Le chantier fini nourrit la matrice : les heures pointées se répartissent sur les gestes du devis au prorata du prévu."""
        Retour = self.env["cultiveau.geste.retour"]
        for c in self:
            o = c.sale_order_id
            if not o or not o.cultiveau_heures_pose or not c.heures_reelles:
                continue
            gestes = o._cultiveau_gestes()
            prevu_total = sum(m for _l, _g, _q, m in gestes) * o.cultiveau_coefficient()
            if not prevu_total:
                continue
            ratio = c.heures_reelles * 60 / prevu_total
            c.cultiveau_retour_ids.unlink()
            Retour.create([{"geste_id": g.id, "chantier_id": c.id, "quantite": q, "prevu_min": m, "reel_min": m * ratio, "ratio": ratio} for _l, g, q, m in gestes])
            c.message_post(body=f"Matrice de pose : {c.heures_reelles:g} h pointées pour {o.cultiveau_heures_pose:g} h au devis (× {ratio:.2f}) ; {len(gestes)} geste(s) renseignés.")
        return True


class Settings(models.TransientModel):
    _inherit = "res.config.settings"

    cultiveau_taux_horaire_vente = fields.Float(related="company_id.cultiveau_taux_horaire_vente", readonly=False)

    def action_cultiveau_matrice(self):
        return {"type": "ir.actions.act_window", "name": "Ma matrice de pose", "res_model": "cultiveau.geste", "view_mode": "list,form",
                "domain": [("company_id", "=", self.company_id.id)], "context": {"default_company_id": self.company_id.id}, "target": "current"}

    def action_cultiveau_copier_matrice(self):
        n = self.env["cultiveau.geste"].copier_matrice_reseau(self.company_id)
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"title": "Matrice de pose", "message": f"{n} geste(s) copiés dans votre matrice : ajustez les temps avec vos techniciens.", "sticky": False,
                           "next": {"type": "ir.actions.client", "tag": "reload"}}}
