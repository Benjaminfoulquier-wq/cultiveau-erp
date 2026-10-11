"""Les tarifs fournisseurs négociés par le réseau : un fichier par fournisseur et par an, chaque ligne retrouve son article."""

import base64

from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.exceptions import UserError

from odoo.addons.cultiveau_base import outils

COLONNES = {
    "ref_fournisseur": ["ref fournisseur", "reference fournisseur", "ref fabricant", "code fournisseur", "code article", "code", "ref", "reference", "sku", "article"],
    "nom": ["designation", "libelle", "nom", "description", "produit", "intitule"],
    "prix": ["prix", "prix ht", "prix brut", "prix public", "tarif", "pu ht", "prix unitaire", "prix catalogue", "prix tarif", "pu"],
    "prix_net": ["prix net", "net", "net ht", "prix remise", "prix negocie", "prix cultiveau", "prix reseau", "pu net"],
    "remise": ["remise", "remise %", "taux de remise", "coefficient", "coef"],
    "unite": ["unite", "u", "uom"],
    "conditionnement": ["conditionnement", "cond", "colisage"],
    "delai": ["delai", "delai jours", "delai livraison"],
}
ETATS = [("nouveau", "Inconnu au catalogue"), ("hausse", "Hausse"), ("baisse", "Baisse"), ("inchange", "Inchangé"), ("cree", "Créé au catalogue")]


class Tarif(models.Model):
    _name = "cultiveau.tarif.fournisseur"
    _description = "Tarif fournisseur négocié par le réseau"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    name = fields.Char("Tarif", compute="_compute_name", store=True)
    fournisseur_id = fields.Many2one("res.partner", "Fournisseur", required=True, domain=[("is_company", "=", True)], tracking=True)
    date = fields.Date("Valable à partir du", required=True, default=fields.Date.context_today, tracking=True)
    fichier = fields.Binary("Fichier du tarif")
    nom_fichier = fields.Char()
    remise_pct = fields.Float("Remise réseau (%)", digits=(5, 2), help="Appliquée aux prix bruts quand le fichier ne donne pas de prix net.")
    creer_inconnus = fields.Boolean("Créer les articles inconnus au catalogue Cultiveau", default=False)
    etat = fields.Selection([("brouillon", "À analyser"), ("analyse", "Analysé"), ("applique", "Appliqué")], "État", default="brouillon", tracking=True)
    ligne_ids = fields.One2many("cultiveau.tarif.ligne", "tarif_id", "Lignes")
    nb_lignes = fields.Integer(compute="_compute_nb")
    nb_hausses = fields.Integer("Hausses", compute="_compute_nb")
    nb_baisses = fields.Integer("Baisses", compute="_compute_nb")
    nb_inconnus = fields.Integer("Inconnus", compute="_compute_nb")
    seuil_alerte_pct = fields.Float("Alerter au-delà de (%)", default=5.0)
    note = fields.Text("Remarques")

    @api.depends("fournisseur_id", "date")
    def _compute_name(self):
        for t in self:
            t.name = f"{t.fournisseur_id.name or 'Tarif'} — {t.date.year if t.date else ''}".strip(" —")

    @api.depends("ligne_ids.etat")
    def _compute_nb(self):
        for t in self:
            t.nb_lignes = len(t.ligne_ids)
            t.nb_hausses = len(t.ligne_ids.filtered(lambda l: l.etat == "hausse"))
            t.nb_baisses = len(t.ligne_ids.filtered(lambda l: l.etat == "baisse"))
            t.nb_inconnus = len(t.ligne_ids.filtered(lambda l: l.etat == "nouveau"))

    # ---------------------------------------------------------------- lecture

    def _retrouver(self, ref, nom, cache):
        """L'article du catalogue : d'abord la référence chez ce fournisseur, puis la référence interne, puis la désignation exacte."""
        Produit = self.env["product.template"].sudo()
        cle = (ref or "").strip().lower()
        if cle and cle in cache:
            return cache[cle]
        produit = Produit
        if cle:
            info = self.env["product.supplierinfo"].sudo().search([("partner_id", "=", self.fournisseur_id.id), ("product_code", "=ilike", cle)], limit=1)
            produit = info.product_tmpl_id or Produit.search([("default_code", "=ilike", cle), ("company_id", "=", False)], limit=1)
        if not produit and nom:
            produit = Produit.search([("name", "=ilike", nom.strip()), ("company_id", "=", False)], limit=1)
        if cle:
            cache[cle] = produit
        return produit

    def action_analyser(self):
        self.ensure_one()
        if not self.fichier:
            raise UserError("Choisissez le fichier du tarif (Excel ou CSV du fournisseur).")
        try:
            lignes = outils.lire_tableau(self.nom_fichier or "tarif.csv", base64.b64decode(self.fichier))
            corr, _en_tete, donnees, _inconnus = outils.reconnaitre(lignes, COLONNES, obligatoires=("prix",) if "prix" else ())
        except ValueError as e:
            raise UserError(f"Fichier non reconnu : {e}.") from e
        if "ref_fournisseur" not in corr and "nom" not in corr:
            raise UserError("Je ne trouve ni colonne « Référence » ni colonne « Désignation » dans le fichier.")
        if "prix" not in corr and "prix_net" not in corr:
            raise UserError("Je ne trouve pas de colonne de prix dans le fichier.")
        self.ligne_ids.unlink()
        cache, valeurs = {}, []
        for ligne in donnees:
            ref = outils.valeur(ligne, corr, "ref_fournisseur")
            nom = outils.valeur(ligne, corr, "nom")
            brut = outils.nombre(outils.valeur(ligne, corr, "prix"))
            net = outils.nombre(outils.valeur(ligne, corr, "prix_net"))
            remise = outils.nombre(outils.valeur(ligne, corr, "remise"))
            if brut is None and net is None:
                continue
            if net is None:
                taux = remise if remise is not None else self.remise_pct
                taux = taux * 100 if 0 < taux < 1 else taux  # 0,2 ou 20
                net = round(brut * (1 - taux / 100), 4)
            produit = self._retrouver(ref, nom, cache)
            ancien = produit.seller_ids.filtered(lambda s: s.partner_id == self.fournisseur_id)[:1].price if produit else 0.0
            if not produit:
                etat = "nouveau"
            elif not ancien or abs(net - ancien) < 0.005:
                etat = "inchange"
            else:
                etat = "hausse" if net > ancien else "baisse"
            valeurs.append({"tarif_id": self.id, "ref_fournisseur": (ref or "")[:64], "designation": (nom or "")[:255], "prix_brut": brut or 0.0, "prix_net": net,
                            "product_id": produit.id if produit else False, "ancien_prix": ancien, "etat": etat,
                            "variation_pct": round((net - ancien) / ancien * 100, 1) if ancien else 0.0,
                            "unite": (outils.valeur(ligne, corr, "unite") or "")[:16], "delai": outils.nombre(outils.valeur(ligne, corr, "delai")) or 0})
        if not valeurs:
            raise UserError("Aucune ligne avec un prix dans ce fichier.")
        self.env["cultiveau.tarif.ligne"].create(valeurs)
        self.etat = "analyse"
        return True

    # ---------------------------------------------------------------- application

    def action_appliquer(self):
        """Le nouveau prix net devient le prix d'achat chez ce fournisseur ; les adhérents reçoivent leur coût ; les inconnus sont créés si demandé."""
        self.ensure_one()
        if not self.ligne_ids:
            self.action_analyser()
        Produit = self.env["product.template"].sudo()
        adherents = self.env["res.company"].sudo().search([("cultiveau_adherent", "=", True)])
        crees = 0
        for l in self.ligne_ids:
            produit = l.product_id
            if not produit:
                if not self.creer_inconnus or not l.designation:
                    continue
                produit = Produit.create({"name": l.designation, "default_code": l.ref_fournisseur or False, "type": "consu", "is_storable": True, "sale_ok": True, "purchase_ok": True,
                                          "company_id": False, "cultiveau_reseau": True, "cultiveau_source": "matrice", "list_price": round(l.prix_net * 1.3, 2)})
                l.write({"product_id": produit.id, "etat": "cree"})
                crees += 1
            Produit._cultiveau_fournisseur_prix(produit, self.fournisseur_id, l.prix_net, l.ref_fournisseur or None, l.delai or None)
            info = produit.seller_ids.filtered(lambda s: s.partner_id == self.fournisseur_id)[:1]
            if info:
                info.write({"date_start": self.date})
            for societe in adherents:
                produit.with_company(societe).standard_price = l.prix_net
        self.etat = "applique"
        alertes = self.ligne_ids.filtered(lambda l: l.etat in ("hausse", "baisse") and abs(l.variation_pct) >= self.seuil_alerte_pct)
        resume = (f"<p>Tarif appliqué : {len(self.ligne_ids)} lignes, {self.nb_hausses} hausses, {self.nb_baisses} baisses, {crees} articles créés, "
                  f"{self.nb_inconnus - crees} inconnus laissés de côté.</p>")
        if alertes:
            resume += "<p><b>À regarder (variation au-delà du seuil) :</b></p><ul>" + "".join(
                f"<li>{escape(l.product_id.name)} : {l.ancien_prix:.2f} → {l.prix_net:.2f} € ({l.variation_pct:+.1f} %)</li>" for l in alertes[:40]) + "</ul>"
            self.activity_schedule("mail.mail_activity_data_todo", summary=f"{len(alertes)} prix ont bougé chez {self.fournisseur_id.name} : vérifier les prix de vente",
                                   user_id=self.env.user.id)
        self.message_post(body=Markup(resume))
        # les listes de prix de vente des adhérents suivent (prix d'achat × coefficient)
        for societe in adherents.filtered("cultiveau_tarif_vente_id"):
            societe.cultiveau_appliquer_marges()
        return True


class TarifLigne(models.Model):
    _name = "cultiveau.tarif.ligne"
    _description = "Ligne d'un tarif fournisseur"
    _order = "etat, designation"

    tarif_id = fields.Many2one("cultiveau.tarif.fournisseur", required=True, ondelete="cascade")
    ref_fournisseur = fields.Char("Réf. fournisseur")
    designation = fields.Char("Désignation")
    prix_brut = fields.Float("Prix brut", digits="Product Price")
    prix_net = fields.Float("Prix net", digits="Product Price")
    product_id = fields.Many2one("product.template", "Article")
    ancien_prix = fields.Float("Ancien prix net", digits="Product Price")
    variation_pct = fields.Float("Variation (%)", digits=(6, 1))
    etat = fields.Selection(ETATS, "État")
    unite = fields.Char("Unité")
    delai = fields.Integer("Délai (j)")
