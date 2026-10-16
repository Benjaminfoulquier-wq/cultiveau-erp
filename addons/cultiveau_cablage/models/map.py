"""Le câblage sur la map (bureau d'étude), sur la fiche de l'installation et chez Mathis."""
from odoo import models


class Scene(models.AbstractModel):
    _inherit = "cultiveau.scene"

    def _actions(self):
        return {**super()._actions(), "cablage": ("cultiveau_cablage.action_armoires", {"name": "Dossiers de câblage"})}


class Map(models.AbstractModel):
    _inherit = "cultiveau.map"

    def _portes(self):
        portes = super()._portes()
        if "cablage" in self.env["cultiveau.scene"]._actions_disponibles():
            if "cablage" not in {p["cle"] for p in portes.get("bureau", [])}:
                portes.setdefault("bureau", []).append({"cle": "cablage", "nom": "Câblage des armoires", "icone": "fa-plug"})
        return portes

    def _fiche_dossier(self, company, iid):
        f = super()._fiche_dossier(company, iid)
        a = self.env["cultiveau.armoire"].sudo().search([("installation_id", "=", iid)], order="id desc", limit=1)
        if a:
            couleur = {"brouillon": "ambre", "compile": "bleu", "valide": "vert"}[a.etat]
            f["blocs"] = list(f.get("blocs", [])) + [{"titre": "Câblage", "lignes": [
                {"icone": "fa-plug", "texte": f"{a.name} · indice {a.indice}", "detail": f"{len(a.depart_ids)} départ(s) · {len(a.sortie_ids)} électrovanne(s) · {a.calibre_general_a or '—'} A",
                 "badge": dict(a._fields["etat"].selection)[a.etat], "couleur": couleur, "ouvrir": {"cle": "fiche", "modele": "cultiveau.armoire", "id": a.id}}]}]
        f["actions"] = f["actions"] + [{"cle": "cablage_dossier", "nom": "Câblage de l'armoire" if a else "Préparer le câblage", "icone": "fa-plug",
                                        "doaction": {"type": "ir.actions.server", "id": self.env.ref("cultiveau_cablage.action_serveur_cablage").id, "context": {"active_id": iid, "active_ids": [iid], "active_model": "cultiveau.installation"}}}]
        return f


class Mathis(models.AbstractModel):
    _inherit = "cultiveau.mathis"

    def _ecritures(self):
        return super()._ecritures() | {"compiler_cablage", "concevoir_cablage"}

    def _titres(self):
        return {**super()._titres(), "compiler_cablage": "Compiler le dossier de câblage", "concevoir_cablage": "Concevoir l'armoire et compiler"}

    def _outils(self):
        return super()._outils() + [
            {"type": "function", "function": {"name": "cablage", "description": "Le dossier de câblage (armoire de pompage, électrovannes) d'une installation : départs, courants, protections, "
                                                                               "démarrage, sections, calibre général, points à vérifier. installation_id : l'identifiant de l'installation.",
                                              "parameters": {"type": "object", "properties": {"installation_id": {"type": "integer"}}, "required": ["installation_id"]}}},
            {"type": "function", "function": {"name": "compiler_cablage", "description": "Prépare (depuis l'étude) et compile le dossier de câblage d'une installation : folios, borniers, nomenclature (après confirmation).",
                                              "parameters": {"type": "object", "properties": {"installation_id": {"type": "integer"}}, "required": ["installation_id"]}}},
            {"type": "function", "function": {"name": "concevoir_cablage", "description": "Conçoit l'armoire d'une installation d'après une description en français (pompes, alternance, secours, "
                                                                                          "sondes et flotteurs, variateur, télégestion, heures creuses…), remplit le dossier et compile les folios (après confirmation). "
                                                                                          "Reprendre dans « description » tout ce que la personne a dit de l'armoire.",
                                              "parameters": {"type": "object", "properties": {"installation_id": {"type": "integer"}, "description": {"type": "string"}}, "required": ["installation_id", "description"]}}},
        ]

    def _executer(self, nom, args):
        if nom == "concevoir_cablage":
            i = self.env["cultiveau.installation"].browse(int(args.get("installation_id") or 0)).exists()
            if not i:
                return {"erreur": "Installation introuvable."}, None
            a = self.env["cultiveau.armoire"].depuis_installation(i)
            res = a.concevoir(args.get("description") or "")
            return res, {"type": "lien", "modele": "cultiveau.armoire", "id": a.id, "libelle": f"{a.name} — {a.titre} (indice {a.indice})"}
        if nom in ("cablage", "compiler_cablage"):
            i = self.env["cultiveau.installation"].browse(int(args.get("installation_id") or 0)).exists()
            if not i:
                return {"erreur": "Installation introuvable."}, None
            Armoire = self.env["cultiveau.armoire"]
            if nom == "cablage":
                a = Armoire.search([("installation_id", "=", i.id)], order="id desc", limit=1)
                return (a.resume() if a else {"info": "Pas encore de dossier de câblage : proposer compiler_cablage."}), None
            a = Armoire.depuis_installation(i)
            a.action_compiler()
            return a.resume(), {"type": "lien", "modele": "cultiveau.armoire", "id": a.id, "libelle": f"{a.name} — {a.titre} (indice {a.indice})"}
        return super()._executer(nom, args)

    def _resumer(self, nom, args):
        if nom == "concevoir_cablage":
            return f"Concevoir l'armoire : {(args.get('description') or '')[:120]}"
        if nom == "compiler_cablage":
            i = self.env["cultiveau.installation"].browse(int(args.get("installation_id") or 0)).exists()
            return f"Compiler le câblage de « {i.name} »" if i else "Compiler le câblage"
        return super()._resumer(nom, args)
