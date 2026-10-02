from odoo import fields, models

from odoo.addons.cultiveau_installation.models.installation import TYPES

URGENCES = [("immediate", "Immédiate (irrigation arrêtée en saison)"), ("journee", "Dans la journée"), ("semaine", "Cette semaine"), ("non_urgent", "Non urgent")]
ORIGINES = [("assistant", "Assistant téléphonique"), ("telephone", "Téléphone"), ("visite", "Visite"), ("mail", "E-mail"), ("salon", "Salon, réunion"),
            ("recommandation", "Recommandation"), ("frise", "Fenêtre commerciale (frise)"), ("autre", "Autre")]


class CrmLead(models.Model):
    _inherit = "crm.lead"

    cultiveau_installation_id = fields.Many2one("cultiveau.installation", "Installation", domain="[('partner_id', 'child_of', partner_id)]")
    cultiveau_type_systeme = fields.Selection(TYPES, "Type d'installation")
    cultiveau_surface_ha = fields.Float("Surface (ha)", digits=(8, 2))
    cultiveau_urgence = fields.Selection(URGENCES, "Urgence")
    cultiveau_origine = fields.Selection(ORIGINES, "Origine")
    cultiveau_reference_appel = fields.Char("Référence de l'appel", index=True, help="La référence APL-… de l'assistant téléphonique.")

    def action_creer_installation(self):
        """L'opportunité devient un site : c'est là que l'analyse des besoins (A1.1) se tient."""
        self.ensure_one()
        partner = self.partner_id
        if not partner:
            partner = self._handle_partner_assignment(create_missing=True) if hasattr(self, "_handle_partner_assignment") else None
            partner = self.partner_id
        inst = self.env["cultiveau.installation"].create({
            "name": self.name, "partner_id": partner.id, "type_systeme": self.cultiveau_type_systeme or "mixte", "etat": "projet",
            "surface_ha": self.cultiveau_surface_ha, "company_id": self.company_id.id or self.env.company.id, "user_id": self.user_id.id or self.env.user.id})
        self.cultiveau_installation_id = inst
        stage = self.env.ref("cultiveau_ventes.stage_analyse", raise_if_not_found=False)
        if stage and self.stage_id.sequence < stage.sequence:
            self.stage_id = stage
        return {"type": "ir.actions.act_window", "res_model": "cultiveau.installation", "res_id": inst.id, "view_mode": "form"}
