"""Schéma 3D vers devis : l'étude au format d'échange Cultiveau (schema `cultiveau-echange`, exportée par Réseau 3D) entre dans l'ERP.

Le fichier porte quatre choses utiles ici : les trames A1.1 et A1.2 (`conception`), les objets de l'installation (`installation.objets`),
la nomenclature regroupée (`nomenclature.lignes`, depuis le schéma 1.2.0 ; à défaut on la reconstitue depuis les objets), la
conformité et les pièces. On remplit l'installation, on attache le fichier, on génère le devis par lots."""
import base64
import json
import math
import re

from markupsafe import Markup, escape

from odoo import Command, api, fields, models
from odoo.exceptions import UserError

# famille du catalogue 3D → lot du devis (clés de cultiveau_dimensionnement.LOTS)
LOT_PAR_FAMILLE = {
    "Pompage": "station", "Mesure": "station", "Électricité et régulation": "station",
    "Filtration": "filtration", "Traitement de l’eau / fertigation": "automatisme", "Traitement de l'eau / fertigation": "automatisme",
    "Tuyaux et raccords (réseau)": "reseau", "Fixation": "reseau",
    "Goutte à goutte / micro-irrigation": "secteurs", "Pivots et rampes": "secteurs", "Enrouleurs": "secteurs", "Aspersion": "secteurs",
    "Automatisme et pilotage": "automatisme",
}
# le type de la ligne de nomenclature (quand la famille manque) → lot
LOT_PAR_TYPE = {"pompe": "station", "equip": "station", "filt": "filtration", "pipe": "reseau", "fit": "reseau", "distrib": "secteurs", "organ": "secteurs"}
MOTS_LOT = (("station", ("pompe", "groupe de pompage", "armoire", "variateur", "manomètre", "compteur", "clapet", "anti-bélier", "aspiration")),
            ("filtration", ("filtre", "filtration", "hydrocyclone", "disconnecteur")),
            ("automatisme", ("programmateur", "électrovanne", "sonde", "capteur", "pilotage", "injecteur", "doseur", "fertigation")),
            ("secteurs", ("goutteur", "gaine", "rampe", "asperseur", "micro", "canon", "pivot", "enrouleur", "collier de prise")))
ORDRE_LOTS = ("station", "filtration", "reseau", "secteurs", "automatisme", "pose")

RESSOURCES = (("forage", ("forage", "puits", "nappe")), ("retenue", ("retenue", "réserve", "reserve", "bassin", "lac", "étang")), ("cours_eau", ("rivière", "riviere", "cours", "canal", "fleuve")),
              ("reseau_collectif", ("réseau", "reseau", "asa", "collectif", "concession", "bornes")), ("reut", ("reut", "usées", "usees", "step")))
ENERGIES = (("solaire", ("solaire", "photovolta")), ("thermique", ("thermique", "diesel", "gnr", "groupe électrogène", "groupe electrogene")), ("mixte", ("mixte",)), ("reseau", ("réseau", "reseau", "edf", "enedis", "électri", "electri", "kva")))
AUTOMATISMES = (("pilote", ("pilot", "sonde", "régul", "regul")), ("programmateur", ("programm", "automat", "horloge")), ("manuel", ("manuel",)))
HIERARCHIES = (("eau", ("eau",)), ("energie", ("énergie", "energie")), ("rendement", ("rendement", "récolte", "recolte")))


def _valeur(v):
    """La valeur d'une case des trames : {valeur, origine…} ou {absence, motif}."""
    if not isinstance(v, dict) or "valeur" not in v:
        return None
    return v.get("valeur")


def _nombre(v):
    v = _valeur(v) if isinstance(v, dict) else v
    if v in (None, "", False):
        return 0.0
    try:
        return float(str(v).replace(",", ".").replace(" ", ""))
    except ValueError:
        m = re.search(r"-?\d+(?:[.,]\d+)?", str(v))
        return float(m.group(0).replace(",", ".")) if m else 0.0


def _choix(texte, table, defaut=False):
    t = (texte or "").lower()
    for cle, mots in table:
        if any(m in t for m in mots):
            return cle
    return defaut


class Installation(models.Model):
    _inherit = "cultiveau.installation"

    schema3d_uid = fields.Char("Installation Schéma 3D (uid)", readonly=True, copy=False, help="L'identifiant du projet dans Réseau 3D, pour reconnaître une étude mise à jour.")
    schema3d_derniere_etude = fields.Datetime("Dernière étude Schéma 3D importée", readonly=True, copy=False)
    schema3d_nb_devis = fields.Integer("Devis issus de Schéma 3D", compute="_compute_schema3d")

    def _compute_schema3d(self):
        Order = self.env["sale.order"]
        for i in self:
            i.schema3d_nb_devis = Order.search_count([("cultiveau_installation_id", "=", i.id), ("cultiveau_schema3d", "=", True)])

    def action_voir_devis_schema3d(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "res_model": "sale.order", "view_mode": "list,form", "name": f"Devis Schéma 3D — {self.name}",
                "domain": [("cultiveau_installation_id", "=", self.id), ("cultiveau_schema3d", "=", True)], "context": {"default_cultiveau_installation_id": self.id}}

    def action_importer_schema3d(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "res_model": "cultiveau.schema3d.import", "view_mode": "form", "target": "new", "name": "Importer l'étude Schéma 3D",
                "context": {"default_installation_id": self.id, "default_partner_id": self.partner_id.id}}


class SaleOrder(models.Model):
    _inherit = "sale.order"

    cultiveau_schema3d = fields.Boolean("Issu de Schéma 3D", copy=False)
    cultiveau_schema3d_etude = fields.Char("Étude Schéma 3D", copy=False, help="Document et date de l'export importé.")


class Importer(models.TransientModel):
    _name = "cultiveau.schema3d.import"
    _description = "Importer une étude Schéma 3D (format d'échange Cultiveau)"

    partner_id = fields.Many2one("res.partner", "Agriculteur", required=True)
    installation_id = fields.Many2one("cultiveau.installation", "Installation", domain="[('partner_id', 'child_of', partner_id)]",
                                      help="Vide : une installation est créée au nom du projet.")
    fichier = fields.Binary("Fichier .echange.json", required=True)
    fichier_nom = fields.Char("Nom du fichier")
    remplir_installation = fields.Boolean("Remplir A1.1 et A1.2 sur l'installation", default=True, help="Seulement les champs encore vides, chaque valeur avec son origine dans le fil.")
    ecraser = fields.Boolean("Écraser les valeurs déjà saisies", default=False)
    creer_devis = fields.Boolean("Créer le devis par lots", default=True)
    avec_mise_en_service = fields.Boolean("Ajouter le lot pose, mise en service et réception", default=True,
                                          help="La tranchée au mètre d'après les conduites du schéma, et la nomenclature du réseau « Mise en service, réception et formation ».")
    resume = fields.Html("Ce que contient le fichier", compute="_compute_resume", sanitize=False)

    # ---------------------------------------------------------------- lecture
    def _etude(self):
        self.ensure_one()
        if not self.fichier:
            return None
        try:
            texte = base64.b64decode(self.fichier).decode("utf-8")
            data = json.loads(texte)
        except (ValueError, UnicodeDecodeError) as e:
            raise UserError(f"Ce fichier n'est pas une étude au format d'échange Cultiveau (JSON illisible : {e}).") from e
        entete = data.get("entete") or {}
        if entete.get("schema") != "cultiveau-echange":
            if data.get("app") == "Cultiveau Réseau 3D" or ("state" in data and "project" in data):
                raise UserError("C'est une sauvegarde de projet Réseau 3D, pas l'étude. Dans Réseau 3D, utilisez le bouton « Format d'échange » (menu Projet).")
            raise UserError("Ce fichier n'est pas une étude au format d'échange Cultiveau (entête « cultiveau-echange » absente).")
        return data

    @staticmethod
    def _lignes_nomenclature(data):
        """Les lignes de la nomenclature : celles du fichier (schéma ≥ 1.2.0), sinon reconstituées depuis les objets."""
        nom = data.get("nomenclature") or {}
        lignes = nom.get("lignes") if isinstance(nom, dict) else None
        if lignes:
            return [l for l in lignes if isinstance(l, dict) and _nombre(l.get("quantite")) > 0], True
        resultat = []
        for o in (data.get("installation") or {}).get("objets") or []:
            k = o.get("caracteristiques") or {}
            if o.get("type") == "canalisation":
                lon = _nombre(k.get("longueur_m"))
                if lon <= 0:
                    continue
                dn, mat = _nombre(k.get("dn_mm")), _valeur(k.get("materiau")) or ""
                resultat.append({"libelle": f"Tube {mat} Ø {dn:g}".strip(), "type": "pipe", "quantite": lon, "unite": "m", "dn_mm": dn, "materiau": mat, "famille": "Tuyaux et raccords (réseau)"})
            else:
                resultat.append({"libelle": o.get("libelle") or "Composant", "type": "pompe" if o.get("type") == "pompe" else ("filt" if o.get("type") == "filtration" else "equip"),
                                 "quantite": 1, "unite": "u", "reference": _valeur(k.get("reference")) or "", "designation": _valeur(k.get("designation")) or o.get("libelle") or "",
                                 "fournisseur": _valeur(k.get("fournisseur")) or "", "dn_mm": _nombre(k.get("dn_mm")), "pn_bar": _nombre(k.get("pn_bar"))})
        return resultat, False

    @staticmethod
    def _lot(ligne):
        fam = ligne.get("famille") or ""
        if fam in LOT_PAR_FAMILLE:
            return LOT_PAR_FAMILLE[fam]
        texte = " ".join(str(ligne.get(c) or "") for c in ("libelle", "designation", "sous_famille")).lower()
        lot = _choix(texte, MOTS_LOT)
        if lot:
            return lot
        return LOT_PAR_TYPE.get(ligne.get("type") or "", "reseau")

    @api.depends("fichier")
    def _compute_resume(self):
        for w in self:
            if not w.fichier:
                w.resume = ""
                continue
            try:
                data = w._etude()
            except UserError as e:
                w.resume = Markup(f"<div class='alert alert-danger py-1'>{escape(str(e))}</div>")
                continue
            entete = data.get("entete") or {}
            lignes, native = w._lignes_nomenclature(data)
            objets = (data.get("installation") or {}).get("objets") or []
            conf = data.get("conformite") or []
            nc = [c for c in conf if c.get("statut") == "non_conforme"]
            acteurs = {a.get("role"): a.get("nom") for a in data.get("acteurs") or []}
            lon = sum(_nombre((o.get("caracteristiques") or {}).get("longueur_m")) for o in objets if o.get("type") == "canalisation")
            par_lot = {}
            for l in lignes:
                par_lot[w._lot(l)] = par_lot.get(w._lot(l), 0) + 1
            lots = " · ".join(f"{dict(zip(ORDRE_LOTS, ('station', 'filtration', 'réseau', 'secteurs', 'automatisme', 'pose')))[k]} {n}" for k, n in sorted(par_lot.items(), key=lambda x: ORDRE_LOTS.index(x[0]) if x[0] in ORDRE_LOTS else 9))
            html = (f"<p class='mb-1'><b>{escape(entete.get('type_document', 'étude'))}</b> exportée le {escape(str(entete.get('exporte_le', ''))[:10])} par "
                    f"{escape((entete.get('emetteur') or {}).get('logiciel', 'Réseau 3D'))} v{escape(str((entete.get('emetteur') or {}).get('version', '')))} "
                    f"(schéma {escape(str(entete.get('schema_version', '')))}) · exploitant : {escape(acteurs.get('exploitant') or '?')} · concepteur : {escape(acteurs.get('installateur') or '?')}</p>"
                    f"<p class='mb-1'>{len(objets)} objets du schéma, {lon:.0f} m de conduites · nomenclature : <b>{len(lignes)} lignes</b>")
            if not native:
                html += " <span class='text-warning'>(reconstituée depuis les objets : export antérieur au schéma 1.2.0, raccords non comptés)</span>"
            html += f" · par lot : {escape(lots)}</p>"
            if nc:
                html += f"<p class='mb-0 text-danger'><b>{len(nc)} non-conformité(s)</b> au contrôle avant émission : " + str(escape(" ; ".join(c.get("exigence", "") for c in nc[:6]))) + "</p>"
            else:
                html += "<p class='mb-0 text-success'>Aucune non-conformité au contrôle avant émission.</p>"
            w.resume = Markup(html)

    # ---------------------------------------------------------------- import
    def action_importer(self):
        self.ensure_one()
        data = self._etude()
        entete = data.get("entete") or {}
        inst = self.installation_id
        acteurs = {a.get("role"): a.get("nom") for a in data.get("acteurs") or []}
        if not inst:
            nom = acteurs.get("exploitant") or ""
            nom_projet = next((p.get("titre") for p in data.get("pieces") or [] if p.get("type") == "plans"), None)
            inst = self.env["cultiveau.installation"].create({
                "name": (nom.split(" · ")[-1] if " · " in nom else "") or f"Étude Schéma 3D {fields.Date.today():%d/%m/%Y}",
                "partner_id": self.partner_id.id, "type_systeme": self._type_systeme(data) or "mixte", "etat": "etude", "company_id": self.env.company.id})
        inst.write({"schema3d_uid": entete.get("installation_uid") or inst.schema3d_uid, "schema3d_derniere_etude": fields.Datetime.now()})
        # 1. le fichier reste au dossier (3.10.1)
        piece = self.env["ir.attachment"].create({"name": self.fichier_nom or f"etude-schema3d-{fields.Date.today()}.echange.json", "datas": self.fichier, "res_model": inst._name, "res_id": inst.id,
                                                  "mimetype": "application/json", "description": f"Étude Schéma 3D, document {entete.get('document_uid', '')}, exportée le {entete.get('exporte_le', '')}"})
        # 2. A1.1 et A1.2
        journal = []
        if self.remplir_installation:
            journal = self._remplir(inst, data)
        # 3. le fil : résultats, conformité, avertissements
        self._raconter(inst, data, journal, piece)
        # 4. le devis
        devis = self._devis(inst, data) if self.creer_devis else None
        if devis:
            devis.message_post(body=Markup("Devis construit depuis l'étude Schéma 3D ") + Markup("<a href='#' data-oe-model='ir.attachment' data-oe-id='%s'>%s</a>") % (piece.id, escape(piece.name))
                               + Markup(f" ({len(devis.order_line.filtered('product_id'))} lignes). Les lignes « à préciser » attendent leur article du catalogue et leur prix."))
            return {"type": "ir.actions.act_window", "res_model": "sale.order", "res_id": devis.id, "view_mode": "form", "target": "current"}
        return {"type": "ir.actions.act_window", "res_model": "cultiveau.installation", "res_id": inst.id, "view_mode": "form", "target": "current"}

    @staticmethod
    def _type_systeme(data):
        texte = " ".join(str(_valeur(v) or "") for v in ((data.get("conception") or {}).get("note_dimensionnement") or {}).values()).lower()
        texte += " ".join(str(l.get("famille") or "") + str(l.get("libelle") or "") for l in ((data.get("nomenclature") or {}).get("lignes") or [])).lower()
        if "pivot" in texte:
            return "pivot"
        if "enrouleur" in texte or "canon" in texte:
            return "enrouleur"
        if "goutte" in texte or "gaine" in texte or "goutteur" in texte:
            return "goutte_enterre" if "enterr" in texte else "goutte_surface"
        if "micro" in texte:
            return "micro_aspersion"
        if "asperseur" in texte or "aspersion" in texte:
            return "aspersion"
        return False

    def _remplir(self, inst, data):
        """Les champs vides de l'installation reçoivent les valeurs des trames, avec leur origine ; renvoie le journal."""
        c = data.get("conception") or {}
        besoins, note = c.get("analyse_des_besoins") or {}, c.get("note_dimensionnement") or {}
        valeurs, journal = {}, []

        def pose(champ, v, source, libelle):
            if v in (None, "", 0, 0.0, False):
                return
            if inst[champ] and not self.ecraser:
                return
            valeurs[champ] = v
            origine = source.get("origine", "") if isinstance(source, dict) else ""
            prov = source.get("source", "") if isinstance(source, dict) else ""
            journal.append(f"{libelle} : {escape(str(v))}" + (f" <span class='text-muted'>({escape(origine)}{' · ' + escape(prov) if prov else ''})</span>" if origine else ""))

        pose("surface_ha", _nombre(besoins.get("surface_ha")), besoins.get("surface_ha"), "Surface irriguée (ha)")
        pose("ressource", _choix(_valeur(besoins.get("nature_ressource")), RESSOURCES), besoins.get("nature_ressource"), "Ressource")
        pose("debit_mobilisable_m3h", _nombre(besoins.get("debit_mobilisable_pointe_m3h")), besoins.get("debit_mobilisable_pointe_m3h"), "Débit mobilisable en pointe (m³/h)")
        pose("volume_autorise_m3", _nombre(besoins.get("volume_autorise_m3_an")), besoins.get("volume_autorise_m3_an"), "Volume autorisé (m³/an)")
        pose("analyse_eau_resume", _valeur(besoins.get("qualite_eau_analyse_jointe")), besoins.get("qualite_eau_analyse_jointe"), "Qualité d'eau")
        energie = _valeur(besoins.get("energie_puissance_disponible"))
        pose("energie", _choix(energie, ENERGIES), besoins.get("energie_puissance_disponible"), "Énergie")
        kva = re.search(r"(\d+(?:[.,]\d+)?)\s*kva", str(energie or "").lower())
        pose("puissance_souscrite_kva", float(kva.group(1).replace(",", ".")) if kva else 0.0, besoins.get("energie_puissance_disponible"), "Puissance disponible (kVA)")
        pose("niveau_automatisme", _choix(_valeur(besoins.get("acces_niveau_automatisme")), AUTOMATISMES), besoins.get("acces_niveau_automatisme"), "Niveau d'automatisme")
        pose("hierarchie", _choix(_valeur(besoins.get("hierarchie_eau_energie_rendement")), HIERARCHIES), besoins.get("hierarchie_eau_energie_rendement"), "Hiérarchie des enjeux")
        pose("assolement", _valeur(besoins.get("assolement_actuel")), besoins.get("assolement_actuel"), "Assolement")
        pose("besoin_pointe_mm_j", _nombre(note.get("besoin_pointe_mm_j")), note.get("besoin_pointe_mm_j"), "Besoin de pointe (mm/j)")
        pose("dfc_l_s_ha", _nombre(note.get("debit_fictif_continu_l_s_ha")), note.get("debit_fictif_continu_l_s_ha"), "Débit fictif continu (l/s/ha)")
        pose("temps_fonctionnement_h_j", _nombre(note.get("temps_fonctionnement_h_j")), note.get("temps_fonctionnement_h_j"), "Temps de fonctionnement (h/j)")
        pose("debit_equipement_m3_h", _nombre(note.get("debit_equipement_m3h")), note.get("debit_equipement_m3h"), "Débit d'équipement (m³/h)")
        pose("technique_organes", _valeur(note.get("technique_organes")), note.get("technique_organes"), "Technique et organes")
        pose("pression_service_bar", _nombre(note.get("pression_service_bar")), note.get("pression_service_bar"), "Pression de service (bar)")
        pose("diametres_vitesses", _valeur(note.get("diametres_vitesses")), note.get("diametres_vitesses"), "Diamètres et vitesses")
        pose("hmt_m", _nombre(note.get("bilan_pression_hmt_m")), note.get("bilan_pression_hmt_m"), "HMT (m)")
        pose("pompe", _valeur(note.get("pompe_point_fonctionnement")), note.get("pompe_point_fonctionnement"), "Pompe retenue")
        pose("filtration", _valeur(note.get("filtration_type_finesse")), note.get("filtration_type_finesse"), "Filtration")
        pertes = sum(_nombre((o.get("caracteristiques") or {}).get("perte_de_charge_m")) for o in (data.get("installation") or {}).get("objets") or [] if o.get("type") == "canalisation")
        pose("pertes_charge_m", round(pertes, 1), {"origine": "calcul", "source": "somme des pertes des conduites du schéma"}, "Pertes de charge (m)")
        if valeurs:
            inst.write(valeurs)
        return journal

    def _raconter(self, inst, data, journal, piece):
        entete = data.get("entete") or {}
        res = (data.get("conception") or {}).get("resultats") or []
        conf = [c for c in data.get("conformite") or [] if c.get("statut") == "non_conforme"]
        avert = data.get("avertissements") or []
        hyp = (data.get("conception") or {}).get("hypotheses") or []
        parties = [Markup("<p><b>Étude Schéma 3D importée</b> : ") + Markup("<a href='#' data-oe-model='ir.attachment' data-oe-id='%s'>%s</a>") % (piece.id, escape(piece.name))
                   + Markup(f" (exportée le {escape(str(entete.get('exporte_le', ''))[:16]).replace('T', ' ')}, {escape((entete.get('emetteur') or {}).get('logiciel', ''))} v{escape(str((entete.get('emetteur') or {}).get('version', '')))}).</p>")]
        if journal:
            parties.append(Markup("<p>Champs remplis (A1.1, A1.2) :</p><ul>" + "".join(f"<li>{j}</li>" for j in journal) + "</ul>"))
        if res:
            lignes = []
            for r in res:
                ok = r.get("dans_tolerance")
                ref = r.get("reference") or {}
                lignes.append(f"<li>{escape(r.get('code', ''))} : <b>{escape(str(r.get('valeur', '')))} {escape(r.get('unite', ''))}</b>"
                              + (f" (référence {escape(str(ref.get('valeur', '')))} {escape(ref.get('unite', ''))}, {escape(ref.get('source', ''))})" if ref else "")
                              + ("" if ok is None else (" ✓" if ok else " <span class='text-danger'>hors tolérance</span>")) + ("" if not r.get("estime") else " <i>estimé</i>") + "</li>")
            parties.append(Markup("<p>Résultats de la note de calcul :</p><ul>" + "".join(lignes) + "</ul>"))
        if conf:
            parties.append(Markup("<p class='text-danger'><b>Non-conformités au contrôle avant émission</b> (à lever avant la commande, § 3.5) :</p><ul>"
                                  + "".join(f"<li>{escape(c.get('exigence', ''))}" + (f" : {escape(c.get('motif', ''))}" if c.get("motif") else "") + "</li>" for c in conf) + "</ul>"))
        if hyp:
            parties.append(Markup("<p>Hypothèses de l'étude : " + " ; ".join(escape(str(_valeur(h.get("valeur")) or "")) for h in hyp if isinstance(h, dict)) + "</p>"))
        if avert:
            parties.append(Markup("<p class='text-muted small'>Avertissements de Réseau 3D : " + " ".join(escape(a) for a in avert) + "</p>"))
        inst.message_post(body=Markup("").join(parties))

    # ---------------------------------------------------------------- le devis
    def _article(self, ligne, societe):
        """L'article du catalogue par sa référence (société puis réseau), sinon par la fiche technique et le DN ; sinon rien."""
        Produit = self.env["product.product"].with_company(societe).with_context(active_test=True)
        ref = (ligne.get("reference") or "").strip()
        if ref:
            p = Produit.search([("default_code", "=", ref), ("company_id", "in", [societe.id, False]), ("sale_ok", "=", True)], order="company_id desc", limit=1)
            if p:
                return p
            p = Produit.search([("seller_ids.product_code", "=", ref), ("company_id", "in", [societe.id, False]), ("sale_ok", "=", True)], order="company_id desc", limit=1)
            if p:
                return p
        fiche = ligne.get("fiche_id") or (re.search(r"/d/([\w-]+)", ligne.get("fiche_url") or "") or [None, None])[1]
        if fiche and "cultiveau_fiche_id" in Produit._fields:
            domaine = [("product_tmpl_id.cultiveau_fiche_id.drive_id", "=", fiche), ("company_id", "in", [societe.id, False]), ("sale_ok", "=", True)]
            dn = _nombre(ligne.get("dn_mm"))
            if dn:
                domaine.append(("product_tmpl_id.cultiveau_dn", "=", dn))
            p = Produit.search(domaine, order="company_id desc", limit=1)
            if p:
                return p
        return Produit

    def _devis(self, inst, data):
        from odoo.addons.cultiveau_dimensionnement.models.devis import LOTS
        societe = inst.company_id
        lignes, _native = self._lignes_nomenclature(data)
        if not lignes:
            raise UserError("L'étude ne contient aucune ligne de nomenclature : rien à chiffrer.")
        a_preciser = inst._a_preciser()
        unite, metre = self.env.ref("uom.product_uom_unit"), self.env.ref("uom.product_uom_meter")
        par_lot = {k: [] for k in ORDRE_LOTS}
        for l in lignes:
            par_lot.setdefault(self._lot(l), []).append(l)
        commandes, seq, trouves, manquants = [], 0, 0, 0

        def ajouter(valeurs):
            nonlocal seq
            seq += 1
            valeurs["sequence"] = seq
            commandes.append(Command.create(valeurs))

        for lot in ORDRE_LOTS:
            membres = par_lot.get(lot) or []
            if lot == "pose":
                if not self.avec_mise_en_service:
                    continue
                ajouter({"display_type": "line_section", "name": LOTS["pose"]})
                lon = _nombre((data.get("nomenclature") or {}).get("longueur_conduites_m")) or sum(_nombre((o.get("caracteristiques") or {}).get("longueur_m"))
                                                                                                    for o in (data.get("installation") or {}).get("objets") or [] if o.get("type") == "canalisation")
                if lon > 0:
                    ajouter({"product_id": a_preciser.id, "name": f"Tranchée mécanique hors gel, pose et remblai des conduites du schéma, {lon:.0f} m", "product_uom_qty": round(lon), "product_uom": metre.id, "price_unit": 0.0})
                mes = self.env.ref("cultiveau_ventes.nom_mise_en_service", raise_if_not_found=False)
                if mes:
                    cmds, seq = mes.lignes_devis(1.0, False, seq, titre=None)
                    commandes.extend(cmds)
                continue
            if not membres:
                continue
            ajouter({"display_type": "line_section", "name": LOTS[lot]})
            # le réseau se lit en deux sous-lots : les conduites au mètre, puis les pièces
            groupes = [(None, membres)]
            if lot == "reseau":
                tubes = [m for m in membres if (m.get("unite") or "u") == "m"]
                pieces = [m for m in membres if (m.get("unite") or "u") != "m"]
                groupes = [("Conduites", tubes), ("Raccords, vannes et pièces", pieces)] if tubes and pieces else [(None, membres)]
            for titre, groupe in groupes:
                if not groupe:
                    continue
                if titre:
                    ajouter({"display_type": "line_section", "name": titre, "cultiveau_sous_lot": True})
                for l in sorted(groupe, key=lambda x: (-_nombre(x.get("dn_mm")), str(x.get("libelle") or ""))):
                    article = self._article(l, societe)
                    qte = _nombre(l.get("quantite"))
                    au_metre = (l.get("unite") or "u") == "m"
                    qte = round(qte, 1) if au_metre else max(1, math.ceil(qte - 1e-9))
                    libelle = str(l.get("libelle") or l.get("designation") or "Article").strip()
                    detail = " · ".join(x for x in (l.get("fournisseur"), l.get("reference") and f"réf. {l['reference']}") if x)
                    valeurs = {"product_uom_qty": qte, "product_uom": (metre if au_metre else unite).id}
                    if article:
                        trouves += 1
                        valeurs.update({"product_id": article.id, "name": f"{article.display_name} — {libelle}"[:500]})
                    else:
                        manquants += 1
                        valeurs.update({"product_id": a_preciser.id, "name": (f"{libelle}" + (f" ({detail})" if detail else "") + " — à préciser")[:500], "price_unit": 0.0})
                    ajouter(valeurs)
        entete = data.get("entete") or {}
        modele = self.env["sale.order.template"].search([("cultiveau_type_systeme", "=", inst.type_systeme)], limit=1)
        avert = data.get("avertissements") or []
        conf = [c.get("exigence", "") for c in data.get("conformite") or [] if c.get("statut") == "non_conforme"]
        note = (modele.note or "") if modele else ""
        devis = self.env["sale.order"].with_company(societe).create({
            "partner_id": inst.partner_id.id, "company_id": societe.id, "cultiveau_installation_id": inst.id, "cultiveau_type_systeme": inst.type_systeme,
            "origin": f"Schéma 3D · {inst.name}", "cultiveau_schema3d": True, "cultiveau_schema3d_etude": f"{entete.get('document_uid', '')} · {str(entete.get('exporte_le', ''))[:10]}",
            "note": note, "order_line": commandes})
        resume = f"{trouves} ligne(s) reconnue(s) au catalogue, {manquants} à préciser."
        if conf:
            resume += " Non-conformités du contrôle avant émission à lever avant la commande : " + ", ".join(conf[:8]) + "."
        if avert:
            resume += " " + " ".join(avert[:2])
        devis.message_post(body=resume)
        return devis
