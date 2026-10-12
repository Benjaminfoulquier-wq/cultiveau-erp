"""Ce que le back-office dit à la map : chaque action métier écrit son événement (et la map bouge en moins d'une seconde)."""
from odoo import api, fields, models

CLOTURES = ("1_done", "1_canceled")


class Task(models.Model):
    _inherit = "project.task"

    def write(self, vals):
        avant = {t.id: t.state for t in self} if "state" in vals else {}
        res = super().write(vals)
        if "state" in vals:
            for t in self.filtered("cultiveau_intervention"):
                if avant.get(t.id) not in CLOTURES and t.state == "1_done":
                    self.env["cultiveau.evenement"].publier("intervention_terminee", t, "Intervention terminée", f"{t.name} — {t.partner_id.name or ''}",
                                                             {"task_id": t.id, "technicien_id": t.user_ids[:1].id, "kpi": "interventions"})
                elif avant.get(t.id) in CLOTURES and t.state not in CLOTURES:
                    self.env["cultiveau.evenement"].publier("etape", t, "Intervention rouverte", t.name, {"task_id": t.id})
        return res

    @api.model_create_multi
    def create(self, vals_list):
        taches = super().create(vals_list)
        for t in taches.filtered("cultiveau_intervention"):
            self.env["cultiveau.evenement"].publier("intervention_creee", t, "Nouvelle intervention", f"{t.name} — {t.partner_id.name or ''}",
                                                     {"task_id": t.id, "technicien_id": t.user_ids[:1].id, "kpi": "interventions"})
        return taches


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_confirm(self):
        res = super().action_confirm()
        for o in self:
            self.env["cultiveau.evenement"].publier("devis_signe", o, "Devis signé", f"{o.partner_id.name} accepte {o.name} : {round(o.amount_untaxed):,} € HT".replace(",", " "),
                                                     {"order_id": o.id, "partner_id": o.partner_id.id, "montant": o.amount_untaxed, "kpi": "devis",
                                                      "installation_id": o.cultiveau_installation_id.id if "cultiveau_installation_id" in o._fields else 0})
        return res

    def action_quotation_sent(self):
        res = super().action_quotation_sent()
        for o in self:
            self.env["cultiveau.evenement"].publier("devis_envoye", o, "Devis envoyé", f"{o.name} envoyé à {o.partner_id.name}", {"order_id": o.id, "kpi": "devis"})
        return res


class Picking(models.Model):
    _inherit = "stock.picking"

    def _action_done(self):
        res = super()._action_done()
        for p in self:
            if p.picking_type_code == "incoming":
                self.env["cultiveau.evenement"].publier("livraison", p, "Livraison reçue", f"{p.partner_id.name or 'Fournisseur'} — {len(p.move_ids)} ligne(s)", {"picking_id": p.id, "vehicule": "fournisseur"})
            elif p.picking_type_code == "outgoing":
                self.env["cultiveau.evenement"].publier("sortie_stock", p, "Sortie de stock", f"{p.name} — {p.partner_id.name or ''}", {"picking_id": p.id})
        return res


class Installation(models.Model):
    _inherit = "cultiveau.installation"

    def write(self, vals):
        avant = {i.id: i.etat for i in self} if "etat" in vals else {}
        res = super().write(vals)
        if "etat" in vals:
            etats = dict(self._fields["etat"].selection)
            for i in self:
                if avant.get(i.id) != i.etat:
                    genre = "mise_en_service" if i.etat == "en_service" else ("chantier_demarre" if i.etat == "realisation" else "etape")
                    self.env["cultiveau.evenement"].publier(genre, i, etats.get(i.etat, "Étape"), f"{i.name} — {i.partner_id.name}", {"installation_id": i.id, "etat": i.etat, "kpi": "chantiers"})
        return res


class Move(models.Model):
    _inherit = "account.move"

    def _compute_payment_state(self):
        avant = {m.id: m.payment_state for m in self}
        res = super()._compute_payment_state()
        for m in self:
            if m.move_type == "out_invoice" and m.state == "posted" and avant.get(m.id) not in ("paid", "in_payment") and m.payment_state in ("paid", "in_payment") and m.id:
                self.env["cultiveau.evenement"].publier("facture_payee", m, "Facture payée", f"{m.name} — {m.partner_id.name} : {round(m.amount_total):,} €".replace(",", " "),
                                                         {"move_id": m.id, "partner_id": m.partner_id.id})
        return res


class Users(models.Model):
    _inherit = "res.users"

    cultiveau_role = fields.Char("Rôle sur la map", compute="_compute_cultiveau_role")

    def _compute_cultiveau_role(self):
        Map = self.env["cultiveau.map"]
        for u in self:
            u.cultiveau_role = Map._role(u)
