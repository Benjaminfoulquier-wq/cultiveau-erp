"""Le bon d'intervention : ce que le technicien a fait chez le client, chiffré, signé sur place, facturé ensuite."""
from odoo import api, fields, models
from odoo.exceptions import UserError

ETATS = [("brouillon", "En cours"), ("signe", "Signé"), ("facture", "Facturé"), ("annule", "Annulé")]
GENRES = [("piece", "Pièce"), ("mo", "Main-d'œuvre"), ("deplacement", "Déplacement"), ("autre", "Autre")]


class Bon(models.Model):
    _name = "cultiveau.bon"
    _description = "Bon d'intervention"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    name = fields.Char("Bon", required=True, copy=False, readonly=True, default="Nouveau")
    etat = fields.Selection(ETATS, "État", default="brouillon", required=True, tracking=True, index=True)
    task_id = fields.Many2one("project.task", "Intervention", index=True, domain="[('cultiveau_intervention', '=', True)]")
    chantier_id = fields.Many2one("cultiveau.chantier", "Chantier", index=True)
    partner_id = fields.Many2one("res.partner", "Client", required=True, index=True, tracking=True)
    installation_id = fields.Many2one("cultiveau.installation", "Installation", domain="[('partner_id', 'child_of', partner_id)]")
    company_id = fields.Many2one("res.company", "Adhérent", required=True, default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one(related="company_id.currency_id")
    user_ids = fields.Many2many("res.users", "cultiveau_bon_technicien_rel", "bon_id", "user_id", string="Techniciens",
                                default=lambda self: self.env.user)
    date = fields.Date("Date", required=True, default=fields.Date.context_today)
    heure_arrivee = fields.Float("Arrivée")
    heure_depart = fields.Float("Départ")
    duree_heures = fields.Float("Temps passé (h)", compute="_compute_duree", store=True, readonly=False)
    trajet_km = fields.Float("Trajet (km aller-retour)")
    forfait_deplacement = fields.Boolean("Forfait déplacement")
    travaux = fields.Text("Travaux réalisés")
    observations = fields.Text("Observations")
    recommandations = fields.Text("Recommandations au client")
    ligne_ids = fields.One2many("cultiveau.bon.ligne", "bon_id", string="Lignes", copy=True)
    montant_ht = fields.Monetary("Total HT", compute="_compute_montants", store=True)
    montant_ttc = fields.Monetary("Total TTC", compute="_compute_montants", store=True)
    # les relevés, comparés au PV de mise en service de l'installation
    pression_pompe_mesuree = fields.Float("Pression sortie pompe mesurée (bar)")
    pression_defavorable_mesuree = fields.Float("Pression au point défavorable mesurée (bar)")
    pression_pompe_reference = fields.Float(related="installation_id.pv_pression_sortie_pompe_bar", string="Référence PV sortie pompe")
    pression_defavorable_reference = fields.Float(related="installation_id.pv_pression_point_defavorable_bar", string="Référence PV point défavorable")
    ecart_pct = fields.Float("Écart au PV (%)", compute="_compute_ecart", store=True)
    alerte_ecart = fields.Boolean("Écart à surveiller", compute="_compute_ecart", store=True)
    # la signature, sur place
    signe_par = fields.Char("Signé par (client)")
    signature_client = fields.Binary("Signature du client", attachment=True, copy=False)
    signature_technicien = fields.Binary("Signature du technicien", attachment=True, copy=False)
    signe_le = fields.Datetime("Signé le", readonly=True, copy=False)
    cloturer = fields.Boolean("Clore l'intervention à la signature", default=True)
    demander_avis = fields.Boolean("Demander l'avis du client", help="À la signature, le client reçoit un e-mail pour noter l'intervention.")
    picking_id = fields.Many2one("stock.picking", "Sortie de stock", readonly=True, copy=False)
    invoice_id = fields.Many2one("account.move", "Facture", readonly=True, copy=False, index=True)
    nb_photos = fields.Integer("Photos", compute="_compute_nb_photos")

    @api.depends("heure_arrivee", "heure_depart")
    def _compute_duree(self):
        for b in self:
            if b.heure_depart and b.heure_depart > b.heure_arrivee:
                b.duree_heures = round(b.heure_depart - b.heure_arrivee, 2)

    @api.depends("ligne_ids.sous_total", "ligne_ids.total_ttc")
    def _compute_montants(self):
        for b in self:
            b.montant_ht = sum(b.ligne_ids.mapped("sous_total"))
            b.montant_ttc = sum(b.ligne_ids.mapped("total_ttc"))

    @api.depends("pression_pompe_mesuree", "pression_defavorable_mesuree", "installation_id.pv_pression_sortie_pompe_bar",
                 "installation_id.pv_pression_point_defavorable_bar")
    def _compute_ecart(self):
        """L'écart le plus grand entre une pression mesurée et sa référence du PV ; au-delà de 15 %, on surveille."""
        for b in self:
            ecarts = []
            for mesure, reference in ((b.pression_pompe_mesuree, b.installation_id.pv_pression_sortie_pompe_bar),
                                      (b.pression_defavorable_mesuree, b.installation_id.pv_pression_point_defavorable_bar)):
                if mesure and reference:
                    ecarts.append((mesure - reference) / reference * 100)
            b.ecart_pct = max(ecarts, key=abs) if ecarts else 0.0
            b.alerte_ecart = bool(ecarts) and abs(b.ecart_pct) >= 15

    def _compute_nb_photos(self):
        for b in self:
            b.nb_photos = self.env["ir.attachment"].search_count([("res_model", "=", self._name), ("res_id", "=", b.id), ("mimetype", "ilike", "image/")])

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "Nouveau") == "Nouveau":
                vals["name"] = self.env["ir.sequence"].next_by_code("cultiveau.bon") or "Nouveau"
        return super().create(vals_list)

    @api.onchange("task_id")
    def _onchange_task(self):
        t = self.task_id
        if t:
            self.partner_id = t.partner_id
            self.installation_id = t.cultiveau_installation_id
            self.company_id = t.company_id
            if t.user_ids.filtered("active"):
                self.user_ids = t.user_ids.filtered("active")
            if not self.ligne_ids and t.cultiveau_piece_ids:
                self.ligne_ids = [(0, 0, {"genre": "piece", "product_id": p.product_id.id, "quantite": p.quantite, "description": p.note or p.product_id.display_name})
                                  for p in t.cultiveau_piece_ids]

    # ---------------------------------------------------------------- chiffrer

    def action_chiffrer_temps(self):
        """Ajoute (ou met à jour) la main-d'œuvre et le déplacement d'après le temps passé et les kilomètres."""
        for b in self:
            mo = self.env.ref("cultiveau_terrain.produit_main_oeuvre")
            km = self.env.ref("cultiveau_terrain.produit_deplacement_km")
            forfait = self.env.ref("cultiveau_terrain.produit_deplacement_forfait")
            heures = b.duree_heures * max(1, len(b.user_ids))
            b._ligne_auto("mo", mo, heures, f"Main-d'œuvre : {b.duree_heures:g} h × {max(1, len(b.user_ids))} technicien(s)")
            if b.forfait_deplacement:
                b._ligne_auto("deplacement", forfait, 1, "Forfait déplacement")
            elif b.trajet_km:
                b._ligne_auto("deplacement", km, b.trajet_km, f"Déplacement : {b.trajet_km:g} km")

    def _ligne_auto(self, genre, produit, quantite, description):
        ligne = self.ligne_ids.filtered(lambda l: l.genre == genre and l.auto)
        if not quantite:
            ligne.unlink()
            return
        valeurs = {"genre": genre, "product_id": produit.id, "quantite": quantite, "description": description, "auto": True,
                   "prix_unitaire": produit.with_company(self.company_id).lst_price}
        if ligne:
            ligne[:1].write(valeurs)
        else:
            self.ligne_ids = [(0, 0, valeurs)]

    # ---------------------------------------------------------------- signer

    def action_signer(self):
        for b in self:
            if b.etat != "brouillon":
                continue
            if not b.signature_client or not b.signe_par:
                raise UserError("Faites signer le client et indiquez son nom.")
            if not b.ligne_ids:
                raise UserError("Le bon est vide : ajoutez les pièces, puis « Chiffrer le temps et le déplacement ».")
            b.write({"etat": "signe", "signe_le": fields.Datetime.now()})
            b._sortir_les_pieces()
            if b.task_id and b.cloturer:
                b.task_id._cultiveau_cloturer_depuis_bon(b)
            if b.task_id and b.demander_avis and b.partner_id.email:
                modele = self.env.ref("project.rating_project_request_email_template", raise_if_not_found=False)
                if modele:
                    b.task_id.rating_send_request(modele, lang=b.partner_id.lang, force_send=False)
            if b.alerte_ecart:
                b.message_post(body=f"⚠ Écart de {b.ecart_pct:+.0f} % aux pressions du PV de mise en service : à surveiller.")
                b.activity_schedule("mail.mail_activity_data_todo", summary=f"Écart de {b.ecart_pct:+.0f} % au PV : proposer un diagnostic",
                                    user_id=(b.installation_id.user_id or b.env.user).id)

    def _sortir_les_pieces(self):
        """Les pièces stockées sortent du camion du technicien (ou du stock de l'adhérent) vers le client."""
        self.ensure_one()
        pieces = self.ligne_ids.filtered(lambda l: l.product_id.is_storable and l.quantite > 0)
        if not pieces:
            return
        entrepot = self.env["stock.warehouse"].search([("company_id", "=", self.company_id.id)], limit=1)
        if not entrepot:
            return
        type_sortie = entrepot.out_type_id
        technicien = self.user_ids[:1]
        source = technicien.cultiveau_camion_id if technicien and technicien.cultiveau_camion_id.company_id in (self.company_id, self.env["res.company"]) else type_sortie.default_location_src_id
        destination = self.partner_id.property_stock_customer
        picking = self.env["stock.picking"].create({
            "picking_type_id": type_sortie.id, "partner_id": self.partner_id.id, "origin": self.name, "company_id": self.company_id.id,
            "location_id": source.id, "location_dest_id": destination.id,
            "move_ids": [(0, 0, {"name": l.product_id.display_name, "product_id": l.product_id.id, "product_uom_qty": l.quantite, "product_uom": l.product_id.uom_id.id,
                                 "location_id": source.id, "location_dest_id": destination.id, "company_id": self.company_id.id}) for l in pieces],
        })
        picking.action_confirm()
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
            move.picked = True
        picking.with_context(skip_backorder=True, skip_sanity_check=True).button_validate()
        self.picking_id = picking

    def action_remettre_en_cours(self):
        for b in self:
            if b.invoice_id and b.invoice_id.state != "cancel":
                raise UserError("Le bon est déjà facturé : annulez d'abord la facture.")
            b.write({"etat": "brouillon", "signe_le": False})

    def action_annuler(self):
        self.filtered(lambda b: not b.invoice_id).write({"etat": "annule"})

    # ---------------------------------------------------------------- facturer

    def action_facturer(self):
        """Une facture par client : les bons signés de ce client, chacun en section."""
        bons = self.filtered(lambda b: b.etat == "signe" and not b.invoice_id)
        if not bons:
            raise UserError("Rien à facturer : seuls les bons signés et pas encore facturés le sont.")
        factures = self.env["account.move"]
        for (partner, societe), lot in bons.grouped(lambda b: (b.partner_id.commercial_partner_id, b.company_id)).items():
            lignes = []
            for b in lot.sorted("date"):
                lignes.append((0, 0, {"display_type": "line_section", "name": f"{b.name} du {b.date.strftime('%d/%m/%Y')}"
                                                                          + (f" — {b.installation_id.name}" if b.installation_id else "")}))
                for l in b.ligne_ids:
                    taxes = l.product_id.taxes_id.filtered(lambda t: t.company_id == societe) or societe.account_sale_tax_id
                    lignes.append((0, 0, {"product_id": l.product_id.id, "name": l.description or l.product_id.display_name, "quantity": l.quantite,
                                          "price_unit": l.prix_unitaire, "discount": l.remise, "tax_ids": [(6, 0, taxes.ids)]}))
            facture = self.env["account.move"].with_company(societe).create({
                "move_type": "out_invoice", "partner_id": partner.id, "company_id": societe.id, "invoice_origin": ", ".join(lot.mapped("name")),
                "invoice_line_ids": lignes})
            lot.write({"invoice_id": facture.id, "etat": "facture"})
            factures |= facture
        action = {"type": "ir.actions.act_window", "res_model": "account.move", "context": {"default_move_type": "out_invoice"}}
        if len(factures) == 1:
            return {**action, "res_id": factures.id, "view_mode": "form", "views": [(False, "form")]}
        return {**action, "name": "Factures des bons", "view_mode": "list,form", "views": [(False, "list"), (False, "form")], "domain": [("id", "in", factures.ids)]}

    # ---------------------------------------------------------------- envoyer, voir

    def action_envoyer(self):
        self.ensure_one()
        modele = self.env.ref("cultiveau_terrain.modele_mail_bon")
        return {"type": "ir.actions.act_window", "res_model": "mail.compose.message", "view_mode": "form", "target": "new",
                "context": {"default_model": self._name, "default_res_ids": self.ids, "default_template_id": modele.id, "default_composition_mode": "comment",
                            "force_email": True}}

    def action_voir_photos(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "name": "Photos", "res_model": "ir.attachment", "view_mode": "kanban,list",
                "domain": [("res_model", "=", self._name), ("res_id", "=", self.id), ("mimetype", "ilike", "image/")],
                "context": {"default_res_model": self._name, "default_res_id": self.id}}


class BonLigne(models.Model):
    _name = "cultiveau.bon.ligne"
    _description = "Ligne de bon d'intervention"
    _order = "bon_id, sequence, id"

    bon_id = fields.Many2one("cultiveau.bon", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    genre = fields.Selection(GENRES, "Genre", default="piece", required=True)
    product_id = fields.Many2one("product.product", "Article", required=True, domain=[("sale_ok", "=", True)])
    description = fields.Char("Description")
    quantite = fields.Float("Quantité", default=1.0, digits="Product Unit of Measure")
    uom_id = fields.Many2one(related="product_id.uom_id", string="Unité")
    prix_unitaire = fields.Float("Prix unitaire HT", digits="Product Price")
    remise = fields.Float("Remise (%)")
    sous_total = fields.Float("Total HT", compute="_compute_totaux", store=True)
    total_ttc = fields.Float("Total TTC", compute="_compute_totaux", store=True)
    auto = fields.Boolean("Calculée", help="Ligne calculée d'après le temps passé ou les kilomètres.")

    @api.onchange("product_id")
    def _onchange_product(self):
        if self.product_id:
            societe = self.bon_id.company_id or self.env.company
            self.prix_unitaire = self.product_id.with_company(societe).lst_price
            self.description = self.product_id.display_name
            if self.product_id.type == "service" and self.genre == "piece":
                self.genre = "autre"

    @api.depends("quantite", "prix_unitaire", "remise", "product_id")
    def _compute_totaux(self):
        for l in self:
            ht = l.quantite * l.prix_unitaire * (1 - (l.remise or 0) / 100)
            societe = l.bon_id.company_id or self.env.company
            taxes = l.product_id.taxes_id.filtered(lambda t: t.company_id == societe) or societe.account_sale_tax_id
            l.sous_total = round(ht, 2)
            l.total_ttc = round(taxes.compute_all(ht, societe.currency_id, 1.0, l.product_id)["total_included"], 2) if taxes else round(ht, 2)
