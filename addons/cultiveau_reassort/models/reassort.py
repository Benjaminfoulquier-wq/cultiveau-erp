"""Le réassort : ce que chaque article consomme, ce qu'il reste, ce qu'il faut ; les règles posées d'un clic, la commande d'un clic."""
import math
from datetime import timedelta

from odoo import Command, api, fields, models
from odoo.exceptions import UserError

MOIS_MIN, MOIS_MAX = 1.5, 3.0


class Reassort(models.TransientModel):
    _name = "cultiveau.reassort"
    _description = "Réassort du stock"

    name = fields.Char(default="Réassort du stock")
    company_id = fields.Many2one("res.company", "Société", required=True, default=lambda self: self.env.company)
    ligne_ids = fields.One2many("cultiveau.reassort.ligne", "reassort_id", "Articles")
    nb_sous_minimum = fields.Integer("Sous le minimum", compute="_compute_totaux")
    montant_a_commander = fields.Float("À commander (HT, prix d'achat)", compute="_compute_totaux")
    seulement_actifs = fields.Boolean("Seulement les articles qui bougent", default=True, help="Ceux consommés dans l'année ; décochez pour voir tout le stock.")

    @api.model
    def action_ouvrir(self):
        r = self.create({"company_id": self.env.company.id})
        r.action_recalculer()
        return {"type": "ir.actions.act_window", "res_model": self._name, "res_id": r.id, "view_mode": "form", "target": "current", "name": "Réassort du stock"}

    def _entrepot(self):
        return self.env["stock.warehouse"].search([("company_id", "=", self.company_id.id)], limit=1)

    def _consommation(self, produits):
        """Quantité sortie vers les clients (et la production) sur douze mois, par article."""
        depuis = fields.Datetime.now() - timedelta(days=365)
        grp = self.env["stock.move"].sudo()._read_group(
            [("company_id", "=", self.company_id.id), ("state", "=", "done"), ("date", ">=", depuis), ("product_id", "in", produits.ids),
             ("location_dest_id.usage", "in", ("customer", "production")), ("location_id.usage", "in", ("internal", "transit"))],
            ["product_id"], ["product_uom_qty:sum"])
        return {p.id: q for p, q in grp}

    def action_recalculer(self):
        self.ensure_one()
        wh = self._entrepot()
        if not wh:
            raise UserError("Aucun entrepôt pour cette société.")
        Produit = self.env["product.product"].with_company(self.company_id).with_context(warehouse_id=wh.id, warehouse=wh.id)
        produits = Produit.search([("is_storable", "=", True), ("company_id", "in", [self.company_id.id, False]), ("purchase_ok", "=", True)])
        conso = self._consommation(produits)
        regles = {op.product_id.id: op for op in self.env["stock.warehouse.orderpoint"].sudo().search([("company_id", "=", self.company_id.id), ("warehouse_id", "=", wh.id)])}
        lignes = []
        for p in produits:
            c12 = conso.get(p.id, 0.0)
            stock, arrive, reserve = p.qty_available, p.incoming_qty, p.outgoing_qty
            if self.seulement_actifs and c12 <= 0 and stock <= 0:
                continue
            par_mois = c12 / 12.0
            mini = math.ceil(par_mois * MOIS_MIN) if par_mois else 0
            maxi = math.ceil(par_mois * MOIS_MAX) if par_mois else 0
            op = regles.get(p.id)
            seller = p._select_seller(quantity=max(maxi, 1.0), uom_id=p.uom_id)
            disponible = stock + arrive - reserve
            seuil = op.product_min_qty if op else mini
            cible = op.product_max_qty if op else maxi
            a_commander = max(0.0, cible - disponible) if (seuil and disponible < seuil) else 0.0
            lignes.append(Command.create({
                "product_id": p.id, "conso_12m": c12, "conso_mois": round(par_mois, 1), "stock": stock, "arrive": arrive, "reserve": reserve,
                "couverture": round(disponible / par_mois, 1) if par_mois else 0.0, "mini_propose": mini, "maxi_propose": maxi,
                "mini_actuel": op.product_min_qty if op else 0.0, "maxi_actuel": op.product_max_qty if op else 0.0, "regle_id": op.id if op else False,
                "a_commander": math.ceil(a_commander), "fournisseur_id": seller.partner_id.id if seller else False, "prix": seller.price if seller else p.standard_price,
                "delai": seller.delay if seller else 0, "retenir": bool(par_mois)}))
        self.ligne_ids.unlink()
        self.ligne_ids = lignes
        return True

    @api.depends("ligne_ids.a_commander", "ligne_ids.prix")
    def _compute_totaux(self):
        for r in self:
            r.nb_sous_minimum = len(r.ligne_ids.filtered(lambda l: l.a_commander > 0))
            r.montant_a_commander = sum(l.a_commander * l.prix for l in r.ligne_ids)

    def action_poser_regles(self):
        """Les règles de réassort d'Odoo (minimum, maximum, déclenchement automatique) pour les lignes retenues."""
        self.ensure_one()
        wh = self._entrepot()
        Op = self.env["stock.warehouse.orderpoint"].sudo()
        n = 0
        for l in self.ligne_ids.filtered(lambda l: l.retenir and (l.mini_propose or l.maxi_propose)):
            vals = {"product_min_qty": l.mini_propose, "product_max_qty": max(l.maxi_propose, l.mini_propose), "trigger": "auto"}
            if l.regle_id:
                l.regle_id.write(vals)
            else:
                l.regle_id = Op.create({**vals, "product_id": l.product_id.id, "warehouse_id": wh.id, "location_id": wh.lot_stock_id.id, "company_id": self.company_id.id})
            l.write({"mini_actuel": l.mini_propose, "maxi_actuel": max(l.maxi_propose, l.mini_propose)})
            n += 1
        self.action_recalculer()
        return {"type": "ir.actions.client", "tag": "display_notification", "params": {"title": "Réassort", "message": f"{n} règle(s) posée(s) : Odoo recommandera seul dès qu'un article passe sous son minimum.", "type": "success", "sticky": False}}

    def action_commander(self):
        """Les articles sous le minimum : une demande de prix par fournisseur, tout de suite."""
        self.ensure_one()
        lignes = self.ligne_ids.filtered(lambda l: l.a_commander > 0 and l.fournisseur_id)
        if not lignes:
            raise UserError("Rien à commander : aucun article sous son minimum avec un fournisseur connu.")
        Achat = self.env["purchase.order"].with_company(self.company_id)
        par_fournisseur = {}
        for l in lignes:
            par_fournisseur.setdefault(l.fournisseur_id, []).append(l)
        crees = Achat
        for f, ls in par_fournisseur.items():
            po = Achat.create({"partner_id": f.id, "company_id": self.company_id.id, "origin": "Réassort",
                               "order_line": [(0, 0, {"product_id": l.product_id.id, "name": l.product_id.display_name, "product_qty": l.a_commander, "product_uom": l.product_id.uom_po_id.id or l.product_id.uom_id.id,
                                                      "price_unit": l.prix or l.product_id.standard_price, "date_planned": fields.Datetime.now() + timedelta(days=l.delai or 0)}) for l in ls]})
            crees |= po
        sans = self.ligne_ids.filtered(lambda l: l.a_commander > 0 and not l.fournisseur_id)
        self.action_recalculer()
        action = {"type": "ir.actions.act_window", "name": "Demandes de prix du réassort", "res_model": "purchase.order", "view_mode": "list,form", "domain": [("id", "in", crees.ids)]}
        if sans:
            action["name"] += f" ({len(sans)} article(s) sans fournisseur laissés de côté)"
        return action


class ReassortLigne(models.TransientModel):
    _name = "cultiveau.reassort.ligne"
    _description = "Article du réassort"
    _order = "a_commander desc, conso_12m desc, id"

    reassort_id = fields.Many2one("cultiveau.reassort", required=True, ondelete="cascade")
    product_id = fields.Many2one("product.product", "Article", required=True)
    retenir = fields.Boolean("Règle", default=True, help="Poser (ou mettre à jour) la règle de réassort pour cet article.")
    conso_12m = fields.Float("Sorti sur 12 mois", digits="Product Unit of Measure")
    conso_mois = fields.Float("Par mois", digits=(10, 1))
    stock = fields.Float("En stock", digits="Product Unit of Measure")
    arrive = fields.Float("Arrive", digits="Product Unit of Measure")
    reserve = fields.Float("Réservé", digits="Product Unit of Measure")
    couverture = fields.Float("Couverture (mois)", digits=(6, 1))
    mini_propose = fields.Float("Mini proposé", digits="Product Unit of Measure")
    maxi_propose = fields.Float("Maxi proposé", digits="Product Unit of Measure")
    mini_actuel = fields.Float("Mini actuel", digits="Product Unit of Measure")
    maxi_actuel = fields.Float("Maxi actuel", digits="Product Unit of Measure")
    regle_id = fields.Many2one("stock.warehouse.orderpoint", "Règle")
    a_commander = fields.Float("À commander", digits="Product Unit of Measure")
    fournisseur_id = fields.Many2one("res.partner", "Fournisseur", domain="[('is_company', '=', True)]")
    prix = fields.Float("Prix d'achat", digits="Product Price")
    delai = fields.Integer("Délai (j)")
