import base64
from datetime import date

from odoo import api, fields, models


class ExportAssistant(models.TransientModel):
    _name = "cultiveau.export.assistant"
    _description = "Exporter la comptabilité"

    company_id = fields.Many2one("res.company", "Société", required=True, default=lambda self: self.env.company)
    genre = fields.Selection([("fec", "FEC — fichier des écritures comptables (format DGFiP)"), ("grand_livre", "Grand livre (CSV)"),
                              ("balance", "Balance (CSV)"), ("journaux", "Journaux (CSV)")], "Export", required=True, default="fec")
    date_debut = fields.Date("Du", required=True, default=lambda self: date(fields.Date.context_today(self).year, 1, 1))
    date_fin = fields.Date("Au", required=True, default=lambda self: date(fields.Date.context_today(self).year, 12, 31))

    @api.onchange("company_id")
    def _onchange_company(self):
        if self.company_id:
            fin = date(fields.Date.context_today(self).year, self.company_id.fiscalyear_last_month and int(self.company_id.fiscalyear_last_month) or 12, self.company_id.fiscalyear_last_day or 31)
            if fin > fields.Date.context_today(self):
                fin = fin.replace(year=fin.year - 1)
            self.date_fin = fin
            self.date_debut = (fin.replace(day=1) if fin.month == 12 else fin).replace(year=fin.year - 1 if fin.month != 12 else fin.year, month=fin.month % 12 + 1 if fin.month != 12 else 1, day=1)

    def action_exporter(self):
        self.ensure_one()
        nom, contenu = getattr(self.env["cultiveau.export.compta"], self.genre)(self.company_id, self.date_debut, self.date_fin)
        piece = self.env["ir.attachment"].create({"name": nom, "datas": base64.b64encode(contenu), "mimetype": "text/plain" if self.genre == "fec" else "text/csv"})
        return {"type": "ir.actions.act_url", "url": f"/web/content/{piece.id}?download=true", "target": "self"}
