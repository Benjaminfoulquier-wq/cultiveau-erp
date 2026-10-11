"""Où en est chaque société avec la facture électronique, et les deux boutons qui font tout."""

from odoo import api, fields, models
from odoo.exceptions import UserError

ETATS = [("non", "Pas encore inscrite"), ("demo", "Inscrite en démonstration (rien ne part)"), ("test", "Inscrite en test"),
         ("attente", "Inscription en cours"), ("prod", "Inscrite : factures émises et reçues par la plateforme"), ("refusee", "Inscription refusée")]


class Company(models.Model):
    _inherit = "res.company"

    cultiveau_efacture_etat = fields.Selection(ETATS, "Facture électronique", compute="_compute_efacture_etat")

    @api.depends("account_peppol_proxy_state", "l10n_fr_pdp_registered", "account_edi_proxy_client_ids.edi_mode")
    def _compute_efacture_etat(self):
        for c in self:
            etat_proxy = c.account_peppol_proxy_state
            utilisateur = c.account_edi_proxy_client_ids.filtered(lambda u: u.proxy_type == "pdp")[:1]
            mode = utilisateur.edi_mode if utilisateur else False
            if etat_proxy == "rejected":
                c.cultiveau_efacture_etat = "refusee"
            elif etat_proxy in ("not_registered", False) or not utilisateur:
                c.cultiveau_efacture_etat = "non"
            elif mode == "demo":
                c.cultiveau_efacture_etat = "demo"
            elif mode == "test":
                c.cultiveau_efacture_etat = "test"
            elif etat_proxy == "receiver" and c.l10n_fr_pdp_registered:
                c.cultiveau_efacture_etat = "prod"
            else:
                c.cultiveau_efacture_etat = "attente"

    @api.model
    def cultiveau_double_authentification(self):
        """La double authentification est-elle exigée de tous les utilisateurs internes ?"""
        return self.env["ir.config_parameter"].sudo().get_param("auth_totp.policy") in ("employee_required", "all_required")

    @api.model
    def cultiveau_activer_double_authentification(self):
        """Un code par e-mail à chaque connexion depuis un nouvel appareil (ou une application d'authentification si l'utilisateur l'a choisie)."""
        if not self.env["ir.mail_server"].sudo().search_count([]) and not self.env["ir.config_parameter"].sudo().get_param("mail.catchall.domain"):
            raise UserError("Avant d'exiger la double authentification, configurez l'envoi d'e-mails (Réglages → Technique → Serveurs de messagerie sortants) : "
                            "le code de connexion arrive par e-mail, sans cela plus personne ne pourrait se connecter.")
        self.env["ir.config_parameter"].sudo().set_param("auth_totp.policy", "employee_required")
        return True


class Settings(models.TransientModel):
    _inherit = "res.config.settings"

    cultiveau_efacture_etat = fields.Selection(related="company_id.cultiveau_efacture_etat")
    cultiveau_pdp_identifiant = fields.Char(related="company_id.pdp_identifier")
    cultiveau_annuaire_depuis = fields.Date(related="company_id.l10n_fr_pdp_annuaire_start_date", string="Sur l'annuaire depuis le")
    cultiveau_ereporting = fields.Boolean(related="company_id.l10n_fr_f10_enable_reporting", readonly=False, string="E-reporting des ventes aux particuliers et des encaissements")
    cultiveau_ereporting_depuis = fields.Date(related="company_id.l10n_fr_pdp_flow_10_start_date", readonly=False, string="À partir du")
    cultiveau_double_auth = fields.Boolean("Double authentification exigée", compute="_compute_double_auth")
    cultiveau_siret = fields.Char(related="company_id.siret", readonly=False, string="SIRET")

    def _compute_double_auth(self):
        exigee = self.env["res.company"].cultiveau_double_authentification()
        for s in self:
            s.cultiveau_double_auth = exigee

    def action_cultiveau_inscription(self):
        """Ouvre l'inscription de la société sur la plateforme agréée (démonstration, test ou réel, au choix dans l'assistant)."""
        self.ensure_one()
        if not self.company_id.siret:
            raise UserError("Renseignez d'abord le SIRET de la société : c'est lui qui l'identifie sur l'annuaire.")
        return self.action_open_pdp_form()

    def action_cultiveau_double_auth(self):
        self.env["res.company"].cultiveau_activer_double_authentification()
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"title": "Double authentification", "message": "À la prochaine connexion depuis un nouvel appareil, chaque utilisateur reçoit un code par e-mail.", "sticky": False,
                           "next": {"type": "ir.actions.client", "tag": "reload"}}}
