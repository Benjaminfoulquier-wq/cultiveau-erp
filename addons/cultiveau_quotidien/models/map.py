"""Le budget d'heures, l'écran « Aujourd'hui » et les automatisations sur la map, chez Mathis et dans les réglages."""
from datetime import timedelta

from odoo import fields, models


class Evenement(models.Model):
    _inherit = "cultiveau.evenement"

    genre = fields.Selection(selection_add=[("budget_chantier", "Budget d'heures")], ondelete={"budget_chantier": "cascade"})


class Scene(models.AbstractModel):
    _inherit = "cultiveau.scene"

    def _actions(self):
        return {**super()._actions(),
                "aujourdhui": ("cultiveau_quotidien.action_aujourdhui", {"name": "Aujourd'hui"}),
                "automatisations": ("cultiveau_quotidien.action_regles", {"name": "Automatisations"}),
                "chantiers_budget": ("cultiveau_chantier.action_chantiers", {"name": "Chantiers en dépassement", "domain": [("budget_etat", "in", ("attention", "depasse"))]})}


class Map(models.AbstractModel):
    _inherit = "cultiveau.map"

    def _portes(self):
        portes = super()._portes()
        dispo = self.env["cultiveau.scene"]._actions_disponibles()
        ajouts = {"administratif": [("aujourdhui", "Aujourd'hui : ce qui attend", "fa-sun-o"), ("automatisations", "Automatisations", "fa-magic")],
                  "accueil": [("aujourdhui", "Aujourd'hui : ce qui attend", "fa-sun-o")],
                  "reunion": [("chantiers_budget", "Chantiers en dépassement", "fa-hourglass-end")]}
        for zone, liste in ajouts.items():
            deja = {p["cle"] for p in portes.get(zone, [])}
            # « Aujourd'hui » en tête de l'administratif et de l'accueil
            nouvelles = [{"cle": c, "nom": n, "icone": i} for c, n, i in liste if c in dispo and c not in deja]
            portes[zone] = ([p for p in nouvelles if p["cle"] == "aujourdhui"] + portes.get(zone, []) + [p for p in nouvelles if p["cle"] != "aujourdhui"])
        return portes

    @staticmethod
    def _couleur_budget(pct):
        return "rouge" if pct >= 100 else ("ambre" if pct >= 80 else "vert")

    def _fiche_chantier(self, company, cid):
        f = super()._fiche_chantier(company, cid)
        c = self.env["cultiveau.chantier"].sudo().browse(cid)
        if c.budget_heures:
            lignes = [{"icone": "fa-hourglass-half", "texte": f"{c.heures_reelles:g} h pointées sur {c.budget_heures:g} h", "badge": f"{c.budget_pct} %",
                       "couleur": self._couleur_budget(c.budget_pct), "jauge": c.budget_pct}]
            for p in c.par_poseur():
                lignes.append({"icone": "fa-user", "texte": p["nom"], "detail": f"{p['heures']:g} h · {p['semaine']:g} h cette semaine", "jauge": p["part"], "couleur": "bleu",
                               "badge": f"{p['part']} %"})
            f["blocs"] = list(f.get("blocs", [])) + [{"titre": "Budget d'heures", "lignes": lignes}]
        return f

    def _fiche_personne(self, company, uid):
        f = super()._fiche_personne(company, uid)
        lundi = fields.Date.context_today(self) - timedelta(days=fields.Date.context_today(self).weekday())
        pointages = self.env["cultiveau.chantier.pointage"].sudo().search([("user_id", "=", uid), ("date", ">=", lundi), ("company_id", "=", company.id)])
        if pointages:
            par_chantier = {}
            for p in pointages:
                par_chantier[p.chantier_id] = par_chantier.get(p.chantier_id, 0) + p.heures
            lignes = [{"icone": "fa-wrench", "texte": ch.display_name, "detail": f"{h:g} h cette semaine", "badge": f"{ch.budget_pct} % du budget" if ch.budget_heures else "",
                       "couleur": self._couleur_budget(ch.budget_pct), "jauge": ch.budget_pct if ch.budget_heures else None,
                       "ouvrir": {"cle": "fiche", "modele": "cultiveau.chantier", "id": ch.id}} for ch, h in par_chantier.items()]
            f["blocs"] = list(f.get("blocs", [])) + [{"titre": f"Chantiers · {sum(par_chantier.values()):g} h cette semaine", "lignes": lignes}]
        return f

    def _fiche_zone(self, company, _id, cle=None):
        f = super()._fiche_zone(company, _id, cle=cle)
        if cle == "administratif":
            tuiles = self.env["cultiveau.aujourdhui"].tuiles()
            if tuiles:
                lignes = [{"icone": t["icone"], "texte": t["titre"], "detail": t["detail"], "badge": str(t["nombre"]), "couleur": t["couleur"],
                           "ouvrir": {"cle": "aujourdhui_tuile", "nom": t["titre"], "doaction": t["action"]}} for t in tuiles]
                f["blocs"] = [{"titre": "Aujourd'hui", "lignes": lignes}] + list(f.get("blocs", []))
        return f


class Mathis(models.AbstractModel):
    _inherit = "cultiveau.mathis"

    def _outils(self):
        return super()._outils() + [
            {"type": "function", "function": {"name": "a_faire", "description": "Ce qui attend la personne connectée aujourd'hui : courriels sans réponse, factures échues, devis à relancer, "
                                                                              "interventions en retard, chantiers en dépassement d'heures, congés et notes de frais à valider, stock bas, bons à facturer, rendez-vous du jour.",
                                              "parameters": {"type": "object", "properties": {}}}},
            {"type": "function", "function": {"name": "budget_chantiers", "description": "Le budget d'heures des chantiers en cours : heures pointées, heures prévues, pourcentage, heures par poseur.",
                                              "parameters": {"type": "object", "properties": {"chantier_id": {"type": "integer"}}}}},
        ]

    def _executer(self, nom, args):
        if nom == "a_faire":
            return [{k: t[k] for k in ("titre", "nombre", "detail", "lignes")} for t in self.env["cultiveau.aujourdhui"].tuiles()], None
        if nom == "budget_chantiers":
            Chantier = self.env["cultiveau.chantier"]
            chantiers = Chantier.browse(int(args["chantier_id"])).exists() if args.get("chantier_id") else \
                Chantier.search([("etat", "in", ("planifie", "en_cours")), ("company_id", "=", self.env.company.id)], order="budget_pct desc", limit=10)
            return [{"id": c.id, "chantier": c.display_name, "prevu": c.budget_heures, "pointe": c.heures_reelles, "pct": c.budget_pct, "poseurs": c.par_poseur()}
                    for c in chantiers], None
        return super()._executer(nom, args)


class Settings(models.TransientModel):
    _inherit = "res.config.settings"

    cultiveau_rapport_lundi = fields.Boolean("Rapport du lundi", config_parameter="cultiveau.rapport_lundi", default=True,
                                             help="Chaque lundi matin, le gérant reçoit la semaine écoulée et ce qui attend.")
    cultiveau_jours_relance_devis = fields.Integer("Devis à relancer après (jours)", config_parameter="cultiveau.jours_relance_devis", default=7)

    def action_cultiveau_rapport_maintenant(self):
        n = self.env["cultiveau.rapport"].envoyer(self.env.company, self.env.user)
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"title": "Rapport envoyé", "message": f"Le rapport part à {self.env.user.email or 'votre adresse'}." if n else "Ajoutez votre adresse e-mail à votre profil.",
                           "type": "success" if n else "warning", "sticky": False}}
