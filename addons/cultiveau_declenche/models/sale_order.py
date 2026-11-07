"""Le devis déclenche tout : à la confirmation, le chantier, la facture d'acompte, les demandes de prix des manquants et la
mise en service se créent seuls (en brouillon), selon les réglages de la société. Le devis garde le fil de ce qui a été
déclenché et de ce qu'il reste à faire."""
from datetime import timedelta

from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    cultiveau_declenche_le = fields.Datetime("Déclenchements faits le", readonly=True, copy=False)
    cultiveau_purchase_ids = fields.One2many("purchase.order", "cultiveau_sale_order_id", string="Commandes fournisseurs")
    cultiveau_nb_achats = fields.Integer("Commandes fournisseurs", compute="_compute_achats")
    cultiveau_nb_manquants = fields.Integer("Articles manquants", compute="_compute_achats", help="Articles stockables du devis que le stock et les commandes en cours ne couvrent pas.")
    cultiveau_mise_en_service_id = fields.Many2one("project.task", "Mise en service", readonly=True, copy=False)
    cultiveau_declenchements = fields.Html("Après la signature", compute="_compute_declenchements", sanitize=False)

    # ---------------------------------------------------------------- les besoins
    def cultiveau_besoins(self):
        """Article par article (stockables, hors acompte et lignes de pose) : commandé, disponible, en commande fournisseur, manque."""
        self.ensure_one()
        wh = self.warehouse_id
        ctx = {"warehouse_id": wh.id, "warehouse": wh.id} if wh else {}
        besoins = {}
        for l in self.order_line:
            p = l.product_id
            if not p or l.display_type or l.is_downpayment or not p.is_storable:
                continue
            qte = l.product_uom._compute_quantity(l.product_uom_qty, p.uom_id) if l.product_uom and l.product_uom != p.uom_id else l.product_uom_qty
            if p.id in besoins:
                besoins[p.id]["qte"] += qte
                besoins[p.id]["lignes"] |= l
                continue
            pp = p.with_context(**ctx).with_company(self.company_id)
            besoins[p.id] = {"product": p, "qte": qte, "dispo": pp.qty_available, "reserve_ailleurs": pp.outgoing_qty, "en_commande": pp.incoming_qty, "lignes": l}
        resultat = []
        for b in besoins.values():
            # ce que le stock couvre : le disponible moins ce que d'autres commandes attendent déjà (hors celle-ci une fois confirmée)
            deja_sortant = b["reserve_ailleurs"] - (b["qte"] if self.state in ("sale", "done") else 0.0)
            couvert = max(0.0, b["dispo"] - max(0.0, deja_sortant)) + max(0.0, b["en_commande"])
            b["manque"] = max(0.0, b["qte"] - couvert)
            b["couvert_stock"] = max(0.0, b["dispo"] - max(0.0, deja_sortant))
            resultat.append(b)
        return resultat

    @api.depends("order_line.product_id", "order_line.product_uom_qty", "cultiveau_purchase_ids", "state")
    def _compute_achats(self):
        for o in self:
            o.cultiveau_nb_achats = len(o.cultiveau_purchase_ids)
            try:
                o.cultiveau_nb_manquants = len([b for b in o.cultiveau_besoins() if b["manque"] > 0]) if o.id else 0
            except Exception:  # noqa: BLE001
                o.cultiveau_nb_manquants = 0

    # ---------------------------------------------------------------- la confirmation
    def _cultiveau_est_projet(self):
        self.ensure_one()
        return bool(self.cultiveau_installation_id or self.cultiveau_type_systeme) and (self.origin or "") != "Comptoir"

    def action_confirm(self):
        res = super().action_confirm()
        for o in self.filtered(lambda o: o.state == "sale" and (o.origin or "") != "Comptoir"):
            try:
                o._cultiveau_declencher()
            except Exception as e:  # noqa: BLE001 : la confirmation ne doit jamais échouer à cause d'un déclenchement
                o.message_post(body=f"Les déclenchements de la confirmation n'ont pas pu se faire : {escape(str(e))}. Bouton « Relancer les déclenchements » après correction.")
        return res

    def action_declencher(self):
        """Le bouton : pour une commande confirmée avant le module, ou après avoir corrigé un réglage."""
        for o in self:
            if o.state not in ("sale", "done"):
                raise UserError("Les déclenchements se font sur une commande confirmée.")
            o._cultiveau_declencher()
        return True

    def _cultiveau_declencher(self):
        self.ensure_one()
        c = self.company_id
        faits, restes = [], []
        projet = self._cultiveau_est_projet()
        # 1. le chantier
        if c.cultiveau_decl_chantier and projet:
            if self.cultiveau_chantier_ids:
                restes.append("le chantier existait déjà")
            else:
                self.action_lancer_chantier()
                ch = self.cultiveau_chantier_ids[:1]
                if self.commitment_date and ch:
                    ch.date_debut = self.commitment_date.date()
                faits.append(Markup("chantier <a href='#' data-oe-model='cultiveau.chantier' data-oe-id='%s'>%s</a> créé, phases et matériel prévus") % (ch.id, escape(ch.display_name)))
        # 2. l'intervention de mise en service
        if c.cultiveau_decl_mise_en_service and projet and "cultiveau_nature" in self.env["project.task"]._fields:
            if self.cultiveau_mise_en_service_id:
                restes.append("la mise en service était déjà créée")
            else:
                projet_interv = self.env["project.project"].cultiveau_projet_interventions(c)
                inst = self.cultiveau_installation_id
                t = self.env["project.task"].with_company(c).create({
                    "name": f"Mise en service — {inst.name if inst else self.name}", "project_id": projet_interv.id, "partner_id": self.partner_id.id,
                    "cultiveau_installation_id": inst.id if inst else False, "cultiveau_nature": "mise_en_service", "sale_order_id": self.id if "sale_order_id" in self.env["project.task"]._fields else False,
                    "description": f"Mise en service de la commande {self.name} : rinçage, essais de pression, relevé des pressions et débits de référence (PV A1.3), fiche de réglage A1.5, formation de l'exploitant."})
                self.cultiveau_mise_en_service_id = t
                faits.append(Markup("intervention <a href='#' data-oe-model='project.task' data-oe-id='%s'>%s</a> à planifier") % (t.id, escape(t.name)))
        # 3. la facture d'acompte
        if c.cultiveau_decl_acompte and self.cultiveau_acompte_pct:
            if self.cultiveau_acompte_facture:
                restes.append("l'acompte était déjà facturé")
            else:
                try:
                    wiz = self.env["sale.advance.payment.inv"].with_context(active_model="sale.order", active_ids=self.ids, active_id=self.id).create({
                        "advance_payment_method": "percentage", "amount": self.cultiveau_acompte_pct})
                    factures = wiz._create_invoices(self)
                    f = factures[:1]
                    faits.append(Markup("facture d'acompte <a href='#' data-oe-model='account.move' data-oe-id='%s'>%s</a> (%s %%, %s € TTC) en brouillon")
                                 % (f.id, escape(f.name if f.name and f.name != "/" else "brouillon"), f"{self.cultiveau_acompte_pct:g}", f"{self.cultiveau_acompte_montant:,.0f}".replace(",", " ")))
                except Exception as e:  # noqa: BLE001
                    restes.append(f"facture d'acompte impossible ({escape(str(e))})")
        # 4. les demandes de prix des manquants
        if c.cultiveau_decl_achats:
            if self.cultiveau_purchase_ids:
                restes.append("des commandes fournisseurs existent déjà pour ce devis (voir Approvisionnement)")
            else:
                crees, sans = self._cultiveau_commander_manquants()
                if crees:
                    faits.append(Markup(", ".join("demande de prix <a href='#' data-oe-model='purchase.order' data-oe-id='%s'>%s</a> chez %s (%s article(s))"
                                                   % (po.id, escape(po.name), escape(po.partner_id.name), len(po.order_line)) for po in crees)))
                if sans:
                    restes.append("sans fournisseur connu, à commander à la main : " + ", ".join(escape(p.display_name) for p in sans[:12]) + (" …" if len(sans) > 12 else ""))
                if not crees and not sans:
                    faits.append("rien à commander : le stock couvre le devis")
        self.cultiveau_declenche_le = fields.Datetime.now()
        corps = Markup("<p><b>Devis confirmé, la chaîne est lancée.</b></p>")
        if faits:
            corps += Markup("<ul>") + Markup("").join(Markup("<li>%s</li>") % f for f in faits) + Markup("</ul>")
        if restes:
            corps += Markup("<p class='text-muted'>") + Markup(" · ").join(Markup("%s") % r for r in restes) + Markup("</p>")
        self.message_post(body=corps)
        return True

    def _cultiveau_commander_manquants(self, besoins=None, tout=False):
        """Une demande de prix brouillon par fournisseur pour les manquants (ou tout le devis) ; renvoie (commandes, articles sans fournisseur)."""
        self.ensure_one()
        Achat = self.env["purchase.order"].with_company(self.company_id)
        par_fournisseur, sans = {}, []
        for b in besoins if besoins is not None else self.cultiveau_besoins():
            qte = b.get("a_commander", b["qte"] if tout else b["manque"])
            if qte <= 0:
                continue
            p = b["product"]
            seller = b.get("seller") or p.with_company(self.company_id)._select_seller(quantity=qte, uom_id=p.uom_id)
            if not seller:
                sans.append(p)
                continue
            par_fournisseur.setdefault(seller.partner_id, []).append((p, qte, seller))
        crees = Achat
        for fournisseur, lignes in par_fournisseur.items():
            maintenant = fields.Datetime.now()
            po = Achat.create({
                "partner_id": fournisseur.id, "company_id": self.company_id.id, "origin": self.name, "cultiveau_sale_order_id": self.id,
                "order_line": [(0, 0, {"product_id": p.id, "name": p.display_name, "product_qty": qte, "product_uom": p.uom_po_id.id or p.uom_id.id,
                                       "price_unit": s.price if s.price else p.standard_price, "date_planned": maintenant + timedelta(days=s.delay or 0)}) for p, qte, s in lignes]})
            crees |= po
        return crees, sans

    # ---------------------------------------------------------------- l'écran
    @api.depends("state", "cultiveau_chantier_ids.etat", "picking_ids.state", "cultiveau_purchase_ids.state", "invoice_ids.payment_state", "cultiveau_mise_en_service_id.stage_id",
                 "cultiveau_acompte_pct", "cultiveau_declenche_le", "order_line.product_uom_qty")
    def _compute_declenchements(self):
        for o in self:
            if o.state in ("draft", "sent", "cancel"):
                o.cultiveau_declenchements = Markup("<p class='text-muted'>À la confirmation du devis, l'ERP crée le chantier, la facture d'acompte, les demandes de prix des manquants et "
                                                    "l'intervention de mise en service (selon Réglages › Cultiveau › Le devis déclenche tout). En attendant, « Approvisionnement » montre ce qui manque.</p>")
                continue
            lignes = []

            def ligne(titre, etat, detail="", ok=None):
                badge = "" if ok is None else ("<span class='badge text-bg-success me-1'>✓</span>" if ok else "<span class='badge text-bg-warning me-1'>à faire</span>")
                lignes.append(f"<tr><td class='fw-bold' style='width:28%'>{titre}</td><td>{badge}{etat}</td><td class='text-muted small'>{detail}</td></tr>")

            ch = o.cultiveau_chantier_ids
            if ch:
                etats = dict(ch._fields["etat"].selection)
                ligne("Chantier", " · ".join(f"<a href='#' data-oe-model='cultiveau.chantier' data-oe-id='{c.id}'>{escape(c.name)}</a> ({escape(etats.get(c.etat, c.etat))}, {c.avancement} %)" for c in ch),
                      "équipe et dates sur le chantier", ok=True)
            elif o._cultiveau_est_projet():
                ligne("Chantier", "pas encore créé", "bouton « Lancer le chantier » ou « Relancer les déclenchements »", ok=False)
            pk = o.picking_ids
            if pk:
                etats = dict(pk._fields["state"].selection)
                ligne("Sorties de stock", " · ".join(f"<a href='#' data-oe-model='stock.picking' data-oe-id='{p.id}'>{escape(p.name)}</a> ({escape(etats.get(p.state, p.state))})" for p in pk),
                      "le matériel réservé pour ce client", ok=all(p.state in ("done", "cancel") for p in pk))
            if o.cultiveau_acompte_pct:
                fa = o.invoice_ids.filtered(lambda f: f.move_type == "out_invoice" and any(f.invoice_line_ids.sale_line_ids.mapped("is_downpayment")))
                if fa:
                    payes = dict(fa._fields["payment_state"].selection)
                    ligne("Acompte", " · ".join(f"<a href='#' data-oe-model='account.move' data-oe-id='{f.id}'>{escape(f.name if f.name != '/' else 'brouillon')}</a> ({escape(payes.get(f.payment_state, f.payment_state))}, {escape(dict(f._fields['state'].selection).get(f.state, f.state))})" for f in fa),
                          f"{o.cultiveau_acompte_pct:g} % du devis", ok=any(f.payment_state in ("paid", "in_payment") for f in fa))
                else:
                    ligne("Acompte", "pas encore facturé", f"{o.cultiveau_acompte_pct:g} % du devis, bouton « Facture d'acompte »", ok=False)
            manquants = [b for b in o.cultiveau_besoins() if b["manque"] > 0]
            po = o.cultiveau_purchase_ids
            if po:
                etats = dict(po._fields["state"].selection)
                ligne("Achats", " · ".join(f"<a href='#' data-oe-model='purchase.order' data-oe-id='{p.id}'>{escape(p.name)}</a> {escape(p.partner_id.name)} ({escape(etats.get(p.state, p.state))})" for p in po),
                      (f"encore {len(manquants)} article(s) non couvert(s)" if manquants else "tout est couvert"), ok=all(p.state in ("purchase", "done") for p in po) and not manquants)
            elif manquants:
                ligne("Achats", f"{len(manquants)} article(s) manquent", "bouton « Approvisionnement »", ok=False)
            else:
                ligne("Achats", "rien à commander", "le stock couvre le devis", ok=True)
            t = o.cultiveau_mise_en_service_id
            if t:
                ligne("Mise en service", f"<a href='#' data-oe-model='project.task' data-oe-id='{t.id}'>{escape(t.name)}</a> ({escape(t.stage_id.name or '')})",
                      "PV A1.3, fiche de réglage A1.5, formation", ok=t.stage_id.fold)
            quand = f"<p class='small text-muted mb-0'>Déclenchements faits le {fields.Datetime.context_timestamp(o, o.cultiveau_declenche_le):%d/%m/%Y à %H:%M}.</p>" if o.cultiveau_declenche_le else \
                "<p class='small text-muted mb-0'>Commande confirmée avant la mise en place : « Relancer les déclenchements » crée ce qui manque.</p>"
            o.cultiveau_declenchements = Markup(f"<table class='table table-sm mb-2'><tbody>{''.join(lignes)}</tbody></table>{quand}")

    def action_approvisionnement(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "res_model": "cultiveau.approvisionnement", "view_mode": "form", "target": "new", "name": f"Approvisionnement — {self.name}",
                "context": {"default_order_id": self.id}}

    def action_voir_achats(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "name": f"Achats — {self.name}", "res_model": "purchase.order", "view_mode": "list,form",
                "domain": [("cultiveau_sale_order_id", "=", self.id)], "context": {"default_cultiveau_sale_order_id": self.id, "default_origin": self.name}}
