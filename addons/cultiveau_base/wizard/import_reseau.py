import base64
import json

from markupsafe import Markup, escape

from odoo import fields, models
from odoo.exceptions import UserError


class ImportReseau(models.TransientModel):
    _name = "cultiveau.import.reseau"
    _description = "Importer le réseau Cultiveau (fichier JSON)"

    fichier = fields.Binary("Fichier du réseau (.json)", required=True)
    nom_fichier = fields.Char()
    resultat = fields.Html("Résultat", readonly=True, sanitize=False)

    def action_importer(self):
        self.ensure_one()
        try:
            donnees = json.loads(base64.b64decode(self.fichier).decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as e:
            raise UserError(f"Ce fichier n'est pas le JSON du réseau : {e}.") from e
        bilan = self.env["cultiveau.reseau.moteur"].importer(donnees)
        lignes = [("Sociétés de l'ERP (groupe, adhérents)", f"{bilan['societes_odoo_creees']} créées, {bilan['societes_odoo_maj']} mises à jour"),
                  ("Fournisseurs et prospects", f"{bilan['societes_creees']} créés, {bilan['societes_maj']} mis à jour"),
                  ("Contacts", f"{bilan['contacts_crees']} créés, {bilan['contacts_maj']} mis à jour"),
                  ("Comptes de l'équipe", f"{bilan['utilisateurs_crees']} créés, {bilan['utilisateurs_maj']} mis à jour"),
                  ("Opportunités d'adhésion", str(bilan["prospects"])), ("Réglages", str(bilan["reglages"]))]
        texte = "<ul>" + "".join(f"<li><b>{escape(a)}</b> : {escape(b)}</li>" for a, b in lignes) + "</ul>"
        if bilan["erreurs"]:
            texte += "<p>À regarder :</p><ul>" + "".join(f"<li>{escape(e)}</li>" for e in bilan["erreurs"]) + "</ul>"
        self.resultat = Markup(texte)
        return {"type": "ir.actions.act_window", "res_model": self._name, "res_id": self.id, "view_mode": "form", "target": "new"}
