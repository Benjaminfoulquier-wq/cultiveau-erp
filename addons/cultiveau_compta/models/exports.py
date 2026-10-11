"""Ce que le comptable demande : le FEC, le grand livre, la balance, les journaux. En texte, lisibles par n'importe quel logiciel."""

import io
import csv

from odoo import fields, models


def _nombre(v):
    return f"{v:.2f}".replace(".", ",")


class Export(models.AbstractModel):
    _name = "cultiveau.export.compta"
    _description = "Exports comptables"

    def _ecritures(self, societe, debut, fin):
        return self.env["account.move.line"].search(
            [("company_id", "=", societe.id), ("parent_state", "=", "posted"), ("date", ">=", debut), ("date", "<=", fin), ("display_type", "not in", ("line_section", "line_note"))],
            order="date, move_id, id")

    def fec(self, societe, debut, fin):
        """Le fichier des écritures comptables (art. A.47 A-1 du LPF) : 18 colonnes, séparées par |, dates AAAAMMJJ, décimales à la virgule."""
        lignes = ["JournalCode|JournalLib|EcritureNum|EcritureDate|CompteNum|CompteLib|CompAuxNum|CompAuxLib|PieceRef|PieceDate|EcritureLib|Debit|Credit|EcritureLet|DateLet|ValidDate|Montantdevise|Idevise"]
        for l in self._ecritures(societe, debut, fin):
            move, tiers = l.move_id, l.partner_id
            devise = l.currency_id if l.currency_id and l.currency_id != societe.currency_id else None
            lettre = l.full_reconcile_id
            lettrage = l.matching_number if lettre else ""
            lignes.append("|".join(x.replace("|", "/").replace("\n", " ") for x in (
                move.journal_id.code, move.journal_id.name, move.name, move.date.strftime("%Y%m%d"), l.account_id.code, l.account_id.name,
                (tiers.ref or f"C{tiers.id}") if tiers and l.account_id.account_type in ("asset_receivable", "liability_payable") else "",
                tiers.name if tiers and l.account_id.account_type in ("asset_receivable", "liability_payable") else "",
                move.ref or move.name, (move.invoice_date or move.date).strftime("%Y%m%d"), l.name or move.name or "",
                _nombre(l.debit), _nombre(l.credit), lettrage, lettre.create_date.strftime("%Y%m%d") if lettre else "",
                move.date.strftime("%Y%m%d"), _nombre(abs(l.amount_currency)) if devise else "", devise.name if devise else "")))
        nom = f"{societe.cultiveau_siren()}FEC{fin.strftime('%Y%m%d')}.txt"
        return nom, "\r\n".join(lignes).encode("utf-8")

    def grand_livre(self, societe, debut, fin):
        tampon = io.StringIO()
        w = csv.writer(tampon, delimiter=";")
        w.writerow(["Compte", "Intitulé", "Date", "Journal", "Pièce", "Tiers", "Libellé", "Débit", "Crédit", "Solde", "Lettrage"])
        solde, compte_courant = 0.0, None
        for l in self._ecritures(societe, debut, fin).sorted(lambda l: (l.account_id.code, l.date, l.id)):
            if l.account_id != compte_courant:
                compte_courant, solde = l.account_id, 0.0
            solde += l.debit - l.credit
            w.writerow([l.account_id.code, l.account_id.name, l.date.strftime("%d/%m/%Y"), l.journal_id.code, l.move_id.name, l.partner_id.name or "", l.name or "",
                        _nombre(l.debit), _nombre(l.credit), _nombre(solde), l.matching_number if l.full_reconcile_id else ""])
        return f"grand-livre_{debut:%Y%m%d}_{fin:%Y%m%d}.csv", tampon.getvalue().encode("utf-8-sig")

    def balance(self, societe, debut, fin):
        tampon = io.StringIO()
        w = csv.writer(tampon, delimiter=";")
        w.writerow(["Compte", "Intitulé", "Débit", "Crédit", "Solde débiteur", "Solde créditeur"])
        groupes = self.env["account.move.line"]._read_group(
            [("company_id", "=", societe.id), ("parent_state", "=", "posted"), ("date", ">=", debut), ("date", "<=", fin)], ["account_id"], ["debit:sum", "credit:sum"], order="account_id")
        td = tc = 0.0
        for compte, debit, credit in sorted(groupes, key=lambda g: g[0].code):
            solde = debit - credit
            w.writerow([compte.code, compte.name, _nombre(debit), _nombre(credit), _nombre(solde if solde > 0 else 0), _nombre(-solde if solde < 0 else 0)])
            td, tc = td + debit, tc + credit
        w.writerow(["", "Total", _nombre(td), _nombre(tc), "", ""])
        return f"balance_{debut:%Y%m%d}_{fin:%Y%m%d}.csv", tampon.getvalue().encode("utf-8-sig")

    def journaux(self, societe, debut, fin):
        tampon = io.StringIO()
        w = csv.writer(tampon, delimiter=";")
        w.writerow(["Journal", "Date", "Pièce", "Compte", "Intitulé", "Tiers", "Libellé", "Débit", "Crédit"])
        for l in self._ecritures(societe, debut, fin).sorted(lambda l: (l.journal_id.code, l.date, l.move_id.id, l.id)):
            w.writerow([l.journal_id.code, l.date.strftime("%d/%m/%Y"), l.move_id.name, l.account_id.code, l.account_id.name, l.partner_id.name or "", l.name or "", _nombre(l.debit), _nombre(l.credit)])
        return f"journaux_{debut:%Y%m%d}_{fin:%Y%m%d}.csv", tampon.getvalue().encode("utf-8-sig")
