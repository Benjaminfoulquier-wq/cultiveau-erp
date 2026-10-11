from odoo import api, fields, models
from odoo.exceptions import UserError


class ResCompany(models.Model):
    """Un adhérent du réseau = une société Odoo : ses devis, factures et stocks sont les siens."""

    _inherit = "res.company"

    cultiveau_adherent = fields.Boolean("Adhérent du réseau Cultiveau", default=True)
    cultiveau_numero_dedie = fields.Char(
        "Numéro dédié de l'assistant téléphonique",
        help="Le numéro de la plateforme vocale vers lequel l'adhérent renvoie ses appels (+33…). "
             "C'est par lui que l'assistant sait pour quel adhérent il décroche.")
    cultiveau_dte_slug = fields.Char("Dossier DTe", help="Identifiant du dossier de l'entreprise dans le DTe (dte.cultiveau.fr).")
    cultiveau_disc_slug = fields.Char("Entreprise DISC", help="Identifiant de l'entreprise dans l'outil Management (disc.cultiveau.fr).")
    cultiveau_assistant_id = fields.Integer("N° d'adhérent dans l'assistant", help="Le numéro de l'adhérent dans l'assistant téléphonique (/adherents/<n>/).")

    @api.model_create_multi
    def create(self, vals_list):
        """Un adhérent est en France et travaille en euros, quel que soit l'outil qui crée la société."""
        france, euro = self.env.ref("base.fr", raise_if_not_found=False), self.env.ref("base.EUR", raise_if_not_found=False)
        for vals in vals_list:
            if france and not vals.get("country_id"):
                vals["country_id"] = france.id
            if euro and not vals.get("currency_id"):
                vals["currency_id"] = euro.id
        return super().create(vals_list)

    @api.model
    def cultiveau_tout_en_euros(self):
        """Toutes les sociétés en euros et en France, tout le monde en français ; lancé à chaque mise à jour."""
        euro, france = self.env.ref("base.EUR"), self.env.ref("base.fr")
        if not euro.active:
            euro.active = True
        Ecriture = self.env.get("account.move.line")
        for societe in self.sudo().search([("currency_id", "!=", euro.id)]):
            if Ecriture is not None and Ecriture.sudo().search_count([("company_id", "=", societe.id)]):
                continue  # des écritures existent : la devise ne se change plus
            try:
                societe.write({"currency_id": euro.id, "country_id": societe.country_id.id or france.id})
            except UserError:
                continue
        self.sudo().search([("partner_id.country_id", "=", False)]).write({"country_id": france.id})
        # les listes de prix aussi : c'est leur devise qui fait celle du devis
        Liste = self.env.get("product.pricelist")
        if Liste is not None:
            Liste.sudo().with_context(active_test=False).search([("currency_id", "!=", euro.id)]).write({"currency_id": euro.id})
        Devis = self.env.get("sale.order")
        if Devis is not None:  # les devis en cours suivent leur liste de prix ; les commandes confirmées ne bougent pas
            en_cours = Devis.sudo().search([("state", "in", ("draft", "sent")), ("currency_id", "!=", euro.id)])
            self.env.add_to_compute(Devis._fields["currency_id"], en_cours)
            en_cours.modified(["pricelist_id"])
        # tout le monde en français : utilisateurs, nouveaux utilisateurs, clients (c'est la langue des devis et des e-mails)
        Langue = self.env["res.lang"].sudo()
        if not Langue.search_count([("code", "=", "fr_FR"), ("active", "=", True)]):
            Langue._activate_lang("fr_FR")
            modules = self.env["ir.module.module"].sudo().search([("state", "=", "installed")])
            modules._update_translations("fr_FR")
        self.env["res.users"].sudo().with_context(active_test=False).search([("lang", "!=", "fr_FR")]).write({"lang": "fr_FR"})
        self.env["res.partner"].sudo().with_context(active_test=False).search([("lang", "!=", "fr_FR")]).write({"lang": "fr_FR"})

    def cultiveau_liens(self):
        """Les adresses de l'entreprise dans chaque outil du réseau, d'après les réglages généraux."""
        self.ensure_one()
        param = self.env["ir.config_parameter"].sudo().get_param
        base = {k: (param(f"cultiveau.url_{k}") or "").rstrip("/") for k in ("assistant", "dte", "disc", "academie")}
        liens = []
        if base["assistant"]:
            liens.append(("Assistant téléphonique et CRM", f"{base['assistant']}/adherents/{self.cultiveau_assistant_id}/crm/" if self.cultiveau_assistant_id else base["assistant"]))
        if base["dte"]:
            liens.append(("DTe — diagnostic d'entreprise", f"{base['dte']}/a/{self.cultiveau_dte_slug}/" if self.cultiveau_dte_slug else base["dte"]))
        if base["disc"]:
            liens.append(("Management — DISC, one-to-one", f"{base['disc']}/e/{self.cultiveau_disc_slug}/" if self.cultiveau_disc_slug else base["disc"]))
        if base["academie"]:
            liens.append(("Académie — e-learning", base["academie"]))
        return liens
