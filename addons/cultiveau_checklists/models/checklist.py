"""Les checklists par nature d'intervention : le modèle (du réseau ou de l'adhérent) et les points cochés sur le bon."""
from odoo import api, fields, models

from odoo.addons.cultiveau_installation.models.installation import TYPES
from odoo.addons.cultiveau_interventions.models.project_task import NATURES

GENRES = [("case", "À cocher"), ("mesure", "Mesure"), ("texte", "À renseigner")]
# une mesure peut alimenter un relevé du bon
CLES = [("pression_pompe", "Pression sortie pompe (bar)"), ("pression_defavorable", "Pression au point défavorable (bar)"), ("heures", "Temps passé (h)"), ("km", "Trajet (km)")]


class Modele(models.Model):
    _name = "cultiveau.checklist.modele"
    _description = "Modèle de checklist d'intervention"
    _order = "nature, sequence, name"

    name = fields.Char("Checklist", required=True)
    nature = fields.Selection(NATURES, "Nature d'intervention", required=True, index=True)
    type_systeme = fields.Selection(TYPES, "Type d'installation", help="Vide : tous les types. Un modèle au type précis passe avant le modèle général.")
    company_id = fields.Many2one("res.company", "Société", default=lambda self: self.env.company, index=True, help="Vide : proposé par le réseau Cultiveau, visible de tous.")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    reference = fields.Char("Référentiel", help="Les sections du référentiel V4 d'où vient la checklist : « § 18.3, A1.6 ».")
    description = fields.Text("Quand l'employer")
    ligne_ids = fields.One2many("cultiveau.checklist.modele.ligne", "modele_id", "Points", copy=True)
    nb_points = fields.Integer("Points", compute="_compute_nb")
    nb_bons = fields.Integer("Bons", compute="_compute_nb")

    def _compute_nb(self):
        Bon = self.env["cultiveau.bon"].sudo()
        for m in self:
            m.nb_points = len(m.ligne_ids)
            m.nb_bons = Bon.search_count([("modele_checklist_id", "=", m.id)])

    @api.model
    def pour(self, nature, company, type_systeme=None):
        """Le modèle qui s'applique : celui de la société avant celui du réseau, celui du type d'installation avant le général."""
        if not nature:
            return self.browse()
        domaine = [("nature", "=", nature), ("company_id", "in", [company.id, False])]
        if type_systeme:
            domaine += ["|", ("type_systeme", "=", type_systeme), ("type_systeme", "=", False)]
        else:
            domaine.append(("type_systeme", "=", False))
        candidats = self.sudo().search(domaine)
        if not candidats:
            return candidats
        return candidats.sorted(lambda m: (0 if m.company_id else 1, 0 if m.type_systeme else 1, m.sequence, m.id))[:1]

    def action_copier_pour_moi(self):
        """Une copie du modèle du réseau, adaptable par l'adhérent (elle passe devant pour sa société)."""
        self.ensure_one()
        copie = self.copy({"company_id": self.env.company.id, "name": self.name})
        return {"type": "ir.actions.act_window", "res_model": self._name, "res_id": copie.id, "view_mode": "form"}

    def action_voir_bons(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "name": f"Bons — {self.name}", "res_model": "cultiveau.bon", "view_mode": "list,form", "domain": [("modele_checklist_id", "=", self.id)]}


class ModeleLigne(models.Model):
    _name = "cultiveau.checklist.modele.ligne"
    _description = "Point d'un modèle de checklist"
    _order = "modele_id, sequence, id"

    modele_id = fields.Many2one("cultiveau.checklist.modele", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="modele_id.company_id", store=True)
    sequence = fields.Integer(default=10)
    name = fields.Char("Point", required=True)
    genre = fields.Selection(GENRES, "Type", default="case", required=True)
    unite = fields.Char("Unité", size=16)
    cle = fields.Selection(CLES, "Alimente le relevé", help="La mesure saisie remplit ce relevé du bon.")
    reference = fields.Char("Réf.", size=24, help="Section du référentiel : « 18.3.1 ».")
    obligatoire = fields.Boolean("Obligatoire", help="Un point obligatoire non fait est signalé à la signature (sans bloquer : le technicien décide).")
    aide = fields.Char("Aide", help="Ce qu'on regarde, la valeur attendue, le geste.")


class Point(models.Model):
    _name = "cultiveau.checklist.point"
    _description = "Point de checklist d'un bon"
    _order = "bon_id, sequence, id"

    bon_id = fields.Many2one("cultiveau.bon", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="bon_id.company_id", store=True)
    sequence = fields.Integer(default=10)
    name = fields.Char("Point", required=True)
    genre = fields.Selection(GENRES, "Type", default="case", required=True)
    unite = fields.Char("Unité", size=16)
    cle = fields.Selection(CLES, "Alimente")
    reference = fields.Char("Réf.", size=24)
    obligatoire = fields.Boolean("Obligatoire")
    aide = fields.Char("Aide")
    fait = fields.Boolean("Fait")
    valeur = fields.Float("Valeur", digits=(12, 2))
    texte = fields.Char("Réponse")
    remarque = fields.Char("Remarque")
    etat = fields.Selection([("ok", "Fait"), ("non", "Non fait"), ("sans_objet", "Sans objet")], "État", default="non", required=True)

    @api.onchange("fait", "valeur", "texte")
    def _onchange_fait(self):
        for p in self:
            if p.genre == "case":
                p.etat = "ok" if p.fait else ("non" if p.etat != "sans_objet" else p.etat)
            elif p.genre == "mesure" and p.valeur:
                p.etat, p.fait = "ok", True
            elif p.genre == "texte" and p.texte:
                p.etat, p.fait = "ok", True

    def write(self, vals):
        res = super().write(vals)
        if "valeur" in vals or "fait" in vals or "etat" in vals:
            self._pousser_releves()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        points = super().create(vals_list)
        points._pousser_releves()
        return points

    def _pousser_releves(self):
        """Une mesure cochée remplit le relevé du bon qu'elle alimente."""
        champs = {"pression_pompe": "pression_pompe_mesuree", "pression_defavorable": "pression_defavorable_mesuree", "heures": "duree_heures", "km": "trajet_km"}
        for p in self.filtered(lambda p: p.cle and p.genre == "mesure" and p.valeur):
            champ = champs.get(p.cle)
            if champ and champ in p.bon_id._fields and p.bon_id[champ] != p.valeur:
                p.bon_id[champ] = p.valeur
