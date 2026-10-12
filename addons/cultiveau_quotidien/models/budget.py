"""Le budget d'heures des chantiers : alertes à 50, 80 et 100 % des heures prévues, jauge par poseur.

Le budget, ce sont les heures de pose du devis (la matrice de pose) ; à défaut, la somme des heures prévues des phases. À chaque
pointage, le chantier compare ses heures pointées au budget : franchir un seuil laisse une note sur le chantier, une activité
pour le chef de chantier (et pour le gérant au-delà de 100 %), et un signal sur la map.
"""
from datetime import timedelta

from odoo import api, fields, models

PALIERS = (50, 80, 100)


class Chantier(models.Model):
    _inherit = "cultiveau.chantier"

    budget_heures = fields.Float("Budget d'heures", compute="_compute_budget", store=True,
                                 help="Les heures de pose du devis (matrice de pose) ; à défaut, la somme des heures prévues des phases.")
    budget_pct = fields.Integer("Budget consommé (%)", compute="_compute_budget", store=True)
    budget_etat = fields.Selection([("sans", "Sans budget"), ("ok", "Dans le budget"), ("attention", "Au-delà de 80 %"), ("depasse", "Dépassé")],
                                   "Budget", compute="_compute_budget", store=True, index=True)
    budget_palier = fields.Integer("Dernier seuil signalé", readonly=True, copy=False)

    @api.depends("cultiveau_heures_devis", "heures_prevues", "heures_reelles")
    def _compute_budget(self):
        for c in self:
            budget = c.cultiveau_heures_devis or c.heures_prevues
            c.budget_heures = budget
            c.budget_pct = round(c.heures_reelles / budget * 100) if budget else 0
            c.budget_etat = "sans" if not budget else ("depasse" if c.budget_pct >= 100 else "attention" if c.budget_pct >= 80 else "ok")

    def par_poseur(self):
        """[{user_id, nom, heures, part (% du budget), semaine (heures de la semaine)}] : la jauge de chaque poseur sur ce chantier."""
        self.ensure_one()
        lundi = fields.Date.context_today(self) - timedelta(days=fields.Date.context_today(self).weekday())
        res = {}
        for p in self.sudo().pointage_ids:
            r = res.setdefault(p.user_id.id, {"user_id": p.user_id.id, "nom": p.user_id.name, "heures": 0.0, "semaine": 0.0})
            r["heures"] += p.heures
            if p.date >= lundi:
                r["semaine"] += p.heures
        for r in res.values():
            r["part"] = round(r["heures"] / self.budget_heures * 100) if self.budget_heures else 0
        return sorted(res.values(), key=lambda r: -r["heures"])

    def _verifier_budget(self):
        for c in self.sudo().filtered(lambda c: c.budget_heures and c.etat in ("planifie", "en_cours")):
            atteint = max([p for p in PALIERS if c.budget_pct >= p], default=0)
            if atteint > c.budget_palier:
                c.budget_palier = atteint
                c._signaler_budget(atteint)

    def _signaler_budget(self, palier):
        self.ensure_one()
        texte = f"{self.heures_reelles:g} h pointées sur {self.budget_heures:g} h prévues ({self.budget_pct} %)"
        titre = "Budget d'heures dépassé" if palier >= 100 else f"Chantier à {palier} % des heures prévues"
        self.message_post(body=f"{titre} : {texte}.", subtype_xmlid="mail.mt_note")
        todo = self.env.ref("mail.mail_activity_data_todo")
        destinataires = self.chef_id
        if palier >= 100:
            destinataires |= self.env["cultiveau.equipe"].gerants(self.company_id) if "cultiveau.equipe" in self.env else self.env["res.users"]
        if palier >= 80:
            for u in destinataires:
                self.activity_schedule(activity_type_id=todo.id, user_id=u.id, summary=titre, note=f"{self.display_name} : {texte}.")
        self.env["cultiveau.evenement"].publier("budget_chantier", self, f"{titre} — {self.display_name}", texte,
                                                charge={"chantier_id": self.id, "palier": palier, "pct": self.budget_pct}, company=self.company_id)

    def action_voir_poseurs(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "name": f"Heures par poseur — {self.display_name}", "res_model": "cultiveau.chantier.pointage",
                "view_mode": "pivot,list", "views": [[False, "pivot"], [False, "list"]], "domain": [("chantier_id", "=", self.id)],
                "context": {"pivot_row_groupby": ["user_id"], "pivot_measures": ["heures"]}}


class Pointage(models.Model):
    _inherit = "cultiveau.chantier.pointage"

    @api.model_create_multi
    def create(self, vals_list):
        pointages = super().create(vals_list)
        pointages.chantier_id._verifier_budget()
        return pointages

    def write(self, vals):
        res = super().write(vals)
        if "heures" in vals or "chantier_id" in vals:
            self.chantier_id._verifier_budget()
        return res
