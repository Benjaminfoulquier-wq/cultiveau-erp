"""Le tableau de l'effort commercial : les activités faites sur les affaires, par personne, par type et par mois (une vue SQL
sur les messages d'activité du fil)."""
from odoo import fields, models, tools


class EffortCommercial(models.Model):
    _name = "cultiveau.effort.commercial"
    _description = "Effort commercial (activités faites)"
    _auto = False
    _order = "date desc"

    date = fields.Datetime("Fait le", readonly=True)
    mois = fields.Char("Mois", readonly=True)
    user_id = fields.Many2one("res.users", "Par", readonly=True)
    activity_type_id = fields.Many2one("mail.activity.type", "Activité", readonly=True)
    lead_id = fields.Many2one("crm.lead", "Affaire", readonly=True)
    partner_id = fields.Many2one("res.partner", "Client", readonly=True)
    stage_id = fields.Many2one("crm.stage", "Étape actuelle", readonly=True)
    company_id = fields.Many2one("res.company", "Société", readonly=True)
    gagnee = fields.Boolean("Affaire gagnée", readonly=True)
    nombre = fields.Integer("Nombre", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT m.id AS id, m.date AS date, to_char(m.date, 'YYYY-MM') AS mois,
                       COALESCE(u.id, l.user_id) AS user_id, m.mail_activity_type_id AS activity_type_id,
                       l.id AS lead_id, l.partner_id AS partner_id, l.stage_id AS stage_id, l.company_id AS company_id,
                       COALESCE(s.is_won, false) AS gagnee, 1 AS nombre
                FROM mail_message m
                JOIN crm_lead l ON l.id = m.res_id
                LEFT JOIN res_users u ON u.partner_id = m.author_id
                LEFT JOIN crm_stage s ON s.id = l.stage_id
                WHERE m.model = 'crm.lead' AND m.mail_activity_type_id IS NOT NULL
            )""")
