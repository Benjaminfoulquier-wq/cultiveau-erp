"""Le devis simple : le stock sur chaque ligne, des phases dans le devis, et le chantier qui les reprend."""
from datetime import timedelta

from markupsafe import Markup, escape

from odoo import Command, api, fields, models


class Ligne(models.Model):
    _inherit = "sale.order.line"

    cultiveau_phase = fields.Boolean("Phase de chantier", help="Une section qui est une phase du chantier : ses jours, son jalon, son matériel dessous.")
    cultiveau_jours = fields.Float("Jours prévus", digits=(5, 1), help="Durée prévue de la phase sur le chantier (jours ouvrés, équipe complète).")
    cultiveau_jalon_pct = fields.Float("Jalon (% du devis)", digits=(5, 1), help="Facturé à la fin de la phase (facture d'acompte) ; le solde à la mise en service.")
    cultiveau_dispo = fields.Float("Disponible", compute="_compute_dispo", digits="Product Unit of Measure", help="En stock aujourd'hui, hors ce que d'autres commandes réservent.")
    cultiveau_manque = fields.Float("Manque", compute="_compute_dispo", digits="Product Unit of Measure")

    @api.depends("product_id", "product_uom_qty", "order_id.warehouse_id", "order_id.state")
    def _compute_dispo(self):
        for l in self:
            p = l.product_id
            if not p or l.display_type or not p.is_storable:
                l.cultiveau_dispo, l.cultiveau_manque = 0.0, 0.0
                continue
            wh = l.order_id.warehouse_id
            pp = p.with_company(l.order_id.company_id).with_context(warehouse_id=wh.id, warehouse=wh.id) if wh else p.with_company(l.order_id.company_id)
            deja = max(0.0, pp.outgoing_qty - (l.product_uom_qty if l.order_id.state in ("sale", "done") else 0.0))
            dispo = max(0.0, pp.qty_available - deja)
            l.cultiveau_dispo = dispo
            l.cultiveau_manque = max(0.0, l.product_uom_qty - dispo)


class Order(models.Model):
    _inherit = "sale.order"

    cultiveau_nb_phases = fields.Integer("Phases", compute="_compute_phases_apercu")
    cultiveau_phases_apercu = fields.Html("Phases du chantier", compute="_compute_phases_apercu", sanitize=False)

    def cultiveau_phases(self):
        """Les phases du devis : [{ligne, nom, jours, jalon, lignes (articles sous la phase), heures}] dans l'ordre."""
        self.ensure_one()
        phases, courante = [], None
        for l in self.order_line.sorted(lambda l: (l.sequence, l.id)):
            if l.display_type == "line_section":
                if l.cultiveau_phase:
                    courante = {"ligne": l, "nom": l.name, "jours": l.cultiveau_jours, "jalon": l.cultiveau_jalon_pct, "lignes": self.env["sale.order.line"], "heures": 0.0}
                    phases.append(courante)
                elif not l.cultiveau_sous_lot:
                    courante = None  # un lot ordinaire ferme la phase
                continue
            if courante is None or l.display_type or not l.product_id:
                continue
            courante["lignes"] |= l
            if l.product_id.type == "service" and l.product_uom and "hour" in (l.product_uom.name or "").lower() + (l.product_uom.category_id.name or "").lower():
                courante["heures"] += l.product_uom_qty
            elif l.product_id.type == "service" and "heure" in (l.name or "").lower():
                courante["heures"] += l.product_uom_qty
        return phases

    @api.depends("order_line.cultiveau_phase", "order_line.cultiveau_jours", "order_line.cultiveau_jalon_pct", "order_line.name", "order_line.sequence", "order_line.product_uom_qty", "order_line.product_id")
    def _compute_phases_apercu(self):
        for o in self:
            phases = o.cultiveau_phases()
            o.cultiveau_nb_phases = len(phases)
            if not phases:
                o.cultiveau_phases_apercu = Markup("<p class='text-muted mb-0'>Pas de phase dans ce devis : « Ajouter une phase » sous les lignes. Sans phase, le chantier prend les quatre phases type.</p>")
                continue
            total_j = sum(p["jours"] for p in phases)
            total_pct = sum(p["jalon"] for p in phases)
            lignes = "".join(f"<tr><td>{i + 1}</td><td>{escape(p['nom'])}</td><td class='text-end'>{p['jours']:g} j</td><td class='text-end'>{p['jalon']:g} %</td>"
                             f"<td class='text-end'>{len(p['lignes'].filtered(lambda l: l.product_id.is_storable))} art.</td><td class='text-end'>{p['heures']:g} h</td></tr>" for i, p in enumerate(phases))
            o.cultiveau_phases_apercu = Markup(f"<table class='table table-sm mb-1'><thead><tr><th></th><th>Phase</th><th class='text-end'>Jours</th><th class='text-end'>Jalon</th><th class='text-end'>Matériel</th><th class='text-end'>Pose</th></tr></thead>"
                                               f"<tbody>{lignes}</tbody><tfoot><tr class='fw-bold'><td></td><td>Total</td><td class='text-end'>{total_j:g} j</td><td class='text-end'>{total_pct:g} %</td><td></td><td></td></tr></tfoot></table>"
                                               f"<p class='small text-muted mb-0'>À la confirmation, le chantier reprend ces phases, leur matériel et leurs jalons ; l'acompte du devis s'ajoute aux jalons, le solde part à la mise en service.</p>")

    def action_depuis_mon_stock(self):
        """Le catalogue, filtré sur ce que l'adhérent a en stock."""
        self.ensure_one()
        action = self.action_add_from_catalog()
        ctx = dict(action.get("context") or {})
        ctx.update({"search_default_real_stock_available": 1, "cultiveau_depuis_stock": True})
        action["context"] = ctx
        action["name"] = "Depuis mon stock"
        return action

    def action_lancer_chantier(self):
        res = super().action_lancer_chantier()
        chantier = self.cultiveau_chantier_ids.sorted("id")[-1:] if self.cultiveau_chantier_ids else None
        if chantier:
            self._cultiveau_phases_vers_chantier(chantier)
        return res

    def _cultiveau_phases_vers_chantier(self, chantier):
        """Les phases du devis deviennent celles du chantier : ordre, jours (dates à la suite), jalon, matériel rattaché, heures prévues."""
        self.ensure_one()
        phases = self.cultiveau_phases()
        if not phases:
            return False
        chantier.phase_ids.unlink()
        debut = chantier.date_debut or (self.commitment_date.date() if self.commitment_date else False)
        commandes, curseur = [], debut
        for i, p in enumerate(phases):
            vals = {"name": p["nom"], "sequence": (i + 1) * 10, "jalon_pct": p["jalon"], "heures_prevues": p["heures"]}
            if curseur and p["jours"]:
                fin = curseur + timedelta(days=max(0, round(p["jours"]) - 1))
                vals.update({"date_debut": curseur, "date_fin": fin})
                curseur = fin + timedelta(days=1)
            commandes.append(Command.create(vals))
        chantier.write({"phase_ids": commandes})
        if curseur and debut:
            chantier.date_fin = curseur - timedelta(days=1)
        par_nom = {ph.name: ph for ph in chantier.phase_ids}
        for p in phases:
            ph = par_nom.get(p["nom"])
            for l in p["lignes"].filtered(lambda l: l.product_id.is_storable):
                for cl in chantier.ligne_ids.filtered(lambda cl: cl.product_id == l.product_id and not cl.phase_id):
                    cl.phase_id = ph
        chantier.message_post(body=f"Phases reprises du devis {self.name} : " + ", ".join(f"{p['nom']} ({p['jours']:g} j, jalon {p['jalon']:g} %)" for p in phases) + ".")
        return True
