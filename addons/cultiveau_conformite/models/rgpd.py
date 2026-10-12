"""Le RGPD : exporter toutes les données d'un client, les effacer (ou les limiter quand la loi oblige à garder les factures).

L'export rassemble en un fichier JSON lisible : la fiche et ses contacts, les devis et commandes, les factures, les
installations, les interventions, les chantiers, les rendez-vous, les courriels et les échanges notés sur sa fiche.

L'effacement :
- sans pièce comptable : la fiche et ses contacts sont anonymisés, leurs échanges et courriels supprimés ;
- avec des factures (à garder dix ans) : on limite. Les coordonnées de contact (courriel, téléphones), les notes, les échanges
  et les courriels sont supprimés ; le nom et l'adresse de facturation restent, la fiche est archivée.
Chaque export et chaque effacement est noté au journal d'audit.
"""
import base64
import json

from odoo import fields, models
from odoo.exceptions import UserError


class Partenaire(models.Model):
    _inherit = "res.partner"

    def _cultiveau_rgpd_donnees(self):
        self.ensure_one()
        p = self.commercial_partner_id
        tous = self.env["res.partner"].with_context(active_test=False).search([("id", "child_of", p.id)])
        env = self.env

        def lignes(modele, domaine, champs):
            if modele not in env:
                return []
            M = env[modele].sudo().with_context(active_test=False)
            champs = [c for c in champs if c in M._fields]
            return [{c: (r[c].display_name if hasattr(r[c], "display_name") and isinstance(r[c], models.BaseModel) else r[c]) for c in champs}
                    for r in M.search(domaine, limit=500)]

        champs_fiche = ["name", "is_company", "email", "phone", "mobile", "street", "street2", "zip", "city", "country_id", "vat", "website", "function", "comment",
                        "create_date"]
        donnees = {
            "export": {"date": fields.Datetime.now(), "societe": self.env.company.name, "objet": "Données personnelles détenues sur ce client (RGPD, article 15)"},
            "fiche": lignes("res.partner", [("id", "=", p.id)], champs_fiche),
            "contacts": lignes("res.partner", [("parent_id", "=", p.id)], champs_fiche),
            "devis_et_commandes": lignes("sale.order", [("partner_id", "in", tous.ids)], ["name", "date_order", "state", "amount_untaxed", "amount_total"]),
            "factures": lignes("account.move", [("partner_id", "in", tous.ids), ("move_type", "in", ("out_invoice", "out_refund"))],
                               ["name", "invoice_date", "state", "amount_total", "payment_state"]),
            "installations": lignes("cultiveau.installation", [("partner_id", "in", tous.ids)], ["name", "type_systeme", "surface_ha", "pv_date"]),
            "interventions": lignes("project.task", [("partner_id", "in", tous.ids)], ["name", "date_deadline", "stage_id"]),
            "chantiers": lignes("cultiveau.chantier", [("partner_id", "in", tous.ids)], ["name", "titre", "etat", "date_debut"]),
            "rendez_vous": lignes("calendar.event", [("partner_ids", "in", tous.ids)], ["name", "start", "location"]),
            "courriels": lignes("cultiveau.courriel", [("partner_id", "in", tous.ids)], ["name", "date_reception", "expediteur", "etat"]),
            "echanges": [{"date": m.date, "auteur": m.author_id.name or m.email_from or "", "objet": m.subject or "", "texte": m.preview or ""}
                         for m in self.env["mail.message"].sudo().search([("model", "=", "res.partner"), ("res_id", "in", tous.ids), ("message_type", "!=", "notification")],
                                                                          limit=500)],
        }
        return donnees

    def action_cultiveau_rgpd_export(self):
        self.ensure_one()
        donnees = self._cultiveau_rgpd_donnees()
        contenu = json.dumps(donnees, ensure_ascii=False, indent=2, default=str).encode()
        nom = f"donnees-personnelles-{self.commercial_partner_id.id}-{fields.Date.context_today(self)}.json"
        piece = self.env["ir.attachment"].sudo().create({"name": nom, "datas": base64.b64encode(contenu), "res_model": "res.partner",
                                                         "res_id": self.commercial_partner_id.id, "mimetype": "application/json"})
        self.env["cultiveau.audit"].noter(self.commercial_partner_id, "rgpd", resume="Export des données personnelles")
        return {"type": "ir.actions.act_url", "url": f"/web/content/{piece.id}?download=true", "target": "self"}

    def action_cultiveau_rgpd_effacer(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "res_model": "cultiveau.rgpd.effacement", "view_mode": "form", "target": "new",
                "name": "Effacer les données de ce client", "context": {"default_partner_id": self.commercial_partner_id.id}}


class Effacement(models.TransientModel):
    _name = "cultiveau.rgpd.effacement"
    _description = "Effacement RGPD d'un client"

    partner_id = fields.Many2one("res.partner", "Client", required=True, readonly=True)
    pieces_comptables = fields.Integer("Pièces comptables", compute="_compute_bilan")
    en_cours = fields.Char("Dossiers en cours", compute="_compute_bilan")
    mode = fields.Selection([("anonymiser", "Anonymiser complètement"), ("limiter", "Limiter (les factures restent)")], compute="_compute_bilan")
    confirmation = fields.Char("Tapez EFFACER pour confirmer")

    def _compute_bilan(self):
        for w in self:
            tous = self.env["res.partner"].with_context(active_test=False).search([("id", "child_of", w.partner_id.id)])
            w.pieces_comptables = self.env["account.move"].sudo().search_count([("partner_id", "in", tous.ids), ("state", "=", "posted")])
            ouverts = []
            n = self.env["sale.order"].sudo().search_count([("partner_id", "in", tous.ids), ("state", "in", ("sent", "sale")), ("invoice_status", "=", "to invoice")])
            if n:
                ouverts.append(f"{n} commande(s) à facturer")
            n = self.env["account.move"].sudo().search_count([("partner_id", "in", tous.ids), ("state", "=", "posted"), ("payment_state", "in", ("not_paid", "partial")),
                                                              ("move_type", "=", "out_invoice")])
            if n:
                ouverts.append(f"{n} facture(s) impayée(s)")
            w.en_cours = ", ".join(ouverts)
            w.mode = "limiter" if w.pieces_comptables else "anonymiser"

    def action_effacer(self):
        self.ensure_one()
        if (self.confirmation or "").strip().upper() != "EFFACER":
            raise UserError("Tapez EFFACER pour confirmer.")
        if self.en_cours:
            raise UserError(f"Des dossiers sont en cours ({self.en_cours}) : soldez-les avant d'effacer.")
        p = self.partner_id.sudo()
        tous = self.env["res.partner"].sudo().with_context(active_test=False).search([("id", "child_of", p.id)])
        # les échanges et courriels
        self.env["mail.message"].sudo().search([("model", "=", "res.partner"), ("res_id", "in", tous.ids)]).unlink()
        if "cultiveau.courriel" in self.env:
            self.env["cultiveau.courriel"].sudo().search([("partner_id", "in", tous.ids)]).unlink()
        if "cultiveau.appel" in self.env:
            Appel = self.env["cultiveau.appel"].sudo()
            if "partner_id" in Appel._fields:
                Appel.search([("partner_id", "in", tous.ids)]).unlink()
        effaces = {"email": False, "phone": False, "mobile": False, "comment": False, "website": False, "function": False, "image_1920": False}
        if self.mode == "anonymiser":
            for c in tous:
                c.with_context(cultiveau_sans_audit=True).write({**effaces, "name": f"Client effacé n° {c.id}", "street": False, "street2": False, "zip": False,
                                                                "city": False, "vat": False, "ref": False, "active": False})
            resume = "Effacement : fiche et contacts anonymisés, échanges et courriels supprimés"
        else:
            for c in tous:
                c.with_context(cultiveau_sans_audit=True).write({**effaces, "active": False})
            resume = "Limitation : coordonnées, échanges et courriels supprimés ; factures conservées (obligation légale)"
        self.env["cultiveau.audit"].noter(p, "rgpd", resume=resume)
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"title": "Données effacées", "message": resume + ".", "type": "success", "sticky": True, "next": {"type": "ir.actions.act_window_close"}}}
