import base64

from odoo import api, fields, models
from odoo.exceptions import UserError

from ..models import formats


class ImportReleve(models.TransientModel):
    _name = "cultiveau.import.releve"
    _description = "Importer un relevé bancaire"

    journal_id = fields.Many2one("account.journal", "Compte bancaire", required=True, domain="[('type', '=', 'bank'), ('company_id', '=', company_id)]")
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, required=True)
    fichier = fields.Binary("Fichier du relevé", required=True, help="Le relevé téléchargé sur le site de la banque : CSV, OFX, CAMT.053 (XML) ou QIF.")
    nom_fichier = fields.Char("Nom du fichier")

    @api.model
    def default_get(self, champs):
        valeurs = super().default_get(champs)
        if "journal_id" in champs and not valeurs.get("journal_id"):
            banque = self.env["account.journal"].search([("type", "=", "bank"), ("company_id", "=", self.env.company.id), ("code", "!=", "CHQ")], limit=1)
            valeurs["journal_id"] = banque.id
        return valeurs

    def action_importer(self):
        self.ensure_one()
        contenu = base64.b64decode(self.fichier or b"")
        try:
            lues, solde_debut, solde_fin = formats.lire(self.nom_fichier or "releve", contenu)
        except Exception as e:  # noqa: BLE001 — on explique
            raise UserError(f"Relevé illisible ({e.__class__.__name__}) : envoyez le CSV, l'OFX, le CAMT.053 ou le QIF de la banque.") from e
        if not lues:
            raise UserError("Aucune opération trouvée dans ce fichier (il faut une date et un montant par ligne).")
        Ligne = self.env["account.bank.statement.line"].with_company(self.company_id)
        deja = set(Ligne.search([("journal_id", "=", self.journal_id.id), ("cultiveau_empreinte", "in", [l["empreinte"] for l in lues])]).mapped("cultiveau_empreinte"))
        nouvelles = [l for l in lues if l["empreinte"] not in deja]
        if not nouvelles:
            raise UserError(f"Les {len(lues)} opérations de ce fichier sont déjà importées.")
        dates = [l["date"] for l in nouvelles]
        releve = self.env["account.bank.statement"].with_company(self.company_id).create({
            "name": f"{self.nom_fichier or 'Relevé'} ({min(dates):%d/%m/%Y} → {max(dates):%d/%m/%Y})", "journal_id": self.journal_id.id, "date": max(dates),
            **({"balance_start": solde_debut} if solde_debut is not None else {}), **({"balance_end_real": solde_fin} if solde_fin is not None else {})})
        lignes = Ligne.create([{"statement_id": releve.id, "journal_id": self.journal_id.id, "date": l["date"], "payment_ref": l["libelle"], "amount": l["montant"],
                                "ref": l["reference"][:64] if l["reference"] else False, "cultiveau_empreinte": l["empreinte"]} for l in sorted(nouvelles, key=lambda l: l["date"])])
        faites, restantes = lignes.cultiveau_rapprocher_auto()
        action = self.env["ir.actions.act_window"]._for_xml_id("cultiveau_compta.action_a_rapprocher")
        action["display_name"] = f"{len(lignes)} opérations importées, {faites} rapprochées d'elles-mêmes, {restantes} à voir"
        action["domain"] = [("journal_id", "=", self.journal_id.id), ("is_reconciled", "=", False)]
        action["context"] = {"search_default_journal_id": self.journal_id.id}
        return action
