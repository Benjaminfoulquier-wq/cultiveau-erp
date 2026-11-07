"""L'aide par écran : à quoi sert l'écran, par où commencer, où lire la suite."""
from odoo import api, fields, models


class Aide(models.Model):
    _name = "cultiveau.aide"
    _description = "Aide d'un écran"
    _order = "sequence, name"

    name = fields.Char("Écran", required=True)
    sequence = fields.Integer(default=10)
    action_xmlid = fields.Char("Action (identifiant externe)", help="Ex. cultiveau_vue3d.action_map. L'aide s'affiche sur cet écran.")
    res_model = fields.Char("Modèle", help="À défaut d'action : l'aide s'affiche sur tous les écrans de ce modèle (ex. sale.order).")
    resume = fields.Char("En une phrase", required=True)
    texte = fields.Html("Par où commencer", sanitize=True)
    doc = fields.Char("Documentation", help="Un lien : page du dépôt, tutoriel vidéo…")
    active = fields.Boolean(default=True)

    @api.model
    def pour(self, action_xmlid=None, res_model=None):
        """L'aide de l'écran courant : par action, sinon par modèle."""
        aide = self.env["cultiveau.aide"]
        if action_xmlid:
            aide = self.search([("action_xmlid", "=", action_xmlid)], limit=1)
        if not aide and res_model:
            aide = self.search([("res_model", "=", res_model), ("action_xmlid", "=", False)], limit=1) or self.search([("res_model", "=", res_model)], limit=1)
        if not aide:
            return False
        return {"id": aide.id, "nom": aide.name, "resume": aide.resume, "texte": aide.texte or "", "doc": aide.doc or "",
                "editable": self.env.user.has_group("cultiveau_base.group_equipe")}
