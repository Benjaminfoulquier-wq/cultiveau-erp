"""L'acompte du devis payé au portail : le pourcentage Cultiveau pilote le paiement en ligne d'Odoo, le virement est prêt pour
chaque société qui a un compte bancaire."""
from odoo import api, fields, models


class Societe(models.Model):
    _inherit = "res.company"

    cultiveau_acompte_en_ligne = fields.Boolean("Demander l'acompte en ligne à la signature du devis", default=True)
    cultiveau_virement_actif = fields.Boolean("Virement bancaire prêt", compute="_compute_virement")
    cultiveau_fournisseurs_actifs = fields.Char("Moyens de paiement en ligne", compute="_compute_virement")

    def _compute_virement(self):
        Prov = self.env["payment.provider"].sudo()
        for c in self:
            actifs = Prov.search([("company_id", "=", c.id), ("state", "in", ("enabled", "test"))])
            c.cultiveau_virement_actif = bool(actifs.filtered(lambda p: p.code == "custom" and p.custom_mode == "wire_transfer"))
            c.cultiveau_fournisseurs_actifs = ", ".join(actifs.mapped("name")) or "aucun"

    def write(self, vals):
        res = super().write(vals)
        if any(k in vals for k in ("cultiveau_acompte_pct", "cultiveau_acompte_en_ligne")):
            self._synchroniser_paiement_portail()
        return res

    def _synchroniser_paiement_portail(self):
        """Les réglages natifs du portail suivent les nôtres : signature, paiement, pourcentage."""
        for c in self:
            pct = (c.cultiveau_acompte_pct or 0.0) / 100.0
            if c.cultiveau_acompte_en_ligne and 0 < pct <= 1:
                super(Societe, c).write({"portal_confirmation_sign": True, "portal_confirmation_pay": True, "prepayment_percent": pct})
            else:
                super(Societe, c).write({"portal_confirmation_pay": False})

    def cultiveau_activer_paiement_en_ligne(self):
        """Pour chaque société : les réglages du portail, et le virement bancaire activé si elle a un compte bancaire (le RIB et le QR code viennent de là)."""
        Prov = self.env["payment.provider"].sudo()
        modele = Prov.search([("code", "=", "custom"), ("custom_mode", "=", "wire_transfer")], order="id", limit=1)
        for c in self:
            c._synchroniser_paiement_portail()
            if not c.bank_ids:
                continue
            virement = Prov.search([("company_id", "=", c.id), ("code", "=", "custom"), ("custom_mode", "=", "wire_transfer")], limit=1)
            if not virement and modele:
                virement = modele.copy({"company_id": c.id, "name": "Virement bancaire", "state": "disabled"})
            if virement and virement.name in ("Wire Transfer", "Virement"):
                virement.name = "Virement bancaire"
            if virement and virement.state == "disabled":
                try:
                    virement.write({"state": "enabled", "qr_code": True, "journal_id": self.env["account.journal"].sudo().search([("company_id", "=", c.id), ("type", "=", "bank")], limit=1).id or virement.journal_id.id})
                except Exception:  # noqa: BLE001 : un journal manquant ne doit pas bloquer l'installation
                    virement.write({"state": "enabled"})
        return True

    def action_fournisseurs_paiement(self):
        return {"type": "ir.actions.act_window", "name": "Fournisseurs de paiement", "res_model": "payment.provider", "view_mode": "kanban,list,form",
                "domain": [("company_id", "in", self.env.companies.ids)], "context": {"active_test": False}}


class Reglages(models.TransientModel):
    _inherit = "res.config.settings"

    cultiveau_acompte_en_ligne = fields.Boolean(related="company_id.cultiveau_acompte_en_ligne", readonly=False)
    cultiveau_virement_actif = fields.Boolean(related="company_id.cultiveau_virement_actif")
    cultiveau_fournisseurs_actifs = fields.Char(related="company_id.cultiveau_fournisseurs_actifs")

    def action_activer_virement(self):
        self.company_id.cultiveau_activer_paiement_en_ligne()
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_fournisseurs_paiement(self):
        return self.company_id.action_fournisseurs_paiement()


class Devis(models.Model):
    _inherit = "sale.order"

    cultiveau_acompte_en_ligne_texte = fields.Char("Paiement en ligne", compute="_compute_acompte_en_ligne_texte")

    @api.depends("cultiveau_acompte_pct", "company_id.cultiveau_acompte_en_ligne")
    def _compute_prepayment_percent(self):
        super()._compute_prepayment_percent()
        for o in self:
            if o.company_id.cultiveau_acompte_en_ligne and o.cultiveau_acompte_pct:
                o.prepayment_percent = min(1.0, max(0.0, o.cultiveau_acompte_pct / 100.0))

    @api.depends("require_payment", "prepayment_percent", "company_id.cultiveau_fournisseurs_actifs")
    def _compute_acompte_en_ligne_texte(self):
        for o in self:
            if o.require_payment and o.prepayment_percent:
                o.cultiveau_acompte_en_ligne_texte = f"Acompte de {o.prepayment_percent * 100:g} % demandé à la signature en ligne ({o.company_id.cultiveau_fournisseurs_actifs})."
            else:
                o.cultiveau_acompte_en_ligne_texte = ""

    def write(self, vals):
        res = super().write(vals)
        if "cultiveau_acompte_pct" in vals:
            for o in self.filtered(lambda o: o.company_id.cultiveau_acompte_en_ligne and o.state in ("draft", "sent")):
                pct = (o.cultiveau_acompte_pct or 0.0) / 100.0
                if 0 < pct <= 1 and o.prepayment_percent != pct:
                    super(Devis, o).write({"prepayment_percent": pct})
        return res
