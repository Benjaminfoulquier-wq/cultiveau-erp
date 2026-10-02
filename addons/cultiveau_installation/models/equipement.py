from odoo import api, fields, models

# Durées de vie indicatives du référentiel (§ 3.9), en années : la valeur médiane de la fourchette.
CATEGORIES = [
    ("pompe", "Pompe", 15), ("moteur", "Moteur", 20), ("variateur", "Variateur / armoire", 12), ("groupe_thermique", "Groupe motopompe thermique", 15),
    ("filtration", "Filtration (corps)", 20), ("fertigation", "Fertigation", 10), ("canalisation_enterree", "Canalisation enterrée", 35),
    ("aluminium", "Conduites aluminium", 20), ("gaine", "Gaine goutte à goutte", 4), ("goutte_enterre", "Goutte à goutte enterré", 12),
    ("asperseur", "Asperseurs / canons", 12), ("enrouleur", "Enrouleur", 20), ("pivot", "Pivot / rampe", 20), ("vanne", "Vannes, électrovannes", 10),
    ("programmateur", "Programmateur / automatisme", 10), ("capteur", "Capteurs, sondes, compteurs", 8), ("reserve", "Réserve / retenue", 30), ("autre", "Autre", 10),
]
DUREES = {code: duree for code, _l, duree in CATEGORIES}


class Equipement(models.Model):
    _name = "cultiveau.equipement"
    _description = "Équipement posé chez un agriculteur"
    _order = "installation_id, categorie, name"

    installation_id = fields.Many2one("cultiveau.installation", "Installation", required=True, ondelete="cascade", index=True)
    partner_id = fields.Many2one(related="installation_id.partner_id", store=True)
    company_id = fields.Many2one(related="installation_id.company_id", store=True)
    categorie = fields.Selection([(c, l) for c, l, _d in CATEGORIES], "Catégorie", required=True, default="autre")
    name = fields.Char("Désignation", required=True, help="Marque, modèle, taille : « Pompe Caprari E6S 30 m³/h », « Pivot Valley 7 travées »…")
    product_id = fields.Many2one("product.template", "Article du catalogue", help="Si l'équipement est au catalogue : fiche technique, pièces.")
    marque = fields.Char("Marque")
    modele = fields.Char("Modèle")
    numero_serie = fields.Char("N° de série")
    caracteristiques = fields.Char("Caractéristiques (puissance, débit, DN…)")
    annee_pose = fields.Integer("Année de pose")
    duree_vie_ans = fields.Integer("Durée de vie indicative (ans)", compute="_compute_duree_vie", store=True, readonly=False,
                                   help="D'après le référentiel (§ 3.9) ; modifiable.")
    fin_vie_estimee = fields.Integer("Renouvellement vers", compute="_compute_fin_vie", store=True)
    a_renouveler = fields.Boolean("À renouveler sous 2 ans", compute="_compute_fin_vie", store=True)
    notice_url = fields.Char("Notice / fiche technique (lien)")
    notes = fields.Char("Notes")
    actif = fields.Boolean("En service", default=True)

    @api.depends("categorie")
    def _compute_duree_vie(self):
        """La durée du référentiel pour la catégorie ; une valeur saisie à la main tient jusqu'au changement de catégorie."""
        for e in self:
            e.duree_vie_ans = DUREES.get(e.categorie, 10)

    @api.depends("annee_pose", "duree_vie_ans")
    def _compute_fin_vie(self):
        annee = fields.Date.context_today(self).year
        for e in self:
            e.fin_vie_estimee = (e.annee_pose + e.duree_vie_ans) if e.annee_pose and e.duree_vie_ans else 0
            e.a_renouveler = bool(e.fin_vie_estimee and e.fin_vie_estimee <= annee + 2)

    @api.onchange("product_id")
    def _onchange_product(self):
        if self.product_id and not self.name:
            self.name = self.product_id.name
        if self.product_id and self.product_id.cultiveau_fiche_url and not self.notice_url:
            self.notice_url = self.product_id.cultiveau_fiche_url

    @api.depends("name", "categorie", "annee_pose")
    def _compute_display_name(self):
        for e in self:
            e.display_name = f"{e.name}" + (f" ({e.annee_pose})" if e.annee_pose else "")
