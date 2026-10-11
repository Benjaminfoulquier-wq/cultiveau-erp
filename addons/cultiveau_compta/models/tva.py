"""La déclaration de TVA (CA3 / CA12) lue dans les écritures, et l'écriture qui solde la TVA de la période."""

import base64
import re
from datetime import date, timedelta

from odoo import Command, api, fields, models
from odoo.exceptions import UserError

LIBELLES = {
    "box_A1": "A1 — Ventes, prestations de services", "box_A2": "A2 — Autres opérations imposables", "box_A3": "A3 — Achats de prestations de services intracommunautaires",
    "box_A4": "A4 — Importations", "box_B2": "B2 — Acquisitions intracommunautaires", "box_B4": "B4 — Achats auprès d'un assujetti non établi en France",
    "box_B5": "B5 — Régularisations", "box_E1": "E1 — Exportations hors UE", "box_E2": "E2 — Autres opérations non imposables", "box_E3": "E3 — Ventes à distance dans l'UE",
    "box_F2": "F2 — Livraisons intracommunautaires", "box_F6": "F6 — Achats en franchise", "box_F7": "F7 — Ventes de biens ou prestations par un assujetti non établi",
    "box_08_base": "08 — Taux normal 20 % : base", "box_08_taxe": "08 — Taux normal 20 % : TVA", "box_09_base": "09 — Taux réduit 5,5 % : base", "box_09_taxe": "09 — Taux réduit 5,5 % : TVA",
    "box_9B_base": "9B — Taux réduit 10 % : base", "box_9B_taxe": "9B — Taux réduit 10 % : TVA", "box_T6_base": "T6 — Taux 2,1 % : base", "box_T6_taxe": "T6 — Taux 2,1 % : TVA",
    "box_15": "15 — TVA antérieurement déduite à reverser", "box_5B": "5B — Sommes à ajouter", "box_16": "16 — Total de la TVA brute due", "box_17": "17 — dont TVA sur acquisitions intracommunautaires",
    "box_19": "19 — TVA déductible sur immobilisations", "box_20": "20 — TVA déductible sur autres biens et services", "box_21": "21 — Autre TVA à déduire",
    "box_22": "22 — Report du crédit de la déclaration précédente", "box_2C": "2C — Sommes à imputer", "box_23": "23 — Total de la TVA déductible", "box_24": "24 — dont TVA déductible sur importations",
    "box_25": "25 — Crédit de TVA", "box_TD": "TD — TVA due", "box_27": "27 — Crédit à reporter", "box_28": "28 — TVA nette due", "box_29": "29 — Taxes assimilées", "box_32": "32 — Total à payer",
}
TOUJOURS = {"box_A1", "box_08_base", "box_08_taxe", "box_16", "box_20", "box_22", "box_23", "box_25", "box_TD", "box_28", "box_32"}
ORDRE = list(LIBELLES)


class Tva(models.Model):
    _name = "cultiveau.tva"
    _description = "Déclaration de TVA"
    _inherit = ["mail.thread"]
    _order = "date_fin desc, id desc"

    name = fields.Char("Période", compute="_compute_name", store=True)
    company_id = fields.Many2one("res.company", "Société", required=True, default=lambda self: self.env.company, readonly=True)
    currency_id = fields.Many2one(related="company_id.currency_id")
    date_debut = fields.Date("Du", required=True, default=lambda self: self._periode_proposee()[0])
    date_fin = fields.Date("Au", required=True, default=lambda self: self._periode_proposee()[1])
    etat = fields.Selection([("brouillon", "À calculer"), ("calculee", "Calculée"), ("validee", "Validée, écriture passée")], "État", default="brouillon", tracking=True)
    ligne_ids = fields.One2many("cultiveau.tva.ligne", "tva_id", "Cases")
    tva_brute = fields.Monetary("TVA brute (16)", currency_field="currency_id", readonly=True)
    tva_deductible = fields.Monetary("TVA déductible (23)", currency_field="currency_id", readonly=True)
    tva_due = fields.Monetary("TVA nette due (28)", currency_field="currency_id", readonly=True)
    credit = fields.Monetary("Crédit de TVA (25)", currency_field="currency_id", readonly=True)
    report_credit = fields.Monetary("Report de crédit (22)", currency_field="currency_id", readonly=True)
    ca_ht = fields.Monetary("Chiffre d'affaires HT (A1)", currency_field="currency_id", readonly=True)
    move_id = fields.Many2one("account.move", "Écriture de TVA", readonly=True, copy=False)
    note = fields.Text("Remarques")

    _sql_constraints = [("periode_unique", "unique(company_id, date_debut, date_fin)", "Une déclaration existe déjà pour cette période.")]

    @api.depends("date_debut", "date_fin", "company_id")
    def _compute_name(self):
        mois = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
        for t in self:
            if not (t.date_debut and t.date_fin):
                t.name = "TVA"
            elif t.date_debut.month == t.date_fin.month and t.date_debut.year == t.date_fin.year:
                t.name = f"TVA {mois[t.date_debut.month - 1]} {t.date_debut.year}"
            elif t.date_debut.month == 1 and t.date_fin.month == 12:
                t.name = f"TVA année {t.date_debut.year}"
            else:
                t.name = f"TVA {t.date_debut:%d/%m/%Y} → {t.date_fin:%d/%m/%Y}"

    @api.model
    def _periode_proposee(self, societe=None):
        """La période qui suit la dernière déclaration, selon le régime : le mois, le trimestre ou l'année écoulés."""
        societe = societe or self.env.company
        derniere = self.search([("company_id", "=", societe.id)], order="date_fin desc", limit=1)
        regime = societe.cultiveau_regime_tva or "mensuel"
        if derniere:
            debut = derniere.date_fin + timedelta(days=1)
        else:
            aujourdhui = fields.Date.context_today(self)
            premier = aujourdhui.replace(day=1)
            if regime == "mensuel":
                debut = (premier - timedelta(days=1)).replace(day=1)
            elif regime == "trimestriel":
                trimestre_courant = (aujourdhui.month - 1) // 3 * 3 + 1
                debut = date(aujourdhui.year, trimestre_courant, 1)
                debut = (debut - timedelta(days=1)).replace(day=1)
                debut = date(debut.year, (debut.month - 1) // 3 * 3 + 1, 1)
            else:
                debut = date(aujourdhui.year - 1, 1, 1)
        duree = {"mensuel": 1, "trimestriel": 3, "annuel": 12}[regime]
        m, a = debut.month - 1 + duree, debut.year
        fin = date(a + m // 12, m % 12 + 1, 1) - timedelta(days=1)
        return debut, fin

    # ---------------------------------------------------------------- calcul

    def action_calculer(self):
        for t in self:
            if t.etat == "validee":
                raise UserError("Cette déclaration est validée : son écriture est passée.")
            valeurs = t._calculer()
            t.ligne_ids.unlink()
            lignes = []
            for code in ORDRE:
                v = valeurs.get(code, 0.0)
                if v or code in TOUJOURS:
                    lignes.append(Command.create({"code": code, "libelle": LIBELLES[code], "montant": v, "total": code in ("box_16", "box_23", "box_25", "box_TD", "box_28", "box_32")}))
            t.write({"ligne_ids": lignes, "etat": "calculee", "tva_brute": valeurs.get("box_16", 0), "tva_deductible": valeurs.get("box_23", 0),
                     "tva_due": valeurs.get("box_28", 0), "credit": valeurs.get("box_25", 0), "report_credit": valeurs.get("box_22", 0), "ca_ht": valeurs.get("box_A1", 0)})
        return True

    def _calculer(self):
        """Chaque case de la CA3 d'après les étiquettes fiscales des écritures de la période (le rapport de la localisation française)."""
        self.ensure_one()
        rapport = self.env.ref("l10n_fr_account.tax_report")
        lignes = {l.code: l for l in rapport.line_ids if l.code}
        tags_par_code = {}
        for code, l in lignes.items():
            for e in l.expression_ids.filtered(lambda e: e.engine == "tax_tags"):
                tags_par_code[code] = e.formula
        Tag = self.env["account.account.tag"]
        etiquettes = Tag.search([("applicability", "=", "taxes"), ("country_id", "=", self.company_id.account_fiscal_country_id.id or self.env.ref("base.fr").id),
                                 ("name", "in", [s + f for f in tags_par_code.values() for s in "+-"])])
        par_nom = {t.name: t for t in etiquettes}
        groupes = self.env["account.move.line"]._read_group(
            [("company_id", "=", self.company_id.id), ("parent_state", "=", "posted"), ("date", ">=", self.date_debut), ("date", "<=", self.date_fin),
             ("tax_tag_ids", "in", etiquettes.ids)], ["tax_tag_ids", "tax_tag_invert"], ["balance:sum"])
        somme_par_tag = {}
        for tag, invert, balance in groupes:
            somme_par_tag[tag.id] = somme_par_tag.get(tag.id, 0.0) + balance * (-1 if tag.tax_negate else 1) * (-1 if invert else 1)
        brut = {}
        for code, nom in tags_par_code.items():
            brut[code] = sum(somme_par_tag.get(par_nom[s + nom].id, 0.0) for s in "+-" if s + nom in par_nom)
        # le crédit de la déclaration précédente : le solde du compte 445670 à l'ouverture de la période
        report = self.env["account.move.line"]._read_group(
            [("company_id", "=", self.company_id.id), ("parent_state", "=", "posted"), ("date", "<", self.date_debut), ("account_id.code", "=like", "44567%")], [], ["balance:sum"])
        brut["box_22"] = max(0.0, report[0][0] or 0.0) if report else 0.0
        memo = {}

        def valeur(code, label="balance"):
            cle = (code, label)
            if cle in memo:
                return memo[cle]
            ligne = lignes.get(code)
            if not ligne:
                return 0.0
            if label in ("adjustment", "_balance_temp") and code != "box_27":
                return 0.0
            if code == "box_27" and label == "_balance_temp":
                return valeur("box_25")
            expr = ligne.expression_ids.filtered(lambda e: e.label == label)[:1]
            if not expr or expr.engine == "tax_tags":
                v = brut.get(code, 0.0)
            elif expr.engine == "external":
                v = 0.0
            else:
                v = 0.0
                # les formules du rapport : des cases qui s'ajoutent ou se retranchent, parfois multipliées (la TVA = la base × le taux)
                for signe, ref, facteur in re.findall(r"([+-]?)\s*(box_[A-Za-z0-9_]+\.[a-z_]+)(?:\s*\*\s*([0-9.]+))?", expr.formula or ""):
                    c, lab = ref.split(".")
                    v += (-1 if signe == "-" else 1) * valeur(c, lab) * (float(facteur) if facteur else 1.0)
                sous = expr.subformula or ""
                if sous.startswith("round("):
                    v = float(round(v))
                elif sous.startswith("if_above("):
                    v = v if v > 0 else 0.0
                elif sous.startswith("if_other_expr_above("):
                    autre = re.search(r"\((box_[A-Za-z0-9_]+)\.([a-z_]+)", sous)
                    v = v if autre and valeur(autre.group(1), autre.group(2)) > 0 else 0.0
            if label == "balance" and expr and expr.engine == "tax_tags":
                v = float(round(v))
            memo[cle] = round(v, 2)
            return memo[cle]

        return {code: valeur(code) for code in lignes}

    # ---------------------------------------------------------------- validation

    def action_valider(self):
        """Passe l'écriture qui solde les comptes de TVA de la période et verrouille la période pour la TVA."""
        for t in self:
            if t.etat == "brouillon":
                t.action_calculer()
            if t.move_id:
                raise UserError("L'écriture de TVA existe déjà.")
            t.move_id = t._ecriture_de_cloture()
            t.etat = "validee"
            societe = t.company_id.sudo()
            if not societe.tax_lock_date or societe.tax_lock_date < t.date_fin:
                societe.tax_lock_date = t.date_fin
            t.message_post(body=f"Déclaration validée : TVA nette due {t.tva_due:.2f} €, crédit {t.credit:.2f} €. Écriture {t.move_id.name}.")
        return True

    def _ecriture_de_cloture(self):
        self.ensure_one()
        societe = self.company_id
        Compte = self.env["account.account"].with_company(societe)
        od = self.env["account.journal"].search([("company_id", "=", societe.id), ("type", "=", "general")], order="sequence, id", limit=1)
        if not od:
            raise UserError("Aucun journal d'opérations diverses dans cette société.")
        comptes = Compte.search([("company_ids", "in", societe.id), "|", ("code", "=like", "4456%"), ("code", "=like", "4457%")])
        soldes = self.env["account.move.line"]._read_group(
            [("company_id", "=", societe.id), ("parent_state", "=", "posted"), ("date", ">=", self.date_debut), ("date", "<=", self.date_fin),
             ("account_id", "in", comptes.ids), ("move_id.cultiveau_tva_id", "=", False)], ["account_id"], ["balance:sum"])
        lignes, net = [], 0.0
        for compte, balance in soldes:
            if abs(balance) < 0.005:
                continue
            lignes.append(Command.create({"account_id": compte.id, "name": f"Solde {compte.name}", "debit": -balance if balance < 0 else 0.0, "credit": balance if balance > 0 else 0.0}))
            net -= balance  # collectée (crédit) → positif ; déductible (débit) → négatif
        credit_compte, decaisser = Compte.search([("company_ids", "in", societe.id), ("code", "=like", "44567%")], limit=1), Compte.search([("company_ids", "in", societe.id), ("code", "=like", "44551%")], limit=1)
        if not (credit_compte and decaisser):
            raise UserError("Les comptes 445510 (TVA à décaisser) et 445670 (crédit de TVA) manquent au plan comptable.")
        report = self.report_credit
        if report > 0.005:
            lignes.append(Command.create({"account_id": credit_compte.id, "name": "Crédit de TVA imputé", "credit": report}))
            net -= report
        if net > 0.005:
            lignes.append(Command.create({"account_id": decaisser.id, "name": "TVA à décaisser", "credit": round(net, 2)}))
        elif net < -0.005:
            lignes.append(Command.create({"account_id": credit_compte.id, "name": "Crédit de TVA à reporter", "debit": round(-net, 2)}))
        if not lignes:
            raise UserError("Aucune TVA sur la période : rien à solder.")
        move = self.env["account.move"].with_company(societe).create({"journal_id": od.id, "date": self.date_fin, "ref": self.name, "move_type": "entry",
                                                                      "cultiveau_tva_id": self.id, "line_ids": lignes})
        move.action_post()
        return move

    def action_annuler(self):
        for t in self:
            if t.move_id:
                t.move_id.button_draft()
                t.move_id.with_context(force_delete=True).unlink()
            t.write({"etat": "calculee", "move_id": False})
        return True

    def action_export_csv(self):
        self.ensure_one()
        contenu = "Case;Libellé;Montant\n" + "".join(f"{l.code.replace('box_', '')};{l.libelle};{l.montant:.0f}\n".replace(".", ",") for l in self.ligne_ids)
        piece = self.env["ir.attachment"].create({"name": f"{self.name}.csv", "datas": base64.b64encode(contenu.encode("utf-8-sig")),
                                                  "res_model": self._name, "res_id": self.id, "mimetype": "text/csv"})
        return {"type": "ir.actions.act_url", "url": f"/web/content/{piece.id}?download=true", "target": "self"}


class TvaLigne(models.Model):
    _name = "cultiveau.tva.ligne"
    _description = "Case de la déclaration de TVA"
    _order = "sequence, id"

    tva_id = fields.Many2one("cultiveau.tva", required=True, ondelete="cascade")
    sequence = fields.Integer(compute="_compute_sequence", store=True)
    code = fields.Char("Case", required=True)
    libelle = fields.Char("Libellé", required=True)
    montant = fields.Float("Montant (€)", digits=(16, 0))
    total = fields.Boolean("Total")

    @api.depends("code")
    def _compute_sequence(self):
        for l in self:
            l.sequence = ORDRE.index(l.code) if l.code in ORDRE else 999


class Move(models.Model):
    _inherit = "account.move"

    cultiveau_tva_id = fields.Many2one("cultiveau.tva", "Déclaration de TVA", readonly=True, index=True)
