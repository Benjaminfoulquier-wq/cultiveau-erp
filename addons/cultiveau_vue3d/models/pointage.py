"""Les pointages : l'arrivée, la pause, le départ en intervention, le départ du soir. La badgeuse de l'accueil ou l'ERP lui-même.

Le statut de présence d'une personne se lit ici d'abord ; à défaut, dans ses interventions et chantiers du jour ; à défaut,
dans sa connexion à l'ERP (connecté = au poste).
"""
from datetime import timedelta

from odoo import api, fields, models

GENRES = [("arrivee", "Arrivée"), ("pause_debut", "Début de pause"), ("pause_fin", "Fin de pause"), ("depart_intervention", "Départ en intervention"),
          ("retour_intervention", "Retour d'intervention"), ("depart_chantier", "Départ sur chantier"), ("retour_chantier", "Retour de chantier"),
          ("reunion_debut", "Début de réunion"), ("reunion_fin", "Fin de réunion"), ("depart", "Départ")]
STATUT_APRES = {"arrivee": "au_poste", "pause_debut": "en_pause", "pause_fin": "au_poste", "depart_intervention": "en_intervention",
                "retour_intervention": "au_poste", "depart_chantier": "sur_chantier", "retour_chantier": "au_poste",
                "reunion_debut": "en_reunion", "reunion_fin": "au_poste", "depart": "parti"}


class Pointage(models.Model):
    _name = "cultiveau.pointage"
    _description = "Pointage (badgeuse)"
    _order = "horodatage desc, id desc"

    user_id = fields.Many2one("res.users", "Personne", required=True, index=True, ondelete="cascade")
    company_id = fields.Many2one("res.company", "Adhérent", required=True, default=lambda self: self.env.company, index=True)
    genre = fields.Selection(GENRES, "Pointage", required=True)
    horodatage = fields.Datetime("Le", required=True, default=fields.Datetime.now, index=True)
    source = fields.Selection([("badgeuse", "Badgeuse"), ("erp", "ERP"), ("map", "Map"), ("demo", "Démonstration")], "Source", default="erp")
    task_id = fields.Many2one("project.task", "Intervention")
    note = fields.Char("Note")
    evenement_id = fields.Many2one("cultiveau.evenement", "Événement", readonly=True)

    @api.model
    def badger(self, genre, user=None, source="erp", task=None, note=None, horodatage=None, company=None):
        """Un pointage, puis l'événement qui va avec (la map bouge)."""
        user = user or self.env.user
        company = company or user.company_id or self.env.company
        p = self.sudo().create({"user_id": user.id, "company_id": company.id, "genre": genre, "source": source, "task_id": task and task.id,
                                "note": note, "horodatage": horodatage or fields.Datetime.now()})
        libelles = dict(GENRES)
        p.evenement_id = self.env["cultiveau.evenement"].sudo().publier(genre, user, libelles[genre], f"{user.name} : {libelles[genre].lower()}" + (f" — {task.name}" if task else ""),
                                                                    {"statut": STATUT_APRES[genre], "user_id": user.id, "task_id": task and task.id}, company=company, demo=source == "demo")
        return p

    @api.model
    def du_jour(self, company, users=None):
        """Les pointages du jour (heure locale de la société), les plus récents d'abord."""
        debut = fields.Datetime.to_datetime(fields.Date.context_today(self.with_context(tz=company.partner_id.tz or "Europe/Paris")))
        debut = debut - timedelta(hours=2)  # la journée commence à 22 h la veille en UTC l'été : large
        domaine = [("company_id", "=", company.id), ("horodatage", ">=", debut)]
        if users is not None:
            domaine.append(("user_id", "in", users.ids))
        return self.sudo().search(domaine)

    @api.model
    def statut_depuis_pointages(self, pointages):
        """(statut, depuis, arrivé à) d'après les pointages d'une personne, du plus récent au plus ancien."""
        if not pointages:
            return None, None, None
        dernier = pointages[0]
        arrivee = next((p.horodatage for p in reversed(pointages) if p.genre == "arrivee"), None)
        return STATUT_APRES[dernier.genre], dernier.horodatage, arrivee
