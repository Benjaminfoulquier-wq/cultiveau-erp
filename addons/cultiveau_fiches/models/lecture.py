"""Lire une fiche technique : le texte du PDF, puis l'IA qui en tire les caractéristiques de la famille, page à l'appui."""

import base64
import io
import json
import logging
import re
import unicodedata

import requests

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)
MISTRAL = "https://api.mistral.ai/v1"
MODELE_LECTURE = "mistral-small-latest"
MODELE_OCR = "mistral-ocr-latest"
LIMITE_TEXTE = 40000  # caractères envoyés au modèle : une fiche de 10 pages

SYSTEME = """Tu lis une fiche technique de matériel d'irrigation agricole (pompe, asperseur, goutte à goutte, tube, vanne, filtre, programmateur…).
On te donne le texte de la fiche, page par page, et la liste des caractéristiques attendues pour cette famille, avec leur unité.
Tu réponds en JSON strict :
{"resume": "une phrase sur le produit ou la gamme",
 "references": [{"reference": "la référence ou le modèle tel qu'écrit sur la fiche (ou \\"*\\" si la fiche décrit un seul produit)",
                 "caracteristiques": {"cle": {"valeur": nombre ou texte court, "page": numéro de page}}}]}
Règles : une entrée par référence ou modèle de la gamme ; les clés sont exactement celles demandées ; une valeur numérique est un nombre
dans l'unité demandée (convertis si la fiche en utilise une autre) ; si une plage est donnée, mets "min-max" ; laisse de côté ce que la
fiche ne dit pas ; n'invente rien."""


def _plat(t):
    return re.sub(r"[^a-z0-9]+", " ", unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()).strip()


class Famille(models.Model):
    _name = "cultiveau.famille.caracteristiques"
    _description = "Caractéristiques attendues d'une famille d'articles"
    _order = "sequence, name"

    name = fields.Char("Famille", required=True)
    sequence = fields.Integer(default=10)
    mots = fields.Char("Mots-clés", required=True, help="Dans le nom de l'article, de la fiche ou de sa famille, séparés par des virgules.")
    champs = fields.Text("Caractéristiques", required=True, help="Une par ligne : clé: libellé (unité). Ex. « debit_m3h: Débit (m³/h) ».")

    def liste(self):
        self.ensure_one()
        resultat = []
        for ligne in (self.champs or "").splitlines():
            if ":" in ligne:
                cle, libelle = ligne.split(":", 1)
                resultat.append((cle.strip(), libelle.strip()))
        return resultat

    @api.model
    def pour(self, textes):
        """La famille dont un mot-clé apparaît dans l'un des textes (nom d'article, de fiche, de famille)."""
        plat = " " + " ".join(_plat(t) for t in textes if t) + " "
        for f in self.search([]):
            for m in (f.mots or "").split(","):
                m = _plat(m)
                if m and re.search(r"\b" + re.escape(m), plat):
                    return f
        return self.browse()


class Fiche(models.Model):
    _inherit = "cultiveau.fiche"

    texte = fields.Text("Texte lu", help="Le texte extrait du PDF (ou de l'OCR), page par page.")
    lue_le = fields.Datetime("Lue par l'IA le")
    lecture_etat = fields.Selection([("a_lire", "À lire"), ("lue", "Lue"), ("sans_texte", "Illisible"), ("echec", "Échec")], "Lecture", default="a_lire", index=True)
    lecture_message = fields.Char("Dernier message")
    resume_ia = fields.Char("Résumé par l'IA")
    famille_carac_id = fields.Many2one("cultiveau.famille.caracteristiques", "Famille de caractéristiques")

    # ---------------------------------------------------------------- le texte

    def _cle_mistral(self):
        return (self.env["ir.config_parameter"].sudo().get_param("cultiveau.mistral_cle") or "").strip()

    def extraire_texte(self):
        """Le texte du PDF par PyPDF2 ; s'il est vide (fiche scannée) et qu'une clé existe, l'OCR de Mistral. Renvoie le texte."""
        self.ensure_one()
        if not self.fichier:
            return ""
        contenu = base64.b64decode(self.fichier)
        pages = []
        try:
            import PyPDF2
            lecteur = PyPDF2.PdfReader(io.BytesIO(contenu))
            for i, page in enumerate(lecteur.pages[:40], start=1):
                t = (page.extract_text() or "").strip()
                if t:
                    pages.append(f"--- page {i} ---\n{t}")
        except Exception as e:  # noqa: BLE001 — PDF abîmé, chiffré…
            _logger.info("Fiche %s : PDF illisible par PyPDF2 (%s)", self.id, e)
        texte = "\n".join(pages)
        if len(texte) < 200 and self._cle_mistral():
            texte = self._ocr(contenu) or texte
        self.texte = texte
        return texte

    def _ocr(self, contenu):
        """L'OCR de Mistral pour une fiche scannée : du markdown par page."""
        try:
            r = requests.post(f"{MISTRAL}/ocr", headers={"Authorization": f"Bearer {self._cle_mistral()}"}, timeout=180, json={
                "model": MODELE_OCR, "document": {"type": "document_url", "document_url": "data:application/pdf;base64," + base64.b64encode(contenu).decode()}})
            r.raise_for_status()
            return "\n".join(f"--- page {p.get('index', i) + 1} ---\n{p.get('markdown', '')}" for i, p in enumerate(r.json().get("pages", [])))
        except Exception as e:  # noqa: BLE001
            _logger.warning("Fiche %s : OCR impossible (%s)", self.id, e)
            return ""

    # ---------------------------------------------------------------- la lecture

    def action_lire(self):
        """Lit la fiche et range les caractéristiques sur ses articles. Une fiche décrivant une gamme sert chaque référence."""
        cle = self._cle_mistral()
        if not cle:
            raise UserError("Saisissez la clé Mistral dans Réglages → Cultiveau → Fiches techniques et IA.")
        for fiche in self:
            texte = fiche.texte or fiche.extraire_texte()
            if len(texte) < 50:
                fiche.write({"lecture_etat": "sans_texte", "lecture_message": "Pas de texte lisible dans ce PDF."})
                continue
            famille = fiche.famille_carac_id or self.env["cultiveau.famille.caracteristiques"].pour([fiche.name, fiche.famille, fiche.sous_famille] + fiche.produit_ids.mapped("name"))
            if not famille:
                fiche.write({"lecture_etat": "echec", "lecture_message": "Famille de caractéristiques inconnue : choisissez-la sur la fiche."})
                continue
            attendues = "\n".join(f"- {cle_}: {lib}" for cle_, lib in famille.liste())
            demande = f"Famille : {famille.name}\nCaractéristiques attendues (clé: libellé (unité)) :\n{attendues}\n\nArticles reliés : {', '.join(fiche.produit_ids.mapped('display_name')[:30]) or 'aucun'}\n\nTexte de la fiche :\n{texte[:LIMITE_TEXTE]}"
            try:
                r = requests.post(f"{MISTRAL}/chat/completions", headers={"Authorization": f"Bearer {cle}"}, timeout=180, json={
                    "model": MODELE_LECTURE, "temperature": 0.0, "response_format": {"type": "json_object"},
                    "messages": [{"role": "system", "content": SYSTEME}, {"role": "user", "content": demande}]})
                r.raise_for_status()
                reponse = json.loads(r.json()["choices"][0]["message"]["content"])
            except Exception as e:  # noqa: BLE001
                fiche.write({"lecture_etat": "echec", "lecture_message": f"Lecture refusée : {str(e)[:200]}"})
                continue
            n = fiche._ranger(reponse, famille)
            fiche.write({"lecture_etat": "lue", "lue_le": fields.Datetime.now(), "famille_carac_id": famille.id, "resume_ia": (reponse.get("resume") or "")[:255],
                         "lecture_message": f"{len(reponse.get('references') or [])} référence(s) lue(s), {n} article(s) renseigné(s)."})
        return True

    def _ranger(self, reponse, famille):
        """Chaque article relié reçoit les caractéristiques de sa référence (ou celles de la fiche entière s'il n'y en a qu'une)."""
        self.ensure_one()
        references = reponse.get("references") or []
        if not references:
            return 0
        cles = [c for c, _l in famille.liste()]

        def propre(carac):
            resultat = {}
            for cle_, v in (carac or {}).items():
                if cle_ not in cles:
                    continue
                if isinstance(v, dict):
                    valeur, page = v.get("valeur"), v.get("page")
                else:
                    valeur, page = v, None
                if valeur in (None, "", []):
                    continue
                resultat[cle_] = {"valeur": valeur, "page": page, "fiche": self.id}
            return resultat

        n = 0
        for produit in self.produit_ids:
            nom_plat = _plat(produit.name) + " " + _plat(produit.default_code or "")
            choisie = None
            for ref in references:
                r_ = _plat(str(ref.get("reference") or ""))
                if r_ and r_ != "*" and r_ in nom_plat:
                    choisie = ref
                    break
            if choisie is None and len(references) == 1:
                choisie = references[0]
            if choisie is None:
                continue
            carac = propre(choisie.get("caracteristiques"))
            if carac:
                produit.write({"cultiveau_caracteristiques": {**(produit.cultiveau_caracteristiques or {}), **carac}, "cultiveau_famille_carac_id": famille.id,
                               "cultiveau_fiche_lue_le": fields.Date.today()})
                n += 1
        return n

    @api.model
    def _cron_lire(self, lot=40):
        """Chaque nuit, un lot de fiches à lire, si la clé est là : quelques dizaines de centimes par fiche, une seule fois."""
        if not self._cle_mistral():
            return 0
        fiches = self.search([("fichier", "!=", False), ("lecture_etat", "=", "a_lire"), ("produit_ids", "!=", False)], limit=lot)
        fiches.action_lire()
        return len(fiches)


class Product(models.Model):
    _inherit = "product.template"

    cultiveau_famille_carac_id = fields.Many2one("cultiveau.famille.caracteristiques", "Famille de caractéristiques", index=True)
    cultiveau_fiche_lue_le = fields.Date("Fiche lue le")
    cultiveau_caracteristiques_texte = fields.Char("Caractéristiques (recherche)", compute="_compute_caracteristiques_texte", store=True, index="trigram")

    @api.depends("cultiveau_caracteristiques")
    def _compute_caracteristiques_texte(self):
        for p in self:
            carac = p.cultiveau_caracteristiques or {}
            morceaux = []
            for cle_, v in carac.items():
                valeur = v.get("valeur") if isinstance(v, dict) else v
                if valeur not in (None, ""):
                    morceaux.append(f"{cle_}={valeur}")
            p.cultiveau_caracteristiques_texte = " ; ".join(morceaux)[:2000] or False

    @api.depends("cultiveau_caracteristiques", "cultiveau_famille_carac_id")
    def _compute_caracteristiques_html(self):
        """Les caractéristiques lues : libellé de la famille, valeur, page de la fiche."""
        from markupsafe import Markup, escape
        for p in self:
            carac = p.cultiveau_caracteristiques or {}
            if not carac:
                p.cultiveau_caracteristiques_html = Markup("")
                continue
            libelles = dict(p.cultiveau_famille_carac_id.liste()) if p.cultiveau_famille_carac_id else {}
            lignes = []
            for cle_, v in carac.items():
                valeur, page = (v.get("valeur"), v.get("page")) if isinstance(v, dict) else (v, None)
                if valeur in (None, "", []):
                    continue
                lignes.append(f"<tr><th style='text-align:left;padding:2px 10px 2px 0;color:#5d6b78;font-weight:500'>{escape(libelles.get(cle_, str(cle_).replace('_', ' ')))}</th>"
                              f"<td style='padding:2px 0'>{escape(str(valeur))}{f' <span class=text-muted>(p. {page})</span>' if page else ''}</td></tr>")
            p.cultiveau_caracteristiques_html = Markup(f"<table style='font-size:13px'>{''.join(lignes)}</table>")

    def action_lire_fiche(self):
        fiches = self.mapped("cultiveau_fiche_id")
        if not fiches:
            raise UserError("Aucune fiche technique jointe à ces articles.")
        fiches.action_lire()
        return True

    def action_comparer(self):
        if len(self) < 2:
            raise UserError("Cochez au moins deux articles à comparer.")
        comparateur = self.env["cultiveau.comparateur"].create({"product_ids": [(6, 0, self.ids[:6])]})
        return {"type": "ir.actions.act_window", "res_model": "cultiveau.comparateur", "res_id": comparateur.id, "view_mode": "form", "target": "current", "name": "Comparer"}


class Settings(models.TransientModel):
    _inherit = "res.config.settings"

    cultiveau_mistral_cle = fields.Char("Clé Mistral", config_parameter="cultiveau.mistral_cle")
    cultiveau_fiches_a_lire = fields.Integer("Fiches à lire", compute="_compute_fiches")
    cultiveau_fiches_lues = fields.Integer("Fiches lues", compute="_compute_fiches")

    def _compute_fiches(self):
        Fiche = self.env["cultiveau.fiche"]
        for s in self:
            s.cultiveau_fiches_a_lire = Fiche.search_count([("fichier", "!=", False), ("lecture_etat", "=", "a_lire"), ("produit_ids", "!=", False)])
            s.cultiveau_fiches_lues = Fiche.search_count([("lecture_etat", "=", "lue")])

    def action_cultiveau_lire_lot(self):
        n = self.env["cultiveau.fiche"]._cron_lire(lot=20)
        return {"type": "ir.actions.client", "tag": "display_notification", "params": {"title": "Fiches techniques", "message": f"{n} fiche(s) lue(s) ; la suite se fait chaque nuit.", "sticky": False}}
