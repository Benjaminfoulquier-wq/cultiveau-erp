"""Le flux d'activité : chaque action métier écrit une ligne {genre, modèle, id, titre, texte, acteur, charge}.

La map s'y abonne en temps réel (bus) pour déclencher une animation et une notification ; le fil d'activité et le journal
d'audit le lisent. Un événement par société, sur le canal « cultiveau_map_<société> ».
"""
import json

from odoo import api, fields, models

GENRES = [
    ("arrivee", "Arrivée"), ("pause_debut", "Pause"), ("pause_fin", "Fin de pause"), ("depart_intervention", "Départ en intervention"),
    ("retour_intervention", "Retour d'intervention"), ("depart_chantier", "Départ sur chantier"), ("retour_chantier", "Retour de chantier"),
    ("reunion_debut", "Réunion"), ("reunion_fin", "Fin de réunion"), ("depart", "Départ"),
    ("intervention_creee", "Intervention créée"), ("intervention_demarree", "Intervention démarrée"), ("intervention_terminee", "Intervention terminée"),
    ("bon_signe", "Bon signé"), ("devis_envoye", "Devis envoyé"), ("devis_signe", "Devis signé"), ("facture_payee", "Facture payée"),
    ("chantier_demarre", "Chantier démarré"), ("chantier_termine", "Chantier terminé"), ("mise_en_service", "Mise en service"),
    ("livraison", "Livraison reçue"), ("sortie_stock", "Sortie de stock"), ("stock_bas", "Stock bas"), ("alerte_irrigation", "Alerte irrigation"),
    ("etape", "Changement d'étape"), ("appel", "Appel téléphonique"), ("reunion", "Réunion"), ("ambiance", "Ambiance"), ("autre", "Autre"),
]


class Evenement(models.Model):
    _name = "cultiveau.evenement"
    _description = "Événement de la Map vivante"
    _order = "horodatage desc, id desc"

    company_id = fields.Many2one("res.company", "Adhérent", required=True, default=lambda self: self.env.company, index=True)
    genre = fields.Selection(GENRES, "Genre", required=True, index=True)
    modele = fields.Char("Modèle")
    res_id = fields.Integer("Enregistrement")
    titre = fields.Char("Titre", required=True)
    texte = fields.Char("Texte")
    acteur_id = fields.Many2one("res.users", "Acteur", default=lambda self: self.env.user)
    horodatage = fields.Datetime("Le", default=fields.Datetime.now, required=True, index=True)
    charge = fields.Json("Charge")
    demo = fields.Boolean("Démonstration", default=False)

    @api.model
    def publier(self, genre, record=None, titre="", texte="", charge=None, company=None, demo=False):
        """Écrit l'événement et le pousse sur le canal de la société."""
        genres = dict(self._fields["genre"].selection)  # avec les genres ajoutés par les autres modules
        if genre not in genres:
            genre = "autre"
        company = company or (record is not None and getattr(record, "company_id", None)) or self.env.company
        if not company:
            company = self.env.company
        e = self.sudo().create({"company_id": company.id, "genre": genre, "modele": record is not None and record._name or False,
                                "res_id": record is not None and record.id or 0, "titre": titre or genres[genre], "texte": texte,
                                "acteur_id": self.env.user.id, "charge": charge or {}, "demo": demo})
        self.env["bus.bus"].sudo()._sendone(self.canal(company), "cultiveau_map", e.charge_utile())
        return e

    @api.model
    def canal(self, company):
        return f"cultiveau_map_{company.id}"

    def charge_utile(self):
        self.ensure_one()
        return {"id": self.id, "genre": self.genre, "modele": self.modele, "res_id": self.res_id, "titre": self.titre, "texte": self.texte or "",
                "acteur": self.acteur_id.name or "", "horodatage": fields.Datetime.to_string(self.horodatage), "charge": self.charge or {}, "demo": self.demo}

    @api.model
    def recents(self, company=None, limite=30):
        company = company or self.env.company
        return [e.charge_utile() for e in self.sudo().search([("company_id", "=", company.id)], limit=limite)]

    def json(self):
        return json.dumps([e.charge_utile() for e in self])
