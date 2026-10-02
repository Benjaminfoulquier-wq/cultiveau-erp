from odoo import api, fields, models

from odoo.addons.cultiveau_installation.models.installation import TYPES


class SaleOrder(models.Model):
    _inherit = "sale.order"

    cultiveau_installation_id = fields.Many2one("cultiveau.installation", "Installation", tracking=True,
                                                domain="[('partner_id', 'child_of', partner_id)]")
    cultiveau_type_systeme = fields.Selection(TYPES, "Type d'installation", compute="_compute_type_systeme", store=True, readonly=False)
    cultiveau_surface_ha = fields.Float(related="cultiveau_installation_id.surface_ha")
    cultiveau_analyse_validee = fields.Boolean("Analyse des besoins validée", compute="_compute_cultiveau")
    cultiveau_dimensionnement = fields.Char("Dimensionnement", compute="_compute_cultiveau")

    @api.depends("cultiveau_installation_id")
    def _compute_type_systeme(self):
        for o in self:
            i = o.cultiveau_installation_id
            if i and not o.cultiveau_type_systeme:
                o.cultiveau_type_systeme = i.type_systeme
            elif not o.cultiveau_type_systeme:
                o.cultiveau_type_systeme = False

    @api.depends("cultiveau_installation_id", "cultiveau_installation_id.analyse_validee_le", "cultiveau_installation_id.besoin_pointe_mm_j",
                 "cultiveau_installation_id.debit_equipement_m3_h", "cultiveau_installation_id.hmt_m", "cultiveau_installation_id.pompe")
    def _compute_cultiveau(self):
        for o in self:
            i = o.cultiveau_installation_id
            o.cultiveau_analyse_validee = bool(i and i.analyse_validee_le)
            o.cultiveau_dimensionnement = (f"Besoin de pointe {i.besoin_pointe_mm_j:g} mm/j · débit d'équipement {i.debit_equipement_m3_h:g} m³/h · "
                                           f"HMT {i.hmt_m:g} m · {i.pompe or 'pompe à définir'}") if i and i.besoin_pointe_mm_j else ""

    def action_confirm(self):
        for o in self:
            if o.cultiveau_installation_id and not o.cultiveau_analyse_validee:
                o.message_post(body="⚠ Commande confirmée sans analyse des besoins (A1.1) validée avec l'exploitant : "
                                    "le référentiel la demande avant tout dimensionnement (§ 3.2). À régulariser sur l'installation.")
        return super().action_confirm()

    def action_creer_installation(self):
        """Depuis un devis sans installation : créer le site chez le client, pour y tenir le dossier."""
        self.ensure_one()
        inst = self.env["cultiveau.installation"].create({
            "name": self.cultiveau_type_systeme and dict(TYPES)[self.cultiveau_type_systeme] or f"Projet {self.name}",
            "partner_id": self.partner_id.commercial_partner_id.id if self.partner_id.is_company else self.partner_id.id,
            "type_systeme": self.cultiveau_type_systeme or "mixte", "etat": "projet", "company_id": self.company_id.id, "user_id": self.user_id.id})
        self.cultiveau_installation_id = inst
        return {"type": "ir.actions.act_window", "res_model": "cultiveau.installation", "res_id": inst.id, "view_mode": "form"}
