"""Les enchaînements du pipeline : une étape franchie planifie l'activité suivante ; une affaire oubliée revient."""
from datetime import timedelta

from odoo import api, fields, models

JOURS_SANS_NOUVELLES = 14


class Lead(models.Model):
    _inherit = "crm.lead"

    cultiveau_jours_sans_action = fields.Integer("Jours sans action", compute="_compute_sans_action", help="Depuis le dernier message, activité faite ou changement d'étape.")
    cultiveau_nb_activites_faites = fields.Integer("Activités faites", compute="_compute_sans_action")

    @api.depends("message_ids", "date_last_stage_update", "write_date")
    def _compute_sans_action(self):
        Message = self.env["mail.message"].sudo()
        for l in self:
            if not l.id:
                l.cultiveau_jours_sans_action, l.cultiveau_nb_activites_faites = 0, 0
                continue
            msgs = Message.search([("model", "=", "crm.lead"), ("res_id", "=", l.id), ("message_type", "in", ("comment", "email", "notification"))], order="date desc", limit=1)
            repere = max(x for x in (msgs.date if msgs else None, l.date_last_stage_update, l.create_date) if x)
            l.cultiveau_jours_sans_action = (fields.Datetime.now() - repere).days
            l.cultiveau_nb_activites_faites = Message.search_count([("model", "=", "crm.lead"), ("res_id", "=", l.id), ("mail_activity_type_id", "!=", False)])

    def write(self, vals):
        avant = {l.id: l.stage_id for l in self} if "stage_id" in vals else {}
        res = super().write(vals)
        if "stage_id" in vals:
            for l in self:
                if avant.get(l.id) != l.stage_id:
                    l._cultiveau_enchainer()
        return res

    def _cultiveau_planifier(self, xmlid, jours=None, note=None):
        """Planifie l'activité si aucune du même type n'est déjà ouverte."""
        self.ensure_one()
        t = self.env.ref(xmlid, raise_if_not_found=False)
        if not t or self.activity_ids.filtered(lambda a: a.activity_type_id == t):
            return False
        date = fields.Date.context_today(self) + timedelta(days=jours if jours is not None else (t.delay_count or 1))
        return self.activity_schedule(activity_type_id=t.id, date_deadline=date, summary=t.summary or t.name, note=note, user_id=(self.user_id or self.env.user).id)

    def _cultiveau_enchainer(self):
        """Ce qu'une étape déclenche."""
        self.ensure_one()
        ref = lambda x: self.env.ref(f"cultiveau_ventes.{x}", raise_if_not_found=False)  # noqa: E731
        s = self.stage_id
        if s == ref("stage_analyse"):
            self._cultiveau_planifier("cultiveau_crm_effort.act_r1", 3, "Les huit données d'entrée de l'analyse des besoins (A1.1), validées avec l'exploitant.")
        elif s == ref("stage_etude"):
            self._cultiveau_planifier("cultiveau_crm_effort.act_r2", 7, "Présenter le devis par lots avec la note de dimensionnement (A1.2) et les engagements de performance.")
        elif s == ref("stage_devis"):
            self._cultiveau_planifier("cultiveau_crm_effort.act_relance", 7, "Le devis est parti : rappeler, répondre aux questions, parler financement et date de pose.")
        elif s == ref("stage_mise_en_service"):
            self._cultiveau_planifier("cultiveau_crm_effort.act_visite_chantier", 30, "Un mois après la mise en service : passer voir, écouter, proposer le contrat d'entretien.")
        # une étape franchie clôt la relance devenue sans objet
        if s and s != ref("stage_devis"):
            t = self.env.ref("cultiveau_crm_effort.act_relance", raise_if_not_found=False)
            if t:
                self.activity_ids.filtered(lambda a: a.activity_type_id == t).unlink()

    @api.model
    def _cultiveau_cron_reprendre_contact(self):
        """Les affaires ouvertes, avant la commande, sans activité planifiée ni mouvement depuis 14 jours : « Reprendre contact »."""
        limite = fields.Datetime.now() - timedelta(days=JOURS_SANS_NOUVELLES)
        commande = self.env.ref("cultiveau_ventes.stage_commande", raise_if_not_found=False)
        domaine = [("type", "=", "opportunity"), ("active", "=", True), ("probability", "<", 100), ("stage_id.is_won", "=", False), ("activity_ids", "=", False), ("write_date", "<", limite)]
        if commande:
            domaine.append(("stage_id.sequence", "<", commande.sequence))
        n = 0
        for l in self.search(domaine):
            if l.cultiveau_jours_sans_action >= JOURS_SANS_NOUVELLES:
                l._cultiveau_planifier("cultiveau_crm_effort.act_reprendre", 1, f"Aucune action depuis {l.cultiveau_jours_sans_action} jours : rappeler, ou marquer l'affaire perdue avec sa raison.")
                n += 1
        return n
