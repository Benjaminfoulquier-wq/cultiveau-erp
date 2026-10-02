from odoo import fields, models


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
