"""La bibliothèque technique : les fiches techniques, brochures, notices et listes de pièces des fournisseurs,
classées par fournisseur, famille et type, reliées aux articles du catalogue.

L'inventaire vient du Drive du réseau (donnees/bibliotheque.csv) ; chaque document garde son lien Drive. Quand le
fichier a pu être rapatrié (scripts/charger_fiches.py), il est joint au document et sa première page sert d'image,
à l'article aussi s'il n'en a pas.
"""
import base64
import csv
import io

from odoo import api, fields, models

TYPES = [("fiche", "Fiche technique"), ("brochure", "Brochure"), ("notice", "Manuel / notice"), ("pieces", "Pièces détachées"),
         ("catalogue", "Catalogue"), ("services", "Services"), ("autre", "Autre")]
TYPES_CSV = {"Fiche technique": "fiche", "Fiche technique ?": "fiche", "Brochure": "brochure", "Manuel / notice": "notice",
             "Pièces détachées": "pieces", "Catalogue": "catalogue", "Services": "services"}


class Fiche(models.Model):
    _name = "cultiveau.fiche"
    _description = "Document technique (fiche, brochure, notice)"
    _order = "fournisseur_nom, famille, name"
    _inherit = ["mail.thread"]

    name = fields.Char("Titre", required=True, index=True)
    drive_id = fields.Char("Identifiant Drive", index=True)
    url = fields.Char("Lien", help="Le document dans le Drive du réseau.")
    type_doc = fields.Selection(TYPES, "Type", default="fiche", required=True, index=True)
    fournisseur_nom = fields.Char("Fournisseur (dossier)", index=True)
    fournisseur_id = fields.Many2one("res.partner", "Fournisseur", domain="[('is_company', '=', True)]", index=True)
    famille = fields.Char("Famille", index=True)
    sous_famille = fields.Char("Sous-famille", index=True)
    source = fields.Char("Dossier d'origine")
    chemin = fields.Char("Chemin dans le Drive")
    mime = fields.Char("Format")
    taille = fields.Integer("Taille (octets)")
    notes = fields.Char("Résumé")
    fichier = fields.Binary("Fichier", attachment=True)
    fichier_nom = fields.Char("Nom du fichier")
    vignette = fields.Image("Première page", max_width=800, max_height=800)
    produit_ids = fields.One2many("product.template", "cultiveau_fiche_id", string="Articles")
    nb_produits = fields.Integer("Nombre d'articles", compute="_compute_nb_produits")
    active = fields.Boolean(default=True)

    _sql_constraints = [("drive_unique", "unique(drive_id)", "Ce document Drive est déjà dans la bibliothèque.")]

    @api.depends("produit_ids")
    def _compute_nb_produits(self):
        groupes = self.env["product.template"]._read_group([("cultiveau_fiche_id", "in", self.ids)], ["cultiveau_fiche_id"], ["__count"])
        compte = {f.id: n for f, n in groupes}
        for f in self:
            f.nb_produits = compte.get(f.id, 0)

    def action_ouvrir(self):
        self.ensure_one()
        if self.fichier:
            return {"type": "ir.actions.act_url", "url": f"/web/content/cultiveau.fiche/{self.id}/fichier/{self.fichier_nom or 'document.pdf'}?download=false", "target": "new"}
        return {"type": "ir.actions.act_url", "url": self.url, "target": "new"}

    def cultiveau_joindre(self, contenu, nom, vignette=None, propager=True):
        """Joint le fichier rapatrié (octets) au document, avec sa première page en image ; l'image devient aussi
        celle des articles reliés qui n'en ont pas. Renvoie le nombre d'articles illustrés. Sans contenu (fichier
        trop gros pour la base), seuls le nom et l'image sont gardés : le document reste ouvert depuis le Drive."""
        self.ensure_one()
        vals = {"fichier": base64.b64encode(contenu) if contenu else False, "fichier_nom": nom}
        if vignette:
            vals["vignette"] = base64.b64encode(vignette)
        self.write(vals)
        if not (propager and vignette):
            return 0
        produits = self.with_context(active_test=False).produit_ids.filtered(lambda p: not p.image_1920)
        if produits:
            produits.write({"image_1920": vals["vignette"]})
        return len(produits)

    def action_produits(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "name": f"Articles — {self.name}", "res_model": "product.template",
                "view_mode": "list,kanban,form", "domain": [("cultiveau_fiche_id", "=", self.id)]}

    @api.model
    def cultiveau_trouver_ou_creer(self, drive_id, titre=None, notes=None, cache=None):
        """Le document d'après son identifiant Drive ; créé a minima s'il n'est pas encore dans la bibliothèque."""
        if not drive_id:
            return self.browse()
        cache = cache if cache is not None else {}
        if drive_id in cache:
            return cache[drive_id]
        fiche = self.with_context(active_test=False).search([("drive_id", "=", drive_id)], limit=1)
        if not fiche:
            fiche = self.create({"name": (titre or drive_id)[:255], "drive_id": drive_id, "notes": (notes or "")[:255] or False,
                                 "url": f"https://drive.google.com/file/d/{drive_id}/view"})
        elif notes and not fiche.notes:
            fiche.notes = notes[:255]
        cache[drive_id] = fiche
        return fiche

    @api.model
    def cultiveau_importer_inventaire(self, contenu):
        """L'inventaire du Drive (bibliotheque.csv : source;fournisseur;famille;sous_famille;type_doc;titre;chemin;mime;taille_octets;id;viewUrl).
        Renvoie un bilan. Relançable : un document est reconnu par son identifiant Drive."""
        lignes = list(csv.DictReader(io.StringIO(contenu), delimiter=";"))
        existants = {f.drive_id: f for f in self.with_context(active_test=False).search([("drive_id", "!=", False)])}
        fournisseurs = {}
        bilan = {"crees": 0, "maj": 0, "ignores": 0}
        a_creer = []
        for l in lignes:
            drive_id = (l.get("id") or "").strip()
            if not drive_id:
                bilan["ignores"] += 1
                continue
            nom_f = (l.get("fournisseur") or "").strip()
            fournisseur = self._fournisseur(nom_f, fournisseurs) if nom_f and nom_f != "(racine)" else None
            valeurs = {"name": (l.get("titre") or drive_id)[:255], "drive_id": drive_id, "url": (l.get("viewUrl") or f"https://drive.google.com/file/d/{drive_id}/view")[:500],
                       "type_doc": TYPES_CSV.get((l.get("type_doc") or "").strip(), "autre"), "fournisseur_nom": nom_f[:128] or False,
                       "fournisseur_id": fournisseur.id if fournisseur else False, "famille": (l.get("famille") or "")[:128] or False,
                       "sous_famille": (l.get("sous_famille") or "")[:128] or False, "source": (l.get("source") or "")[:64] or False,
                       "chemin": (l.get("chemin") or "")[:500] or False, "mime": (l.get("mime") or "")[:128] or False,
                       "taille": int(l["taille_octets"]) if (l.get("taille_octets") or "").isdigit() else 0}
            if drive_id in existants:
                existants[drive_id].write(valeurs)
                bilan["maj"] += 1
            else:
                a_creer.append(valeurs)
        if a_creer:
            self.create(a_creer)
            bilan["crees"] = len(a_creer)
        return bilan

    def _fournisseur(self, nom, cache):
        """Le fournisseur de la fiche : un dossier Drive s'appelle souvent « Nelson_Irrigation_Fiches_techniques » ou
        « ATUSA (REF SANS PAIEMENT) » ; on cherche le partenaire fournisseur dont le nom commence pareil, sans en créer."""
        cle = nom.lower()
        if cle in cache:
            return cache[cle]
        mot = nom.split("(")[0].split("_")[0].strip()
        Partner = self.env["res.partner"]
        trouve = Partner.search([("is_company", "=", True), ("name", "=ilike", mot)], limit=1) or \
            (Partner.search([("is_company", "=", True), ("name", "=ilike", mot + "%"), ("supplier_rank", ">", 0)], limit=1) if len(mot) >= 4 else Partner)
        cache[cle] = trouve or None
        return cache[cle]
