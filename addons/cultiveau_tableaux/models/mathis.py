"""Mathis construit le tableau de bord qu'on lui demande en français, et l'enregistre dans Mes tableaux si on le lui dit."""
from odoo import models

from .tableau import GRAPHIQUES, GROUPES, MESURES, PERIODES


class Mathis(models.AbstractModel):
    _inherit = "cultiveau.mathis"

    def _outils(self):
        T = self.env["cultiveau.tableau.demande"]
        sujets = T.sujets()
        detail = " ; ".join(f"{k} (mesures : {', '.join(s['mesures'])} ; par : {', '.join(s['groupes'])})" for k, s in sujets.items())
        return super()._outils() + [
            {"type": "function", "function": {"name": "tableau", "description": "Ouvre un tableau de bord (graphique + tableau croisé) sur les données de la société : un sujet, une mesure, un "
                                                                                 "regroupement, une période. À utiliser dès qu'on demande « montre-moi », « combien par », « répartition », "
                                                                                 "« évolution », « graphique », « tableau ». Sujets : " + detail + ". enregistrer=true le garde dans Mes tableaux.",
                                              "parameters": {"type": "object", "properties": {
                                                  "sujet": {"type": "string", "enum": list(sujets)}, "mesure": {"type": "string", "enum": [m for m, _ in MESURES]},
                                                  "regrouper_par": {"type": "string", "enum": [g for g, _ in GROUPES]}, "puis_par": {"type": "string", "enum": [g for g, _ in GROUPES]},
                                                  "periode": {"type": "string", "enum": [p for p, _ in PERIODES]}, "graphique": {"type": "string", "enum": [g for g, _ in GRAPHIQUES]},
                                                  "titre": {"type": "string"}, "enregistrer": {"type": "boolean"}}, "required": ["sujet"]}}},
        ]

    def _executer(self, nom, args):
        if nom == "tableau":
            T = self.env["cultiveau.tableau.demande"]
            action = T.action(args.get("sujet"), args.get("mesure") or "nombre", args.get("regrouper_par"), args.get("puis_par"), args.get("periode") or "tout",
                              args.get("graphique") or "barres", args.get("titre"))
            res = {"tableau": action["name"], "ouvert": True}
            if args.get("enregistrer"):
                f = self.env["cultiveau.tableau.favori"].create({"name": action["name"], "sujet": args.get("sujet"), "mesure": args.get("mesure") or "nombre",
                                                                 "groupe": args.get("regrouper_par") or "mois", "groupe2": args.get("puis_par") or False,
                                                                 "periode": args.get("periode") or "tout", "graphique": args.get("graphique") or "barres"})
                res["enregistre_dans_mes_tableaux"] = f.id
            return res, {"type": "action", "action": action}
        return super()._executer(nom, args)
