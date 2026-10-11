import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

NOMS_JOURNAUX = {
    "Customer Invoices": "Ventes", "Vendor Bills": "Achats", "Bank": "Banque", "Cash": "Caisse",
    "Miscellaneous Operations": "Opérations diverses", "Cash Basis Taxes": "TVA sur encaissements",
    "Exchange Difference": "Écarts de change", "Inventory Valuation": "Stock", "Point of Sale": "Comptoir",
}

# Les lignes de relevé que l'on reconnaît à leur libellé : (nom, compte, motif, nature)
MODELES = [
    ("Frais bancaires", "627800", r"FRAIS|COMMISSION|COTISATION|ABONNEMENT|TENUE DE COMPTE", "amount_paid"),
    ("Agios et intérêts", "661600", r"AGIOS|INTERETS? DEBITEURS|INT\.? DEB", "amount_paid"),
    ("Échéance d'emprunt", "164000", r"ECHEANCE|ECH\.? PRET|REMBOURSEMENT PRET|REMB\.? PRET|EMPRUNT", "amount_paid"),
    ("TVA payée", "445510", r"DGFIP|TVA|IMPOT", "amount_paid"),
    ("URSSAF", "431000", r"URSSAF", "amount_paid"),
    ("Virement interne", "580000", r"VIR(EMENT)? INTERNE|VIREMENT DE COMPTE A COMPTE", "both"),
]


class Company(models.Model):
    _inherit = "res.company"

    cultiveau_regime_tva = fields.Selection(
        [("mensuel", "CA3 chaque mois (réel normal)"), ("trimestriel", "CA3 chaque trimestre (réel normal, TVA < 4 000 €/an)"),
         ("annuel", "CA12 une fois par an (réel simplifié)")],
        "Régime de TVA", default="mensuel", help="Détermine la période proposée pour chaque déclaration.")
    cultiveau_compta_en_place = fields.Boolean("Comptabilité en place", compute="_compute_compta_en_place")

    @api.depends("chart_template")
    def _compute_compta_en_place(self):
        for c in self:
            c.cultiveau_compta_en_place = c.chart_template == "fr"

    def cultiveau_siren(self):
        self.ensure_one()
        chiffres = "".join(ch for ch in (self.company_registry or "") if ch.isdigit())
        if len(chiffres) >= 9:
            return chiffres[:9]
        tva = "".join(ch for ch in (self.vat or "") if ch.isdigit())
        return tva[2:11] if len(tva) >= 11 else "000000000"

    # ---------------------------------------------------------------- mise en place

    def cultiveau_mettre_en_place_compta(self):
        """Une société prête à tenir ses comptes : plan français, journaux lisibles, modèles de rapprochement. À relancer sans risque."""
        for societe in self:
            if societe.country_id and societe.country_id.code != "FR":
                continue
            Plan = self.env["account.chart.template"].with_company(societe)
            if societe.chart_template != "fr":
                if societe.chart_template and societe.root_id._existing_accounting():
                    _logger.warning("Société %s : plan %s avec des écritures, on ne le remplace pas.", societe.name, societe.chart_template)
                    continue
                Plan.try_loading("fr", societe, install_demo=False)
            societe._cultiveau_journaux()
            societe._cultiveau_modeles()
        return True

    def _cultiveau_compte(self, code):
        self.ensure_one()
        return self.env["account.account"].with_company(self).search([("company_ids", "in", self.id), ("code", "=", code)], limit=1)

    def _cultiveau_journaux(self):
        self.ensure_one()
        Journal = self.env["account.journal"].with_company(self)
        for j in Journal.search([("company_id", "=", self.id)]):
            if j.name in NOMS_JOURNAUX:
                j.name = NOMS_JOURNAUX[j.name]
        if not Journal.search([("company_id", "=", self.id), ("type", "=", "bank"), ("code", "=", "CHQ")], limit=1):
            compte = self._cultiveau_compte("511200")
            Journal.create({"name": "Chèques", "code": "CHQ", "type": "bank", "company_id": self.id, "sequence": 12,
                            "default_account_id": compte.id or False})
        banque = Journal.search([("company_id", "=", self.id), ("type", "=", "bank"), ("code", "!=", "CHQ")], limit=1)
        if banque and banque.name == "Bank":
            banque.name = "Banque"

    def _cultiveau_modeles(self):
        self.ensure_one()
        Modele = self.env["account.reconcile.model"].with_company(self)
        for nom, code, motif, nature in MODELES:
            if Modele.search([("company_id", "=", self.id), ("name", "=", nom)], limit=1):
                continue
            compte = self._cultiveau_compte(code)
            if not compte:
                continue
            Modele.create({"name": nom, "company_id": self.id, "rule_type": "writeoff_suggestion", "auto_reconcile": False,
                           "match_label": "match_regex", "match_label_param": motif, "match_nature": nature,
                           "line_ids": [(0, 0, {"account_id": compte.id, "amount_type": "percentage", "amount_string": "100", "label": nom})]})

    @api.model
    def _cron_compta_en_place(self):
        self.sudo().search([]).cultiveau_mettre_en_place_compta()

    @api.model
    def cultiveau_planifier_compta(self):
        """À chaque mise à jour : les sociétés sans comptabilité en ont une dès que le serveur tourne."""
        cron = self.env.ref("cultiveau_compta.cron_compta_en_place", raise_if_not_found=False)
        if cron:
            cron._trigger()

    @api.model_create_multi
    def create(self, vals_list):
        societes = super().create(vals_list)
        self.cultiveau_planifier_compta()
        return societes

    # ---------------------------------------------------------------- le comptable

    def cultiveau_inviter_comptable(self, email, nom=None):
        """Un utilisateur en lecture seule sur la comptabilité de cette société, prévenu par e-mail."""
        self.ensure_one()
        Utilisateur = self.env["res.users"].sudo()
        groupes = [self.env.ref("base.group_user").id, self.env.ref("account.group_account_readonly").id]
        utilisateur = Utilisateur.search([("login", "=", email)], limit=1)
        if utilisateur:
            utilisateur.write({"company_ids": [(4, self.id)], "groups_id": [(4, g) for g in groupes]})
        else:
            utilisateur = Utilisateur.with_context(no_reset_password=True).create({
                "name": nom or email.split("@")[0].replace(".", " ").title(), "login": email, "email": email,
                "company_id": self.id, "company_ids": [(6, 0, [self.id])], "groups_id": [(6, 0, groupes)], "lang": "fr_FR"})
        utilisateur.with_context(create_user=True).action_reset_password()
        return utilisateur


class Settings(models.TransientModel):
    _inherit = "res.config.settings"

    cultiveau_regime_tva = fields.Selection(related="company_id.cultiveau_regime_tva", readonly=False)
    cultiveau_compta_en_place = fields.Boolean(related="company_id.cultiveau_compta_en_place")
    cultiveau_comptable_email = fields.Char("E-mail du comptable")

    def action_cultiveau_compta_en_place(self):
        self.company_id.cultiveau_mettre_en_place_compta()
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_cultiveau_inviter_comptable(self):
        self.ensure_one()
        if not self.cultiveau_comptable_email:
            return False
        self.company_id.cultiveau_inviter_comptable(self.cultiveau_comptable_email.strip())
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"title": "Comptable invité", "message": f"{self.cultiveau_comptable_email} reçoit un e-mail pour choisir son mot de passe ; il voit la comptabilité sans pouvoir la modifier.", "sticky": False}}
