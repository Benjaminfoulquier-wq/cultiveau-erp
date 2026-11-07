"""Les jalons de facturation des phases, le solde, et la date de besoin du matériel."""
from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.exceptions import UserError

JALONS_DEFAUT = {"Préparation et implantation": 0.0, "Tranchées et pose des réseaux": 30.0, "Station de tête et raccordements": 30.0}


class Phase(models.Model):
    _inherit = "cultiveau.chantier.phase"

    jalon_pct = fields.Float("Jalon (% du devis)", digits=(5, 1), help="La part du devis facturée à la fin de cette phase. Le solde (tout ce qui reste) se facture à part.")
    jalon_invoice_id = fields.Many2one("account.move", "Facture du jalon", readonly=True, copy=False)
    jalon_etat = fields.Selection([("sans", "Sans jalon"), ("a_facturer", "À facturer"), ("facture", "Facturée"), ("payee", "Encaissée")], "Jalon", compute="_compute_jalon_etat")
    ligne_ids = fields.One2many("cultiveau.chantier.ligne", "phase_id", "Matériel de la phase")
    nb_lignes = fields.Integer("Articles", compute="_compute_nb_lignes")

    @api.depends("jalon_pct", "jalon_invoice_id.state", "jalon_invoice_id.payment_state", "etat")
    def _compute_jalon_etat(self):
        for p in self:
            if not p.jalon_pct:
                p.jalon_etat = "sans"
            elif not p.jalon_invoice_id or p.jalon_invoice_id.state == "cancel":
                p.jalon_etat = "a_facturer"
            elif p.jalon_invoice_id.payment_state in ("paid", "in_payment", "reversed"):
                p.jalon_etat = "payee"
            else:
                p.jalon_etat = "facture"

    @api.depends("ligne_ids")
    def _compute_nb_lignes(self):
        for p in self:
            p.nb_lignes = len(p.ligne_ids)

    def action_facturer_jalon(self):
        """La facture d'acompte du jalon : jalon_pct % du devis, déduite au solde."""
        for p in self:
            o = p.chantier_id.sale_order_id
            if not o or o.state not in ("sale", "done"):
                raise UserError("Le chantier n'a pas de commande confirmée : rien à facturer.")
            if not p.jalon_pct:
                raise UserError(f"La phase « {p.name} » n'a pas de jalon (% du devis).")
            if p.jalon_invoice_id and p.jalon_invoice_id.state != "cancel":
                raise UserError(f"Le jalon « {p.name} » est déjà facturé ({p.jalon_invoice_id.name}).")
            wiz = self.env["sale.advance.payment.inv"].with_context(active_model="sale.order", active_ids=o.ids, active_id=o.id).create({"advance_payment_method": "percentage", "amount": p.jalon_pct})
            factures = wiz._create_invoices(o)
            f = factures[:1]
            f.write({"narration": f"Situation de travaux : {p.name} ({p.jalon_pct:g} % du devis {o.name}), chantier {p.chantier_id.name}."})
            p.jalon_invoice_id = f
            p.chantier_id.message_post(body=Markup("Jalon « %s » facturé : <a href='#' data-oe-model='account.move' data-oe-id='%s'>%s</a> (%s %% du devis).")
                                       % (escape(p.name), f.id, escape(f.name if f.name != "/" else "brouillon"), f"{p.jalon_pct:g}"))
        if len(self) == 1 and self.jalon_invoice_id:
            return {"type": "ir.actions.act_window", "res_model": "account.move", "res_id": self.jalon_invoice_id.id, "view_mode": "form"}
        return True


class Ligne(models.Model):
    _inherit = "cultiveau.chantier.ligne"

    phase_id = fields.Many2one("cultiveau.chantier.phase", "Phase", domain="[('chantier_id', '=', chantier_id)]", index=True, ondelete="set null")
    besoin_le = fields.Date("Besoin le", related="phase_id.date_debut", store=True, help="Le début de la phase : la date de livraison demandée aux fournisseurs.")


class Chantier(models.Model):
    _inherit = "cultiveau.chantier"

    jalons_pct_total = fields.Float("Jalons (% total)", compute="_compute_plan_facturation")
    plan_facturation = fields.Html("Plan de facturation", compute="_compute_plan_facturation", sanitize=False)
    solde_invoice_id = fields.Many2one("account.move", "Facture de solde", readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        chantiers = super().create(vals_list)
        for c in chantiers:
            for ph in c.phase_ids.filtered(lambda ph: not ph.jalon_pct and ph.name in JALONS_DEFAUT):
                ph.jalon_pct = JALONS_DEFAUT[ph.name]
            c._rattacher_materiel()
        return chantiers

    def _rattacher_materiel(self):
        """Le matériel sans phase se rattache à la phase des réseaux (tubes, raccords) ou de la station (pompe, filtre, armoire) d'après son nom."""
        for c in self:
            phases = {ph.name: ph for ph in c.phase_ids}
            reseau = phases.get("Tranchées et pose des réseaux") or c.phase_ids[:1]
            station = phases.get("Station de tête et raccordements") or reseau
            mots_station = ("pompe", "filtre", "filtration", "armoire", "variateur", "clapet", "compteur", "manomètre", "anti-bélier", "programmateur", "électrovanne")
            for l in c.ligne_ids.filtered(lambda l: not l.phase_id):
                nom = (l.product_id.display_name or "").lower()
                l.phase_id = station if any(m in nom for m in mots_station) else reseau

    @api.depends("phase_ids.jalon_pct", "phase_ids.jalon_invoice_id.payment_state", "phase_ids.jalon_invoice_id.state", "sale_order_id.cultiveau_acompte_pct", "sale_order_id.invoice_ids.payment_state",
                 "sale_order_id.amount_total", "solde_invoice_id.state", "solde_invoice_id.payment_state")
    def _compute_plan_facturation(self):
        for c in self:
            o = c.sale_order_id
            c.jalons_pct_total = sum(c.phase_ids.mapped("jalon_pct"))
            if not o:
                c.plan_facturation = Markup("<p class='text-muted'>Reliez le chantier à sa commande pour établir le plan de facturation.</p>")
                continue
            acompte = o.cultiveau_acompte_pct if "cultiveau_acompte_pct" in o._fields else 0.0
            total = acompte + c.jalons_pct_total
            solde = max(0.0, 100.0 - total)
            eur = lambda v: f"{v:,.0f}".replace(",", " ") + " €"  # noqa: E731
            lignes = []
            fa = o.invoice_ids.filtered(lambda f: f.move_type == "out_invoice" and any(f.invoice_line_ids.sale_line_ids.mapped("is_downpayment")) and f.state != "cancel")
            acompte_f = fa[:1] if fa and not c.phase_ids.filtered(lambda ph: ph.jalon_invoice_id == fa[:1]) else self.env["account.move"]
            etats_p = {"paid": "encaissée", "in_payment": "en cours d'encaissement", "not_paid": "à encaisser", "partial": "partiellement encaissée", "reversed": "annulée"}

            def ligne(nom, pct, facture):
                montant = o.amount_total * pct / 100
                if facture and facture.state != "cancel":
                    etat = f"<a href='#' data-oe-model='account.move' data-oe-id='{facture.id}'>{escape(facture.name if facture.name != '/' else 'brouillon')}</a> · " + \
                           (escape(etats_p.get(facture.payment_state, facture.payment_state)) if facture.state == "posted" else "brouillon")
                    ok = facture.payment_state in ("paid", "in_payment")
                else:
                    etat, ok = "à facturer", None
                badge = "" if ok is None else ("<span class='badge text-bg-success me-1'>✓</span>" if ok else "<span class='badge text-bg-info me-1'>facturé</span>")
                lignes.append(f"<tr><td>{escape(nom)}</td><td class='text-end'>{pct:g} %</td><td class='text-end'>{eur(montant)}</td><td>{badge}{etat}</td></tr>")

            if acompte:
                ligne("Acompte à la commande", acompte, acompte_f)
            for ph in c.phase_ids.filtered("jalon_pct"):
                ligne(f"Fin de phase : {ph.name}", ph.jalon_pct, ph.jalon_invoice_id)
            ligne("Solde à la mise en service", solde, c.solde_invoice_id)
            avert = f"<p class='text-danger small mb-0'>Acompte et jalons font {total:g} % : au-delà de 100 %, réduisez un jalon.</p>" if total > 100 else ""
            c.plan_facturation = Markup(f"<table class='table table-sm mb-1'><thead><tr><th>Jalon</th><th class='text-end'>Part</th><th class='text-end'>TTC</th><th>État</th></tr></thead><tbody>{''.join(lignes)}</tbody></table>"
                                        f"<p class='small text-muted mb-0'>Devis {escape(o.name)} : {eur(o.amount_total)} TTC. Chaque jalon est une facture d'acompte ; le solde les déduit toutes.</p>{avert}")

    def action_facturer_solde(self):
        for c in self:
            o = c.sale_order_id
            if not o or o.state not in ("sale", "done"):
                raise UserError("Pas de commande confirmée.")
            if c.solde_invoice_id and c.solde_invoice_id.state != "cancel":
                raise UserError(f"Le solde est déjà facturé ({c.solde_invoice_id.name}).")
            factures = o._create_invoices(final=True)
            c.solde_invoice_id = factures[:1]
            c.message_post(body=Markup("Facture de solde créée : <a href='#' data-oe-model='account.move' data-oe-id='%s'>%s</a>.") % (factures[:1].id, escape(factures[:1].name if factures[:1].name != "/" else "brouillon")))
        if len(self) == 1 and self.solde_invoice_id:
            return {"type": "ir.actions.act_window", "res_model": "account.move", "res_id": self.solde_invoice_id.id, "view_mode": "form"}
        return True


class Approvisionnement(models.TransientModel):
    _inherit = "cultiveau.approvisionnement"

    @api.model
    def default_get(self, champs):
        valeurs = super().default_get(champs)
        order_id = valeurs.get("order_id") or self.env.context.get("default_order_id")
        if order_id and valeurs.get("ligne_ids"):
            order = self.env["sale.order"].browse(order_id)
            besoins = {}
            for l in order.cultiveau_chantier_ids.mapped("ligne_ids").filtered("besoin_le"):
                besoins[l.product_id.id] = min(besoins.get(l.product_id.id, l.besoin_le), l.besoin_le)
            for cmd in valeurs["ligne_ids"]:
                if len(cmd) == 3 and isinstance(cmd[2], dict) and cmd[2].get("product_id") in besoins:
                    cmd[2]["besoin_le"] = besoins[cmd[2]["product_id"]]
        return valeurs


class ApprovisionnementLigne(models.TransientModel):
    _inherit = "cultiveau.approvisionnement.ligne"

    besoin_le = fields.Date("Besoin le", help="Le début de la phase du chantier qui pose cet article : la date de livraison demandée au fournisseur.")
