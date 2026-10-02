import re
import unicodedata
from markupsafe import Markup, escape

from odoo import api, fields, models

COTES_3D = ["dn", "pn", "pouces", "d_ext", "ep", "L", "L1", "H", "K", "D_bride", "nb_trous", "d_trous", "notes"]
UNITES = {"unite": "uom.product_uom_unit", "unité": "uom.product_uom_unit", "u": "uom.product_uom_unit", "piece": "uom.product_uom_unit",
          "pièce": "uom.product_uom_unit", "metre": "uom.product_uom_meter", "mètre": "uom.product_uom_meter", "m": "uom.product_uom_meter",
          "ml": "uom.product_uom_meter", "kg": "uom.product_uom_kgm", "litre": "uom.product_uom_litre", "l": "uom.product_uom_litre",
          "m3": "uom.product_uom_cubic_meter", "heure": "uom.product_uom_hour", "h": "uom.product_uom_hour"}
COLONNES = {"reference": "reference", "ref": "reference", "code": "reference",
            "nom du produit": "nom", "nom": "nom", "designation": "nom", "produit": "nom",
            "fournisseur": "fournisseur", "categorie": "categorie", "famille": "categorie", "description": "description",
            "prix ht": "prix", "prix ht (eur)": "prix", "prix": "prix", "unite": "unite", "conditionnement": "conditionnement",
            "poids": "poids", "poids (kg)": "poids", "url image": "image", "image": "image",
            "fiche technique": "fiche", "delai": "delai", "delai (jours)": "delai",
            "dn": "dn", "pn": "pn", "matiere": "matiere", "raccordement": "raccordement", "diametre ext (mm)": "d_ext"}


def _normaliser(texte):
    s = unicodedata.normalize("NFKD", str(texte or "")).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[*()]", " ", s).replace("€", " eur ")
    return " ".join(s.replace("_", " ").split())


def _nombre(valeur):
    if valeur in (None, "", False):
        return None
    if isinstance(valeur, (int, float)):
        return float(valeur)
    s = re.sub(r"[^0-9.,\-]", "", str(valeur).replace(" ", "")).replace(",", ".")
    try:
        return float(s) if s not in ("", "-", ".") else None
    except ValueError:
        return None


class ProductTemplate(models.Model):
    _inherit = "product.template"

    cultiveau_dn = fields.Float("DN", digits=(8, 1), help="Diamètre nominal (mm).")
    cultiveau_pn = fields.Float("PN (bar)", digits=(8, 1), help="Pression nominale.")
    cultiveau_pouces = fields.Char("Pouces", size=12)
    cultiveau_d_ext = fields.Float("Ø extérieur (mm)", digits=(8, 1))
    cultiveau_epaisseur = fields.Float("Épaisseur (mm)", digits=(8, 2))
    cultiveau_matiere = fields.Char("Matière", index=True, help="inox 304, laiton, PE, PVC, acier galvanisé…")
    cultiveau_raccordement = fields.Char("Raccordement", index=True, help="bout à bout, fileté, à brides, rainuré, compression, électrosoudable…")
    cultiveau_conditionnement = fields.Char("Conditionnement", help="Ex. « Rouleau 500 m », « Carton de 100 ».")
    cultiveau_fiche_url = fields.Char("Fiche technique (lien)")
    cultiveau_fiche_notes = fields.Char("Fiche technique (résumé)")
    cultiveau_caracteristiques = fields.Json("Caractéristiques (données)")
    cultiveau_caracteristiques_html = fields.Html("Caractéristiques", compute="_compute_caracteristiques_html", sanitize=False)
    cultiveau_source = fields.Selection([("matrice", "Matrice d'import"), ("catalogue3d", "Catalogue 3D"), ("saisie", "Saisie")],
                                        string="Source Cultiveau", index=True)

    @api.depends("cultiveau_caracteristiques")
    def _compute_caracteristiques_html(self):
        for p in self:
            carac = p.cultiveau_caracteristiques or {}
            if not carac:
                p.cultiveau_caracteristiques_html = Markup("")
                continue
            lignes = "".join(f"<tr><th style='text-align:left;padding:2px 10px 2px 0;color:#5d6b78;font-weight:500'>{escape(str(k).replace('_', ' '))}</th>"
                             f"<td style='padding:2px 0'>{escape(str(v))}</td></tr>" for k, v in carac.items() if v not in (None, "", []))
            p.cultiveau_caracteristiques_html = Markup(f"<table style='font-size:13px'>{lignes}</table>")

    # ---------------------------------------------------------------- outils communs aux imports

    @api.model
    def _cultiveau_uom(self, libelle):
        xmlid = UNITES.get(_normaliser(libelle), "uom.product_uom_unit")
        return self.env.ref(xmlid, raise_if_not_found=False) or self.env.ref("uom.product_uom_unit")

    @api.model
    def _cultiveau_fournisseur(self, nom, cache=None):
        nom = " ".join((nom or "").split())
        if not nom:
            return self.env["res.partner"]
        if cache is not None and nom.lower() in cache:
            return cache[nom.lower()]
        Partner = self.env["res.partner"]
        f = Partner.search([("name", "=ilike", nom), ("is_company", "=", True)], limit=1)
        if not f:
            f = Partner.create({"name": nom, "is_company": True, "supplier_rank": 1, "cultiveau_type": "fournisseur", "company_id": False})
        elif not f.supplier_rank:
            f.supplier_rank = 1
        if cache is not None:
            cache[nom.lower()] = f
        return f

    @api.model
    def _cultiveau_categorie(self, nom, parent=None, cache=None):
        nom = " ".join((nom or "").split())
        if not nom:
            return parent or self.env.ref("product.product_category_all")
        cle = (parent.id if parent else 0, nom.lower())
        if cache is not None and cle in cache:
            return cache[cle]
        Cat = self.env["product.category"]
        domaine = [("name", "=ilike", nom), ("parent_id", "=", parent.id if parent else False)]
        c = Cat.search(domaine, limit=1) or Cat.create({"name": nom, "parent_id": parent.id if parent else False})
        if cache is not None:
            cache[cle] = c
        return c

    @api.model
    def _cultiveau_fournisseur_prix(self, produit, fournisseur, prix=None, reference=None, delai=None):
        """Le fournisseur de l'article, avec son prix d'achat et son délai (product.supplierinfo)."""
        if not fournisseur:
            return
        ligne = produit.seller_ids.filtered(lambda s: s.partner_id == fournisseur)[:1]
        valeurs = {}
        if prix is not None:
            valeurs["price"] = prix
        if reference:
            valeurs["product_code"] = reference
        if delai is not None:
            valeurs["delay"] = int(delai)
        if ligne:
            if valeurs:
                ligne.write(valeurs)
        else:
            self.env["product.supplierinfo"].create(dict(valeurs, partner_id=fournisseur.id, product_tmpl_id=produit.id, company_id=False))

    # ---------------------------------------------------------------- la matrice d'import Cultiveau

    @api.model
    def cultiveau_lire_matrice(self, contenu):
        """Lit le classeur (octets) ; renvoie (lignes, erreurs). L'en-tête est reconnu où qu'il soit."""
        import io

        import openpyxl

        wb = openpyxl.load_workbook(io.BytesIO(contenu), read_only=True, data_only=True)
        ws = wb.active
        lignes, erreurs, colonnes = [], [], None
        for i, row in enumerate(ws.iter_rows(values_only=True), start=1):
            if colonnes is None:
                noms = [_normaliser(c) for c in row]
                if "reference" in noms and any(n in noms for n in ("nom du produit", "nom", "designation")):
                    colonnes = [COLONNES.get(n) for n in noms]
                continue
            champs = {cle: val for cle, val in zip(colonnes, row) if cle and val not in (None, "")}
            if not champs:
                continue
            if str(champs.get("reference", "")).lower().startswith("code unique"):
                continue  # la ligne d'exemple sous l'en-tête
            if not champs.get("reference") or not champs.get("nom"):
                erreurs.append(f"ligne {i} : référence ou nom manquant")
                continue
            lignes.append(champs)
        if colonnes is None:
            erreurs.append("En-tête introuvable : il faut au moins les colonnes « Référence » et « Nom du produit ».")
        return lignes, erreurs

    @api.model
    def cultiveau_importer_matrice(self, contenu, fournisseur_defaut=None):
        """Importe la matrice ; un article est reconnu par sa référence interne. Renvoie un bilan."""
        lignes, erreurs = self.cultiveau_lire_matrice(contenu)
        bilan = {"crees": 0, "maj": 0, "ignores": 0, "erreurs": erreurs}
        cache_f, cache_c = {}, {}
        for champs in lignes:
            fournisseur = self._cultiveau_fournisseur(champs.get("fournisseur"), cache_f) or fournisseur_defaut
            if not fournisseur:
                bilan["ignores"] += 1
                bilan["erreurs"].append(f"{champs['reference']} : fournisseur manquant")
                continue
            reference = str(champs["reference"]).strip()[:64]
            valeurs = {
                "name": str(champs["nom"]).strip()[:255], "default_code": reference, "type": "consu", "is_storable": True,
                "categ_id": self._cultiveau_categorie(champs.get("categorie"), cache=cache_c).id,
                "description_sale": str(champs.get("description") or "").strip() or False,
                "list_price": _nombre(champs.get("prix")) or 0.0, "weight": _nombre(champs.get("poids")) or 0.0,
                "uom_id": self._cultiveau_uom(champs.get("unite")).id,
                "cultiveau_conditionnement": str(champs.get("conditionnement") or "")[:120] or False,
                "cultiveau_fiche_url": str(champs.get("fiche") or "")[:500] or False,
                "cultiveau_source": "matrice", "sale_ok": True, "purchase_ok": True, "company_id": False,
            }
            valeurs["uom_po_id"] = valeurs["uom_id"]
            for cle, champ in (("dn", "cultiveau_dn"), ("pn", "cultiveau_pn"), ("d_ext", "cultiveau_d_ext")):
                if _nombre(champs.get(cle)) is not None:
                    valeurs[champ] = _nombre(champs.get(cle))
            for cle, champ in (("matiere", "cultiveau_matiere"), ("raccordement", "cultiveau_raccordement")):
                if champs.get(cle):
                    valeurs[champ] = str(champs[cle])[:64]
            produit = self.search([("default_code", "=", reference)], limit=1)
            if produit:
                produit.write(valeurs)
                bilan["maj"] += 1
            else:
                produit = self.create(valeurs)
                bilan["crees"] += 1
            self._cultiveau_fournisseur_prix(produit, fournisseur, _nombre(champs.get("prix")), reference, _nombre(champs.get("delai")))
        return bilan

    # ---------------------------------------------------------------- le catalogue 3D

    @api.model
    def cultiveau_importer_3d(self, dicts, fiches, produits):
        """Un lot de produits du catalogue 3D (clés dicts/fiches/produits de catalogue.json). Renvoie un bilan.

        Appelable en XML-RPC par lots de 1 000 à 2 000 produits (scripts/importer_catalogue_3d.py)."""
        def idx(liste, i):
            return liste[i] if isinstance(i, int) and 0 <= i < len(liste) else None

        cache_f, cache_c = {}, {}
        fournisseurs = {nom: self._cultiveau_fournisseur(nom, cache_f) for nom in dicts["four"]}
        familles = {i: self._cultiveau_categorie(nom, cache=cache_c) for i, nom in enumerate(dicts["fam"])}
        autre = self._cultiveau_categorie("Autre", cache=cache_c)
        references = {}
        for p in produits:
            references.setdefault((p.get("ref") or p["id"])[:64], p)
        existants = {p.default_code: p for p in self.with_context(active_test=False).search([("default_code", "in", list(references))])}
        bilan = {"crees": 0, "maj": 0}
        a_creer = []
        for reference, p in references.items():
            fournisseur = fournisseurs.get(idx(dicts["four"], p.get("F"))) or fournisseurs.get(dicts["four"][0])
            parent = familles.get(p.get("f"), autre)
            sous = idx(dicts["sub"], p.get("S"))
            categorie = self._cultiveau_categorie(sous, parent, cache_c) if sous and sous != "Autre" else parent
            carac = {k: p[k] for k in COTES_3D if p.get(k) not in (None, "")}
            raccordement, matiere = idx(dicts["rac"], p.get("t")), idx(dicts["mat"], p.get("m"))
            for ix, val in p.get("x") or []:
                cle = idx(dicts["xk"], ix)
                if cle:
                    carac[cle] = val
            fiche_id = idx(dicts["fiche"], p.get("k"))
            fiche = (fiches or {}).get(fiche_id) if fiche_id else None
            valeurs = {
                "name": p["designation"][:255], "default_code": reference, "type": "consu", "is_storable": True,
                "categ_id": categorie.id, "weight": float(p["poids"]) if p.get("poids") not in (None, "") else 0.0,
                "cultiveau_dn": float(p["dn"]) if p.get("dn") not in (None, "") else 0.0,
                "cultiveau_pn": float(p["pn"]) if p.get("pn") not in (None, "") else 0.0,
                "cultiveau_pouces": (p.get("pouces") or "")[:12] or False,
                "cultiveau_d_ext": float(p["d_ext"]) if p.get("d_ext") not in (None, "") else 0.0,
                "cultiveau_epaisseur": float(p["ep"]) if p.get("ep") not in (None, "") else 0.0,
                "cultiveau_matiere": matiere or False, "cultiveau_raccordement": raccordement or False,
                "cultiveau_fiche_url": f"https://drive.google.com/file/d/{fiche_id}/view" if fiche_id else False,
                "cultiveau_fiche_notes": ((fiche or {}).get("n") or "")[:255] or False,
                "cultiveau_caracteristiques": carac, "cultiveau_source": "catalogue3d",
                "sale_ok": True, "purchase_ok": True, "company_id": False,
            }
            if reference in existants:
                existants[reference].write(valeurs)
                bilan["maj"] += 1
            else:
                valeurs["_fournisseur"] = fournisseur
                a_creer.append(valeurs)
        for i in range(0, len(a_creer), 500):
            lot = a_creer[i:i + 500]
            crees = self.create([{k: v for k, v in val.items() if k != "_fournisseur"} for val in lot])
            self.env["product.supplierinfo"].create([
                {"partner_id": val["_fournisseur"].id, "product_tmpl_id": prod.id, "product_code": val["default_code"], "company_id": False}
                for val, prod in zip(lot, crees) if val["_fournisseur"]])
            bilan["crees"] += len(crees)
        return bilan
