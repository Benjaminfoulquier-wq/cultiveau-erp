from odoo import api, fields, models
from odoo.exceptions import UserError

from odoo.addons.cultiveau_ventes.models.crm_lead import ORIGINES, URGENCES

NATURES = [("depannage", "Dépannage (curatif)"), ("entretien", "Entretien (préventif)"), ("remise_en_service", "Remise en service (§ 18.3)"),
           ("hivernage", "Hivernage (§ 18.5)"), ("mise_en_service", "Mise en service (A1.3)"), ("diagnostic", "Diagnostic (A1.7)"),
           ("modification", "Modification / extension (A1.9)"), ("livraison", "Livraison"), ("autre", "Autre")]
NATURE_VERS_REGISTRE = {"depannage": "curatif", "entretien": "preventif", "remise_en_service": "remise_en_service", "hivernage": "hivernage",
                        "mise_en_service": "mise_en_service", "diagnostic": "diagnostic", "modification": "modification"}
PRIORITE = {"immediate": "1", "journee": "1"}


class ProjectTask(models.Model):
    _inherit = "project.task"

    cultiveau_intervention = fields.Boolean("Intervention Cultiveau", compute="_compute_intervention", store=True)
    cultiveau_installation_id = fields.Many2one("cultiveau.installation", "Installation", domain="[('partner_id', 'child_of', partner_id)]", index=True)
    cultiveau_equipement_id = fields.Many2one("cultiveau.equipement", "Équipement", domain="[('installation_id', '=', cultiveau_installation_id)]")
    cultiveau_nature = fields.Selection(NATURES, "Nature", default="depannage")
    cultiveau_urgence = fields.Selection(URGENCES, "Urgence", default="semaine")
    cultiveau_origine = fields.Selection(ORIGINES, "Origine")
    cultiveau_reference_appel = fields.Char("Référence de l'appel", index=True)
    cultiveau_symptome = fields.Char("Symptôme / demande")
    cultiveau_releves = fields.Char("Valeurs relevées", help="Pressions, débits, kWh/m³… à comparer au PV de mise en service (§ 18.9).")
    cultiveau_piece_ids = fields.One2many("cultiveau.intervention.piece", "task_id", string="Pièces et prestations")
    cultiveau_sale_order_id = fields.Many2one("sale.order", "Devis / commande", copy=False)
    cultiveau_registre_id = fields.Many2one("cultiveau.registre", "Ligne du registre", copy=False, readonly=True)
    cultiveau_reference_pressions = fields.Char("Références du PV", compute="_compute_reference_pressions")

    @api.depends("project_id.cultiveau_interventions")
    def _compute_intervention(self):
        for t in self:
            t.cultiveau_intervention = bool(t.project_id.cultiveau_interventions)

    @api.depends("cultiveau_installation_id.pv_pression_sortie_pompe_bar", "cultiveau_installation_id.pv_pression_point_defavorable_bar")
    def _compute_reference_pressions(self):
        for t in self:
            i = t.cultiveau_installation_id
            t.cultiveau_reference_pressions = (f"{i.pv_pression_sortie_pompe_bar:g} bar sortie pompe · {i.pv_pression_point_defavorable_bar:g} bar point défavorable"
                                               if i and i.pv_pression_sortie_pompe_bar else "Pas de PV de mise en service : sans référence, on tâtonne.")

    @api.onchange("cultiveau_urgence")
    def _onchange_urgence(self):
        if self.cultiveau_urgence in PRIORITE:
            self.priority = PRIORITE[self.cultiveau_urgence]

    def write(self, vals):
        res = super().write(vals)
        if "state" in vals and vals["state"] == "1_done":
            self._cultiveau_inscrire_au_registre()
        return res

    def _cultiveau_inscrire_au_registre(self):
        """Une intervention terminée s'inscrit au registre de maintenance (A1.8) de l'installation."""
        for t in self.filtered(lambda t: t.cultiveau_installation_id and not t.cultiveau_registre_id):
            genre = NATURE_VERS_REGISTRE.get(t.cultiveau_nature, "curatif")
            t.cultiveau_registre_id = self.env["cultiveau.registre"].create({
                "installation_id": t.cultiveau_installation_id.id, "date": fields.Date.context_today(t), "genre": genre,
                "description": t.name, "releves": t.cultiveau_releves or "", "reference": t.cultiveau_reference_appel or f"Intervention {t.id}",
                "intervenant": ", ".join(t.user_ids.mapped("name")) or self.env.user.name})
            champ = {"remise_en_service": "remise_en_service_le", "hivernage": "hivernage_le"}.get(t.cultiveau_nature)
            if champ:
                t.cultiveau_installation_id[champ] = fields.Date.context_today(t)

    def action_creer_devis(self):
        """Les pièces et prestations de l'intervention deviennent un devis (ou s'ajoutent au devis existant)."""
        self.ensure_one()
        if not self.partner_id:
            raise UserError("L'intervention n'a pas de client.")
        if not self.cultiveau_piece_ids:
            raise UserError("Ajoutez d'abord les pièces et prestations utilisées.")
        devis = self.cultiveau_sale_order_id
        if not devis or devis.state not in ("draft", "sent"):
            devis = self.env["sale.order"].create({
                "partner_id": self.partner_id.id, "company_id": self.company_id.id or self.env.company.id,
                "origin": f"Intervention {self.name}", "cultiveau_installation_id": self.cultiveau_installation_id.id})
            self.cultiveau_sale_order_id = devis
        for p in self.cultiveau_piece_ids.filtered(lambda p: not p.sale_line_id):
            p.sale_line_id = self.env["sale.order.line"].create({
                "order_id": devis.id, "product_id": p.product_id.id, "product_uom_qty": p.quantite,
                "name": p.product_id.get_product_multiline_description_sale() + (f"\n{p.note}" if p.note else "")})
        return {"type": "ir.actions.act_window", "res_model": "sale.order", "res_id": devis.id, "view_mode": "form"}

    @api.model
    def cultiveau_creer_depuis_appel(self, company, partner, donnees):
        """Une fiche d'intervention depuis l'assistant téléphonique (voir cultiveau_connecteurs)."""
        projet = self.env["project.project"].cultiveau_projet_interventions(company)
        urgence = donnees.get("urgence") if donnees.get("urgence") in dict(URGENCES) else "semaine"
        return self.with_company(company).create({
            "name": (donnees.get("resume") or donnees.get("symptome") or "Appel : demande d'intervention")[:200],
            "project_id": projet.id, "partner_id": partner.id, "company_id": company.id,
            "cultiveau_nature": "depannage", "cultiveau_urgence": urgence, "cultiveau_origine": "assistant",
            "cultiveau_reference_appel": donnees.get("reference"), "cultiveau_symptome": (donnees.get("symptome") or donnees.get("resume") or "")[:200],
            "priority": PRIORITE.get(urgence, "0"), "description": donnees.get("transcription") or donnees.get("resume") or "",
            "cultiveau_installation_id": partner.cultiveau_installation_ids[:1].id if len(partner.cultiveau_installation_ids) == 1 else False})


class InterventionPiece(models.Model):
    _name = "cultiveau.intervention.piece"
    _description = "Pièce ou prestation d'une intervention"

    task_id = fields.Many2one("project.task", required=True, ondelete="cascade")
    product_id = fields.Many2one("product.product", "Article", required=True, domain=[("sale_ok", "=", True)])
    quantite = fields.Float(default=1.0, digits="Product Unit of Measure")
    note = fields.Char("Précision")
    sale_line_id = fields.Many2one("sale.order.line", "Ligne de devis", readonly=True)
