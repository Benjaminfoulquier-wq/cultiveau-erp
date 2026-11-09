"""Les prix du marché : une base de données de relevés par article (sites internet, réseau, saisie), et un calculateur de
positionnement qui la lit pour conseiller un prix. L'outil ne touche jamais aux prix de vente ni à la grille : il informe,
l'adhérent décide. Les prix relevés sont ramenés en HT pour être comparés au prix d'achat et au prix catalogue."""

import json

from odoo import api, fields, models
from odoo.exceptions import UserError


def mediane(valeurs):
    v = sorted(x for x in valeurs if x)
    if not v:
        return 0.0
    n = len(v)
    m = n // 2
    return v[m] if n % 2 else (v[m - 1] + v[m]) / 2.0


class PrixMarche(models.Model):
    _name = "cultiveau.prix.marche"
    _description = "Prix du marché relevé pour un article"
    _order = "product_tmpl_id, date_releve desc, id desc"

    product_tmpl_id = fields.Many2one("product.template", "Article", required=True, ondelete="cascade", index=True)
    origine = fields.Selection([("web", "Site internet"), ("reseau", "Réseau Cultiveau"), ("manuel", "Saisie / devis concurrent")],
                               "Origine", required=True, default="manuel")
    source = fields.Char("Source", help="Le site ou l'enseigne où le prix a été relevé.")
    url = fields.Char("Lien")
    prix = fields.Float("Prix relevé", digits="Product Price", required=True)
    ttc = fields.Boolean("Prix TTC", default=True, help="Les prix en ligne grand public sont souvent TTC ; décochez pour un prix HT.")
    taux_tva = fields.Float("TVA (%)", default=20.0)
    prix_ht = fields.Float("Prix HT", compute="_compute_prix_ht", store=True, digits="Product Price")
    unite = fields.Char("Unité")
    date_releve = fields.Date("Relevé le", required=True, default=fields.Date.context_today, index=True)
    note = fields.Char("Remarque")
    a_valider = fields.Boolean("À valider", default=False, index=True,
                               help="Relevé trouvé par un benchmark et pas encore vérifié. Les relevés à valider ne comptent pas dans le calcul tant que vous ne les avez pas acceptés.")
    company_id = fields.Many2one("res.company", "Société", help="Vide : relevé partagé par le réseau.", index=True)

    @api.depends("prix", "ttc", "taux_tva")
    def _compute_prix_ht(self):
        for r in self:
            r.prix_ht = r.prix / (1 + (r.taux_tva or 0.0) / 100.0) if r.ttc and r.taux_tva else r.prix

    def action_valider(self):
        self.write({"a_valider": False})

    @api.model
    def _article_pour(self, ref=None, ean=None, nom=None):
        """Retrouve l'article Cultiveau d'un relevé : par code-barres, puis référence interne, puis désignation exacte."""
        Produit = self.env["product.template"].sudo()
        if ean:
            p = Produit.search([("barcode", "=", str(ean).strip())], limit=1)
            if p:
                return p
        if ref:
            p = Produit.search([("default_code", "=ilike", str(ref).strip())], limit=1)
            if p:
                return p
        if nom:
            p = Produit.search([("name", "=ilike", str(nom).strip())], limit=1)
            if p:
                return p
        return Produit.browse()

    @api.model
    def ingerer(self, releves, origine="web", a_valider=True, company_id=False):
        """Charge une liste de relevés trouvés par un benchmark. Chaque relevé : {article_id | ref | ean | nom, source, url, prix,
        ttc, tva, date, unite, note}. L'article est retrouvé, jamais inventé ; un prix sans article reconnu est laissé de côté et signalé.
        Ne touche à aucun prix de vente. Renvoie {crees, ignores, inconnus:[...]}."""
        crees, inconnus = 0, []
        for r in releves or []:
            if not r.get("prix"):
                continue
            produit = self.env["product.template"].sudo().browse(r["article_id"]).exists() if r.get("article_id") else \
                self._article_pour(r.get("ref"), r.get("ean"), r.get("nom"))
            if not produit:
                inconnus.append(r.get("nom") or r.get("ref") or r.get("ean") or "?")
                continue
            vals = {"product_tmpl_id": produit.id, "origine": origine, "source": (r.get("source") or "")[:255], "url": (r.get("url") or "")[:1024],
                    "prix": float(r["prix"]), "ttc": bool(r.get("ttc", True)), "taux_tva": float(r.get("tva", 20.0)),
                    "unite": (r.get("unite") or "")[:16], "note": (r.get("note") or "")[:255], "a_valider": a_valider, "company_id": company_id or False}
            if r.get("date"):
                vals["date_releve"] = r["date"]
            self.create(vals)
            crees += 1
        return {"crees": crees, "ignores": len(inconnus), "inconnus": inconnus[:30]}


class Product(models.Model):
    _inherit = "product.template"

    cultiveau_marche_ids = fields.One2many("cultiveau.prix.marche", "product_tmpl_id", "Prix du marché")
    cultiveau_marche_nb = fields.Integer("Relevés de prix", compute="_compute_marche")
    cultiveau_marche_median = fields.Float("Marché médian HT", compute="_compute_marche", digits="Product Price")

    @api.depends("cultiveau_marche_ids.prix_ht", "cultiveau_marche_ids.a_valider")
    def _compute_marche(self):
        for p in self:
            prix = p.cultiveau_marche_ids.filtered(lambda r: not r.a_valider).mapped("prix_ht")
            p.cultiveau_marche_nb = len(prix)
            p.cultiveau_marche_median = mediane(prix)

    def action_cultiveau_marche(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "name": "Prix du marché", "res_model": "cultiveau.prix.marche", "view_mode": "list,form",
                "domain": [("product_tmpl_id", "=", self.id)], "context": {"default_product_tmpl_id": self.id}}


class Benchmark(models.TransientModel):
    _name = "cultiveau.benchmark"
    _description = "Benchmark des prix sur internet (prépare la recherche, ingère les relevés)"

    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)
    perimetre = fields.Selection([("sans", "Les articles sans relevé"), ("famille", "Une famille"), ("selection", "Une sélection d'articles")],
                                 "Sur quoi", required=True, default="sans")
    categ_id = fields.Many2one("product.category", "Famille")
    product_ids = fields.Many2many("product.template", string="Articles")
    limite = fields.Integer("Nombre d'articles au maximum", default=50)
    recherches = fields.Text("Recherches à lancer", readonly=True,
                             help="La liste des articles et des requêtes, au format JSON, à confier à un assistant qui a accès au web.")
    resultats_json = fields.Text("Résultats du benchmark (JSON)",
                                 help="Collez ici la liste des prix trouvés : [{\"article_id\": 12, \"source\": \"Site X\", \"url\": \"…\", \"prix\": 19.9, \"ttc\": true, \"tva\": 20, \"date\": \"2026-11-09\"}, …]")

    def _articles(self):
        self.ensure_one()
        company = self.company_id or self.env.company
        if self.perimetre == "selection":
            return self.product_ids
        if self.perimetre == "famille":
            if not self.categ_id:
                raise UserError("Choisissez la famille.")
            familles = self.env["product.category"].search([("id", "child_of", self.categ_id.id)])
            domaine = [("categ_id", "in", familles.ids), ("sale_ok", "=", True)]
        else:
            domaine = [("sale_ok", "=", True), ("cultiveau_marche_ids", "=", False)]
        domaine += ["|", ("company_id", "=", False), ("company_id", "=", company.id)]
        return self.env["product.template"].with_company(company).search(domaine, limit=self.limite or 50)

    def action_preparer(self):
        self.ensure_one()
        articles = self._articles()
        if not articles:
            raise UserError("Aucun article à benchmarker avec ce choix.")
        lignes = []
        for p in articles:
            termes = " ".join(x for x in [p.name, p.default_code or "", p.barcode or ""] if x).strip()
            lignes.append({"article_id": p.id, "ref": p.default_code or None, "ean": p.barcode or None, "nom": p.name,
                           "requete": f"{termes} prix"})
        self.recherches = json.dumps(lignes, ensure_ascii=False, indent=2)
        return {"type": "ir.actions.act_window", "res_model": "cultiveau.benchmark", "res_id": self.id, "view_mode": "form", "target": "new",
                "name": "Benchmark des prix"}

    def action_ingerer(self):
        self.ensure_one()
        if not self.resultats_json:
            raise UserError("Collez d'abord les résultats du benchmark dans la case prévue.")
        try:
            releves = json.loads(self.resultats_json)
        except (ValueError, TypeError) as e:
            raise UserError(f"Le texte collé n'est pas du JSON valide : {e}.") from e
        if not isinstance(releves, list):
            raise UserError("Les résultats doivent être une liste JSON de relevés.")
        res = self.env["cultiveau.prix.marche"].ingerer(releves, origine="web", a_valider=True, company_id=self.company_id.id)
        message = f"{res['crees']} relevé(s) ajouté(s), à valider dans « Prix du marché »."
        if res["inconnus"]:
            message += f" {res['ignores']} laissé(s) de côté (article non reconnu) : {', '.join(res['inconnus'][:8])}."
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"title": "Benchmark ingéré", "message": message, "type": "success", "sticky": bool(res["inconnus"]),
                           "next": {"type": "ir.actions.act_window", "res_model": "cultiveau.prix.marche", "view_mode": "list,form",
                                    "domain": [("a_valider", "=", True)], "name": "Prix du marché à valider"}}}


class Positionnement(models.TransientModel):
    _name = "cultiveau.positionnement"
    _description = "Calculateur de positionnement prix (indicatif)"

    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)
    currency_id = fields.Many2one(related="company_id.currency_id")
    perimetre = fields.Selection([("releves", "Les articles qui ont des relevés"), ("famille", "Une famille"), ("article", "Un article")],
                                 "Sur quoi", required=True, default="releves")
    categ_id = fields.Many2one("product.category", "Famille")
    product_tmpl_id = fields.Many2one("product.template", "Article")
    marge_cible = fields.Float("Marge visée (%)", digits=(5, 1), default=lambda self: self.env.company.cultiveau_marge_pct or 30.0)
    mois_fraicheur = fields.Integer("Ne garder que les relevés de moins de (mois)", default=12)
    ligne_ids = fields.One2many("cultiveau.positionnement.ligne", "positionnement_id", "Positionnement")

    def _articles(self):
        self.ensure_one()
        company = self.company_id or self.env.company
        Marche = self.env["cultiveau.prix.marche"]
        if self.perimetre == "article":
            if not self.product_tmpl_id:
                raise UserError("Choisissez l'article.")
            return self.product_tmpl_id
        if self.perimetre == "famille":
            if not self.categ_id:
                raise UserError("Choisissez la famille.")
            familles = self.env["product.category"].search([("id", "child_of", self.categ_id.id)])
            domaine = [("categ_id", "in", familles.ids), ("cultiveau_marche_ids", "!=", False)]
        else:
            domaine = [("cultiveau_marche_ids", "!=", False)]
        return self.env["product.template"].with_company(company).search(domaine)

    def action_calculer(self):
        self.ensure_one()
        self.ligne_ids.unlink()
        company = self.company_id or self.env.company
        limite = fields.Date.subtract(fields.Date.context_today(self), months=self.mois_fraicheur) if self.mois_fraicheur else False
        valeurs = []
        for p in self._articles().with_company(company):
            releves = p.cultiveau_marche_ids.filtered(lambda r: not r.a_valider and (not limite or r.date_releve >= limite))
            prix_marche = releves.mapped("prix_ht")
            if not prix_marche:
                continue
            med = mediane(prix_marche)
            achat = p.standard_price or 0.0
            vente = p.list_price or 0.0
            marge_actuelle = (vente - achat) / vente * 100.0 if vente else 0.0
            # prix conseillé indicatif : la marge visée sur le prix d'achat, sans dépasser la médiane du marché
            voulu = achat / (1 - self.marge_cible / 100.0) if self.marge_cible < 100 and achat else vente
            conseille = min(voulu, med) if med and voulu else (med or voulu)
            if conseille and conseille < achat:
                conseille = voulu  # ne jamais conseiller en dessous du prix d'achat
            ecart = (vente - med) / med * 100.0 if med and vente else 0.0
            if not vente or not med:
                position = "a_regarder"
            elif vente > med * 1.05:
                position = "cher"
            elif vente < med * 0.95:
                position = "bas"
            else:
                position = "marche"
            valeurs.append({"positionnement_id": self.id, "product_tmpl_id": p.id, "nb": len(prix_marche),
                            "prix_achat": achat, "prix_vente": vente, "marche_min": min(prix_marche), "marche_median": med,
                            "marche_max": max(prix_marche), "marge_actuelle": marge_actuelle, "prix_conseille": round(conseille, 2) if conseille else 0.0,
                            "ecart_marche": ecart, "position": position})
        valeurs.sort(key=lambda v: v["ecart_marche"], reverse=True)
        self.env["cultiveau.positionnement.ligne"].create(valeurs)
        return {"type": "ir.actions.act_window", "res_model": "cultiveau.positionnement", "res_id": self.id, "view_mode": "form",
                "target": "new", "name": "Positionnement prix"}


class PositionnementLigne(models.TransientModel):
    _name = "cultiveau.positionnement.ligne"
    _description = "Positionnement d'un article face au marché"
    _order = "ecart_marche desc"

    positionnement_id = fields.Many2one("cultiveau.positionnement", required=True, ondelete="cascade")
    currency_id = fields.Many2one(related="positionnement_id.currency_id")
    product_tmpl_id = fields.Many2one("product.template", "Article")
    nb = fields.Integer("Relevés")
    prix_achat = fields.Monetary("Prix d'achat")
    prix_vente = fields.Monetary("Mon prix de vente")
    marche_min = fields.Monetary("Marché min")
    marche_median = fields.Monetary("Marché médian")
    marche_max = fields.Monetary("Marché max")
    marge_actuelle = fields.Float("Ma marge (%)", digits=(5, 1))
    ecart_marche = fields.Float("Écart au marché (%)", digits=(5, 1))
    prix_conseille = fields.Monetary("Prix conseillé")
    position = fields.Selection([("cher", "Au-dessus du marché"), ("marche", "Dans le marché"), ("bas", "En dessous du marché"), ("a_regarder", "À regarder")], "Position")
