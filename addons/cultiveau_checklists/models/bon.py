from markupsafe import Markup, escape

from odoo import Command, api, fields, models

from odoo.addons.cultiveau_interventions.models.project_task import NATURES


class Bon(models.Model):
    _inherit = "cultiveau.bon"

    nature = fields.Selection(NATURES, "Nature", compute="_compute_nature", store=True, readonly=False, precompute=True, index=True,
                              help="Celle de l'intervention ; elle choisit la checklist.")
    modele_checklist_id = fields.Many2one("cultiveau.checklist.modele", "Checklist", readonly=True, copy=False)
    point_ids = fields.One2many("cultiveau.checklist.point", "bon_id", "Points de contrôle", copy=False)
    checklist_faits = fields.Integer("Points faits", compute="_compute_checklist")
    checklist_total = fields.Integer("Points", compute="_compute_checklist")
    checklist_avancement = fields.Integer("Checklist (%)", compute="_compute_checklist")
    checklist_manques = fields.Char("Points obligatoires non faits", compute="_compute_checklist")

    @api.depends("task_id.cultiveau_nature")
    def _compute_nature(self):
        for b in self:
            if b.task_id and b.task_id.cultiveau_nature:
                b.nature = b.task_id.cultiveau_nature
            elif not b.nature:
                b.nature = "depannage" if not b.chantier_id else "mise_en_service"

    @api.depends("point_ids.etat", "point_ids.obligatoire")
    def _compute_checklist(self):
        for b in self:
            pts = b.point_ids.filtered(lambda p: p.etat != "sans_objet")
            faits = pts.filtered(lambda p: p.etat == "ok")
            b.checklist_total = len(pts)
            b.checklist_faits = len(faits)
            b.checklist_avancement = round(len(faits) / len(pts) * 100) if pts else 0
            manques = pts.filtered(lambda p: p.obligatoire and p.etat != "ok")
            b.checklist_manques = ", ".join(manques.mapped("name")[:6]) + (" …" if len(manques) > 6 else "") if manques else False

    def _charger_checklist(self, forcer=False):
        """La checklist de la nature du bon (société puis réseau, type d'installation puis général)."""
        Modele = self.env["cultiveau.checklist.modele"]
        for b in self:
            if b.point_ids and not forcer:
                continue
            m = Modele.pour(b.nature, b.company_id, b.installation_id.type_systeme if b.installation_id else None)
            if not m:
                continue
            b.point_ids.unlink()
            b.write({"modele_checklist_id": m.id, "point_ids": [Command.create({"sequence": l.sequence, "name": l.name, "genre": l.genre, "unite": l.unite, "cle": l.cle,
                                                                                 "reference": l.reference, "obligatoire": l.obligatoire, "aide": l.aide}) for l in m.ligne_ids]})

    @api.model_create_multi
    def create(self, vals_list):
        bons = super().create(vals_list)
        bons._charger_checklist()
        return bons

    def write(self, vals):
        res = super().write(vals)
        if "nature" in vals:
            self.filtered(lambda b: b.etat == "brouillon")._charger_checklist(forcer=True)
        return res

    def action_recharger_checklist(self):
        self._charger_checklist(forcer=True)
        return True

    def action_tout_cocher(self):
        for b in self:
            b.point_ids.filtered(lambda p: p.genre == "case" and p.etat == "non").write({"fait": True, "etat": "ok"})
        return True

    def action_signer(self):
        res = super().action_signer()
        for b in self.filtered(lambda b: b.etat == "signe" and b.checklist_manques):
            b.message_post(body=Markup("⚠ Signé avec des points obligatoires non faits : %s. À noter au registre et à reprogrammer si besoin.") % escape(b.checklist_manques))
        return res
