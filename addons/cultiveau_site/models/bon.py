"""Les bons d'intervention saisis sur cultiveau.fr : le réalisé chez le client (articles, main-d'œuvre, déplacement, signatures)."""
from odoo import api, fields, models
from odoo.exceptions import UserError


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

    invoice_id = fields.Many2one("account.move", "Facture", copy=False, readonly=True, index=True)
    a_facturer = fields.Boolean("À facturer", compute="_compute_a_facturer", store=True,
                                help="Signé par le client, chiffré, pas encore facturé dans l'ERP et pas exporté vers la comptabilité depuis cultiveau.fr.")

    _sql_constraints = [("ref_unique", "unique(connexion_id, ref)", "Un bon du site n'est importé qu'une fois.")]

    @api.depends("signe_client", "total_ht", "invoice_id", "exporte", "statut")
    def _compute_a_facturer(self):
        for b in self:
            b.a_facturer = bool(b.signe_client and b.total_ht and not b.invoice_id and not b.exporte and b.statut not in ("annule", "brouillon"))

    # ---------------------------------------------------------------- facturer dans l'ERP (10/11/2026)

    def _taxe(self, societe, taux, produit):
        """La taxe de vente de la société au taux du bon ; sinon celle de l'article, sinon celle de la société."""
        if taux:
            t = self.env["account.tax"].search([("company_id", "=", societe.id), ("type_tax_use", "=", "sale"), ("amount_type", "=", "percent"),
                                                ("amount", "=", taux), ("price_include", "=", False)], limit=1)
            if t:
                return t
        return produit.taxes_id.filtered(lambda t: t.company_id == societe)[:1] or societe.account_sale_tax_id

    def _lignes_facture(self, societe):
        self.ensure_one()
        lignes = [(0, 0, {"display_type": "line_section", "name": " ".join(x for x in (
            f"Bon {self.numero or self.ref}", self.date and f"du {self.date.strftime('%d/%m/%Y')}", self.equipement and f"— {self.equipement}") if x)})]
        for l in self.ligne_ids.sorted(lambda l: (l.sequence, l.id)):
            if l.genre == "machine" and not l.total_ht:
                continue  # les heures machine sans prix sont une information du bon, pas une ligne de facture
            quantite, prix = l.quantite, l.prix_unitaire_ht
            if not quantite or not prix:
                quantite, prix = 1, l.total_ht
            if not prix:
                continue
            nom = l.designation or l.product_id.display_name or ("Main-d'œuvre" if l.genre == "mo" else "Article")
            if l.reference and l.reference not in nom:
                nom = f"[{l.reference}] {nom}"
            lignes.append((0, 0, {"product_id": l.product_id.id or False, "name": nom, "quantity": quantite, "price_unit": prix, "discount": l.remise,
                                  "tax_ids": [(6, 0, self._taxe(societe, l.tva, l.product_id).ids)]}))
        if self.total_deplacement_ht:
            lignes.append((0, 0, {"name": "Déplacement", "quantity": 1, "price_unit": self.total_deplacement_ht,
                                  "tax_ids": [(6, 0, self._taxe(societe, 0, self.env["product.product"]).ids)]}))
        return lignes

    def action_facturer(self):
        """Une facture brouillon par client : ses bons du site signés, chacun en section. Un bon déjà exporté vers la comptabilité
        depuis cultiveau.fr n'est pas repris (il serait facturé deux fois), sauf demande expresse sur sa fiche."""
        if not self.env.user.has_group("account.group_account_invoice"):
            raise UserError("Votre accès ne permet pas de créer des factures : demandez-le au gérant.")
        force = self.env.context.get("cultiveau_malgre_export")
        deja = self.filtered("invoice_id")
        exportes = (self - deja).filtered("exporte")
        bons = (self - deja).filtered(lambda b: b.signe_client and b.total_ht and (force or not b.exporte))
        if not bons:
            if exportes and not force:
                raise UserError("Ces bons ont déjà été exportés vers la comptabilité depuis cultiveau.fr : les facturer ici ferait une "
                                "deuxième facture. Pour le faire quand même, ouvrez le bon et utilisez « Facturer malgré l'export ».")
            raise UserError("Rien à facturer : seuls les bons signés par le client, chiffrés et pas encore facturés le sont.")
        sans_client = bons.filtered(lambda b: not b.partner_id)
        if sans_client:
            raise UserError("Pas de client relié sur : %s. Reliez le client sur cultiveau.fr puis relancez la synchronisation." % ", ".join(
                b.numero or b.ref for b in sans_client))
        factures = self.env["account.move"]
        for (partner, societe), lot in bons.grouped(lambda b: (b.partner_id.commercial_partner_id, b.company_id)).items():
            lignes = []
            for b in lot.sorted(lambda b: (b.date or fields.Date.today(), b.id)):
                lignes += b._lignes_facture(societe)
            facture = self.env["account.move"].with_company(societe).create({
                "move_type": "out_invoice", "partner_id": partner.id, "company_id": societe.id,
                "invoice_origin": ", ".join(b.numero or b.ref for b in lot), "invoice_line_ids": lignes})
            lot.sudo().write({"invoice_id": facture.id})
            attendu = sum(lot.mapped("total_ht"))
            if abs(facture.amount_untaxed - attendu) > 0.05:
                facture.message_post(body=f"Écart avec cultiveau.fr : les bons totalisent {attendu:.2f} € HT, la facture {facture.amount_untaxed:.2f} € HT. "
                                          "À vérifier avant de valider.")
            factures |= facture
        action = {"type": "ir.actions.act_window", "res_model": "account.move", "context": {"default_move_type": "out_invoice"}}
        if len(factures) == 1:
            return {**action, "res_id": factures.id, "view_mode": "form", "views": [(False, "form")]}
        return {**action, "name": "Factures des bons", "view_mode": "list,form", "views": [(False, "list"), (False, "form")], "domain": [("id", "in", factures.ids)]}

    def action_facturer_malgre_export(self):
        return self.with_context(cultiveau_malgre_export=True).action_facturer()

    def action_voir_facture(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "res_model": "account.move", "res_id": self.invoice_id.id, "view_mode": "form", "views": [(False, "form")]}


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
