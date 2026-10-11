"""L'intervention planifiée : son créneau, ses techniciens, ses bons."""
from datetime import timedelta

from odoo import api, fields, models


class Intervention(models.Model):
    _inherit = "project.task"

    cultiveau_debut = fields.Datetime("Début prévu", index=True, tracking=True)
    cultiveau_fin = fields.Datetime("Fin prévue")
    cultiveau_duree_prevue = fields.Float("Durée prévue (h)", default=2.0)
    cultiveau_bon_ids = fields.One2many("cultiveau.bon", "task_id", string="Bons d'intervention")
    cultiveau_nb_bons = fields.Integer(compute="_compute_nb_bons")
    cultiveau_adresse = fields.Char("Adresse", compute="_compute_adresse")

    def _compute_nb_bons(self):
        for t in self:
            t.cultiveau_nb_bons = len(t.cultiveau_bon_ids)

    def _compute_adresse(self):
        for t in self:
            p = t.partner_id
            t.cultiveau_adresse = ", ".join(x for x in (p.street, f"{p.zip or ''} {p.city or ''}".strip()) if x) if p else ""

    @api.onchange("cultiveau_debut", "cultiveau_duree_prevue")
    def _onchange_creneau(self):
        if self.cultiveau_debut:
            self.cultiveau_fin = self.cultiveau_debut + timedelta(hours=self.cultiveau_duree_prevue or 1)

    def write(self, vals):
        res = super().write(vals)
        if ("cultiveau_debut" in vals or "cultiveau_duree_prevue" in vals) and "cultiveau_fin" not in vals:
            # la fin suit le début et la durée prévue
            for t in self.filtered("cultiveau_debut"):
                super(Intervention, t).write({"cultiveau_fin": t.cultiveau_debut + timedelta(hours=t.cultiveau_duree_prevue or 1)})
        if vals.get("cultiveau_debut"):
            etape = self._cultiveau_etape("Planifiée")
            for t in self.filtered(lambda t: t.cultiveau_intervention and t.stage_id.name == "À planifier" and etape.get(t.project_id.id)):
                super(Intervention, t).write({"stage_id": etape[t.project_id.id].id})
        return res

    def _cultiveau_etape(self, nom):
        return {t.project_id.id: t.project_id.type_ids.filtered(lambda e: e.name == nom)[:1] for t in self if t.project_id}

    def action_arrive_sur_place(self):
        """Le technicien arrive : un bon s'ouvre, pré-rempli (client, installation, pièces prévues, heure d'arrivée)."""
        self.ensure_one()
        bon = self.cultiveau_bon_ids.filtered(lambda b: b.etat == "brouillon")[:1]
        if not bon:
            maintenant = fields.Datetime.context_timestamp(self, fields.Datetime.now())
            bon = self.env["cultiveau.bon"].create({
                "task_id": self.id, "partner_id": self.partner_id.id, "installation_id": self.cultiveau_installation_id.id,
                "company_id": self.company_id.id or self.env.company.id, "user_ids": [(6, 0, (self.user_ids.filtered("active") or self.env.user).ids)],
                "heure_arrivee": round(maintenant.hour + maintenant.minute / 60, 2),
                "ligne_ids": [(0, 0, {"genre": "piece", "product_id": p.product_id.id, "quantite": p.quantite, "prix_unitaire": p.product_id.lst_price,
                                      "description": p.note or p.product_id.display_name}) for p in self.cultiveau_piece_ids],
            })
            etape = self._cultiveau_etape("En cours").get(self.project_id.id)
            if etape:
                self.stage_id = etape
        return {"type": "ir.actions.act_window", "res_model": "cultiveau.bon", "res_id": bon.id, "view_mode": "form", "views": [(False, "form")]}

    def action_voir_bons(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "name": "Bons d'intervention", "res_model": "cultiveau.bon", "view_mode": "list,form",
                "domain": [("task_id", "=", self.id)], "context": {"default_task_id": self.id, "default_partner_id": self.partner_id.id}}

    def _cultiveau_cloturer_depuis_bon(self, bon):
        """Le bon signé clôt l'intervention : relevés repris, étape « Terminée », inscription au registre."""
        releves = []
        if bon.pression_pompe_mesuree:
            releves.append(f"{bon.pression_pompe_mesuree:g} bar sortie pompe")
        if bon.pression_defavorable_mesuree:
            releves.append(f"{bon.pression_defavorable_mesuree:g} bar point défavorable")
        valeurs = {"state": "1_done"}
        if releves:
            valeurs["cultiveau_releves"] = " · ".join(releves)
        etape = self._cultiveau_etape("Terminée").get(self.project_id.id)
        if etape:
            valeurs["stage_id"] = etape.id
        self.write(valeurs)
