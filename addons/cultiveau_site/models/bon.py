"""Les bons d'intervention saisis sur cultiveau.fr : le réalisé chez le client (articles, main-d'œuvre, déplacement, signatures)."""
from odoo import fields, models


class SiteBon(models.Model):
    _name = "cultiveau.site.bon"
    _description = "Bon d'intervention (cultiveau.fr)"
    _order = "date desc, id desc"
    _rec_name = "numero"

    connexion_id = fields.Many2one("cultiveau.site.connexion", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="connexion_id.company_id", store=True, string="Adhérent")
    ref = fields.Char("Référence cultiveau.fr", required=True, index=True)
    numero = fields.Char("Numéro")
    date = fields.Date("Date")
    statut = fields.Char("Statut")
    type_intervention = fields.Char("Type")
    partner_id = fields.Many2one("res.partner", "Client", index=True)
    client_nom = fields.Char("Client (sur le bon)")
    task_id = fields.Many2one("project.task", "Intervention", index=True)
    chantier_id = fields.Many2one("cultiveau.chantier", "Chantier", index=True)
    technicien = fields.Char("Technicien")
    equipement = fields.Char("Équipement")
    description = fields.Text("Description")
    observations = fields.Text("Observations")
    recommandations = fields.Text("Recommandations")
    duree_minutes = fields.Integer("Durée (min)")
    total_articles_ht = fields.Float("Articles HT")
    total_mo_ht = fields.Float("Main-d'œuvre HT")
    total_deplacement_ht = fields.Float("Déplacement HT")
    total_ht = fields.Float("Total HT")
    total_tva = fields.Float("TVA")
    total_ttc = fields.Float("Total TTC")
    signe_client = fields.Boolean("Signé par le client")
    signe_technicien = fields.Boolean("Signé par le technicien")
    exporte = fields.Boolean("Exporté (site)")
    modifie_sur_site = fields.Datetime("Modifié sur le site")
    ligne_ids = fields.One2many("cultiveau.site.bon.ligne", "bon_id", string="Lignes")

    _sql_constraints = [("ref_unique", "unique(connexion_id, ref)", "Un bon du site n'est importé qu'une fois.")]


class SiteBonLigne(models.Model):
    _name = "cultiveau.site.bon.ligne"
    _description = "Ligne d'un bon d'intervention (cultiveau.fr)"
    _order = "bon_id, sequence, id"

    bon_id = fields.Many2one("cultiveau.site.bon", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer()
    genre = fields.Selection([("article", "Article"), ("mo", "Main-d'œuvre"), ("machine", "Heures machine")], required=True)
    reference = fields.Char("Référence")
    designation = fields.Char("Désignation")
    product_id = fields.Many2one("product.product", "Article ERP")
    quantite = fields.Float("Quantité")
    unite = fields.Char("Unité")
    prix_unitaire_ht = fields.Float("Prix unitaire HT")
    remise = fields.Float("Remise (%)")
    tva = fields.Float("TVA (%)")
    total_ht = fields.Float("Total HT")
    duree_minutes = fields.Integer("Durée (min)")
