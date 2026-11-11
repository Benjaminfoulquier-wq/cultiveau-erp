"""Le schéma de câblage dessiné dans l'éditeur (armoire de l'atelier, Map vivante).

Le dessin vit dans un JSON : `composants` [{id, type, x, y, repere, nom, valeurs}] et `fils`
[{id, de: {c, b}, a: {c, b}, num, section, longueur}]. Le serveur ne fait que le garder, par société : la palette,
le tracé et les contrôles (référentiel § 11.2 et 11.3) sont dans `static/src/js/schema.js`.
"""
import json

from odoo import Command, api, fields, models
from odoo.exceptions import UserError, ValidationError


class SchemaCablage(models.Model):
    _name = "cultiveau.schema.cablage"
    _description = "Schéma de câblage"
    _order = "write_date desc, id desc"

    name = fields.Char("Nom", required=True, default="Nouveau schéma")
    company_id = fields.Many2one("res.company", "Société", required=True, default=lambda self: self.env.company, index=True)
    partner_id = fields.Many2one("res.partner", "Client")
    donnees = fields.Text("Dessin (JSON)", default='{"composants": [], "fils": []}')
    nb_composants = fields.Integer("Appareils", compute="_compute_nb", store=True)
    active = fields.Boolean(default=True)
    devis_id = fields.Many2one("sale.order", "Devis", copy=False, readonly=True)

    @api.depends("donnees")
    def _compute_nb(self):
        for schema in self:
            try:
                schema.nb_composants = len(json.loads(schema.donnees or "{}").get("composants") or [])
            except (ValueError, AttributeError):
                schema.nb_composants = 0

    @api.constrains("donnees")
    def _verifier_donnees(self):
        for schema in self:
            try:
                dessin = json.loads(schema.donnees or "{}")
            except ValueError:
                raise ValidationError("Le dessin du schéma est illisible.")
            if not isinstance(dessin, dict) or not isinstance(dessin.get("composants", []), list) or not isinstance(dessin.get("fils", []), list):
                raise ValidationError("Le dessin du schéma est illisible.")

    # ---------------------------------------------------------------- vers le devis
    def _a_preciser(self):
        """L'article « à préciser » de la société (le même que celui des devis par lots)."""
        Produit = self.env["product.product"].with_company(self.company_id)
        p = Produit.search([("default_code", "=", "A-PRECISER"), ("company_id", "in", [self.company_id.id, False])], limit=1)
        if not p:
            p = Produit.sudo().create({"name": "Article à préciser (nomenclature)", "default_code": "A-PRECISER", "type": "service", "list_price": 0.0, "sale_ok": True,
                                       "purchase_ok": False, "company_id": self.company_id.id})
        return p

    def creer_devis(self, lignes):
        """Le matériel du schéma devient un devis : une section, puis une ligne par appareil et par câble.

        `lignes` vient de l'éditeur : [{designation, quantite, unite: "u" | "m", reperes, article_id}]. Une ligne qui a son
        article du catalogue prend son prix ; les autres attendent d'être précisées, à zéro. Un devis encore en
        brouillon est remis à jour ; un devis déjà envoyé ou confirmé n'est pas touché, un nouveau est créé.
        """
        self.ensure_one()
        if not self.partner_id:
            raise UserError("Choisissez d'abord le client du schéma.")
        lignes = [l for l in (lignes or []) if isinstance(l, dict) and (l.get("designation") or "").strip()]
        if not lignes:
            raise UserError("Le schéma ne contient aucun appareil : rien à chiffrer.")
        a_preciser = self._a_preciser()
        unite, metre = self.env.ref("uom.product_uom_unit"), self.env.ref("uom.product_uom_meter")
        Produit = self.env["product.product"].with_company(self.company_id)
        commandes = [Command.create({"display_type": "line_section", "name": f"Armoire et câblage · {self.name}", "sequence": 1})]
        trouves = manquants = 0
        for n, l in enumerate(lignes, start=2):
            au_metre = l.get("unite") == "m"
            try:
                qte = float(l.get("quantite") or 0)
            except (TypeError, ValueError):
                qte = 0.0
            if qte <= 0:
                continue
            designation = str(l["designation"]).strip()
            reperes = ", ".join(str(r) for r in (l.get("reperes") or []) if r)
            article = Produit.browse(int(l["article_id"])).exists() if l.get("article_id") else Produit
            if article and (not article.sale_ok or article.company_id not in (self.company_id, self.env["res.company"])):
                article = Produit
            valeurs = {"sequence": n, "product_uom_qty": round(qte, 1) if au_metre else max(1, round(qte))}
            if article:
                trouves += 1
                valeurs.update({"product_id": article.id, "name": (f"{article.display_name} — {designation}" + (f" ({reperes})" if reperes else ""))[:500]})
            else:
                manquants += 1
                valeurs.update({"product_id": a_preciser.id, "product_uom": (metre if au_metre else unite).id, "price_unit": 0.0,
                                "name": (designation + (f" ({reperes})" if reperes else "") + " — à préciser")[:500]})
            commandes.append(Command.create(valeurs))
        if len(commandes) < 2:
            raise UserError("Le schéma ne contient aucun appareil : rien à chiffrer.")
        devis = self.devis_id if self.devis_id.state == "draft" and self.devis_id.partner_id == self.partner_id else self.env["sale.order"]
        if devis:
            devis.write({"order_line": [Command.clear()] + commandes})
        else:
            devis = self.env["sale.order"].with_company(self.company_id).create({
                "partner_id": self.partner_id.id, "company_id": self.company_id.id, "origin": f"Schéma de câblage · {self.name}", "order_line": commandes})
            self.devis_id = devis
        devis.message_post(body=f"Matériel repris du schéma de câblage « {self.name} » : {trouves} ligne(s) avec leur article du catalogue, {manquants} à préciser.")
        return {"type": "ir.actions.act_window", "res_model": "sale.order", "res_id": devis.id, "views": [[False, "form"]], "target": "current"}
