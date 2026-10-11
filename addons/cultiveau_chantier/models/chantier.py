"""Le chantier de pose : l'équipe, les dates, le matériel, le journal, la mise en service.

Le référentiel (A1.3) veut une mise en service avec PV : pressions de référence, essais, sécurités, protection sanitaire.
Le PV est celui de l'installation ; le chantier le remplit et le fait signer par l'exploitant sur place.
"""
from odoo import api, fields, models
from odoo.exceptions import UserError

ETATS = [("brouillon", "À planifier"), ("planifie", "Planifié"), ("en_cours", "En cours"), ("termine", "Terminé"), ("annule", "Annulé")]


class Chantier(models.Model):
    _name = "cultiveau.chantier"
    _description = "Chantier de pose"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_debut desc, id desc"

    name = fields.Char("Chantier", required=True, copy=False, readonly=True, default="Nouveau")
    titre = fields.Char("Objet", required=True, help="Ex. « Pose du pivot des Grandes Terres », « Goutte à goutte vigne, 6 ha ».")
    installation_id = fields.Many2one("cultiveau.installation", "Installation", required=True, index=True, tracking=True, ondelete="restrict")
    partner_id = fields.Many2one(related="installation_id.partner_id", store=True, string="Agriculteur")
    company_id = fields.Many2one("res.company", "Adhérent", required=True, default=lambda self: self.env.company, index=True)
    sale_order_id = fields.Many2one("sale.order", "Commande", domain="[('partner_id', 'child_of', partner_id)]", tracking=True)
    etat = fields.Selection(ETATS, "État", default="brouillon", required=True, tracking=True, index=True)
    date_debut = fields.Date("Début prévu", tracking=True)
    date_fin = fields.Date("Fin prévue", tracking=True)
    date_debut_reel = fields.Date("Démarré le", readonly=True)
    date_fin_reel = fields.Date("Terminé le", readonly=True)
    jours = fields.Integer("Jours prévus", compute="_compute_jours", store=True)
    chef_id = fields.Many2one("res.users", "Chef de chantier", tracking=True, default=lambda self: self.env.user)
    equipe_ids = fields.Many2many("res.users", "cultiveau_chantier_equipe_rel", "chantier_id", "user_id", string="Équipe de pose")
    machines = fields.Char("Machines (trancheuse, pelle, dérouleuse…)")
    sous_traitant_id = fields.Many2one("res.partner", "Sous-traitant", domain="[('is_company', '=', True)]")
    acces = fields.Char("Accès et consignes", help="Où entrer, qui prévenir, horaires, contraintes de la parcelle.")
    ligne_ids = fields.One2many("cultiveau.chantier.ligne", "chantier_id", string="Matériel")
    picking_id = fields.Many2one("stock.picking", "Bon de sortie", readonly=True, copy=False)
    avancement = fields.Integer("Avancement (%)", compute="_compute_avancement", store=True)
    mise_en_service_le = fields.Date("Mis en service le", readonly=True, tracking=True)
    pv_signe_par = fields.Char("PV signé par (exploitant)")
    pv_signature = fields.Binary("Signature de l'exploitant", attachment=True)
    pv_signe_le = fields.Date("PV signé le")
    reserves = fields.Text("Réserves à lever")
    notes = fields.Text("Préparation du chantier")
    nb_photos = fields.Integer("Photos", compute="_compute_nb_photos")
    # Le PV de l'installation, rempli depuis le chantier.
    pv_date = fields.Date(related="installation_id.pv_date", readonly=False)
    pv_intervenant = fields.Char(related="installation_id.pv_intervenant", readonly=False)
    pv_rincage = fields.Boolean(related="installation_id.pv_rincage", readonly=False)
    pv_essai_pression_bar = fields.Float(related="installation_id.pv_essai_pression_bar", readonly=False)
    pv_essai_resultat = fields.Char(related="installation_id.pv_essai_resultat", readonly=False)
    pv_pression_sortie_pompe_bar = fields.Float(related="installation_id.pv_pression_sortie_pompe_bar", readonly=False)
    pv_pression_point_defavorable_bar = fields.Float(related="installation_id.pv_pression_point_defavorable_bar", readonly=False)
    pv_debits_secteurs = fields.Text(related="installation_id.pv_debits_secteurs", readonly=False)
    pv_uniformite_pct = fields.Float(related="installation_id.pv_uniformite_pct", readonly=False)
    pv_kwh_m3 = fields.Float(related="installation_id.pv_kwh_m3", readonly=False)
    pv_securites_testees = fields.Boolean(related="installation_id.pv_securites_testees", readonly=False)
    pv_antiretour = fields.Boolean(related="installation_id.pv_antiretour", readonly=False)
    pv_reserves = fields.Text(related="installation_id.pv_reserves", readonly=False)
    type_systeme = fields.Selection(related="installation_id.type_systeme")
    surface_ha = fields.Float(related="installation_id.surface_ha")

    @api.depends("name", "titre")
    def _compute_display_name(self):
        for c in self:
            c.display_name = f"{c.name} — {c.titre}" if c.titre else c.name

    @api.depends("date_debut", "date_fin")
    def _compute_jours(self):
        for c in self:
            c.jours = (c.date_fin - c.date_debut).days + 1 if c.date_debut and c.date_fin and c.date_fin >= c.date_debut else 0

    @api.depends("ligne_ids.quantite_prevue", "ligne_ids.quantite_posee", "etat", "mise_en_service_le")
    def _compute_avancement(self):
        for c in self:
            prevu = sum(c.ligne_ids.mapped("quantite_prevue"))
            if c.etat == "termine":
                c.avancement = 100
            elif c.etat == "en_cours" and prevu:
                c.avancement = 10 + min(85, round(85 * sum(c.ligne_ids.mapped("quantite_posee")) / prevu))
            elif c.etat == "en_cours" and c.mise_en_service_le:
                c.avancement = 95
            else:
                c.avancement = {"brouillon": 0, "planifie": 5, "en_cours": 50}.get(c.etat, 0)

    def _compute_nb_photos(self):
        for c in self:
            c.nb_photos = self.env["ir.attachment"].search_count([("res_model", "=", self._name), ("res_id", "=", c.id), ("mimetype", "ilike", "image/")])

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "Nouveau") == "Nouveau":
                vals["name"] = self.env["ir.sequence"].with_company(vals.get("company_id")).next_by_code("cultiveau.chantier") or "Nouveau"
        return super().create(vals_list)

    @api.onchange("sale_order_id")
    def _onchange_sale_order(self):
        if self.sale_order_id and not self.ligne_ids:
            self.ligne_ids = [(0, 0, v) for v in self._lignes_depuis_commande(self.sale_order_id)]
            if not self.titre:
                self.titre = f"Pose — {self.sale_order_id.name}"

    @api.model
    def _lignes_depuis_commande(self, commande):
        """Le matériel prévu : les articles stockables de la commande, dans leurs quantités."""
        return [{"product_id": l.product_id.id, "quantite_prevue": l.product_uom_qty, "note": l.name if l.name != l.product_id.display_name else ""}
                for l in commande.order_line if l.product_id and l.product_id.is_storable and l.product_uom_qty]

    # ---------------------------------------------------------------- le déroulé

    def action_planifier(self):
        for c in self:
            if not (c.date_debut and c.date_fin):
                raise UserError("Donnez les dates de début et de fin prévues.")
            if not c.chef_id:
                raise UserError("Désignez le chef de chantier.")
            c.etat = "planifie"

    def action_demarrer(self):
        for c in self:
            c.write({"etat": "en_cours", "date_debut_reel": fields.Date.context_today(c)})
            if c.installation_id.etat in ("projet", "etude"):
                c.installation_id.etat = "realisation"

    def action_sortir_materiel(self):
        """Le bon de sortie du magasin vers le chantier (livraison au client), pour le matériel prévu."""
        self.ensure_one()
        if self.picking_id:
            return self.action_voir_picking()
        lignes = self.ligne_ids.filtered(lambda l: l.quantite_prevue > 0)
        if not lignes:
            raise UserError("Ajoutez d'abord le matériel prévu.")
        entrepot = self.env["stock.warehouse"].search([("company_id", "=", self.company_id.id)], limit=1)
        if not entrepot:
            raise UserError("Aucun entrepôt pour cette société.")
        type_sortie = entrepot.out_type_id
        destination = self.partner_id.property_stock_customer
        picking = self.env["stock.picking"].create({
            "picking_type_id": type_sortie.id, "partner_id": self.partner_id.id, "origin": f"{self.name} — {self.titre}", "company_id": self.company_id.id,
            "location_id": type_sortie.default_location_src_id.id, "location_dest_id": destination.id,
            "move_ids": [(0, 0, {"name": l.product_id.display_name, "product_id": l.product_id.id, "product_uom_qty": l.quantite_prevue, "product_uom": l.product_id.uom_id.id,
                                 "location_id": type_sortie.default_location_src_id.id, "location_dest_id": destination.id, "company_id": self.company_id.id}) for l in lignes],
        })
        picking.action_confirm()
        picking.action_assign()
        self.picking_id = picking
        self.message_post(body=f"Bon de sortie {picking.name} créé pour {len(lignes)} article(s).")
        return self.action_voir_picking()

    def action_voir_picking(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "res_model": "stock.picking", "res_id": self.picking_id.id, "view_mode": "form"}

    def action_mise_en_service(self):
        """Le PV est rempli (sur le chantier) : l'installation passe en service et s'inscrit au registre."""
        for c in self:
            c.installation_id.action_mettre_en_service()
            if not c.installation_id.pv_intervenant:
                c.installation_id.pv_intervenant = c.chef_id.name
            c.write({"mise_en_service_le": c.installation_id.pv_date or fields.Date.context_today(c)})
            for l in c.ligne_ids.filtered(lambda l: not l.quantite_posee):
                l.quantite_posee = l.quantite_prevue
            c.message_post(body=f"Mise en service le {c.mise_en_service_le} : PV enregistré sur l'installation, inscrite au registre.")

    def action_terminer(self):
        for c in self:
            if not c.mise_en_service_le and not c.reserves:
                raise UserError("Un chantier se termine par la mise en service (PV), ou avec des réserves écrites.")
            c.write({"etat": "termine", "date_fin_reel": fields.Date.context_today(c)})

    def action_annuler(self):
        self.write({"etat": "annule"})

    def action_brouillon(self):
        self.write({"etat": "brouillon"})

    def action_voir_photos(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "name": "Photos du chantier", "res_model": "ir.attachment", "view_mode": "kanban,list",
                "domain": [("res_model", "=", self._name), ("res_id", "=", self.id), ("mimetype", "ilike", "image/")],
                "context": {"default_res_model": self._name, "default_res_id": self.id}}


class ChantierLigne(models.Model):
    _name = "cultiveau.chantier.ligne"
    _description = "Matériel du chantier"
    _order = "id"

    chantier_id = fields.Many2one("cultiveau.chantier", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="chantier_id.company_id", store=True)
    product_id = fields.Many2one("product.product", "Article", required=True, domain=[("is_storable", "=", True)])
    quantite_prevue = fields.Float("Prévu", digits="Product Unit of Measure", default=1.0)
    quantite_posee = fields.Float("Posé", digits="Product Unit of Measure")
    uom_id = fields.Many2one(related="product_id.uom_id", string="Unité")
    disponible = fields.Float("En stock", compute="_compute_disponible", digits="Product Unit of Measure")
    manque = fields.Float("Manque", compute="_compute_disponible", digits="Product Unit of Measure")
    note = fields.Char("Précision")

    @api.depends("product_id", "quantite_prevue")
    def _compute_disponible(self):
        for l in self:
            l.disponible = l.product_id.with_company(l.company_id).qty_available if l.product_id else 0.0
            l.manque = max(0.0, l.quantite_prevue - l.disponible)
