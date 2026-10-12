"""Le plan 3D d'un site : un JSON versionné par société, construit par le générateur puis affiné dans l'éditeur.

Le moteur construit la scène depuis ce JSON. Aucune pièce n'est codée en dur côté client. Unités : le mètre ; x vers la
droite, z vers la caméra ; y vers le haut.

Le JSON :
  contour  : le polygone du bâtiment [[x, z], …]
  murs     : [{a, b, matiere}] (le moteur baisse lui-même les murs côté caméra, façon maison de poupée)
  portes   : [{a, b}] des ouvertures dans les murs
  cloisons : [{a, b, ouvertures: [[t0, t1]]}] des cloisons vitrées intérieures (t de 0 à 1 le long du segment)
  zones    : [{cle, nom, type, polygone, sol, libelle}] le sol peint et son nom
  objets   : [{id, type, x, z, rot, params, entite: {modele, id} | null, zone}] le mobilier et les équipements
  places   : [{cle, usage, x, z, rot}] des emplacements vides que les données remplissent (camions, voitures, champs, postes, établi)
  exterieur: {route: [[x, z], …] boucle de circulation, clotures: [[a, b]], arbres: [[x, z, taille]], haies: [[a, b]], parking: [...]}
  couloirs : [[x, z], …] des points de passage pour les marcheurs quand la grille ne suffit pas
"""
import json

from odoo import api, fields, models
from odoo.exceptions import UserError

from .secteur import SECTEUR


class Plan(models.Model):
    _name = "cultiveau.plan"
    _description = "Plan 3D d'un site (Map vivante)"
    _order = "company_id, version desc"

    name = fields.Char("Site", required=True, default="Dépôt")
    company_id = fields.Many2one("res.company", "Adhérent", required=True, default=lambda self: self.env.company, index=True, ondelete="cascade")
    version = fields.Integer("Version", default=1, readonly=True)
    publie = fields.Boolean("Publié", default=False, index=True)
    layout = fields.Json("Plan")
    note = fields.Char("Note de version")

    _sql_constraints = [("version_unique", "unique(company_id, name, version)", "Cette version existe déjà.")]

    # ---------------------------------------------------------------- le plan courant

    @api.model
    def courant(self, company=None):
        """Le plan publié de la société (le dernier publié), sinon le dernier brouillon, sinon un plan généré et publié."""
        company = company or self.env.company
        plan = self.sudo().search([("company_id", "=", company.id), ("publie", "=", True)], order="version desc", limit=1)
        if not plan:
            plan = self.sudo().search([("company_id", "=", company.id)], order="version desc", limit=1)
        if not plan:
            plan = self.sudo().create({"company_id": company.id, "layout": self.generer(company), "publie": True, "note": "Plan initial généré"})
        return plan

    @api.model
    def enregistrer(self, layout, publier=False, note=""):
        """Une nouvelle version du plan (l'éditeur). Administrateur de la société seulement."""
        if not self.env.user.has_group("base.group_system") and not self.env.user.has_group("sales_team.group_sale_manager"):
            raise UserError("Seul le gérant ou l'administrateur peut modifier le plan.")
        self._verifier(layout)
        company = self.env.company
        derniere = self.sudo().search([("company_id", "=", company.id)], order="version desc", limit=1)
        plan = self.sudo().create({"company_id": company.id, "name": derniere.name or "Dépôt", "version": (derniere.version or 0) + 1, "layout": layout, "note": note or "Modifié dans l'éditeur"})
        if publier:
            plan.action_publier()
        return {"id": plan.id, "version": plan.version, "publie": plan.publie}

    def action_publier(self):
        for p in self:
            self.sudo().search([("company_id", "=", p.company_id.id), ("name", "=", p.name), ("publie", "=", True)]).write({"publie": False})
            p.sudo().publie = True

    def action_regenerer(self):
        for p in self:
            p.sudo().write({"layout": self.generer(p.company_id), "note": "Plan régénéré"})

    @api.model
    def _verifier(self, layout):
        """Le plan est un dictionnaire avec au moins un contour et des listes là où on les attend."""
        if not isinstance(layout, dict):
            raise UserError("Plan illisible.")
        for cle in ("contour", "murs", "zones", "objets", "places"):
            if not isinstance(layout.get(cle), list):
                raise UserError(f"Plan incomplet : « {cle} » manque.")
        if len(layout["contour"]) < 3:
            raise UserError("Le contour du bâtiment demande au moins trois points.")
        ids = [o.get("id") for o in layout["objets"]]
        if len(ids) != len(set(ids)):
            raise UserError("Deux objets portent le même identifiant.")
        return True

    # ---------------------------------------------------------------- le générateur

    @api.model
    def generer(self, company=None):
        """Le premier plan d'un installateur d'irrigation : un bâtiment en L (hall magasin-stockage-atelier, aile de bureaux),
        la cour poids lourds, le dépôt extérieur, le parking clients, la route et, de l'autre côté, les champs des agriculteurs."""
        company = company or self.env.company
        o = []  # objets
        n = [0]

        def obj(type_, x, z, rot=0, zone=None, params=None, entite=None):
            n[0] += 1
            o.append({"id": f"{type_}-{n[0]}", "type": type_, "x": round(x, 2), "z": round(z, 2), "rot": rot, "zone": zone, "params": params or {}, "entite": entite})
            return o[-1]

        places = []

        def place(cle, usage, x, z, rot=0, zone=None):
            places.append({"cle": cle, "usage": usage, "x": round(x, 2), "z": round(z, 2), "rot": rot, "zone": zone})

        # --- l'accueil et le comptoir (x 10..20, z 20..28), entrée en façade
        obj("comptoir", 15, 23.2, 0, "accueil")
        place("poste-comptoir", "poste", 15, 22.1, 180, "accueil")
        obj("plante", 11, 27, 0, "accueil"); obj("plante", 19, 27, 0, "accueil")
        obj("borne", 12.2, 26.6, 0, "accueil", {"badgeuse": True})
        obj("table", 17.5, 26.3, 0, "accueil", {"l": 1.1, "p": 0.7, "basse": True}); obj("canape", 17.5, 27.3, 180, "accueil")
        obj("ecran_mural", 10.3, 24, 90, "accueil", {"contenu": "bienvenue"})
        obj("liasse", 13.6, 23.3, 0, "accueil")
        for i in range(2):
            place(f"attente-{i + 1}", "attente", 16.7 + i * 1.3, 26.3, 180, "accueil")
        # --- le magasin libre-service (x 20..32, z 20..28)
        for i in range(3):
            obj("gondole", 22.5 + i * 3.4, 24, 90, "magasin", {"famille": i})
        obj("panneau", 31, 27.2, 180, "magasin", {"texte": "LIBRE-SERVICE"})
        # --- le stockage (x 10..32, z 8..20) : rayonnages par famille
        for i in range(6):
            r = obj("rack", 12.5 + i * 3.4, 13.5, 90, "stockage", {"rang": i, "longueur": 9})
            place(f"rayon-{i + 1}", "rayon", 12.5 + i * 3.4, 13.5, 90, "stockage")
        obj("chariot", 31, 18.5, 0, "stockage")
        obj("palette", 29.5, 10, 0, "stockage"); obj("palette", 29.5, 11.5, 0, "stockage", {"haut": 2})
        # --- l'atelier et le SAV (x 32..40, z 8..28)
        obj("etabli", 34, 10, 90, "atelier"); obj("etabli", 34, 14, 90, "atelier")
        for i in range(3):
            place(f"etabli-{i + 1}", "etabli", 38.4, 10 + i * 2.2, -90, "atelier")
        obj("soudeuse", 33.5, 18, 0, "atelier"); obj("bac", 33.5, 20.5, 0, "atelier"); obj("nettoyeur", 38.5, 20, 0, "atelier")
        obj("armoire", 33, 25, 90, "atelier"); obj("armoire", 33, 26.5, 90, "atelier")
        place("poste-atelier", "poste", 35, 16, 0, "atelier")
        obj("panneau", 36, 8.6, 0, "atelier", {"texte": "ATELIER · SAV"})
        # --- l'aile des bureaux (x 40..54, z 8..20)
        obj("bureau", 43.5, 10.5, 0, "bureau", {"ecran": "cao"}); place("poste-bureau-1", "poste", 43.5, 11.5, 180, "bureau")
        obj("bureau", 43.5, 13, 0, "bureau", {"ecran": "tableur"}); place("poste-bureau-2", "poste", 43.5, 14, 180, "bureau")
        obj("plans", 41, 9, 0, "bureau"); obj("armoire", 46.5, 9.2, 0, "bureau"); obj("plante", 46.5, 13.3, 0, "bureau")
        obj("imprimante", 46.3, 11.3, -90, "bureau")
        obj("table", 43.5, 17, 0, "reunion", {"l": 3.2, "p": 1.3})
        for i in range(3):
            place(f"reunion-{i + 1}", "reunion", 42.4 + i * 1.1, 16.1, 0, "reunion")
            place(f"reunion-{i + 4}", "reunion", 42.4 + i * 1.1, 17.9, 180, "reunion")
        obj("ecran_mural", 40.3, 17, 90, "reunion", {"contenu": "presentation"})
        obj("bureau", 50.5, 10.5, 0, "administratif", {"ecran": "compta"}); place("poste-admin-1", "poste", 50.5, 11.5, 180, "administratif")
        obj("bureau", 50.5, 13, 0, "administratif", {"ecran": "crm"}); place("poste-admin-2", "poste", 50.5, 14, 180, "administratif")
        obj("armoire", 53.2, 9.2, -90, "administratif"); obj("dossiers", 52.8, 12.6, 0, "administratif"); obj("serveur", 53.3, 15.5, -90, "administratif")
        obj("machine_cafe", 53.2, 17.2, -90, "pause"); obj("table", 49.5, 18, 0, "pause", {"l": 1.4, "p": 0.8})
        obj("canape", 48, 19.2, 0, "pause"); obj("babyfoot", 51.5, 19.1, 0, "pause"); obj("plante", 47.5, 16.5, 0, "pause")
        for i in range(3):
            place(f"pause-{i + 1}", "pause", 48.7 + i * 0.9, 17.3, 0, "pause")
        # --- l'extérieur : parking clients, cour poids lourds, dépôt extérieur
        for i in range(5):
            place(f"parking-{i + 1}", "parking", 5.5 + i * 2.9, 33.5, 0, "parking")
        obj("lampadaire", 3.5, 31, 0, "parking"); obj("totem", 20.5, 30.5, 0, "parking", {"logo": True})
        obj("quai", 44, 21.2, 0, "cour")
        for i in range(4):
            place(f"camion-{i + 1}", "camion", 43 + i * 3.4, 33, 0, "cour")
        place("livraison", "livraison", 46, 25.5, 90, "cour")
        obj("cantilever", 24, 33, 0, "cour", {"longueur": 10}); obj("bobines", 33, 33, 0, "cour"); obj("prefa", 36, 37.5, 0, "cour")
        obj("benne", 56, 24, 90, "cour"); obj("minipelle", 55, 36, 180, "cour"); obj("tracteur", 29, 38, 0, "cour")
        obj("panneau", 58, 28, 180, "cour", {"texte": "DÉPÔT"})
        obj("lampadaire", 58, 34, 0, "cour")
        # --- chez les agriculteurs : les champs de l'autre côté de la route
        for i in range(6):
            place(f"champ-{i + 1}", "champ", 4 + i * 10.5, 56, 0, "champs")
        arbres = [[x, 4.5, 1] for x in range(2, 58, 5)] + [[x, 48.6, 0.8] for x in range(1, 64, 6)] + [[-1.5, z, 1] for z in range(8, 40, 5)] + [[61.5, z, 1] for z in range(8, 40, 5)]
        return {
            "unite": "m", "site": {"nom": "Dépôt", "largeur": 64, "profondeur": 64},
            "contour": [[10, 8], [54, 8], [54, 20], [40, 20], [40, 28], [10, 28]],
            "murs": [{"a": [10, 8], "b": [54, 8]}, {"a": [54, 8], "b": [54, 20]}, {"a": [54, 20], "b": [40, 20]}, {"a": [40, 20], "b": [40, 28]},
                     {"a": [40, 28], "b": [10, 28]}, {"a": [10, 28], "b": [10, 8]}],
            "portes": [{"a": [14, 28], "b": [16.5, 28], "nom": "entree_clients"}, {"a": [35, 28], "b": [38.5, 28], "nom": "porte_atelier", "grande": True},
                       {"a": [40, 22.5], "b": [40, 26.5], "nom": "porte_cour", "grande": True}, {"a": [54, 16.5], "b": [54, 18.5], "nom": "entree_equipe"}],
            "cloisons": [{"a": [32, 8], "b": [32, 28], "ouvertures": [[0.2, 0.32], [0.7, 0.82]], "basse": True},
                         {"a": [20, 20], "b": [32, 20], "ouvertures": [[0.1, 0.35], [0.6, 0.85]], "basse": True},
                         {"a": [40, 8], "b": [40, 20], "ouvertures": [[0.3, 0.45], [0.78, 0.92]]},
                         {"a": [47, 8], "b": [47, 20], "ouvertures": [[0.35, 0.5], [0.8, 0.95]]},
                         {"a": [40, 14.6], "b": [47, 14.6], "ouvertures": [[0.1, 0.3]]},
                         {"a": [47, 15.5], "b": [54, 15.5], "ouvertures": [[0.65, 0.85]]}],
            "zones": [
                {"cle": "accueil", "nom": "Accueil", "type": "accueil", "polygone": [[10, 20], [20, 20], [20, 28], [10, 28]], "sol": "carrelage"},
                {"cle": "magasin", "nom": "Magasin", "type": "magasin", "polygone": [[20, 20], [32, 20], [32, 28], [20, 28]], "sol": "carrelage"},
                {"cle": "stockage", "nom": "Stockage", "type": "stockage", "polygone": [[10, 8], [32, 8], [32, 20], [10, 20]], "sol": "beton"},
                {"cle": "atelier", "nom": "Atelier", "type": "atelier", "polygone": [[32, 8], [40, 8], [40, 28], [32, 28]], "sol": "beton_marque"},
                {"cle": "bureau", "nom": "Bureau d'étude", "type": "bureau", "polygone": [[40, 8], [47, 8], [47, 14.6], [40, 14.6]], "sol": "parquet"},
                {"cle": "reunion", "nom": "Réunion", "type": "reunion", "polygone": [[40, 14.6], [47, 14.6], [47, 20], [40, 20]], "sol": "moquette"},
                {"cle": "administratif", "nom": "Administratif", "type": "bureau", "polygone": [[47, 8], [54, 8], [54, 15.5], [47, 15.5]], "sol": "parquet"},
                {"cle": "pause", "nom": "Pause", "type": "pause", "polygone": [[47, 15.5], [54, 15.5], [54, 20], [47, 20]], "sol": "carrelage_chaud"},
                {"cle": "parking", "nom": "Parking clients", "type": "parking", "polygone": [[3, 30], [21, 30], [21, 40], [3, 40]], "sol": "enrobe", "exterieur": True},
                {"cle": "cour", "nom": "Cour et dépôt", "type": "cour", "polygone": [[21, 29], [60, 29], [60, 41], [21, 41]], "sol": "beton_ext", "exterieur": True},
                {"cle": "champs", "nom": "Chez les agriculteurs", "type": "champs", "polygone": [[0, 49], [64, 49], [64, 64], [0, 64]], "sol": "terre", "exterieur": True},
            ],
            "objets": o, "places": places,
            "exterieur": {
                "route": [[-6, 44.5], [70, 44.5]], "acces": [[[14, 40], [14, 44.5]], [[50, 41], [50, 44.5]]],
                "clotures": [[[2, 6], [60, 6]], [[2, 6], [2, 42]], [[60, 6], [60, 42]], [[2, 42], [11, 42]], [[17, 42], [47, 42]], [[53, 42], [60, 42]]],
                "arbres": arbres, "haies": [[[2, 29], [2, 41]]],
                "sol": [[-8, -2], [72, 66]],
            },
            "couloirs": [[15, 29.5], [20, 24], [31, 24], [36, 18], [36, 29.5], [42, 24], [55, 17.5], [45, 24], [50, 42], [14, 42]],
            "camera": {"azimut": 0.66, "polaire": 0.86, "cible": [32, 0, 28], "distance": 62},
            "secteur": SECTEUR["nom"],
        }

    def layout_json(self):
        self.ensure_one()
        return json.dumps(self.layout or {})
