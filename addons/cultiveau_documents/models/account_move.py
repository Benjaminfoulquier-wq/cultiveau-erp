"""La facture de l'adhérent : e-mail en français, mentions légales, relances des impayés."""
from datetime import timedelta

from odoo import api, fields, models


class Facture(models.Model):
    _inherit = "account.move"

    cultiveau_relances = fields.Integer("Relances", copy=False, readonly=True)
    cultiveau_derniere_relance = fields.Date("Dernière relance", copy=False, readonly=True)
    cultiveau_jours_retard = fields.Integer("Jours de retard", compute="_compute_retard")

    @api.depends("invoice_date_due", "payment_state", "state")
    def _compute_retard(self):
        aujourdhui = fields.Date.context_today(self)
        for f in self:
            en_retard = f.state == "posted" and f.move_type == "out_invoice" and f.payment_state in ("not_paid", "partial") and f.invoice_date_due
            f.cultiveau_jours_retard = max(0, (aujourdhui - f.invoice_date_due).days) if en_retard else 0

    def _get_mail_template(self):
        if all(m.move_type == "out_invoice" for m in self):
            modele = self.env.ref("cultiveau_documents.modele_mail_facture", raise_if_not_found=False)
            if modele:
                return modele
        return super()._get_mail_template()

    def cultiveau_mentions_legales(self):
        """Les mentions obligatoires d'une facture française (hors particuliers)."""
        self.ensure_one()
        if self.move_type not in ("out_invoice", "out_refund") or (self.company_id.country_id and self.company_id.country_id.code != "FR"):
            return ""
        if self.partner_id.commercial_partner_id.cultiveau_type == "particulier":
            return ""  # entre professionnels seulement
        return ("En cas de retard de paiement, pénalités au taux de trois fois le taux d'intérêt légal et indemnité forfaitaire de 40 € pour frais "
                "de recouvrement (art. L. 441-10 du Code de commerce). Pas d'escompte pour paiement anticipé.")

    def action_relancer(self):
        for f in self:
            f._relancer()

    def _relancer(self):
        self.ensure_one()
        modele = self.env.ref("cultiveau_documents.modele_mail_relance_facture")
        self.message_post_with_source(modele, subtype_xmlid="mail.mt_comment", email_layout_xmlid="mail.mail_notification_light")
        self.write({"cultiveau_relances": self.cultiveau_relances + 1, "cultiveau_derniere_relance": fields.Date.context_today(self)})

    @api.model
    def _cron_relancer_factures(self):
        aujourdhui = fields.Date.context_today(self)
        for societe in self.env["res.company"].sudo().search([("cultiveau_relances_factures", "=", True)]):
            jours = max(1, societe.cultiveau_relance_facture_jours)
            factures = self.with_company(societe).search([("company_id", "=", societe.id), ("move_type", "=", "out_invoice"), ("state", "=", "posted"),
                                                           ("payment_state", "in", ("not_paid", "partial")), ("partner_id.email", "!=", False),
                                                           ("invoice_date_due", "<=", aujourdhui - timedelta(days=jours))])
            for f in factures:
                if f.cultiveau_derniere_relance and f.cultiveau_derniere_relance > aujourdhui - timedelta(days=jours):
                    continue
                if f.cultiveau_relances < societe.cultiveau_relance_facture_max:
                    f._relancer()
                elif not f.activity_ids.filtered(lambda a: a.summary and a.summary.startswith("Appeler")):
                    f.activity_schedule("mail.mail_activity_data_call", user_id=(f.invoice_user_id or self.env.user).id,
                                        summary=f"Appeler {f.partner_id.name} : facture {f.name} impayée, {f.cultiveau_jours_retard} jours de retard")
                    f.write({"cultiveau_derniere_relance": aujourdhui})
