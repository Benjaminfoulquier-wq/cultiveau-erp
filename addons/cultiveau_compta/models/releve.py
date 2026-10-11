"""Le rapprochement bancaire : chaque ligne de relevé trouve sa contrepartie (facture, paiement, compte) et le dit."""

import itertools
import re

from odoo import Command, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero

from .formats import normaliser

MOTS_VIDES = {"SARL", "EARL", "GAEC", "SCEA", "SAS", "SASU", "EURL", "ETS", "STE", "SOCIETE", "MONSIEUR", "MADAME", "MR", "MME", "M", "ET", "DE", "DU", "DES", "LA", "LE", "LES"}
CONFIANCES = [("sure", "Sûr"), ("probable", "À confirmer"), ("aucune", "À la main")]


def mots_significatifs(nom):
    return [m for m in re.split(r"[^A-Z0-9]+", normaliser(nom)) if len(m) >= 3 and m not in MOTS_VIDES]


class LigneReleve(models.Model):
    _inherit = "account.bank.statement.line"

    cultiveau_empreinte = fields.Char("Empreinte", index=True, copy=False, help="Reconnaît une opération déjà importée.")
    cultiveau_confiance = fields.Selection(CONFIANCES, "Proposition", default="aucune", copy=False)
    cultiveau_proposition = fields.Char("Contrepartie proposée", copy=False)
    cultiveau_cible_ids = fields.Many2many("account.move.line", "cultiveau_releve_cible_rel", "ligne_id", "aml_id", string="Écritures proposées", copy=False)
    cultiveau_modele_id = fields.Many2one("account.reconcile.model", "Modèle proposé", copy=False)
    cultiveau_partner_propose_id = fields.Many2one("res.partner", "Tiers reconnu", copy=False)

    # ---------------------------------------------------------------- propositions

    def cultiveau_proposer(self):
        """Pour chaque ligne non rapprochée : la facture, le paiement ou le modèle qui lui correspond, et à quel point on en est sûr."""
        for ligne in self.filtered(lambda l: not l.is_reconciled):
            ligne._cultiveau_proposer()
        return True

    def _cultiveau_proposer(self):
        self.ensure_one()
        societe, montant = self.company_id, self.amount
        libelle = normaliser(" ".join(x for x in (self.payment_ref, self.ref, self.partner_name, self.narration and re.sub("<[^>]+>", " ", self.narration)) if x))
        valeurs = {"cultiveau_confiance": "aucune", "cultiveau_proposition": "", "cultiveau_cible_ids": [Command.clear()], "cultiveau_modele_id": False, "cultiveau_partner_propose_id": False}
        Aml = self.env["account.move.line"].with_company(societe)
        ouvertes = Aml.search(self._get_default_amls_matching_domain() + [("company_id", "=", societe.id)])
        # 1. le tiers nommé dans le libellé
        tiers = self.partner_id
        if not tiers:
            candidats = {}
            for p in ouvertes.partner_id:
                mots = mots_significatifs(p.name)
                if mots and all(m in libelle for m in mots[:3]):
                    candidats[p] = len(mots)
            if candidats:
                tiers = max(candidats, key=candidats.get)
        valeurs["cultiveau_partner_propose_id"] = tiers.id if tiers else False
        # 2. une écriture du même montant : une facture, un paiement du comptoir, un acompte
        memes = ouvertes.filtered(lambda a: float_compare(a.amount_residual, montant, precision_rounding=0.01) == 0)
        score = {}
        for a in memes:
            s = 0
            nom = normaliser(a.move_id.name)
            if nom and (nom in libelle or re.sub(r"[^A-Z0-9]", "", nom) in re.sub(r"[^A-Z0-9]", "", libelle)):
                s += 3
            if a.move_id.payment_reference and normaliser(a.move_id.payment_reference) in libelle:
                s += 3
            if a.payment_id and a.payment_id.memo and normaliser(a.payment_id.memo) in libelle:
                s += 2
            if tiers and a.partner_id == tiers:
                s += 2
            if a.date and a.date <= self.date:
                s += 1 if (self.date - a.date).days <= 60 else 0
            score[a] = s
        if score:
            meilleure = max(score, key=score.get)
            if score[meilleure] >= 2 or len(memes) == 1 and score[meilleure] >= 1:
                valeurs.update(cultiveau_confiance="sure", cultiveau_cible_ids=[Command.set(meilleure.ids)], cultiveau_proposition=self._cultiveau_decrire(meilleure))
                return self.write(valeurs)
            valeurs.update(cultiveau_confiance="probable", cultiveau_cible_ids=[Command.set(meilleure.ids)], cultiveau_proposition=self._cultiveau_decrire(meilleure))
        # 3. plusieurs factures du même tiers qui font le montant
        if tiers and valeurs["cultiveau_confiance"] != "sure":
            du_tiers = ouvertes.filtered(lambda a: a.partner_id == tiers and a.account_id.account_type in ("asset_receivable", "liability_payable") and (a.amount_residual > 0) == (montant > 0))
            groupe = self._cultiveau_combinaison(du_tiers, montant)
            if groupe:
                valeurs.update(cultiveau_confiance="sure", cultiveau_cible_ids=[Command.set(groupe.ids)],
                               cultiveau_proposition=f"{len(groupe)} factures de {tiers.name} : " + ", ".join(groupe.mapped("move_id.name")))
                return self.write(valeurs)
        # 4. un modèle de rapprochement (frais bancaires, emprunt…) reconnu au libellé
        if valeurs["cultiveau_confiance"] == "aucune":
            modele = self._cultiveau_modele(libelle)
            if modele:
                compte = modele.line_ids[:1].account_id
                valeurs.update(cultiveau_confiance="sure" if modele.auto_reconcile else "probable", cultiveau_modele_id=modele.id,
                               cultiveau_proposition=f"{modele.name} → {compte.code} {compte.name}")
        return self.write(valeurs)

    def _cultiveau_decrire(self, aml):
        move = aml.move_id
        if move.is_invoice(include_receipts=True):
            genre = {"out_invoice": "Facture", "out_refund": "Avoir", "in_invoice": "Facture fournisseur", "in_refund": "Avoir fournisseur"}.get(move.move_type, "Pièce")
            return f"{genre} {move.name} — {aml.partner_id.name or ''}".strip(" —")
        if aml.payment_id:
            return f"Paiement {aml.payment_id.name} ({aml.payment_id.journal_id.name}) — {aml.partner_id.name or ''}".strip(" —")
        return f"{move.name} — {aml.account_id.code} {aml.partner_id.name or aml.account_id.name}"

    @api.model
    def _cultiveau_combinaison(self, amls, montant):
        amls = amls.sorted(lambda a: a.date or fields.Date.today())
        if not amls or len(amls) > 12:
            return amls.browse()
        if float_compare(sum(amls.mapped("amount_residual")), montant, precision_rounding=0.01) == 0 and len(amls) > 1:
            return amls
        for n in range(2, min(len(amls), 6) + 1):
            for combo in itertools.combinations(amls, n):
                if float_compare(sum(a.amount_residual for a in combo), montant, precision_rounding=0.01) == 0:
                    return amls.browse([a.id for a in combo])
        return amls.browse()

    def _cultiveau_modele(self, libelle):
        self.ensure_one()
        modeles = self.env["account.reconcile.model"].with_company(self.company_id).search(
            [("company_id", "=", self.company_id.id), ("rule_type", "in", ("writeoff_suggestion", "writeoff_button")), ("line_ids", "!=", False)], order="sequence, id")
        for m in modeles:
            if m.match_journal_ids and self.journal_id not in m.match_journal_ids:
                continue
            if m.match_nature == "amount_received" and self.amount < 0 or m.match_nature == "amount_paid" and self.amount > 0:
                continue
            param = normaliser(m.match_label_param or "")
            if m.match_label == "contains" and param and param not in libelle:
                continue
            if m.match_label == "not_contains" and param and param in libelle:
                continue
            if m.match_label == "match_regex" and (not param or not re.search(param, libelle, re.I)):
                continue
            if not m.match_label and not m.match_label_param:
                continue  # un modèle sans critère ne se devine pas
            return m
        return self.env["account.reconcile.model"]

    # ---------------------------------------------------------------- actions

    def cultiveau_rapprocher_auto(self):
        """Propose, puis applique ce qui est sûr. Renvoie (nombre rapprochées, nombre à voir)."""
        self.cultiveau_proposer()
        sures = self.filtered(lambda l: not l.is_reconciled and l.cultiveau_confiance == "sure")
        for ligne in sures:
            ligne.action_valider_proposition()
        return len(sures), len(self.filtered(lambda l: not l.is_reconciled))

    def action_proposer(self):
        self.cultiveau_proposer()
        return True

    def action_rapprocher_sur(self):
        faites, restantes = self.cultiveau_rapprocher_auto()
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"title": "Rapprochement", "message": f"{faites} ligne(s) rapprochée(s), {restantes} à voir.", "sticky": False,
                           "next": {"type": "ir.actions.client", "tag": "soft_reload"}}}

    def action_valider_proposition(self):
        for ligne in self:
            if ligne.is_reconciled:
                continue
            if ligne.cultiveau_cible_ids:
                ligne.cultiveau_lettrer_avec(ligne.cultiveau_cible_ids)
            elif ligne.cultiveau_modele_id:
                ligne.cultiveau_appliquer_modele(ligne.cultiveau_modele_id)
            else:
                raise UserError(f"Rien n'est proposé pour « {ligne.payment_ref} » : choisissez une facture ou un compte.")
        return True

    def action_choisir_facture(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "res_model": "cultiveau.rapprochement.choix", "view_mode": "form", "target": "new",
                "name": "Rapprocher avec une facture", "context": {"default_ligne_id": self.id, "default_partner_id": (self.partner_id or self.cultiveau_partner_propose_id).id}}

    def action_autre_compte(self):
        self.ensure_one()
        modele = self.cultiveau_modele_id
        return {"type": "ir.actions.act_window", "res_model": "cultiveau.rapprochement.compte", "view_mode": "form", "target": "new",
                "name": "Passer sur un compte", "context": {"default_ligne_id": self.id, "default_partner_id": (self.partner_id or self.cultiveau_partner_propose_id).id,
                                                            "default_account_id": modele.line_ids[:1].account_id.id, "default_libelle": self.payment_ref}}

    def action_acompte(self):
        """Un règlement sans facture : sur le compte du client (ou du fournisseur), à lettrer plus tard."""
        for ligne in self:
            tiers = ligne.partner_id or ligne.cultiveau_partner_propose_id
            if not tiers:
                raise UserError("Indiquez d'abord le client ou le fournisseur sur la ligne.")
            tiers = tiers.with_company(ligne.company_id)
            compte = tiers.property_account_receivable_id if ligne.amount > 0 else tiers.property_account_payable_id
            ligne._cultiveau_ecrire([{"account_id": compte.id, "partner_id": tiers.id, "montant": ligne.amount, "name": ligne.payment_ref}])
        return True

    def action_defaire(self):
        self.action_undo_reconciliation()
        self.cultiveau_proposer()
        return True

    # ---------------------------------------------------------------- écriture des contreparties

    def cultiveau_lettrer_avec(self, amls):
        """La ligne paie ces écritures : une contrepartie par écriture, lettrée avec elle ; le reste éventuel va sur le compte du tiers."""
        self.ensure_one()
        amls = amls.filtered(lambda a: not a.reconciled)
        if not amls:
            raise UserError("Ces écritures sont déjà lettrées.")
        reste = self.amount
        contreparties = []
        for a in amls:
            part = a.amount_residual if abs(a.amount_residual) <= abs(reste) + 0.005 else reste
            contreparties.append({"account_id": a.account_id.id, "partner_id": a.partner_id.id, "montant": part, "name": self.payment_ref, "cible": a})
            reste = round(reste - part, 2)
        if not float_is_zero(reste, precision_rounding=0.01):
            tiers = amls[0].partner_id.with_company(self.company_id)
            compte = tiers.property_account_receivable_id if reste > 0 else tiers.property_account_payable_id
            if amls[0].account_id.account_type in ("asset_receivable", "liability_payable"):
                compte = amls[0].account_id
            contreparties.append({"account_id": compte.id, "partner_id": tiers.id, "montant": reste, "name": f"{self.payment_ref} (solde)"})
        if not self.partner_id and amls[0].partner_id:
            self.with_context(skip_readonly_check=True).partner_id = amls[0].partner_id
        self._cultiveau_ecrire(contreparties)
        return True

    def cultiveau_appliquer_modele(self, modele):
        self.ensure_one()
        contreparties, reste = [], self.amount
        lignes = modele.line_ids
        for i, l in enumerate(lignes):
            if l.amount_type == "percentage":
                part = round(self.amount * float(l.amount_string or 100) / 100, 2)
            elif l.amount_type == "fixed":
                part = abs(float(l.amount_string or 0)) * (1 if self.amount > 0 else -1)
            else:
                part = reste
            if i == len(lignes) - 1:
                part = reste
            reste = round(reste - part, 2)
            contreparties.append({"account_id": l.account_id.id, "partner_id": (self.partner_id or self.cultiveau_partner_propose_id).id,
                                  "montant": part, "name": l.label or self.payment_ref, "taxes": l.tax_ids, "ttc": l.force_tax_included})
        self._cultiveau_ecrire(contreparties)
        return True

    def cultiveau_passer_sur_compte(self, compte, tiers, libelle, taxes=None, ttc=True):
        self.ensure_one()
        self._cultiveau_ecrire([{"account_id": compte.id, "partner_id": tiers.id if tiers else False, "montant": self.amount,
                                 "name": libelle or self.payment_ref, "taxes": taxes, "ttc": ttc}])
        return True

    def _cultiveau_ecrire(self, contreparties):
        """Remplace la ligne d'attente (471) par les contreparties, puis lettre celles qui visent une écriture."""
        self.ensure_one()
        if self.is_reconciled:
            raise UserError(f"« {self.payment_ref} » est déjà rapprochée.")
        move = self.move_id
        liquidite, attente, autres = self._seek_for_lines()
        societe = self.company_id
        commandes = [Command.delete(l.id) for l in attente]
        cibles = []
        for c in contreparties:
            montant = c["montant"]
            for vals in self._cultiveau_lignes(c, montant, societe):
                commandes.append(Command.create(vals))
                cibles.append(c.get("cible") if vals.get("cultiveau_principale") else None)
                vals.pop("cultiveau_principale", None)
        avant = move.line_ids
        move.with_context(skip_readonly_check=True, force_delete=True, skip_invoice_sync=True).write({"line_ids": commandes})
        nouvelles = (move.line_ids - avant).sorted("id")
        for ligne, cible in zip(nouvelles, cibles):
            if cible is not None and cible and not cible.reconciled and ligne.account_id == cible.account_id:
                (ligne + cible).reconcile()
        self.invalidate_recordset(["is_reconciled", "line_ids"])
        self.write({"cultiveau_confiance": "aucune", "cultiveau_cible_ids": [Command.clear()], "cultiveau_modele_id": False})
        return True

    def _cultiveau_lignes(self, c, montant, societe):
        """Les lignes comptables d'une contrepartie : la ligne elle-même et, s'il y a de la TVA, sa décomposition."""
        base = {"move_id": self.move_id.id, "partner_id": c.get("partner_id") or False, "currency_id": societe.currency_id.id,
                "name": (c.get("name") or self.payment_ref or "")[:1000]}
        taxes = c.get("taxes")
        if not taxes:
            return [{**base, "account_id": c["account_id"], "debit": -montant if montant < 0 else 0.0, "credit": montant if montant > 0 else 0.0,
                     "amount_currency": -montant, "cultiveau_principale": True}]
        signe = 1 if montant < 0 else -1  # argent sorti : charge au débit
        taxes = taxes.with_context(force_price_include=True) if c.get("ttc") else taxes
        calcul = taxes.compute_all(abs(montant), currency=societe.currency_id, quantity=1.0, handle_price_include=True)
        ht = calcul["total_excluded"]
        lignes = [{**base, "account_id": c["account_id"], "debit": ht if signe > 0 else 0.0, "credit": ht if signe < 0 else 0.0,
                   "amount_currency": ht * signe, "tax_ids": [Command.set(taxes.ids)], "tax_tag_ids": [Command.set(calcul["base_tags"])], "cultiveau_principale": True}]
        for t in calcul["taxes"]:
            lignes.append({**base, "account_id": t["account_id"] or c["account_id"], "debit": t["amount"] if signe > 0 else 0.0, "credit": t["amount"] if signe < 0 else 0.0,
                           "amount_currency": t["amount"] * signe, "tax_repartition_line_id": t["tax_repartition_line_id"], "tax_tag_ids": [Command.set(t["tag_ids"])],
                           "name": t["name"]})
        return lignes
