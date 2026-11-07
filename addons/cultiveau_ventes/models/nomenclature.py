"""Les nomenclatures : des ensembles d'articles prêts à insérer au devis (une tête de secteur, la protection d'une station, un point
haut, la mise en service et la réception…), à l'adhérent ou proposés par le réseau. Un devis se construit en posant des ensembles,
pas en cherchant trente références une à une ; et un lot bien fait d'un devis se garde comme nomenclature pour le suivant."""
from markupsafe import Markup, escape

from odoo import Command, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.cultiveau_installation.models.installation import TYPES

LOTS = [("station", "Station de pompage et énergie"), ("filtration", "Filtration et protection sanitaire"), ("reseau", "Réseau principal, vannes, raccords"),
        ("secteurs", "Secteurs : conduites, rampes, organes"), ("automatisme", "Automatisme et pilotage"), ("pose", "Pose, mise en service, réception"), ("autre", "Autre")]


class Nomenclature(models.Model):
    _name = "cultiveau.nomenclature"
    _description = "Nomenclature (ensemble d'articles prêt à insérer au devis)"
    _order = "lot, sequence, name"
    _check_company_auto = True

    name = fields.Char("Nomenclature", required=True, translate=False, help="Ex. « Tête de secteur goutte à goutte », « Protection de la station ».")
    code = fields.Char("Code", size=24)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", "Société", default=lambda self: self.env.company, index=True,
                                 help="Vide : une nomenclature proposée par le réseau, visible de tous les adhérents.")
    lot = fields.Selection(LOTS, "Lot du devis", default="autre", required=True, help="Le lot où cet ensemble prend place d'habitude.")
    type_systeme = fields.Selection(TYPES, "Type d'installation", help="Vide : tous les types.")
    unite = fields.Char("Compté", default="par ensemble", help="Ce que vaut une quantité de 1 : « par secteur », « par station », « par point haut ».")
    description = fields.Text("À quoi ça sert", help="Pour celui qui insère : quand l'employer, ce qu'il reste à adapter.")
    reference_referentiel = fields.Char("Référentiel", help="Les sections du référentiel V4 qui demandent ou décrivent cet ensemble : « § 15.3.1, § 8.3 ».")
    ligne_ids = fields.One2many("cultiveau.nomenclature.ligne", "nomenclature_id", "Articles", copy=True)
    nb_lignes = fields.Integer("Articles", compute="_compute_totaux")
    prix_catalogue = fields.Monetary("Prix catalogue (HT)", compute="_compute_totaux", currency_field="currency_id",
                                     help="La somme des prix de vente catalogue des articles pour une quantité de 1 ; le devis applique ensuite tarifs et remises.")
    currency_id = fields.Many2one("res.currency", compute="_compute_totaux")
    origine_order_id = fields.Many2one("sale.order", "Devis d'origine", readonly=True, help="Le devis dont ce lot a été enregistré.")
    nb_usages = fields.Integer("Insérée dans", compute="_compute_usages")

    @api.depends("ligne_ids.quantite", "ligne_ids.product_id.list_price", "ligne_ids.optionnel", "company_id")
    def _compute_totaux(self):
        for n in self:
            n.currency_id = (n.company_id or self.env.company).currency_id
            n.nb_lignes = len(n.ligne_ids)
            n.prix_catalogue = sum(l.quantite * l.product_id.list_price for l in n.ligne_ids if not l.optionnel)

    def _compute_usages(self):
        Ligne = self.env["sale.order.line"].sudo()
        for n in self:
            n.nb_usages = len(Ligne.read_group([("cultiveau_nomenclature_id", "=", n.id)], ["order_id"], ["order_id"]))

    def action_inserer(self):
        """Depuis la nomenclature : la poser dans un devis."""
        self.ensure_one()
        return {"type": "ir.actions.act_window", "res_model": "cultiveau.nomenclature.inserer", "view_mode": "form", "target": "new",
                "name": f"Insérer « {self.name} »", "context": {"default_nomenclature_id": self.id}}

    def action_devis(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "res_model": "sale.order", "view_mode": "list,form", "name": f"Devis avec « {self.name} »",
                "domain": [("order_line.cultiveau_nomenclature_id", "=", self.id)]}

    def lignes_devis(self, quantite=1.0, avec_optionnelles=False, sequence=0, titre=None, sous_lot=True):
        """Les commandes de création des lignes de devis pour cette nomenclature, multipliée par `quantite`."""
        self.ensure_one()
        commandes = []
        seq = sequence
        if titre:
            commandes.append(Command.create({"display_type": "line_section", "name": titre, "sequence": seq, "cultiveau_sous_lot": sous_lot,
                                             "cultiveau_nomenclature_id": self.id}))
        for l in self.ligne_ids:
            if l.optionnel and not avec_optionnelles:
                continue
            seq += 1
            qte = l.quantite * quantite if l.proportionnel else l.quantite
            valeurs = {"product_id": l.product_id.id, "product_uom_qty": qte, "sequence": seq, "cultiveau_nomenclature_id": self.id}
            if l.uom_id:
                valeurs["product_uom"] = l.uom_id.id
            if l.name and l.name != l.product_id.name:
                valeurs["name"] = l.name
            commandes.append(Command.create(valeurs))
            if l.note:
                seq += 1
                commandes.append(Command.create({"display_type": "line_note", "name": l.note, "sequence": seq, "cultiveau_nomenclature_id": self.id}))
        return commandes, seq


class NomenclatureLigne(models.Model):
    _name = "cultiveau.nomenclature.ligne"
    _description = "Article d'une nomenclature"
    _order = "nomenclature_id, sequence, id"

    nomenclature_id = fields.Many2one("cultiveau.nomenclature", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="nomenclature_id.company_id", store=True)
    sequence = fields.Integer(default=10)
    product_id = fields.Many2one("product.product", "Article", required=True, domain="[('sale_ok', '=', True), ('company_id', 'in', [company_id, False])]",
                                 check_company=False)
    name = fields.Char("Libellé au devis", compute="_compute_depuis_article", store=True, readonly=False, help="Vide : le nom de l'article.")
    quantite = fields.Float("Quantité", digits="Product Unit of Measure", default=1.0, required=True)
    uom_id = fields.Many2one("uom.uom", "Unité", compute="_compute_depuis_article", store=True, readonly=False)
    proportionnel = fields.Boolean("× la quantité insérée", default=True,
                                   help="Coché : 3 têtes de secteur = 3 vannes. Décoché : la quantité est fixe quel que soit le nombre d'ensembles (un compteur pour la station).")
    optionnel = fields.Boolean("En option", help="Proposé à l'insertion, pas posé d'office.")
    note = fields.Char("Note sous la ligne", help="Une consigne du référentiel ou un rappel : « finesse selon l'analyse d'eau (§ 5.4) ».")
    prix = fields.Float("Prix catalogue", related="product_id.list_price")

    @api.depends("product_id")
    def _compute_depuis_article(self):
        for l in self:
            if l.product_id:
                l.name = l.product_id.name
                l.uom_id = l.product_id.uom_id


def _devis_actif(self):
    ctx = self.env.context
    return ctx.get("active_id") if ctx.get("active_model") == "sale.order" else False


class Inserer(models.TransientModel):
    _name = "cultiveau.nomenclature.inserer"
    _description = "Insérer une nomenclature dans un devis"
    _devis_actif = _devis_actif

    order_id = fields.Many2one("sale.order", "Devis", required=True, default=lambda self: self._devis_actif())
    nomenclature_id = fields.Many2one("cultiveau.nomenclature", "Nomenclature", required=True,
                                      domain="[('company_id', 'in', [company_id, False]), '|', ('type_systeme', '=', False), ('type_systeme', '=', type_systeme)]")
    company_id = fields.Many2one(related="order_id.company_id")
    type_systeme = fields.Selection(related="order_id.cultiveau_type_systeme")
    quantite = fields.Float("Quantité d'ensembles", default=1.0, required=True, help="3 secteurs : 3. Les articles « × la quantité insérée » sont multipliés.")
    unite = fields.Char(related="nomenclature_id.unite")
    placement = fields.Selection([("sous_lot", "En sous-lot, à la suite du devis"), ("lot", "En nouveau lot"), ("lignes", "Lignes seules, à la suite")],
                                 "Placement", default="sous_lot", required=True)
    titre = fields.Char("Titre du lot ou du sous-lot", compute="_compute_titre", store=True, readonly=False)
    avec_optionnelles = fields.Boolean("Avec les lignes en option")
    apercu = fields.Html("Aperçu", compute="_compute_apercu", sanitize=False)

    @api.depends("nomenclature_id", "quantite")
    def _compute_titre(self):
        for w in self:
            if w.nomenclature_id:
                n = w.nomenclature_id
                w.titre = n.name if w.quantite in (0, 1) else f"{n.name} × {w.quantite:g}"

    @api.depends("nomenclature_id", "quantite", "avec_optionnelles")
    def _compute_apercu(self):
        for w in self:
            n = w.nomenclature_id
            if not n:
                w.apercu = ""
                continue
            lignes = []
            for l in n.ligne_ids:
                if l.optionnel and not w.avec_optionnelles:
                    continue
                qte = l.quantite * w.quantite if l.proportionnel else l.quantite
                prix = f"{l.prix:,.2f}".replace(",", " ").replace(".", ",")
                lignes.append(f"<tr><td>{escape(l.name or l.product_id.name)}{' <span class=\"text-muted\">(option)</span>' if l.optionnel else ''}</td>"
                              f"<td class='text-end'>{qte:g} {escape(l.uom_id.name or '')}</td><td class='text-end text-muted'>{prix} €</td></tr>")
            desc = f"<p class='text-muted small mb-2'>{escape(n.description)}</p>" if n.description else ""
            ref = f"<p class='small mb-2'>Référentiel : {escape(n.reference_referentiel)}</p>" if n.reference_referentiel else ""
            w.apercu = Markup(desc + ref + "<table class='table table-sm mb-0'><tr><th>Article</th><th class='text-end'>Quantité</th><th class='text-end'>Catalogue</th></tr>"
                              + "".join(lignes) + "</table><p class='small text-muted mt-2 mb-0'>Les prix du devis viennent des tarifs et remises de la société, pas du catalogue.</p>")

    def action_inserer(self):
        self.ensure_one()
        o = self.order_id
        if o.state not in ("draft", "sent"):
            raise UserError("Le devis n'est plus modifiable.")
        if not self.nomenclature_id.ligne_ids:
            raise UserError("Cette nomenclature n'a aucun article.")
        seq = max(o.order_line.mapped("sequence") or [0]) + 1
        commandes, _fin = self.nomenclature_id.lignes_devis(self.quantite, self.avec_optionnelles, seq, titre=self.titre if self.placement != "lignes" else None,
                                                             sous_lot=self.placement == "sous_lot")
        o.write({"order_line": commandes})
        o.message_post(body=f"Nomenclature « {self.nomenclature_id.name} » × {self.quantite:g} insérée ({len(commandes)} lignes).")
        return {"type": "ir.actions.client", "tag": "soft_reload"}


class Enregistrer(models.TransientModel):
    _name = "cultiveau.nomenclature.enregistrer"
    _description = "Enregistrer un lot du devis comme nomenclature"
    _devis_actif = _devis_actif

    order_id = fields.Many2one("sale.order", "Devis", required=True, default=lambda self: self._devis_actif())
    section_id = fields.Many2one("sale.order.line", "Lot ou sous-lot", required=True, domain="[('order_id', '=', order_id), ('display_type', '=', 'line_section')]")
    name = fields.Char("Nom de la nomenclature", compute="_compute_depuis_section", store=True, readonly=False, required=True, precompute=True)
    lot = fields.Selection(LOTS, "Lot du devis", default="autre", required=True)
    type_systeme = fields.Selection(TYPES, "Type d'installation", compute="_compute_depuis_section", store=True, readonly=False, precompute=True)
    unite = fields.Char("Compté", default="par ensemble")
    quantite_reference = fields.Float("Ces lignes valent", default=1.0, required=True,
                                      help="Le lot chiffre 3 secteurs : mettre 3, les quantités sont divisées pour revenir à l'ensemble unitaire.")
    reseau = fields.Boolean("Proposer à tout le réseau", help="Réservé à l'équipe Cultiveau : la nomenclature devient visible de tous les adhérents.")
    nb_lignes = fields.Integer("Lignes retenues", compute="_compute_nb_lignes")

    def _lignes(self):
        """Les lignes d'articles sous la section : jusqu'à la prochaine section du même niveau (un lot emporte ses sous-lots)."""
        self.ensure_one()
        s = self.section_id
        if not s:
            return self.env["sale.order.line"]
        lignes = self.order_id.order_line.sorted(lambda l: (l.sequence, l.id))
        resultat, dedans = self.env["sale.order.line"], False
        for l in lignes:
            if l == s:
                dedans = True
                continue
            if not dedans:
                continue
            if l.display_type == "line_section" and (s.cultiveau_sous_lot or not l.cultiveau_sous_lot):
                break
            if not l.display_type and l.product_id:
                resultat |= l
        return resultat

    @api.depends("section_id", "order_id")
    def _compute_depuis_section(self):
        for w in self:
            w.name = w.section_id.name or ""
            w.type_systeme = w.order_id.cultiveau_type_systeme

    @api.depends("section_id", "order_id")
    def _compute_nb_lignes(self):
        for w in self:
            w.nb_lignes = len(w._lignes())

    def action_enregistrer(self):
        self.ensure_one()
        lignes = self._lignes()
        if not lignes:
            raise UserError("Aucune ligne d'article sous ce lot.")
        if self.reseau and not self.env.user.has_group("cultiveau_base.group_equipe"):
            raise UserError("Seule l'équipe Cultiveau propose une nomenclature à tout le réseau.")
        diviseur = self.quantite_reference or 1.0
        n = self.env["cultiveau.nomenclature"].create({
            "name": self.name, "lot": self.lot, "type_systeme": self.type_systeme, "unite": self.unite, "origine_order_id": self.order_id.id,
            "company_id": False if self.reseau else self.order_id.company_id.id,
            "ligne_ids": [Command.create({"product_id": l.product_id.id, "name": l.name.split("\n")[0][:120] if l.name else l.product_id.name,
                                          "quantite": round(l.product_uom_qty / diviseur, 3), "uom_id": l.product_uom.id, "sequence": i * 10})
                          for i, l in enumerate(lignes)]})
        self.order_id.message_post(body=f"Lot « {self.section_id.name} » enregistré comme nomenclature « {n.name} » ({len(lignes)} articles).")
        return {"type": "ir.actions.act_window", "res_model": "cultiveau.nomenclature", "res_id": n.id, "view_mode": "form", "target": "current"}
