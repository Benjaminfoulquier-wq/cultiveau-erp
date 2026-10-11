"""Le comptoir : chercher l'article (douchette ou clavier), le panier, le client, encaisser.

Tout passe par les objets standard (commande, livraison, facture, paiement) : rien de parallèle à réconcilier ensuite.
"""
import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

MODES = {"cash": "Espèces", "bank": "Carte, chèque ou virement"}


def montant(v):
    """4 786,30 — à la française."""
    return f"{v:,.2f}".replace(",", " ").replace(".", ",")


class Comptoir(models.AbstractModel):
    _name = "cultiveau.comptoir"
    _description = "Vente au comptoir"

    # ---------------------------------------------------------------- ce que l'écran a besoin de savoir

    @api.model
    def contexte(self):
        societe = self.env.company
        return {
            "societe": {"id": societe.id, "nom": societe.name},
            "devise": societe.currency_id.symbol,
            "client_defaut": self._client_de_passage(societe).id,
            "journaux": self._journaux(societe),
            "comptabilite": bool(self._journal_vente(societe)),
        }

    def _journal_vente(self, societe):
        return self.env["account.journal"].search([("company_id", "=", societe.id), ("type", "=", "sale")], limit=1)

    def _journaux(self, societe):
        journaux = self.env["account.journal"].search([("company_id", "=", societe.id), ("type", "in", ("cash", "bank"))], order="type desc, sequence, id")
        return [{"id": j.id, "nom": j.name, "type": j.type, "libelle": MODES.get(j.type, j.name)} for j in journaux]

    def _client_de_passage(self, societe):
        Partner = self.env["res.partner"].with_company(societe)
        client = Partner.search([("name", "=", "Client de passage"), ("company_id", "in", (societe.id, False))], limit=1)
        if not client:
            client = Partner.with_context(mail_create_nolog=True, tracking_disable=True).create({"name": "Client de passage", "company_id": societe.id, "is_company": False})
        return client

    # ---------------------------------------------------------------- chercher

    @api.model
    def chercher(self, texte, partner_id=None, limite=12):
        """Les articles qui répondent au code-barres, à la référence ou au nom ; `exact` quand la douchette a lu un code."""
        texte = (texte or "").strip()
        if not texte:
            return []
        societe = self.env.company
        Produit = self.env["product.product"].with_company(societe)
        base = [("sale_ok", "=", True), ("company_id", "in", (societe.id, False))]
        exacts = Produit.search(base + ["|", ("barcode", "=", texte), ("default_code", "=ilike", texte)], limit=limite)
        autres = Produit.search(base + ["|", "|", ("name", "ilike", texte), ("default_code", "ilike", texte), ("barcode", "ilike", texte)], limit=limite) - exacts
        partner = self.env["res.partner"].browse(partner_id) if partner_id else self._client_de_passage(societe)
        return [self._article(p, partner, exact=p in exacts) for p in (exacts + autres)[:limite]]

    def _article(self, produit, partner, exact=False, quantite=1.0):
        prix = self.prix(produit, partner, quantite)
        return {"id": produit.id, "nom": produit.display_name, "code": produit.default_code or "", "barcode": produit.barcode or "", "unite": produit.uom_id.name,
                "stock": produit.qty_available if produit.is_storable else None, "exact": exact, **prix}

    @api.model
    def prix(self, produit, partner, quantite=1.0):
        """Le prix de l'article pour ce client : sa liste de prix, puis les taxes de la société."""
        societe = self.env.company
        produit = produit.with_company(societe)
        liste = partner.with_company(societe).property_product_pricelist
        ht = liste._get_product_price(produit, quantite or 1.0, uom=produit.uom_id) if liste else produit.lst_price
        taxes = produit.taxes_id.filtered(lambda t: t.company_id == societe)
        if liste and liste.fiscal_position_id:
            taxes = liste.fiscal_position_id.map_tax(taxes)
        calcul = taxes.compute_all(ht, societe.currency_id, 1.0, produit, partner)
        return {"prix_ht": round(calcul["total_excluded"], 2), "prix_ttc": round(calcul["total_included"], 2),
                "tva": ", ".join(t.name for t in taxes) if taxes else "sans TVA", "taux": sum(t.amount for t in taxes if t.amount_type == "percent")}

    @api.model
    def clients(self, texte, limite=10):
        texte = (texte or "").strip()
        societe = self.env.company
        domaine = [("company_id", "in", (societe.id, False)), ("parent_id", "=", False)]
        if texte:
            domaine += ["|", "|", "|", ("name", "ilike", texte), ("phone", "ilike", texte), ("mobile", "ilike", texte), ("city", "ilike", texte)]
        partners = self.env["res.partner"].with_company(societe).search(domaine, order="name", limit=limite)
        return [{"id": p.id, "nom": p.display_name, "ville": p.city or "", "telephone": p.phone or p.mobile or "", "type": p.cultiveau_type or ""} for p in partners]

    # ---------------------------------------------------------------- vendre

    @api.model
    def vendre(self, partner_id, lignes, mode="encaisser", journal_id=None, note=""):
        """`devis` : un devis à envoyer. `commande` : confirmée, à livrer. `encaisser` : confirmée, sortie du stock, facturée, payée."""
        societe = self.env.company
        partner = self.env["res.partner"].browse(partner_id) if partner_id else self._client_de_passage(societe)
        lignes = [l for l in (lignes or []) if l.get("product_id") and float(l.get("quantite") or 0) > 0]
        if not lignes:
            raise UserError("Le panier est vide.")
        if mode == "encaisser":
            self._assurer_comptabilite(societe)
            journal = self.env["account.journal"].browse(journal_id) if journal_id else self.env["account.journal"].search([("company_id", "=", societe.id), ("type", "=", "cash")], limit=1)
            if not journal or journal.company_id != societe:
                raise UserError("Choisissez le moyen de paiement (espèces, carte, chèque, virement).")
        Commande = self.env["sale.order"].with_company(societe).with_context(mail_create_nolog=True, tracking_disable=True)
        commande = Commande.create({
            "partner_id": partner.id, "company_id": societe.id, "origin": "Comptoir", "note": note or False,
            "order_line": [(0, 0, {"product_id": l["product_id"], "product_uom_qty": float(l["quantite"]),
                                   **({"price_unit": float(l["prix_ht"])} if l.get("prix_ht") not in (None, "") else {}),
                                   **({"discount": float(l["remise"])} if l.get("remise") else {})}) for l in lignes],
        })
        resultat = {"commande_id": commande.id, "nom": commande.name, "total_ht": commande.amount_untaxed, "total_ttc": commande.amount_total, "facture_id": None, "paiement_id": None}
        if mode == "devis":
            resultat["message"] = f"Devis {commande.name} enregistré."
            return resultat
        commande.action_confirm()
        if mode == "commande":
            resultat["message"] = f"Commande {commande.name} confirmée, à livrer."
            return resultat
        self._sortir_du_stock(commande)
        facture = commande._create_invoices()
        facture.with_context(mail_create_nolog=True, tracking_disable=True).action_post()
        paiement = self.env["account.payment.register"].with_context(active_model="account.move", active_ids=facture.ids).create({"journal_id": journal.id})._create_payments()
        resultat.update({"nom": facture.name, "facture_id": facture.id, "paiement_id": paiement.id, "total_ttc": facture.amount_total, "total_ht": facture.amount_untaxed,
                         "message": f"Encaissé {montant(facture.amount_total)} {societe.currency_id.symbol} — {MODES.get(journal.type, journal.name).lower()} ({journal.name}). Facture {facture.name}."})
        return resultat

    def _sortir_du_stock(self, commande):
        """Le client repart avec : la livraison est validée tout de suite, pour ce qui est en stock (le stock peut passer négatif, c'est l'inventaire qui le dira)."""
        for picking in commande.picking_ids.filtered(lambda p: p.state not in ("done", "cancel")):
            picking.action_assign()
            for move in picking.move_ids.filtered(lambda m: m.state not in ("done", "cancel")):
                move.quantity = move.product_uom_qty
                move.picked = True
            picking.with_context(skip_backorder=True, skip_sms=True, skip_sanity_check=True).button_validate()

    def _assurer_comptabilite(self, societe):
        """Pas de journal de vente : la société n'a pas encore de plan comptable ; on charge le plan français."""
        if self._journal_vente(societe):
            return
        try:
            self.env["account.chart.template"].try_loading("fr", societe, install_demo=False)
        except Exception as e:  # noqa: BLE001 — on explique plutôt que de planter l'encaissement
            _logger.exception("Plan comptable impossible à charger pour %s", societe.name)
            raise UserError(f"La comptabilité de {societe.name} n'est pas en place et le plan comptable n'a pas pu être chargé : {e}") from e
        if not self._journal_vente(societe):
            raise UserError(f"La comptabilité de {societe.name} n'est pas en place : aucun journal de vente.")

    @api.model
    def ticket(self, facture_id):
        """L'action d'impression du ticket (la facture, au format de la société)."""
        return {"type": "ir.actions.report", "report_name": "account.report_invoice_with_payments", "report_type": "qweb-pdf",
                "report_file": "account.report_invoice_with_payments", "name": "Ticket", "context": {"active_ids": [facture_id], "active_model": "account.move"}}
