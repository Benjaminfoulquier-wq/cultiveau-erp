"""Le devis de l'adhérent : acompte, envoi en français, relances automatiques."""
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError


class Devis(models.Model):
    _inherit = "sale.order"

    cultiveau_acompte_pct = fields.Float("Acompte à la commande", default=lambda self: self.env.company.cultiveau_acompte_pct)
    cultiveau_acompte_montant = fields.Monetary("Acompte TTC", compute="_compute_acompte")
    cultiveau_acompte_facture = fields.Boolean("Acompte facturé", compute="_compute_acompte")
    cultiveau_envoye_le = fields.Date("Envoyé le", copy=False, readonly=True)
    cultiveau_relances = fields.Integer("Relances", copy=False, readonly=True)
    cultiveau_derniere_relance = fields.Date("Dernière relance", copy=False, readonly=True)

    @api.depends("amount_total", "cultiveau_acompte_pct", "order_line.is_downpayment")
    def _compute_acompte(self):
        for o in self:
            o.cultiveau_acompte_montant = o.currency_id.round(o.amount_total * (o.cultiveau_acompte_pct or 0) / 100)
            o.cultiveau_acompte_facture = any(o.order_line.filtered("is_downpayment").invoice_lines)

    def write(self, vals):
        res = super().write(vals)
        if vals.get("state") == "sent":
            self.filtered(lambda o: not o.cultiveau_envoye_le).write({"cultiveau_envoye_le": fields.Date.context_today(self)})
        return res

    def _find_mail_template(self):
        """Le devis part avec notre e-mail en français (la confirmation de commande garde le modèle standard)."""
        if self.state in ("draft", "sent") and not self.env.context.get("proforma"):
            modele = self.env.ref("cultiveau_documents.modele_mail_devis", raise_if_not_found=False)
            if modele:
                return modele
        return super()._find_mail_template()

    def action_facture_acompte(self):
        """La facture d'acompte au pourcentage prévu, sans ressaisie."""
        self.ensure_one()
        if not self.cultiveau_acompte_pct:
            raise UserError("Indiquez le pourcentage d'acompte sur le devis.")
        ctx = dict(self.env.context, active_model="sale.order", active_ids=self.ids, active_id=self.id,
                   default_advance_payment_method="percentage", default_amount=self.cultiveau_acompte_pct)
        return {"type": "ir.actions.act_window", "name": "Facture d'acompte", "res_model": "sale.advance.payment.inv", "view_mode": "form",
                "views": [(False, "form")], "target": "new", "context": ctx}

    def action_relancer(self):
        """Une relance à la main, même e-mail que le robot."""
        for o in self:
            o._relancer()

    def _relancer(self):
        self.ensure_one()
        modele = self.env.ref("cultiveau_documents.modele_mail_relance_devis")
        self.with_context(mark_so_as_sent=False).message_post_with_source(modele, subtype_xmlid="mail.mt_comment",
                                                                           email_layout_xmlid="mail.mail_notification_light")
        self.write({"cultiveau_relances": self.cultiveau_relances + 1, "cultiveau_derniere_relance": fields.Date.context_today(self)})

    @api.model
    def _cron_relancer_devis(self):
        aujourdhui = fields.Date.context_today(self)
        for societe in self.env["res.company"].sudo().search([("cultiveau_relances_devis", "=", True)]):
            limite = aujourdhui - timedelta(days=max(1, societe.cultiveau_relance_devis_jours))
            devis = self.with_company(societe).search([("company_id", "=", societe.id), ("state", "=", "sent"), ("partner_id.email", "!=", False),
                                                        "|", ("validity_date", "=", False), ("validity_date", ">=", aujourdhui)])
            for d in devis:
                repere = d.cultiveau_derniere_relance or d.cultiveau_envoye_le or d.date_order.date()
                if repere > limite:
                    continue
                if d.cultiveau_relances < societe.cultiveau_relance_devis_max:
                    d._relancer()
                elif not d.activity_ids.filtered(lambda a: a.summary and a.summary.startswith("Appeler")):
                    d.activity_schedule("mail.mail_activity_data_call", user_id=(d.user_id or self.env.user).id,
                                        summary=f"Appeler {d.partner_id.name} : devis {d.name} sans réponse après {d.cultiveau_relances} relance(s)")
                    d.write({"cultiveau_derniere_relance": aujourdhui})
