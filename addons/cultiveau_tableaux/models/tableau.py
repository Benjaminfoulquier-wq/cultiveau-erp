"""Un tableau de bord en trois choix : le sujet, la mesure, le regroupement (et la période, le type de graphique). L'ERP ouvre
la vue graphique et le tableau croisé d'Odoo sur les données de l'adhérent, avec ses droits."""
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

# sujet -> modèle, domaine, champ de date, mesures (clé -> champ ou __count__), regroupements (clé -> champ)
SUJETS = {
    "interventions": {"titre": "Interventions", "modele": "project.task", "domaine": [("cultiveau_intervention", "=", True)], "date": "cultiveau_debut",
                      "mesures": {"nombre": "__count__", "heures_prevues": "cultiveau_duree_prevue"},
                      "groupes": {"technicien": "user_ids", "client": "partner_id", "nature": "cultiveau_nature", "urgence": "cultiveau_urgence", "etape": "stage_id",
                                  "installation": "cultiveau_installation_id", "mois": "cultiveau_debut:month", "semaine": "cultiveau_debut:week", "jour": "cultiveau_debut:day"}},
    "bons": {"titre": "Bons d'intervention", "modele": "cultiveau.bon", "domaine": [("etat", "!=", "annule")], "date": "date",
             "mesures": {"nombre": "__count__", "montant": "montant_ht", "heures": "duree_heures", "kilometres": "trajet_km"},
             "groupes": {"technicien": "user_ids", "client": "partner_id", "nature": "nature", "etat": "etat", "mois": "date:month", "semaine": "date:week"}},
    "devis": {"titre": "Devis", "modele": "sale.order", "domaine": [("state", "in", ("draft", "sent"))], "date": "date_order",
              "mesures": {"nombre": "__count__", "montant": "amount_untaxed"},
              "groupes": {"commercial": "user_id", "client": "partner_id", "type_installation": "cultiveau_type_systeme", "etat": "state", "mois": "date_order:month", "semaine": "date_order:week"}},
    "commandes": {"titre": "Commandes", "modele": "sale.order", "domaine": [("state", "in", ("sale", "done"))], "date": "date_order",
                  "mesures": {"nombre": "__count__", "montant": "amount_untaxed"},
                  "groupes": {"commercial": "user_id", "client": "partner_id", "type_installation": "cultiveau_type_systeme", "mois": "date_order:month", "trimestre": "date_order:quarter"}},
    "factures": {"titre": "Factures clients", "modele": "account.move", "domaine": [("move_type", "=", "out_invoice"), ("state", "=", "posted")], "date": "invoice_date",
                 "mesures": {"nombre": "__count__", "montant": "amount_untaxed_signed", "reste_du": "amount_residual"},
                 "groupes": {"client": "partner_id", "etat_paiement": "payment_state", "mois": "invoice_date:month", "trimestre": "invoice_date:quarter", "commercial": "invoice_user_id"}},
    "opportunites": {"titre": "Opportunités", "modele": "crm.lead", "domaine": [("type", "=", "opportunity")], "date": "create_date",
                     "mesures": {"nombre": "__count__", "montant": "expected_revenue"},
                     "groupes": {"commercial": "user_id", "etape": "stage_id", "origine": "cultiveau_origine", "type_installation": "cultiveau_type_systeme", "raison_perte": "lost_reason_id",
                                 "mois": "create_date:month", "client": "partner_id"}},
    "effort_commercial": {"titre": "Effort commercial", "modele": "cultiveau.effort.commercial", "domaine": [], "date": "date",
                          "mesures": {"nombre": "nombre"},
                          "groupes": {"personne": "user_id", "activite": "activity_type_id", "mois": "mois", "etape": "stage_id", "client": "partner_id"}},
    "clients": {"titre": "Clients", "modele": "res.partner", "domaine": [("cultiveau_est_client", "=", True), ("parent_id", "=", False)], "date": "create_date",
                "mesures": {"nombre": "__count__"},
                "groupes": {"type": "cultiveau_type", "commune": "city", "persona": "cultiveau_persona_id", "departement": "cultiveau_departement", "mois": "create_date:month"}},
    "installations": {"titre": "Installations", "modele": "cultiveau.installation", "domaine": [], "date": "create_date",
                      "mesures": {"nombre": "__count__", "surface": "surface_ha"},
                      "groupes": {"type_installation": "type_systeme", "etat": "etat", "client": "partner_id", "commune": "commune", "ressource": "ressource", "energie": "energie"}},
    "chantiers": {"titre": "Chantiers", "modele": "cultiveau.chantier", "domaine": [], "date": "date_debut",
                  "mesures": {"nombre": "__count__", "heures_prevues": "heures_prevues", "heures_pointees": "heures_reelles"},
                  "groupes": {"chef": "chef_id", "etat": "etat", "client": "partner_id", "type_installation": "type_systeme", "mois": "date_debut:month"}},
    "achats": {"titre": "Achats", "modele": "purchase.order", "domaine": [("state", "!=", "cancel")], "date": "date_order",
               "mesures": {"nombre": "__count__", "montant": "amount_untaxed"},
               "groupes": {"fournisseur": "partner_id", "etat": "state", "mois": "date_order:month", "trimestre": "date_order:quarter"}},
}
MESURES = [("nombre", "Nombre"), ("montant", "Montant HT"), ("reste_du", "Reste dû"), ("heures", "Heures"), ("heures_prevues", "Heures prévues"), ("heures_pointees", "Heures pointées"),
           ("kilometres", "Kilomètres"), ("surface", "Surface (ha)")]
GROUPES = [("technicien", "Technicien"), ("commercial", "Commercial"), ("personne", "Personne"), ("chef", "Chef de chantier"), ("client", "Client"), ("fournisseur", "Fournisseur"),
           ("nature", "Nature"), ("urgence", "Urgence"), ("etape", "Étape"), ("etat", "État"), ("etat_paiement", "État de paiement"), ("origine", "Origine"), ("raison_perte", "Raison de perte"),
           ("activite", "Type d'activité"), ("type", "Type de client"), ("type_installation", "Type d'installation"), ("installation", "Installation"), ("persona", "Persona"),
           ("commune", "Commune"), ("departement", "Département"), ("ressource", "Ressource en eau"), ("energie", "Énergie"), ("jour", "Jour"), ("semaine", "Semaine"), ("mois", "Mois"), ("trimestre", "Trimestre")]
PERIODES = [("ce_mois", "Ce mois-ci"), ("mois_dernier", "Le mois dernier"), ("trimestre", "Ce trimestre"), ("annee", "Cette année"), ("12_mois", "Les 12 derniers mois"), ("30_jours", "Les 30 derniers jours"), ("tout", "Tout")]
GRAPHIQUES = [("barres", "Barres"), ("courbe", "Courbe"), ("camembert", "Camembert"), ("tableau", "Tableau croisé")]


class Tableau(models.AbstractModel):
    _name = "cultiveau.tableau.demande"
    _description = "Construction d'un tableau de bord"

    @api.model
    def sujets(self):
        """Les sujets disponibles (le modèle existe), avec leurs mesures et regroupements valides."""
        resultat = {}
        for cle, s in SUJETS.items():
            if s["modele"] not in self.env:
                continue
            champs = self.env[s["modele"]]._fields
            groupes = {g: c for g, c in s["groupes"].items() if c.split(":")[0] in champs}
            mesures = {m: c for m, c in s["mesures"].items() if c == "__count__" or c in champs}
            resultat[cle] = {**s, "groupes": groupes, "mesures": mesures}
        return resultat

    @api.model
    def _domaine_periode(self, champ, periode):
        if not champ or not periode or periode == "tout":
            return []
        auj = fields.Date.context_today(self)
        if periode == "ce_mois":
            du, au = auj.replace(day=1), None
        elif periode == "mois_dernier":
            du = (auj.replace(day=1) - relativedelta(months=1))
            au = auj.replace(day=1) - timedelta(days=1)
        elif periode == "trimestre":
            du, au = auj.replace(month=3 * ((auj.month - 1) // 3) + 1, day=1), None
        elif periode == "annee":
            du, au = auj.replace(month=1, day=1), None
        elif periode == "12_mois":
            du, au = auj - relativedelta(months=12), None
        elif periode == "30_jours":
            du, au = auj - timedelta(days=30), None
        else:
            return []
        d = [(champ, ">=", fields.Date.to_string(du))]
        if au:
            d.append((champ, "<=", fields.Date.to_string(au)))
        return d

    @api.model
    def action(self, sujet, mesure="nombre", groupe=None, groupe2=None, periode="tout", graphique="barres", titre=None):
        sujets = self.sujets()
        if sujet not in sujets:
            raise UserError(f"Sujet inconnu : {sujet}. Sujets : {', '.join(sujets)}.")
        s = sujets[sujet]
        if mesure not in s["mesures"]:
            mesure = "nombre" if "nombre" in s["mesures"] else next(iter(s["mesures"]))
        champ_mesure = s["mesures"][mesure]
        groupes = [s["groupes"][g] for g in (groupe, groupe2) if g and g in s["groupes"]]
        if not groupes:
            groupes = [next(iter(s["groupes"].values()))]
        mode = {"barres": "bar", "courbe": "line", "camembert": "pie"}.get(graphique, "bar")
        lib_m = dict(MESURES).get(mesure, mesure)
        lib_g = " et ".join(dict(GROUPES).get(g, g) for g in (groupe, groupe2) if g and g in s["groupes"]) or dict(GROUPES).get(next(iter(s["groupes"])), "")
        lib_p = dict(PERIODES).get(periode, "")
        nom = titre or f"{s['titre']} : {lib_m.lower()} par {lib_g.lower()}" + (f", {lib_p.lower()}" if lib_p and periode != "tout" else "")
        contexte = {"graph_mode": mode, "graph_groupbys": groupes, "pivot_row_groupby": groupes[:1], "pivot_column_groupby": groupes[1:2], "group_by": groupes}
        if champ_mesure != "__count__":
            contexte.update({"graph_measure": champ_mesure, "pivot_measures": [champ_mesure]})
        else:
            contexte.update({"graph_measure": "__count__", "pivot_measures": ["__count__"]})
        vues = [[False, "pivot"], [False, "graph"], [False, "list"]] if graphique == "tableau" else [[False, "graph"], [False, "pivot"], [False, "list"]]
        return {"type": "ir.actions.act_window", "name": nom, "res_model": s["modele"], "views": vues, "view_mode": ",".join(v[1] for v in vues), "target": "current",
                "domain": list(s["domaine"]) + self._domaine_periode(s["date"], periode), "context": contexte}


class Favori(models.Model):
    _name = "cultiveau.tableau.favori"
    _description = "Mes tableaux"
    _order = "sequence, name"

    name = fields.Char("Tableau", required=True)
    sequence = fields.Integer(default=10)
    user_id = fields.Many2one("res.users", "Pour", default=lambda self: self.env.user, required=True)
    company_id = fields.Many2one("res.company", "Société", default=lambda self: self.env.company, required=True)
    partage = fields.Boolean("Partagé avec la société", help="Visible de toute l'équipe, pas seulement de vous.")
    sujet = fields.Selection([(k, v["titre"]) for k, v in SUJETS.items()], "Sujet", required=True, default="interventions")
    mesure = fields.Selection(MESURES, "Mesure", default="nombre", required=True)
    groupe = fields.Selection(GROUPES, "Regroupé par", default="mois", required=True)
    groupe2 = fields.Selection(GROUPES, "Puis par")
    periode = fields.Selection(PERIODES, "Période", default="annee", required=True)
    graphique = fields.Selection(GRAPHIQUES, "Graphique", default="barres", required=True)
    aide = fields.Char("Mesures et regroupements possibles", compute="_compute_aide")

    @api.depends("sujet")
    def _compute_aide(self):
        sujets = self.env["cultiveau.tableau.demande"].sujets()
        for f in self:
            s = sujets.get(f.sujet)
            f.aide = (f"Mesures : {', '.join(dict(MESURES).get(m, m).lower() for m in s['mesures'])} · regroupements : {', '.join(dict(GROUPES).get(g, g).lower() for g in s['groupes'])}") if s else ""

    @api.onchange("sujet", "mesure", "groupe", "periode")
    def _onchange_nom(self):
        if self.sujet and not self.name:
            try:
                self.name = self.env["cultiveau.tableau.demande"].action(self.sujet, self.mesure, self.groupe, self.groupe2, self.periode, self.graphique)["name"]
            except UserError:
                pass

    def action_ouvrir(self):
        self.ensure_one()
        return self.env["cultiveau.tableau.demande"].action(self.sujet, self.mesure, self.groupe, self.groupe2, self.periode, self.graphique, self.name)
