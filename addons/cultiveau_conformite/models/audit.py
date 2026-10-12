"""Le journal d'audit : qui a créé, modifié ou supprimé quoi, avec la valeur avant et après de chaque champ.

Un mixin posé sur les documents du métier. Ne sont suivis que les champs saisis (stockés, non calculés), ni les images, ni les
mots de passe, ni la mécanique interne (messages, activités, dates techniques). Rien n'est noté pendant l'installation des
modules. Le journal n'est lisible que par le gérant et l'administrateur ; il est conservé trois ans (réglable).
"""
import json
from datetime import timedelta

from markupsafe import Markup

from odoo import api, fields, models

TYPES_SUIVIS = {"char", "text", "html", "integer", "float", "monetary", "boolean", "date", "datetime", "selection", "many2one", "many2many"}
EXCLUS = {"write_date", "write_uid", "create_date", "create_uid", "__last_update", "display_name", "password", "signature", "access_token", "message_main_attachment_id",
          "sequence", "is_move_sent", "tax_totals", "invoice_outstanding_credits_debits_widget", "invoice_payments_widget"}
PREFIXES_EXCLUS = ("message_", "activity_", "website_message", "image_", "avatar_", "__", "rating_", "cultiveau_alertes_faites")
OPERATIONS = [("creation", "Création"), ("modification", "Modification"), ("suppression", "Suppression"), ("rgpd", "RGPD")]


class Audit(models.Model):
    _name = "cultiveau.audit"
    _description = "Journal d'audit"
    _order = "id desc"
    _log_access = True

    user_id = fields.Many2one("res.users", "Par", readonly=True, index=True)
    company_id = fields.Many2one("res.company", "Société", readonly=True, index=True)
    modele = fields.Char("Modèle technique", readonly=True, index=True)
    modele_nom = fields.Char("Type de document", readonly=True)
    res_id = fields.Integer("N°", readonly=True, index=True)
    document = fields.Char("Document", readonly=True)
    operation = fields.Selection(OPERATIONS, "Opération", readonly=True, index=True)
    resume = fields.Char("Résumé", readonly=True)
    changements = fields.Text("Changements (JSON)", readonly=True)
    changements_html = fields.Html("Changements", compute="_compute_changements_html", sanitize=False)

    def _compute_changements_html(self):
        for a in self:
            lignes = json.loads(a.changements or "[]")
            if not lignes:
                a.changements_html = False
                continue
            corps = Markup("").join(Markup("<tr><td><b>%s</b></td><td class='text-danger'>%s</td><td class='text-success'>%s</td></tr>") % (l["libelle"], l["avant"], l["apres"])
                                    for l in lignes)
            a.changements_html = Markup("<table class='table table-sm'><thead><tr><th>Champ</th><th>Avant</th><th>Après</th></tr></thead><tbody>%s</tbody></table>") % corps

    @api.model
    def noter(self, record, operation, changements=None, resume=""):
        changements = changements or []
        if not resume:
            resume = ", ".join(f"{c['libelle']} : {c['avant']} → {c['apres']}" for c in changements[:3])[:250]
        company = record["company_id"] if "company_id" in record._fields and record["company_id"] else self.env.company
        self.sudo().create({"user_id": self.env.uid, "company_id": company.id if company else False, "modele": record._name,
                            "modele_nom": record._description or record._name, "res_id": record.id, "document": (record.sudo().display_name or "")[:250],
                            "operation": operation, "resume": resume, "changements": json.dumps(changements, ensure_ascii=False, default=str)})

    @api.model
    def action_pour(self, modele, ids):
        return {"type": "ir.actions.act_window", "name": "Historique des modifications", "res_model": "cultiveau.audit", "view_mode": "list,form",
                "domain": [("modele", "=", modele), ("res_id", "in", list(ids))], "target": "current"}

    @api.model
    def _cron_purger(self):
        annees = int(self.env["ir.config_parameter"].sudo().get_param("cultiveau.audit_annees") or 3)
        self.sudo().search([("create_date", "<", fields.Datetime.now() - timedelta(days=365 * annees))]).unlink()


class Mixin(models.AbstractModel):
    _name = "cultiveau.audit.mixin"
    _description = "Suivi par le journal d'audit"

    def _audit_actif(self):
        return self.pool.ready and not self.env.context.get("install_mode") and not self.env.context.get("cultiveau_sans_audit") \
            and not self.env.context.get("tracking_disable_audit") and "cultiveau.audit" in self.env

    def _audit_champs(self, noms):
        res = []
        for nom in noms:
            f = self._fields.get(nom)
            if not f or not f.store or f.compute and not f.inverse and f.readonly or f.type not in TYPES_SUIVIS:
                continue
            if nom in EXCLUS or nom.startswith(PREFIXES_EXCLUS) or (f.groups and "base.group_system" in f.groups):
                continue
            res.append(f)
        return res

    @staticmethod
    def _audit_valeur(record, f):
        v = record[f.name]
        if f.type == "many2one":
            return v.display_name or ""
        if f.type == "many2many":
            return ", ".join(v.mapped("display_name"))[:200]
        if f.type == "selection":
            return dict(f._description_selection(record.env)).get(v, v or "")
        if f.type == "boolean":
            return "Oui" if v else "Non"
        if f.type == "html":
            from odoo.tools import html2plaintext
            return html2plaintext(v or "")[:200]
        if v in (False, None):
            return ""
        return str(v)[:200]

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if records._audit_actif():
            Audit = self.env["cultiveau.audit"]
            for r in records:
                Audit.noter(r, "creation", resume="Créé")
        return records

    def write(self, vals):
        if not self or not self._audit_actif():
            return super().write(vals)
        champs = self._audit_champs(vals)
        if not champs:
            return super().write(vals)
        avant = {r.id: {f.name: self._audit_valeur(r, f) for f in champs} for r in self.sudo()}
        res = super().write(vals)
        Audit = self.env["cultiveau.audit"]
        for r in self.sudo():
            changements = []
            for f in champs:
                apres = self._audit_valeur(r, f)
                if apres != avant[r.id][f.name]:
                    changements.append({"champ": f.name, "libelle": f._description_string(self.env) if hasattr(f, "_description_string") else f.string,
                                        "avant": avant[r.id][f.name], "apres": apres})
            if changements:
                Audit.noter(r, "modification", changements)
        return res

    def unlink(self):
        if self and self._audit_actif():
            Audit = self.env["cultiveau.audit"]
            for r in self:
                Audit.noter(r, "suppression", resume="Supprimé")
        return super().unlink()

    def action_cultiveau_historique(self):
        return self.env["cultiveau.audit"].action_pour(self._name, self.ids)


# ---------------------------------------------------------------- les documents suivis

class Partenaire(models.Model):
    _name = "res.partner"
    _inherit = ["res.partner", "cultiveau.audit.mixin"]


class Commande(models.Model):
    _name = "sale.order"
    _inherit = ["sale.order", "cultiveau.audit.mixin"]


class Piece(models.Model):
    _name = "account.move"
    _inherit = ["account.move", "cultiveau.audit.mixin"]


class Paiement(models.Model):
    _name = "account.payment"
    _inherit = ["account.payment", "cultiveau.audit.mixin"]


class Article(models.Model):
    _name = "product.template"
    _inherit = ["product.template", "cultiveau.audit.mixin"]


class Achat(models.Model):
    _name = "purchase.order"
    _inherit = ["purchase.order", "cultiveau.audit.mixin"]


class Tache(models.Model):
    _name = "project.task"
    _inherit = ["project.task", "cultiveau.audit.mixin"]


class Installation(models.Model):
    _name = "cultiveau.installation"
    _inherit = ["cultiveau.installation", "cultiveau.audit.mixin"]


class Chantier(models.Model):
    _name = "cultiveau.chantier"
    _inherit = ["cultiveau.chantier", "cultiveau.audit.mixin"]


class Conge(models.Model):
    _name = "hr.leave"
    _inherit = ["hr.leave", "cultiveau.audit.mixin"]


class Depense(models.Model):
    _name = "hr.expense"
    _inherit = ["hr.expense", "cultiveau.audit.mixin"]
