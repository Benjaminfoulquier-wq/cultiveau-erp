"""Les notes de frais : la photo du ticket lue par l'IA, l'envoi au gérant, la validation, le remboursement.

Sur le module standard des notes de frais. Le ticket (photo ou PDF) passe par l'OCR de Mistral puis par une lecture
structurée : date, fournisseur, total TTC, TVA par taux, catégorie. La note est remplie, il ne reste qu'à l'envoyer.
Les catégories sont françaises, chacune avec son compte de charge et son taux de TVA habituel.
"""
import base64
import json
import logging
import re

import requests

from odoo import api, fields, models
from odoo.exceptions import UserError

from .equipe import euros

_logger = logging.getLogger(__name__)

MISTRAL = "https://api.mistral.ai/v1"
MODELE_OCR = "mistral-ocr-latest"
MODELE_LECTURE = "mistral-small-latest"

# clé, nom, référence, comptes de charge (le premier trouvé), taux de TVA habituel (None : pas de TVA récupérable), nature
CATEGORIES = [
    ("repas", "Repas", "CV_REPAS", ["625600", "625100"], 10.0, "service"),
    ("carburant", "Carburant", "CV_CARBU", ["606100", "606800"], 20.0, "consu"),
    ("peage", "Péage et parking", "CV_PEAGE", ["625100"], 20.0, "service"),
    ("hotel", "Hôtel", "CV_HOTEL", ["625100"], None, "service"),
    ("fournitures", "Petites fournitures et outillage", "CV_FOURN", ["606300", "606800"], 20.0, "consu"),
    ("km", "Indemnités kilométriques", "CV_IK", ["625100"], None, "service"),
    ("autre", "Autre dépense", "EXP_GEN", ["625100"], 20.0, "service"),
]
STANDARDS_A_RANGER = ["hr_expense.expense_product_meal", "hr_expense.expense_product_travel_accommodation", "hr_expense.expense_product_mileage",
                      "hr_expense.expense_product_gift", "hr_expense.expense_product_communication"]
ETATS = {"draft": ("À envoyer", "ambre"), "reported": ("À envoyer", "ambre"), "submitted": ("Envoyée", "bleu"), "approved": ("Validée", "vert"),
         "done": ("Remboursée", "vert"), "refused": ("Refusée", "rouge")}

SYSTEME_TICKET = """Tu lis un ticket de caisse ou une facture pour une note de frais d'une entreprise d'irrigation agricole.
Réponds uniquement en JSON :
{"date": "AAAA-MM-JJ", "fournisseur": "nom de l'enseigne", "total_ttc": nombre, "devise": "EUR",
 "tva": [{"taux": 20, "montant": 1.23}], "categorie": "repas|carburant|peage|hotel|fournitures|autre",
 "description": "quelques mots (ex. Déjeuner 2 couverts, Gazole 45 L, Raccords PE)", "confiance": "haute|moyenne|basse"}
Montants en nombres avec un point décimal. Une valeur illisible vaut null. La TVA : chaque taux présent sur le ticket.
Catégories : repas (restaurant, boulangerie, sandwich), carburant (station-service, gazole, essence, AdBlue), peage (autoroute,
parking), hotel (nuitée), fournitures (quincaillerie, outillage, raccords, petites fournitures), autre."""


def _nombre(v):
    if v in (None, "", False):
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(re.sub(r"[^0-9,.\-]", "", str(v)).replace(",", "."))
    except ValueError:
        return 0.0


class Frais(models.AbstractModel):
    _name = "cultiveau.frais"
    _description = "Notes de frais de l'équipe"

    # ---------------------------------------------------------------- les catégories

    @api.model
    def _preparer_categories(self):
        """Les catégories françaises (une fois créées, on ne touche qu'aux comptes et taxes manquants)."""
        Product = self.env["product.product"].sudo().with_context(active_test=False)
        langues = {code for code, _n in self.env["res.lang"].get_installed()} | {"en_US"}
        for cle, nom, ref, _comptes, _taux, nature in CATEGORIES:
            p = Product.search([("default_code", "=", ref)], limit=1)
            if not p:
                p = Product.create({"name": nom, "default_code": ref, "type": nature, "can_be_expensed": True, "purchase_ok": True, "sale_ok": False,
                                    "standard_price": 0.0, "supplier_taxes_id": [(5, 0, 0)], "taxes_id": [(5, 0, 0)]})
                for code in langues:
                    p.with_context(lang=code).write({"name": nom})
            elif ref == "EXP_GEN" and p.with_context(lang="en_US").name == "Expenses":
                for code in langues:
                    p.with_context(lang=code).write({"name": nom})
            if not p.active or not p.can_be_expensed:
                p.write({"active": True, "can_be_expensed": True})
        for xmlid in STANDARDS_A_RANGER:
            p = self.env.ref(xmlid, raise_if_not_found=False)
            if p and p.active:
                p.sudo().write({"active": False})
        for company in self.env["res.company"].sudo().search([]):
            self._preparer_comptes(company)

    def _preparer_comptes(self, company):
        km = float(self.env["ir.config_parameter"].sudo().get_param("cultiveau.frais_km") or 0.636)
        for cle, _nom, ref, comptes, taux, nature in CATEGORIES:
            p = self._categorie(cle)
            if not p:
                continue
            p = p.sudo().with_company(company)
            vals = {}
            if not p.property_account_expense_id:
                for code in comptes:
                    compte = self.env["account.account"].sudo().with_company(company).search([("code", "=", code), ("company_ids", "in", company.id)], limit=1)
                    if compte:
                        vals["property_account_expense_id"] = compte.id
                        break
            if cle == "km" and not p.standard_price:
                vals["standard_price"] = km
            les_siennes = p.supplier_taxes_id.filtered(lambda t: t.company_id == company)
            if taux is None and les_siennes:
                vals["supplier_taxes_id"] = [(3, t.id) for t in les_siennes]  # pas de TVA récupérable (hôtel, kilomètres)
            elif taux and not les_siennes.filtered(lambda t: t.amount == taux):
                taxe = self._taxe(company, taux, nature)  # sans la bonne TVA dans le plan comptable : aucune plutôt qu'une fausse
                vals["supplier_taxes_id"] = [(3, t.id) for t in les_siennes] + ([(4, taxe.id)] if taxe else [])
            if vals:
                p.write(vals)

    @api.model
    def _categorie(self, cle):
        ref = next((c[2] for c in CATEGORIES if c[0] == cle), "EXP_GEN")
        return self.env["product.product"].sudo().search([("default_code", "=", ref)], limit=1)

    @api.model
    def _cle_categorie(self, product):
        return next((c[0] for c in CATEGORIES if c[2] == product.default_code), "autre")

    @api.model
    def categories(self):
        return [{"cle": c[0], "nom": c[1]} for c in CATEGORIES if self._categorie(c[0])]

    @api.model
    def _taxe(self, company, taux, nature="service"):
        """La TVA déductible française de ce taux (hors import, intracommunautaire, immobilier ; prix hors taxe)."""
        taxes = self.env["account.tax"].sudo().search([("company_id", "=", company.id), ("type_tax_use", "=", "purchase"), ("amount_type", "=", "percent"),
                                                        ("amount", "=", taux)])
        exclus = re.compile(r"\b(EU|EX|IMPORT|R ?E|INC|intra|import|immo)", re.I)
        taxes = taxes.filtered(lambda t: not exclus.search(t.with_context(lang="en_US").name or "") and t.price_include_override != "tax_included")
        return taxes.filtered(lambda t: t.tax_scope == nature)[:1] or taxes.filtered(lambda t: not t.tax_scope)[:1] or taxes[:1]

    # ---------------------------------------------------------------- la lecture du ticket

    @api.model
    def _cle_mistral(self):
        return (self.env["ir.config_parameter"].sudo().get_param("cultiveau.mistral_cle") or "").strip()

    @api.model
    def _lire_contenu(self, contenu, mimetype):
        """Le ticket brut → le dictionnaire lu par l'IA (OCR puis lecture structurée ; l'image directement si l'OCR échoue)."""
        cle = self._cle_mistral()
        entetes = {"Authorization": f"Bearer {cle}"}
        donnee = f"data:{mimetype or 'image/jpeg'};base64," + base64.b64encode(contenu).decode()
        texte = ""
        try:
            document = {"type": "document_url", "document_url": donnee} if "pdf" in (mimetype or "") else {"type": "image_url", "image_url": donnee}
            r = requests.post(f"{MISTRAL}/ocr", headers=entetes, timeout=120, json={"model": MODELE_OCR, "document": document})
            r.raise_for_status()
            texte = "\n".join(p.get("markdown", "") for p in r.json().get("pages", []))
        except Exception as e:  # noqa: BLE001
            _logger.info("Ticket : OCR impossible (%s), lecture directe de l'image", e)
        if texte.strip():
            contenu_message = f"Texte du ticket :\n{texte[:12000]}"
        elif "pdf" not in (mimetype or ""):
            contenu_message = [{"type": "text", "text": "Voici la photo du ticket."}, {"type": "image_url", "image_url": donnee}]
        else:
            raise UserError("Le PDF n'a pas pu être lu.")
        r = requests.post(f"{MISTRAL}/chat/completions", headers=entetes, timeout=120, json={
            "model": MODELE_LECTURE, "temperature": 0.0, "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": SYSTEME_TICKET}, {"role": "user", "content": contenu_message}]})
        r.raise_for_status()
        return json.loads(r.json()["choices"][0]["message"]["content"])

    @api.model
    def lire(self, expense):
        """Lit le ticket joint à la note et la remplit. Renvoie un court résumé (ou lève une erreur lisible)."""
        expense = expense.sudo()
        if not self._cle_mistral():
            expense.write({"cultiveau_lecture": "sans_cle", "cultiveau_lecture_message": "Lecture automatique non configurée (clé Mistral)."})
            return expense.cultiveau_lecture_message
        piece = expense.message_main_attachment_id or expense.attachment_ids[:1]
        if not piece:
            raise UserError("Pas de ticket joint à cette note.")
        try:
            lu = self._lire_contenu(base64.b64decode(piece.datas), piece.mimetype)
        except Exception as e:  # noqa: BLE001
            expense.write({"cultiveau_lecture": "echec", "cultiveau_lecture_message": f"Ticket illisible : {str(e)[:180]}"})
            return expense.cultiveau_lecture_message
        return self._appliquer(expense, lu)

    def _appliquer(self, expense, lu):
        total = round(_nombre(lu.get("total_ttc")), 2)
        cle = lu.get("categorie") if lu.get("categorie") in {c[0] for c in CATEGORIES} else "autre"
        vals = {}
        if expense.state in ("draft", "reported") and self._cle_categorie(expense.product_id) == "autre" and cle != "autre":
            p = self._categorie(cle)
            if p:
                vals["product_id"] = p.id
        d = fields.Date.to_date(lu.get("date")) if isinstance(lu.get("date"), str) and re.match(r"^\d{4}-\d{2}-\d{2}$", lu["date"]) else None
        if d and d <= fields.Date.context_today(self):
            vals["date"] = d
        fournisseur = (lu.get("fournisseur") or "").strip()
        description = (lu.get("description") or "").strip()
        nom = " — ".join(x for x in (fournisseur, description) if x)
        if nom and (not expense.name or expense.name == (expense.message_main_attachment_id.name or "").rsplit(".", 1)[0]):
            vals["name"] = nom[:120]
        if fournisseur:
            vendeur = self.env["res.partner"].sudo().search([("name", "=ilike", fournisseur)], limit=1)
            if vendeur:
                vals["vendor_id"] = vendeur.id
        if vals:
            expense.write(vals)
        # le montant et la TVA après la catégorie (qui recalcule les taxes par défaut)
        vals = {}
        if total > 0 and not expense.product_has_cost:
            vals["total_amount_currency"] = total
        tvas = [t for t in (lu.get("tva") or []) if isinstance(t, dict) and _nombre(t.get("taux")) > 0]
        if tvas:
            principal = max(tvas, key=lambda t: _nombre(t.get("montant")))
            nature = next((c[5] for c in CATEGORIES if c[0] == self._cle_categorie(expense.product_id)), "service")
            taxe = self._taxe(expense.company_id, _nombre(principal.get("taux")), nature)
            vals["tax_ids"] = [(6, 0, taxe.ids)] if taxe else [(5, 0, 0)]
        elif lu.get("tva") == [] or self._cle_categorie(expense.product_id) == "hotel":
            vals["tax_ids"] = [(5, 0, 0)]
        detail = ", ".join(f"TVA {_nombre(t.get('taux')):g} % : {euros(_nombre(t.get('montant')))}" for t in tvas)
        resume = " · ".join(x for x in (euros(total) if total else "", expense.product_id.name, expense.date.strftime("%d/%m") if expense.date else "", detail) if x)
        vals.update({"cultiveau_lecture": "lu", "cultiveau_confiance": lu.get("confiance") if lu.get("confiance") in ("haute", "moyenne", "basse") else "moyenne",
                     "cultiveau_lecture_message": f"Lu : {resume}"[:250]})
        if len(tvas) > 1:
            vals["description"] = ((expense.description or "") + f"\nTicket à plusieurs taux : {detail}").strip()
        expense.write(vals)
        return expense.cultiveau_lecture_message

    # ---------------------------------------------------------------- les notes de la personne

    @api.model
    def depuis_photo(self, nom_fichier, contenu, mimetype=None, montant=0.0, categorie=None, kilometres=0.0, note=""):
        """Une note de frais à partir d'une photo (ou PDF) de ticket, pour la personne connectée ; ou des kilomètres sans ticket."""
        e = self.env["cultiveau.equipe"].employe()
        if not e:
            raise UserError("Vous n'avez pas de fiche salarié dans cette société.")
        kilometres = _nombre(kilometres)
        cle = "km" if kilometres else (categorie or "autre")
        p = self._categorie(cle) or self._categorie("autre")
        vals = {"name": note or (nom_fichier or "").rsplit(".", 1)[0] or p.name, "employee_id": e.id, "product_id": p.id, "payment_mode": "own_account"}
        if kilometres:
            vals.update({"quantity": kilometres, "name": note or f"{kilometres:g} km"})
        expense = self.env["hr.expense"].create(vals)
        if _nombre(montant) and not kilometres:
            expense.total_amount_currency = _nombre(montant)
        if contenu:
            piece = self.env["ir.attachment"].create({"name": nom_fichier or "ticket.jpg", "datas": base64.b64encode(contenu), "res_model": "hr.expense",
                                                      "res_id": expense.id, "mimetype": mimetype or "image/jpeg"})
            expense._message_set_main_attachment_id(piece, force=True)
            if not kilometres:
                self.lire(expense)
                if _nombre(montant):
                    expense.total_amount_currency = _nombre(montant)  # le montant saisi l'emporte sur la lecture
        return self._ligne(expense)

    @api.model
    def _ligne(self, x):
        x = x.sudo()
        etat, couleur = ETATS.get(x.state, (x.state, "ardoise"))
        return {"id": x.id, "nom": x.name, "employe": x.employee_id.name, "user_id": x.employee_id.user_id.id, "date": fields.Date.to_string(x.date),
                "date_texte": x.date.strftime("%d/%m") if x.date else "", "categorie": x.product_id.name, "cle": self._cle_categorie(x.product_id), "montant": round(x.total_amount, 2), "montant_texte": euros(x.total_amount),
                "tva": round(x.tax_amount, 2), "etat": x.state, "etat_nom": etat, "couleur": couleur, "lecture": x.cultiveau_lecture or "",
                "lecture_message": x.cultiveau_lecture_message or "", "ticket": bool(x.message_main_attachment_id), "note_id": x.sheet_id.id}

    @api.model
    def mes_frais(self, user=None, limite=20):
        e = self.env["cultiveau.equipe"].employe(user, creer=False)
        if not e:
            return []
        return [self._ligne(x) for x in self.env["hr.expense"].sudo().search([("employee_id", "=", e.id)], order="date desc, id desc", limit=limite)]

    @api.model
    def envoyer(self, expense_ids=None):
        """Envoie au gérant les notes à envoyer de la personne connectée (ou celles données). Renvoie {message, notes}."""
        e = self.env["cultiveau.equipe"].employe(creer=False)
        domaine = [("employee_id", "=", e.id), ("state", "in", ("draft", "reported")), ("sheet_id", "=", False)]
        if expense_ids:
            domaine.append(("id", "in", [int(i) for i in expense_ids]))
        notes = self.env["hr.expense"].search(domaine)
        if not notes:
            raise UserError("Aucune note de frais à envoyer.")
        vides = notes.filtered(lambda x: not x.total_amount_currency)
        if vides:
            raise UserError(f"Montant manquant : {', '.join(vides.mapped('name'))}.")
        notes.action_submit_expenses()
        feuilles = notes.sheet_id
        feuilles.action_submit_sheet()
        total = sum(feuilles.mapped("total_amount"))
        for f in feuilles.sudo():
            self.env["cultiveau.evenement"].publier("frais", f, f"Note de frais — {f.employee_id.name}", f"{len(f.expense_line_ids)} dépense(s) · {euros(f.total_amount)}",
                                                    charge={"user_id": f.employee_id.user_id.id, "montant": f.total_amount}, company=f.company_id)
        return {"message": f"{len(notes)} dépense(s) envoyée(s) au gérant · {euros(total)}", "notes": [self._feuille(f) for f in feuilles]}

    # ---------------------------------------------------------------- la validation

    @api.model
    def _feuille(self, f):
        etat, couleur = {"submit": ("À valider", "ambre"), "approve": ("Validée", "vert"), "post": ("À rembourser", "bleu"), "done": ("Remboursée", "vert"),
                         "cancel": ("Refusée", "rouge"), "draft": ("Brouillon", "ardoise")}.get(f.state, (f.state, "ardoise"))
        return {"id": f.id, "nom": f.name, "employe": f.employee_id.name, "user_id": f.employee_id.user_id.id, "montant": round(f.total_amount, 2),
                "montant_texte": euros(f.total_amount), "lignes": [self._ligne(x) for x in f.expense_line_ids], "etat": f.state, "etat_nom": etat, "couleur": couleur}

    @api.model
    def a_valider(self):
        feuilles = self.env["hr.expense.sheet"].search([("state", "=", "submit"), ("company_id", "=", self.env.company.id)], order="id")
        return [self._feuille(f) for f in feuilles if f.can_approve]

    @api.model
    def decider(self, sheet_id, oui=True, motif=""):
        """Valide (et comptabilise si réglé ainsi) ou refuse une note, avec les droits de la personne connectée."""
        f = self.env["hr.expense.sheet"].browse(int(sheet_id)).exists()
        if not f:
            raise UserError("Note de frais introuvable.")
        if oui:
            f._check_can_approve()
            f._validate_analytic_distribution()
            if f.expense_line_ids.duplicate_expense_ids.filtered(lambda x: x.state in ("approved", "done")):
                raise UserError("Une dépense de cette note ressemble à une dépense déjà validée : vérifiez-la dans l'ERP avant de valider.")
            f._do_approve()
            message = f"Note de {f.employee_id.name} validée · {euros(f.total_amount)}"
            if self.env["ir.config_parameter"].sudo().get_param("cultiveau.frais_comptabiliser"):
                try:
                    with self.env.cr.savepoint():
                        f.sudo().action_sheet_move_post()
                    message += ", passée en comptabilité (à rembourser)"
                except Exception as e:  # noqa: BLE001 — la validation reste acquise
                    message += f" (comptabilisation à faire : {str(e)[:120]})"
        else:
            f._check_can_refuse()
            f._do_refuse(motif or "Refusée")
            message = f"Note de {f.employee_id.name} refusée."
        self.env["cultiveau.evenement"].publier("frais", f, f"Note de frais {'validée' if oui else 'refusée'} — {f.employee_id.name}", euros(f.total_amount),
                                                charge={"user_id": f.employee_id.user_id.id, "montant": f.total_amount}, company=f.company_id)
        return {"message": message, "note": self._feuille(f)}

    @api.model
    def _cron_lire(self, lot=20):
        """Les tickets joints sans montant, pas encore lus (déposés depuis le back-office) : lus en lot."""
        if not self._cle_mistral():
            return
        for x in self.env["hr.expense"].sudo().search([("state", "in", ("draft", "reported")), ("cultiveau_lecture", "=", False),
                                                       ("total_amount_currency", "=", 0), ("message_main_attachment_id", "!=", False)], limit=lot):
            try:
                self.lire(x)
                self.env.cr.commit()
            except Exception as e:  # noqa: BLE001
                self.env.cr.rollback()
                _logger.warning("Note de frais %s : lecture impossible (%s)", x.id, e)


class Expense(models.Model):
    _inherit = "hr.expense"

    cultiveau_lecture = fields.Selection([("lu", "Lu par l'IA"), ("echec", "Illisible"), ("sans_cle", "Lecture non configurée")], "Lecture du ticket", copy=False)
    cultiveau_lecture_message = fields.Char("Résultat de la lecture", copy=False)
    cultiveau_confiance = fields.Selection([("haute", "Haute"), ("moyenne", "Moyenne"), ("basse", "Basse — à vérifier")], "Confiance", copy=False)

    def action_cultiveau_lire_ticket(self):
        for x in self:
            self.env["cultiveau.frais"].lire(x)
        return True

    @api.model
    def create_expense_from_attachments(self, attachment_ids=None, view_type="list"):
        """Déposer des tickets dans la liste : chacun devient une note, lue tout de suite."""
        res = super().create_expense_from_attachments(attachment_ids, view_type)
        Frais = self.env["cultiveau.frais"]
        if Frais._cle_mistral():
            for x in self.env["ir.attachment"].browse(attachment_ids or []).filtered(lambda a: a.res_model == "hr.expense"):
                try:
                    Frais.lire(self.browse(x.res_id))
                except Exception as e:  # noqa: BLE001
                    _logger.info("Ticket %s non lu (%s)", x.id, e)
        return res
