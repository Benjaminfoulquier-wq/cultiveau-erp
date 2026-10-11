import base64

from odoo import fields, models


class ImportTelepac(models.TransientModel):
    _name = "cultiveau.import.telepac"
    _description = "Importer la déclaration PAC d'un client"

    partner_id = fields.Many2one("res.partner", "Client", required=True)
    fichier = fields.Binary("Fichier Telepac", required=True)
    nom_fichier = fields.Char("Nom du fichier")
    campagne = fields.Integer("Campagne PAC", required=True, default=lambda self: fields.Date.context_today(self).year)

    def action_importer(self):
        self.ensure_one()
        bilan = self.env["cultiveau.parcelle"].importer(self.partner_id, self.nom_fichier, base64.b64decode(self.fichier), self.campagne)
        message = f"{bilan['parcelles']} parcelles lues ({bilan['creees']} nouvelles)."
        if bilan["codes_inconnus"]:
            message += f" Codes PAC à relier à une culture : {', '.join(bilan['codes_inconnus'])} (menu Parcelles → Codes cultures PAC)."
        if bilan["sans_contour"]:
            message += f" {bilan['sans_contour']} parcelle(s) sans contour lisible : pas de suivi satellite pour elles."
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"title": "Déclaration PAC importée", "message": message, "sticky": bool(bilan["codes_inconnus"]),
                           "type": "warning" if bilan["codes_inconnus"] else "success",
                           "next": self.partner_id.action_voir_parcelles()}}
