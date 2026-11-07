"""Le chantier en un clic : la phase démarre et sort son matériel (sur la livraison de la commande, jamais deux fois), la phase se
termine et facture son jalon, la mise en service facture le solde et déclenche la suite."""
from datetime import timedelta

from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.exceptions import UserError


class Phase(models.Model):
    _inherit = "cultiveau.chantier.phase"

    picking_id = fields.Many2one("stock.picking", "Sortie de stock de la phase", readonly=True, copy=False)
    date_debut_reel = fields.Date("Démarrée le", readonly=True, copy=False)
    date_fin_reel = fields.Date("Terminée le", readonly=True, copy=False)

    def action_demarrer_phase(self):
        for p in self:
            if p.etat == "termine":
                raise UserError(f"La phase « {p.name} » est terminée.")
            c = p.chantier_id
            if c.etat in ("brouillon", "planifie"):
                c.action_demarrer()
            p.write({"etat": "en_cours", "date_debut_reel": fields.Date.context_today(p), "date_debut": p.date_debut or fields.Date.context_today(p)})
            sortie = c._sortir_materiel_pour(p.ligne_ids.filtered(lambda l: l.quantite_prevue > 0), p)
            if sortie:
                p.picking_id = sortie
            c.message_post(body=Markup("Phase « %s » démarrée%s.") % (escape(p.name), Markup(" : matériel sorti du stock (<a href='#' data-oe-model='stock.picking' data-oe-id='%s'>%s</a>)") % (sortie.id, escape(sortie.name)) if sortie else ""))
        return True

    def action_terminer_phase(self):
        for p in self:
            if p.etat == "termine":
                continue
            for l in p.ligne_ids.filtered(lambda l: not l.quantite_posee):
                l.quantite_posee = l.quantite_prevue
            p.write({"etat": "termine", "date_fin_reel": fields.Date.context_today(p), "date_fin": p.date_fin or fields.Date.context_today(p)})
            texte = f"Phase « {p.name} » terminée."
            if p.jalon_pct and p.chantier_id.sale_order_id and p.chantier_id.sale_order_id.state in ("sale", "done") and (not p.jalon_invoice_id or p.jalon_invoice_id.state == "cancel"):
                try:
                    p.action_facturer_jalon()
                    texte += f" Facture du jalon ({p.jalon_pct:g} %) préparée."
                except Exception as e:  # noqa: BLE001
                    texte += f" Facture du jalon impossible : {e}."
            suivante = p.chantier_id.phase_ids.filtered(lambda x: x.etat == "a_faire").sorted("sequence")[:1]
            if suivante:
                texte += f" Prochaine phase : {suivante.name}."
            p.chantier_id.message_post(body=texte)
        return True


class Chantier(models.Model):
    _inherit = "cultiveau.chantier"

    def _pickings_commande(self):
        """Les livraisons de la commande encore ouvertes : c'est là que le stock sort, pas ailleurs."""
        self.ensure_one()
        o = self.sale_order_id
        if not o:
            return self.env["stock.picking"]
        return o.picking_ids.filtered(lambda p: p.picking_type_code == "outgoing" and p.state not in ("done", "cancel")).sorted("id")

    def _sortir_materiel_pour(self, lignes, phase=None):
        """Sort du stock le matériel donné. Sur la livraison de la commande quand elle existe (le reste part en reliquat) ; sinon un bon de
        sortie propre au chantier. Renvoie la sortie validée, ou vide."""
        self.ensure_one()
        lignes = lignes.filtered(lambda l: l.product_id.is_storable and l.quantite_prevue > 0)
        if not lignes:
            return self.env["stock.picking"]
        voulu = {}
        for l in lignes:
            voulu[l.product_id] = voulu.get(l.product_id, 0.0) + l.quantite_prevue
        pickings = self._pickings_commande()
        if pickings:
            picking = pickings[0]
            picking.action_assign()
            touche = False
            for m in picking.move_ids.filtered(lambda m: m.state not in ("done", "cancel")):
                q = voulu.pop(m.product_id, 0.0)
                if q > 0:
                    m.quantity = min(q, m.product_uom_qty) if m.product_uom_qty else q
                    m.picked = True
                    touche = True
                else:
                    m.quantity = 0.0
                    m.picked = False
            if touche:
                picking.with_context(skip_backorder=True, skip_sms=True, skip_sanity_check=True).button_validate()
                self.picking_id = picking
                if voulu:
                    # ce qui n'était pas sur la commande (ajouté au chantier) sort par un bon propre
                    return picking | self._bon_de_sortie_propre(voulu, phase)
                return picking
        return self._bon_de_sortie_propre(voulu, phase)

    def _bon_de_sortie_propre(self, voulu, phase=None):
        if not voulu:
            return self.env["stock.picking"]
        entrepot = self.env["stock.warehouse"].search([("company_id", "=", self.company_id.id)], limit=1)
        if not entrepot:
            raise UserError("Aucun entrepôt pour cette société.")
        t = entrepot.out_type_id
        dest = self.partner_id.property_stock_customer
        picking = self.env["stock.picking"].create({
            "picking_type_id": t.id, "partner_id": self.partner_id.id, "origin": f"{self.name}" + (f" — {phase.name}" if phase else ""), "company_id": self.company_id.id,
            "location_id": t.default_location_src_id.id, "location_dest_id": dest.id,
            "move_ids": [(0, 0, {"name": p.display_name, "product_id": p.id, "product_uom_qty": q, "product_uom": p.uom_id.id, "location_id": t.default_location_src_id.id,
                                 "location_dest_id": dest.id, "company_id": self.company_id.id}) for p, q in voulu.items()]})
        picking.action_confirm()
        picking.action_assign()
        for m in picking.move_ids:
            m.quantity = m.product_uom_qty
            m.picked = True
        picking.with_context(skip_backorder=True, skip_sms=True, skip_sanity_check=True).button_validate()
        if not self.picking_id:
            self.picking_id = picking
        return picking

    def action_sortir_materiel(self):
        """Tout le matériel prévu en une fois (chantier sans phases, ou vieux réflexe) : par la livraison de la commande, jamais en double."""
        self.ensure_one()
        if self.picking_id and self.picking_id.state == "done" and not self._pickings_commande():
            return self.action_voir_picking()
        sortie = self._sortir_materiel_pour(self.ligne_ids, None)
        if not sortie:
            raise UserError("Ajoutez d'abord le matériel prévu.")
        self.message_post(body=Markup("Matériel sorti du stock : %s.") % Markup(", ").join(Markup("<a href='#' data-oe-model='stock.picking' data-oe-id='%s'>%s</a>") % (p.id, escape(p.name)) for p in sortie))
        return {"type": "ir.actions.act_window", "res_model": "stock.picking", "res_id": sortie[0].id, "view_mode": "form"}

    def action_mise_en_service(self):
        res = super().action_mise_en_service()
        for c in self:
            faits = []
            o = c.sale_order_id
            # 1. le solde
            if o and o.state in ("sale", "done") and not (c.solde_invoice_id and c.solde_invoice_id.state != "cancel"):
                try:
                    c.action_facturer_solde()
                    faits.append("facture de solde préparée")
                except Exception as e:  # noqa: BLE001
                    faits.append(f"facture de solde impossible ({e})")
            # 2. l'intervention de mise en service se clôt
            t = o.cultiveau_mise_en_service_id if o and "cultiveau_mise_en_service_id" in o._fields else None
            if t and t.state not in ("1_done", "1_canceled"):
                t.write({"state": "1_done"})
                faits.append("intervention de mise en service clôturée")
            # 3. le matériel non posé revient
            reste = c.ligne_ids.filtered(lambda l: l.quantite_prevue - l.quantite_posee > 0)
            if reste and c.picking_id and c.picking_id.state == "done" and not c.retour_picking_id:
                try:
                    c.action_retour_materiel()
                    faits.append(f"retour au dépôt de {len(reste)} article(s) non posé(s) préparé")
                except Exception:  # noqa: BLE001
                    pass
            # 4. l'entretien se propose
            qui = (o.user_id if o and o.user_id else c.chef_id) or self.env.user
            c.activity_schedule("cultiveau_crm_effort.act_visite_chantier", date_deadline=fields.Date.context_today(c) + timedelta(days=30), user_id=qui.id,
                                summary=f"Proposer le contrat d'entretien à {c.partner_id.name}", note="Un mois après la mise en service : passer voir, écouter, proposer l'entretien (hivernage, remise en service).")
            faits.append("visite d'après-vente et contrat d'entretien planifiés dans un mois")
            # 5. les phases restantes se terminent
            c.phase_ids.filtered(lambda p: p.etat != "termine").write({"etat": "termine", "date_fin_reel": fields.Date.context_today(c)})
            c.message_post(body="Mise en service, la suite est lancée : " + " ; ".join(faits) + ".")
        return res
