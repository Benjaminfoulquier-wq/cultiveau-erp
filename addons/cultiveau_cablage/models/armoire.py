"""Le dossier de câblage : de l'étude de l'installation à l'armoire de pompage et au câblage des électrovannes, sans dessin.

On décrit l'armoire (ou on la reprend de l'étude : la pompe du dimensionnement, un secteur = une électrovanne), on clique
« Compiler » : l'ERP calcule les courants, choisit les protections, les contacteurs ou le variateur, les sections de câble et
vérifie les chutes de tension, pose les repères (IEC 81346 : Q, KM, U, T, M, Y, B, S, H, A, X), construit les borniers et la
nomenclature, puis trace les folios. Une modification recompile en indice suivant.
"""
import base64
from datetime import date

from markupsafe import Markup

from odoo import Command, api, fields, models
from odoo.exceptions import UserError

from . import folios, regles

PUISSANCES_MOTEUR = [0.37, 0.55, 0.75, 1.1, 1.5, 2.2, 3, 4, 5.5, 7.5, 9.2, 11, 15, 18.5, 22, 30, 37, 45, 55, 75, 90]
GENRES = [("pompe", "Pompe principale"), ("surpresseur", "Surpresseur"), ("doseuse", "Pompe doseuse (fertirrigation)"), ("filtration", "Filtration (contre-lavage)"),
          ("agitateur", "Agitateur / brasseur"), ("auxiliaire", "Prise et éclairage"), ("autre", "Autre moteur")]
DEMARRAGES = [("auto", "Conseillé"), ("direct", "Direct"), ("etoile_triangle", "Étoile-triangle"), ("variateur", "Variateur"), ("progressif", "Démarreur progressif")]
MOTEURS = {"pompe", "surpresseur", "doseuse", "filtration", "agitateur", "autre"}
MENTION = "Pré-dimensionnement généré par l'ERP Cultiveau : à vérifier et valider par l'électricien qui réalise l'armoire."
NORMES = "NF C 15-100 · IEC 60617 · IEC 81346"


def _puissance_standard(kw):
    return next((p for p in PUISSANCES_MOTEUR if p >= kw - 1e-9), PUISSANCES_MOTEUR[-1])


def _indice_suivant(i):
    return chr(ord(i) + 1) if i and "A" <= i < "Z" else "A"


class Armoire(models.Model):
    _name = "cultiveau.armoire"
    _description = "Dossier de câblage (armoire de pompage)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char("Dossier", required=True, copy=False, readonly=True, default="Nouveau")
    titre = fields.Char("Objet", required=True, default="Armoire de pompage")
    installation_id = fields.Many2one("cultiveau.installation", "Installation", required=True, index=True, ondelete="restrict", tracking=True)
    partner_id = fields.Many2one(related="installation_id.partner_id", store=True, string="Client")
    company_id = fields.Many2one("res.company", "Adhérent", required=True, default=lambda self: self.env.company, index=True)
    etat = fields.Selection([("brouillon", "À compiler"), ("compile", "Compilé"), ("valide", "Validé par l'électricien")], "État", default="brouillon", tracking=True)
    indice = fields.Char("Indice", default="A", readonly=True, copy=False)
    compile_le = fields.Datetime("Compilé le", readonly=True, copy=False)
    compile_par = fields.Many2one("res.users", "Par", readonly=True, copy=False)
    # l'alimentation
    reseau = fields.Selection([("tri", "Triphasé 400 V + N"), ("mono", "Monophasé 230 V")], "Réseau", default="tri", required=True)
    regime_neutre = fields.Selection([("TT", "TT (réseau public)"), ("TN", "TN"), ("IT", "IT")], "Régime de neutre", default="TT", required=True)
    source = fields.Selection([("reseau", "Compteur du réseau"), ("coffret", "Coffret existant"), ("groupe", "Groupe électrogène"), ("solaire", "Onduleur solaire")], "Source", default="reseau", required=True)
    longueur_alimentation_m = fields.Float("Du point de livraison à l'armoire (m)", digits=(8, 0), default=10)
    parafoudre = fields.Boolean("Parafoudre type 2", default=True, help="Conseillé en zone rurale (lignes aériennes, orages).")
    # le pilotage
    pilotage = fields.Selection([("programmateur", "Programmateur 24 V"), ("automate", "Automate (régulation, sondes, télégestion)")], "Pilotage", default="programmateur", required=True)
    vanne_maitre = fields.Boolean("Vanne maître", default=True, help="Une électrovanne générale en tête de réseau, pilotée en même temps que chaque secteur.")
    simultaneite = fields.Integer("Secteurs ouverts en même temps", default=1)
    regulation_pression = fields.Boolean("Régulation de pression (variateur)", help="La pompe suit la demande : variateur et capteur de pression.")
    manque_eau = fields.Boolean("Protection manque d'eau", default=True)
    pluviometre = fields.Boolean("Pluviomètre / sonde de pluie")
    compteur_impulsions = fields.Boolean("Compteur d'eau à impulsions")
    # le contenu
    depart_ids = fields.One2many("cultiveau.armoire.depart", "armoire_id", "Départs", copy=True)
    sortie_ids = fields.One2many("cultiveau.armoire.sortie", "armoire_id", "Électrovannes", copy=True)
    borne_ids = fields.One2many("cultiveau.armoire.borne", "armoire_id", "Bornes", readonly=True)
    ligne_ids = fields.One2many("cultiveau.armoire.ligne", "armoire_id", "Nomenclature", readonly=True)
    # les résultats
    courant_total_a = fields.Float("Courant total (A)", digits=(6, 1), readonly=True)
    calibre_general_a = fields.Integer("Calibre général (A)", readonly=True)
    ddr_type = fields.Char("Différentiel", readonly=True)
    transfo_va = fields.Integer("Transformateur 24 V (VA)", readonly=True)
    voies = fields.Integer("Voies du pilotage", readonly=True)
    alertes = fields.Text("Points à vérifier", readonly=True)
    folio_puissance = fields.Text(readonly=True)
    folio_commande = fields.Text(readonly=True)
    folio_borniers = fields.Text(readonly=True)
    folio_nomenclature = fields.Text(readonly=True)
    apercu_html = fields.Html("Folios", compute="_compute_apercu", sanitize=False)
    nb_folios = fields.Integer(compute="_compute_apercu")
    note = fields.Text("Notes pour l'électricien")

    _sql_constraints = [("simultaneite_positive", "check(simultaneite >= 1)", "Au moins un secteur ouvert à la fois.")]

    @api.depends("folio_puissance", "folio_commande", "folio_borniers", "folio_nomenclature")
    def _compute_apercu(self):
        for a in self:
            svgs = [s for s in (a.folio_puissance, a.folio_commande, a.folio_borniers, a.folio_nomenclature) if s]
            a.nb_folios = len(svgs)
            a.apercu_html = Markup("").join(Markup("<div style='margin:0 0 18px;border:1px solid #d5dde1'>%s</div>") % Markup(s) for s in svgs) if svgs else False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "Nouveau") == "Nouveau":
                vals["name"] = self.env["ir.sequence"].next_by_code("cultiveau.armoire") or "ARM"
        return super().create(vals_list)

    def write(self, vals):
        res = super().write(vals)
        champs = set(vals) & {"reseau", "regime_neutre", "source", "longueur_alimentation_m", "parafoudre", "pilotage", "vanne_maitre", "simultaneite", "regulation_pression",
                              "manque_eau", "pluviometre", "compteur_impulsions", "depart_ids", "sortie_ids"}
        if champs and not self.env.context.get("cultiveau_compilation"):
            self.filtered(lambda a: a.etat != "brouillon").with_context(cultiveau_sans_audit=True).write({"etat": "brouillon"})
        return res

    # ---------------------------------------------------------------- depuis l'étude

    @api.model
    def _depuis_etude(self, i):
        """Ce que l'étude donne : la pompe du dimensionnement (puissance moteur standard), une électrovanne par secteur."""
        departs, sorties = [], []
        kw = _puissance_standard(i.puissance_kw) if i.puissance_kw else 0.0
        if kw:
            departs.append(Command.create({"genre": "pompe", "name": "Pompe principale", "puissance_kw": kw, "sequence": 10, "longueur_cable_m": 15}))
        departs.append(Command.create({"genre": "auxiliaire", "name": "Prise 16 A et éclairage", "puissance_kw": 2.5, "sequence": 90, "longueur_cable_m": 5}))
        principale = (i.longueur_principale_m if "longueur_principale_m" in i._fields else 0.0) or 0.0
        for k, s in enumerate(i.secteur_ids if "secteur_ids" in i._fields else []):
            sorties.append(Command.create({"name": s.name, "secteur_id": s.id, "sequence": (k + 1) * 10, "longueur_m": principale + (s.longueur_m or 0.0) + 20}))
        return kw, departs, sorties

    @api.model
    def depuis_installation(self, installation):
        """Le dossier de l'installation (créé depuis l'étude s'il n'existe pas)."""
        a = self.search([("installation_id", "=", installation.id)], order="id desc", limit=1)
        if a:
            return a
        i = installation
        kw, departs, sorties = self._depuis_etude(i)
        niveau = getattr(i, "niveau_automatisme", "") or ""
        return self.create({"installation_id": i.id, "company_id": i.company_id.id, "titre": f"Armoire de pompage — {i.name}", "reseau": "tri" if (kw > 2.2 or not kw) else "mono",
                            "pilotage": "automate" if niveau == "pilote" else "programmateur", "regulation_pression": niveau == "pilote",
                            "simultaneite": max(1, getattr(i, "simultaneite", 1) or 1), "depart_ids": departs, "sortie_ids": sorties})

    def action_reprendre_etude(self):
        """Reprend la pompe et les secteurs de l'étude (remplace les départs et électrovannes)."""
        self.ensure_one()
        _kw, departs, sorties = self._depuis_etude(self.installation_id)
        self.depart_ids.unlink()
        self.sortie_ids.unlink()
        self.write({"depart_ids": departs, "sortie_ids": sorties})
        return True

    # ---------------------------------------------------------------- la compilation

    def action_compiler(self):
        for a in self:
            a._compiler()
        return True

    def _compiler(self):
        self.ensure_one()
        if not self.env.context.get("cultiveau_compilation"):
            return self.with_context(cultiveau_compilation=True)._compiler()
        if not self.depart_ids:
            raise UserError("Ajoutez au moins un départ (la pompe).")
        alertes = []
        reseau = self.reseau
        # --- les départs
        courant_total = 0.0
        n_q, n_km, n_m, n_u, n_f = 1, 1, 1, 1, 1
        for dep in self.depart_ids.sorted("sequence"):
            dep_reseau = dep.reseau or reseau
            if dep_reseau == "tri" and reseau == "mono":
                dep_reseau = "mono"
                alertes.append(f"{dep.name} : réseau monophasé, le moteur doit être monophasé.")
            moteur = dep.genre in MOTEURS
            kw = dep.puissance_kw or 0.0
            courant = regles.courant_moteur(kw, dep_reseau) if moteur else regles.courant_resistif(kw, dep_reseau)
            demarrage = dep.demarrage if dep.demarrage != "auto" else (regles.demarrage_conseille(kw, dep.regulation or (dep.genre == "pompe" and self.regulation_pression)) if moteur else "direct")
            if dep_reseau == "mono" and demarrage == "etoile_triangle":
                demarrage = "direct" if kw <= 2.2 else "variateur"
            lo, hi = regles.disjoncteur_moteur(courant) if moteur else (0, 0)
            if not moteur:
                calibre = next((c for c in (10, 16, 20, 25, 32) if c >= courant * 1.1), 32)
            section, chute = regles.section_cable(courant, dep.longueur_cable_m or 0.0, dep_reseau)
            vals = {"courant_a": regles.arrondi(courant), "demarrage_retenu": demarrage, "section_mm2": section, "chute_pct": regles.arrondi(chute, 2), "reseau_retenu": dep_reseau,
                    "repere_q": f"Q{n_q}", "repere_f": "", "repere_km": "", "variateur_kw": 0.0, "contacteur_kw": 0.0}
            if moteur:
                vals["disjoncteur"] = f"Disj. moteur {lo:g}–{hi:g} A, réglé {courant:.1f} A"
                vals["repere"] = f"M{n_m}"
                n_m += 1
                if demarrage == "variateur":
                    vals.update({"repere_km": f"U{n_u}", "variateur_kw": regles.variateur(kw)})
                    n_u += 1
                else:
                    ckw, _ci = regles.contacteur(kw, courant, dep_reseau)
                    vals.update({"repere_km": f"KM{n_km}", "contacteur_kw": ckw, "repere_f": f"F{n_f}"})
                    n_km += 1
                    n_f += 1
            else:
                vals["disjoncteur"] = f"Disj. {calibre} A courbe C + ΔI 30 mA"
                vals["repere"] = f"X{n_q}"
            n_q += 1
            dep.write(vals)
            courant_total += courant if moteur else courant * 0.5
            if chute > regles.CHUTE_MAX_PCT:
                alertes.append(f"{dep.name} : chute de tension {chute:.1f} % sur {dep.longueur_cable_m:g} m même en {section:g} mm² : rapprocher l'armoire ou passer en aluminium / section supérieure.")
            if moteur and kw > 5.5 and demarrage == "direct":
                alertes.append(f"{dep.name} : démarrage direct d'un moteur de {kw:g} kW ; le distributeur peut l'interdire (courant d'appel) : préférer étoile-triangle ou variateur.")
        # --- le transformateur et le pilotage (ajoutés comme départs virtuels dans les folios)
        transfo = regles.transformateur_va(self.simultaneite, 10 if self.pilotage == "programmateur" else 30)
        courant_total += 0.5
        calibre = regles.calibre_general(courant_total)
        ddr = "B" if any(d.demarrage_retenu == "variateur" and d.reseau_retenu == "tri" for d in self.depart_ids) else "A"
        # --- les électrovannes
        sorties = self.sortie_ids.sorted("sequence")
        voie = 1
        for s in sorties:
            section, chute = regles.section_electrovanne(s.longueur_m or 0.0, 1)
            s.write({"voie": voie, "repere": f"Y{voie}", "section_mm2": section, "chute_v": regles.arrondi(chute, 2)})
            if chute > regles.EV_CHUTE_MAX_V:
                alertes.append(f"{s.name} : {s.longueur_m:g} m de câble 24 V, chute {chute:.1f} V même en {section:g} mm² : déporter le programmateur ou relais local.")
            voie += 1
        voies = regles.programmateur_voies(len(sorties) + (1 if self.vanne_maitre else 0))
        if self.pilotage == "programmateur" and self.simultaneite > 1:
            alertes.append("Un programmateur n'ouvre qu'un secteur à la fois : avec plusieurs secteurs simultanés, passer en automate.")
        if self.pilotage == "programmateur" and len(sorties) > 24:
            alertes.append(f"{len(sorties)} secteurs : au-delà de 24 voies, un automate (ou plusieurs programmateurs) s'impose.")
        commun = regles.section_electrovanne(max([s.longueur_m or 0 for s in sorties] or [0]), min(self.simultaneite + (1 if self.vanne_maitre else 0), 4))[0]
        self.write({"courant_total_a": regles.arrondi(courant_total), "calibre_general_a": calibre, "ddr_type": f"300 mA type {ddr}", "transfo_va": transfo, "voies": voies})
        # --- les borniers et la nomenclature
        self._construire_borniers(commun)
        self._construire_nomenclature(ddr, transfo, voies, commun)
        # --- les folios
        if self.etat != "brouillon" or self.compile_le:
            self.indice = _indice_suivant(self.indice)
        d = self._donnees(commun)
        cartouche = self._cartouche()
        total = 4
        self.write({"folio_puissance": folios.folio_puissance(d, cartouche, 1, total), "folio_commande": folios.folio_commande(d, cartouche, 2, total),
                    "folio_borniers": folios.folio_borniers(d, cartouche, 3, total), "folio_nomenclature": folios.folio_nomenclature(d, cartouche, 4, total),
                    "alertes": "\n".join(alertes), "etat": "compile", "compile_le": fields.Datetime.now(), "compile_par": self.env.user.id})
        self.message_post(body=f"Dossier compilé en indice {self.indice} : {len(self.depart_ids)} départ(s), {len(sorties)} électrovanne(s), {len(self.ligne_ids)} lignes de nomenclature."
                          + (f" {len(alertes)} point(s) à vérifier." if alertes else ""))
        return True

    def _cartouche(self):
        i = self.installation_id
        return {"societe": self.company_id.name, "client": f"{i.partner_id.name or ''} · {i.name}", "dossier": self.name, "indice": self.indice,
                "date": date.today().strftime("%d/%m/%Y"), "auteur": self.env.user.name, "mention": MENTION, "normes": NORMES}

    def _construire_borniers(self, commun):
        self.borne_ids.unlink()
        Borne = self.env["cultiveau.armoire.borne"]
        vals = []
        n = 1
        for dep in self.depart_ids.sorted("sequence"):
            nb = 3 if dep.reseau_retenu == "tri" else 2
            cable = f"{nb + 1}G{dep.section_mm2:g} mm²"
            for k in range(nb):
                conducteur = ("L1", "L2", "L3")[k] if nb == 3 else ("L", "N")[k]
                vals.append({"armoire_id": self.id, "bornier": "XA", "numero": n, "repere": dep.repere, "destination": f"{dep.name} · {conducteur}", "cable": cable,
                             "longueur": f"{dep.longueur_cable_m:g} m", "note": dep.repere_km or ""})
                n += 1
            vals.append({"armoire_id": self.id, "bornier": "XA", "numero": n, "repere": dep.repere, "destination": f"{dep.name} · PE", "cable": cable, "longueur": f"{dep.longueur_cable_m:g} m", "note": "terre"})
            n += 1
            dep.borne = f"XA{n - nb - 1}"
        n = 1
        for s in self.sortie_ids.sorted("sequence"):
            vals.append({"armoire_id": self.id, "bornier": "XB", "numero": n, "repere": s.repere, "destination": f"{s.name} · sortie {s.voie}", "cable": f"2×{s.section_mm2:g} mm²",
                         "longueur": f"{s.longueur_m:g} m", "note": f"chute {s.chute_v:.1f} V"})
            s.borne = f"XB{n}"
            n += 1
        if self.vanne_maitre:
            vals.append({"armoire_id": self.id, "bornier": "XB", "numero": n, "repere": "Y0", "destination": "Vanne maître · sortie MV", "cable": f"2×{commun:g} mm²", "longueur": "", "note": ""})
            n += 1
        vals.append({"armoire_id": self.id, "bornier": "XB", "numero": n, "repere": "COM", "destination": "Commun des électrovannes", "cable": f"{commun:g} mm²", "longueur": "", "note": "retour commun"})
        n = 1
        for e in self._entrees():
            vals.append({"armoire_id": self.id, "bornier": "XC", "numero": n, "repere": e["repere"], "destination": e["nom"], "cable": "NC" if e.get("ferme") else "NO", "longueur": "2×0,75 mm²", "note": e["entree"]})
            n += 1
        Borne.create(vals)

    def _entrees(self):
        res = []
        if self.manque_eau:
            res.append({"repere": "B1", "nom": "Manque d'eau (pressostat / flotteur)", "ferme": True, "entree": "IN1 · arrêt pompe", "note": "manque d'eau"})
        if self.regulation_pression or any(d.demarrage_retenu == "variateur" and d.genre == "pompe" for d in self.depart_ids):
            res.append({"repere": "B2", "nom": "Capteur de pression 4–20 mA", "ferme": False, "entree": "AI1 · consigne variateur", "note": "pression"})
        if self.pluviometre:
            res.append({"repere": "B3", "nom": "Pluviomètre / sonde de pluie", "ferme": False, "entree": "SENSOR", "note": "pluie"})
        if self.compteur_impulsions:
            res.append({"repere": "B4", "nom": "Compteur d'eau à impulsions", "ferme": False, "entree": "IN2 · impulsions", "note": "compteur"})
        return res

    def _construire_nomenclature(self, ddr, transfo, voies, commun):
        self.ligne_ids.unlink()
        lignes = []

        def ajouter(repere, designation, carac, qte=1, unite="u", folio="01", mots=()):
            lignes.append({"armoire_id": self.id, "sequence": len(lignes) * 10, "repere": repere, "designation": designation, "caracteristiques": carac, "quantite": qte,
                           "unite": unite, "folio": folio, "product_id": self._article(mots).id if mots else False})

        g_reseau = "tétrapolaire" if self.reseau == "tri" else "bipolaire"
        ajouter("Q0", f"Interrupteur-sectionneur général {g_reseau}", f"{self.calibre_general_a} A", mots=("interrupteur", "sectionneur"))
        ajouter("Q0.1", f"Disjoncteur différentiel {g_reseau}", f"{self.calibre_general_a} A · {self.ddr_type}", mots=("différentiel",))
        if self.parafoudre:
            ajouter("F0", "Parafoudre type 2", "Imax 20 kA · avec déconnecteur", mots=("parafoudre",))
        for dep in self.depart_ids.sorted("sequence"):
            if dep.genre in MOTEURS:
                ajouter(dep.repere_q, "Disjoncteur moteur magnétothermique", dep.disjoncteur, mots=("disjoncteur", "moteur"))
                if dep.demarrage_retenu == "variateur":
                    ajouter(dep.repere_km, f"Variateur de fréquence {dep.variateur_kw:g} kW", f"{'400 V tri' if dep.reseau_retenu == 'tri' else '230 V mono'} · filtre CEM" + (" · régulation PID pression" if dep.regulation or self.regulation_pression else ""),
                            mots=("variateur",))
                elif dep.demarrage_retenu == "etoile_triangle":
                    ajouter(dep.repere_km, f"Démarreur étoile-triangle {dep.puissance_kw:g} kW", f"3 contacteurs AC-3 {dep.contacteur_kw:g} kW · temporisateur KT", mots=("contacteur",))
                    ajouter(dep.repere_f, "Relais thermique", f"réglé {dep.courant_a / 1.73:.1f} A (en Δ)", mots=("relais", "thermique"))
                elif dep.demarrage_retenu == "progressif":
                    ajouter(dep.repere_km, f"Démarreur progressif {dep.puissance_kw:g} kW", f"{dep.courant_a:.1f} A", mots=("démarreur",))
                else:
                    ajouter(dep.repere_km, f"Contacteur AC-3 {dep.contacteur_kw:g} kW", f"bobine 230 V AC · {dep.courant_a:.1f} A", mots=("contacteur",))
                    ajouter(dep.repere_f, "Relais thermique", f"réglé {dep.courant_a:.1f} A", mots=("relais", "thermique"))
                nb = 4 if dep.reseau_retenu == "tri" else 3
                ajouter("", f"Câble U-1000 R2V {nb}G{dep.section_mm2:g} mm² vers {dep.repere} ({dep.name})", f"{dep.longueur_cable_m:g} m · chute {dep.chute_pct:.1f} %", dep.longueur_cable_m, "m",
                        mots=("câble", f"{dep.section_mm2:g}"))
            else:
                ajouter(dep.repere_q, "Disjoncteur + différentiel 30 mA (prise, éclairage)", dep.disjoncteur, mots=("disjoncteur",))
                ajouter(dep.repere, "Prise 2P+T 16 A et point lumineux", "", mots=("prise",))
        ajouter("Q1.0", "Disjoncteur commande bipolaire", "2 A courbe C", folio="02", mots=("disjoncteur",))
        ajouter("T1", "Transformateur de commande 230/24 V AC", f"{transfo} VA", folio="02", mots=("transformateur", "24"))
        if self.pilotage == "programmateur":
            ajouter("A1", f"Programmateur d'irrigation {voies} voies", "24 V AC · vanne maître · entrée sonde" + (" · impulsions" if self.compteur_impulsions else ""), folio="02", mots=("programmateur",))
        else:
            ajouter("A1", "Automate d'irrigation", f"{voies} sorties 24 V · entrées TOR et 4–20 mA · télégestion", folio="02", mots=("automate",))
        ajouter("KA1", "Relais d'interface ordre de pompe", "bobine 24 V AC · 1 contact 230 V", folio="02", mots=("relais",))
        ajouter("S0", "Arrêt d'urgence coup de poing", "NC, à clé ou à tirer", folio="02", mots=("arrêt", "urgence"))
        ajouter("S1", "Commutateur Auto / 0 / Manu", "3 positions", folio="02", mots=("commutateur",))
        ajouter("H1, H2", "Voyants marche (vert) et défaut (rouge)", "230 V", 2, folio="02", mots=("voyant",))
        for e in self._entrees():
            ajouter(e["repere"], e["nom"], "contact " + ("NC" if e.get("ferme") else "NO / 4–20 mA"), folio="02", mots=(e["note"],))
        for s in self.sortie_ids.sorted("sequence"):
            ajouter(s.repere, f"Électrovanne 24 V AC — {s.name}", f"sortie {s.voie} · câble 2×{s.section_mm2:g} mm² · {s.longueur_m:g} m", folio="02", mots=("électrovanne",))
        if self.vanne_maitre:
            ajouter("Y0", "Électrovanne 24 V AC — vanne maître", "sortie MV", folio="02", mots=("électrovanne",))
        total_cable = sum(s.longueur_m or 0 for s in self.sortie_ids)
        if total_cable:
            ajouter("", f"Câble de commande 24 V (multiconducteur, commun {commun:g} mm²)", "enterré, gaine", total_cable, "m", folio="02", mots=("câble", "commande"))
        ajouter("XA, XB, XC", "Borniers à ressort sur rail DIN", f"{len(self.borne_ids)} bornes + peigne PE", folio="03", mots=("borne",))
        ajouter("", "Coffret polyester étanche IP65 avec platine", f"≈ {max(400, 300 + 60 * len(self.depart_ids) + 10 * len(self.sortie_ids))} × {max(300, 250 + 40 * len(self.depart_ids))} mm, serrure",
                mots=("coffret",))
        self.env["cultiveau.armoire.ligne"].create(lignes)

    def _article(self, mots):
        """L'article du catalogue de l'adhérent (puis du réseau) qui porte tous ces mots : le nom le plus court gagne (le plus précis),
        jamais un lot « programmateur + électrovannes » pour une électrovanne seule."""
        if not mots:
            return self.env["product.product"]
        Produit = self.env["product.product"].with_company(self.company_id)
        domaine = [("sale_ok", "=", True), ("company_id", "in", [self.company_id.id, False])] + [("name", "ilike", m) for m in mots]
        candidats = Produit.search(domaine, limit=20)
        candidats = candidats.filtered(lambda p: "+" not in (p.name or "") and " et " not in (p.name or "").lower()) or candidats
        return candidats.sorted(lambda p: (p.company_id != self.company_id, len(p.name or "")))[:1]

    def _donnees(self, commun):
        """Tout ce que les folios tracent."""
        departs = []
        for dep in self.depart_ids.sorted("sequence"):
            moteur = dep.genre in MOTEURS
            nb = 4 if dep.reseau_retenu == "tri" else 3
            departs.append({"nom": dep.name, "genre": "auxiliaire" if not moteur else dep.genre, "moteur": moteur, "reseau": dep.reseau_retenu, "repere_q": dep.repere_q,
                            "disjoncteur": dep.disjoncteur.split(",")[0].replace("Disj. moteur ", "").replace("Disj. ", ""), "repere": dep.repere, "repere_km": dep.repere_km,
                            "demarrage": dep.demarrage_retenu, "variateur_kw": dep.variateur_kw, "contacteur_kw": dep.contacteur_kw, "regulation": dep.regulation or (dep.genre == "pompe" and self.regulation_pression),
                            "puissance_kw": dep.puissance_kw, "cable": f"{nb}G{dep.section_mm2:g} mm²", "longueur_cable_m": dep.longueur_cable_m, "chute_pct": dep.chute_pct, "borne": dep.borne or "",
                            "texte": f"{dep.puissance_kw:g} kW · {dep.courant_a:.1f} A" if moteur else "16 A"})
        departs.append({"nom": "Commande", "genre": "transformateur", "moteur": False, "reseau": "mono", "repere_q": "Q1.0", "disjoncteur": "2 A", "repere": "T1", "repere_km": "",
                        "demarrage": "direct", "variateur_kw": 0, "contacteur_kw": 0, "regulation": False, "puissance_kw": 0, "cable": "", "longueur_cable_m": 0, "chute_pct": 0, "borne": "",
                        "texte": f"230/24 V · {self.transfo_va} VA"})
        pompe = next((d for d in self.depart_ids.sorted("sequence") if d.genre == "pompe"), self.depart_ids[:1])
        km = pompe.repere_km or "KM1"
        variateur = pompe.demarrage_retenu == "variateur"
        echelon1 = [{"type": "contact", "repere": "S0", "ferme": True, "bouton": True, "note": "arrêt d'urgence"}, {"type": "contact", "repere": "S1", "note": "Auto"}]
        if pompe.repere_f:
            echelon1.append({"type": "contact", "repere": pompe.repere_f, "ferme": True, "note": "thermique"})
        if self.manque_eau:
            echelon1.append({"type": "contact", "repere": "B1", "ferme": True, "note": "manque d'eau"})
        echelon1.append({"type": "contact", "repere": "KA1", "note": "ordre programmateur"})
        echelon1.append({"type": "bobine", "repere": km, "note": "RUN variateur" if variateur else f"contacteur {pompe.name}"})
        echelons = [{"nom": f"Marche {pompe.name}", "elements": echelon1},
                    {"nom": "Marche manuelle", "elements": [{"type": "contact", "repere": "S1", "note": "Manu"}, {"type": "contact", "repere": "B1" if self.manque_eau else "S0", "ferme": True, "note": "manque d'eau" if self.manque_eau else ""},
                                                            {"type": "bobine", "repere": km, "note": "(même bobine)"}]},
                    {"nom": "Voyant marche", "elements": [{"type": "contact", "repere": km, "note": "contact aux."}, {"type": "voyant", "repere": "H1", "note": "vert · marche"}]},
                    {"nom": "Voyant défaut", "elements": [{"type": "contact", "repere": pompe.repere_f or km, "note": "défaut" if pompe.repere_f else "défaut variateur"}, {"type": "voyant", "repere": "H2", "note": "rouge · défaut"}]}]
        for dep in self.depart_ids.sorted("sequence"):
            if dep.genre in MOTEURS and dep != pompe:
                echelons.append({"nom": f"Marche {dep.name}", "elements": [{"type": "contact", "repere": "S1", "note": "Auto"}, {"type": "contact", "repere": f"A1·{dep.repere}", "note": "ordre pilotage"},
                                                                           {"type": "bobine", "repere": dep.repere_km, "note": dep.name}]})
        sorties = [{"nom": s.name, "repere": s.repere, "sortie": f"{s.voie}", "borne": s.borne or "", "cable": f"2×{s.section_mm2:g} mm²", "longueur_m": s.longueur_m, "chute_v": s.chute_v}
                   for s in self.sortie_ids.sorted("sequence")]
        if self.vanne_maitre:
            sorties.insert(0, {"nom": "Vanne maître", "repere": "Y0", "sortie": "MV", "borne": "", "cable": f"2×{commun:g} mm²", "longueur_m": 0, "chute_v": 0})
        pilotage = {"repere": "A1", "nom": f"Programmateur {self.voies} voies" if self.pilotage == "programmateur" else f"Automate · {self.voies} sorties", "detail": f"24 V AC · T1 {self.transfo_va} VA"}
        borniers = {b: [] for b in ("XA", "XB", "XC")}
        for b in self.borne_ids:
            borniers[b.bornier].append({"numero": b.numero, "repere": b.repere, "destination": b.destination, "cable": b.cable, "longueur": b.longueur, "note": b.note})
        nomenclature = [{"repere": l.repere, "designation": l.designation, "caracteristiques": l.caracteristiques, "quantite": l.quantite, "unite": l.unite, "folio": l.folio,
                         "article": l.product_id.display_name if l.product_id else ""} for l in self.ligne_ids.sorted("sequence")]
        return {"general": {"tension": "400 V 3N~ 50 Hz" if self.reseau == "tri" else "230 V 1N~ 50 Hz", "source": dict(self._fields["source"].selection)[self.source], "regime": self.regime_neutre,
                            "longueur_alimentation": f"{self.longueur_alimentation_m:g} m jusqu'à l'armoire", "reseau": self.reseau, "calibre": self.calibre_general_a,
                            "ddr": self.ddr_type.replace("300 mA type ", ""), "parafoudre": self.parafoudre, "courant_total": self.courant_total_a, "transfo_va": self.transfo_va},
                "departs": departs, "commande": {"echelons": echelons, "entrees": [{**e, "note": e["note"]} for e in self._entrees()], "pilotage": pilotage, "commun": f"{commun:g} mm²"},
                "sorties": sorties, "borniers": borniers, "nomenclature": nomenclature, "alertes": (self.alertes or "").split("\n") if self.alertes else []}

    # ---------------------------------------------------------------- les suites

    def action_valider(self):
        for a in self:
            if a.etat != "compile":
                raise UserError("Compilez le dossier avant de le valider.")
            a.write({"etat": "valide"})
            a.message_post(body=f"Dossier indice {a.indice} validé par {self.env.user.name}.")
        return True

    def action_imprimer(self):
        self.ensure_one()
        if self.etat == "brouillon":
            self._compiler()
        return self.env.ref("cultiveau_cablage.action_report_armoire").report_action(self)

    def action_joindre_au_dossier(self):
        """Le PDF des folios, joint à l'installation (dossier technique)."""
        self.ensure_one()
        if self.etat == "brouillon":
            self._compiler()
        pdf, _t = self.env["ir.actions.report"]._render_qweb_pdf("cultiveau_cablage.action_report_armoire", res_ids=self.ids)
        nom = f"{self.name} - cablage indice {self.indice}.pdf"
        self.env["ir.attachment"].create({"name": nom, "datas": base64.b64encode(pdf), "res_model": "cultiveau.installation", "res_id": self.installation_id.id, "mimetype": "application/pdf"})
        self.installation_id.message_post(body=f"Schéma de câblage joint : {nom} ({self.nb_folios} folios).")
        return {"type": "ir.actions.client", "tag": "display_notification", "params": {"title": "Dossier joint", "message": f"{nom} est dans les pièces de l'installation.", "type": "success", "sticky": False}}

    def action_ajouter_au_devis(self):
        """La nomenclature en lot « Armoire électrique et câblage » sur le devis de l'installation (le dernier devis ouvert)."""
        self.ensure_one()
        if self.etat == "brouillon":
            self._compiler()
        Order = self.env["sale.order"]
        if "cultiveau_installation_id" not in Order._fields:
            raise UserError("Le lien devis ↔ installation n'est pas installé.")
        devis = Order.search([("cultiveau_installation_id", "=", self.installation_id.id), ("state", "in", ("draft", "sent"))], order="id desc", limit=1)
        if not devis:
            raise UserError("Aucun devis ouvert pour cette installation : générez-le depuis l'étude (« Générer le devis »), puis revenez ici.")
        titre = "Lot 7 — Armoire électrique et câblage"
        anciennes = devis.order_line.filtered(lambda l: l.cultiveau_armoire_id == self)
        anciennes.unlink()
        seq = (max(devis.order_line.mapped("sequence")) if devis.order_line else 0) + 10
        a_preciser = self.installation_id._a_preciser() if hasattr(self.installation_id, "_a_preciser") else None
        lignes = [Command.create({"display_type": "line_section", "name": titre, "sequence": seq, "cultiveau_armoire_id": self.id})]
        for l in self.ligne_ids.sorted("sequence"):
            seq += 10
            produit = l.product_id or a_preciser
            if not produit:
                continue
            uom = self.env.ref("uom.product_uom_meter") if l.unite == "m" else self.env.ref("uom.product_uom_unit")
            lignes.append(Command.create({"product_id": produit.id, "name": f"{l.repere + ' — ' if l.repere else ''}{l.designation}" + (f" ({l.caracteristiques})" if l.caracteristiques else ""),
                                          "product_uom_qty": l.quantite, "product_uom": uom.id, "sequence": seq, "cultiveau_armoire_id": self.id}))
        devis.write({"order_line": lignes})
        self.message_post(body=f"Nomenclature ajoutée au devis {devis.name} ({len(lignes) - 1} lignes).")
        return {"type": "ir.actions.act_window", "res_model": "sale.order", "res_id": devis.id, "view_mode": "form", "target": "current"}

    def folios_svg(self):
        """Les folios dans l'ordre, prêts pour le rapport (du SVG, pas du texte à échapper)."""
        self.ensure_one()
        return [Markup(x) for x in (self.folio_puissance, self.folio_commande, self.folio_borniers, self.folio_nomenclature) if x]

    def resume(self):
        """Pour la map et Mathis."""
        self.ensure_one()
        return {"id": self.id, "nom": self.name, "titre": self.titre, "installation": self.installation_id.name, "client": self.partner_id.name or "", "etat": self.etat,
                "indice": self.indice, "reseau": dict(self._fields["reseau"].selection)[self.reseau], "calibre_general_a": self.calibre_general_a, "courant_total_a": self.courant_total_a,
                "departs": [{"nom": d.name, "kw": d.puissance_kw, "courant_a": d.courant_a, "demarrage": d.demarrage_retenu, "protection": d.disjoncteur, "cable": f"{d.section_mm2:g} mm² · {d.longueur_cable_m:g} m"}
                            for d in self.depart_ids],
                "electrovannes": len(self.sortie_ids), "voies": self.voies, "transfo_va": self.transfo_va, "alertes": (self.alertes or "").split("\n") if self.alertes else []}


class LigneArmoire(models.AbstractModel):
    """Une ligne du dossier (départ, électrovanne) : la modifier remet le dossier « à compiler »."""
    _name = "cultiveau.armoire.ligne.mixin"
    _description = "Ligne d'un dossier de câblage"

    CHAMPS_SAISIS = ()

    def _a_recompiler(self):
        self.mapped("armoire_id").filtered(lambda a: a.etat != "brouillon").with_context(cultiveau_sans_audit=True).write({"etat": "brouillon"})

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if not self.env.context.get("cultiveau_compilation"):
            records._a_recompiler()
        return records

    def write(self, vals):
        res = super().write(vals)
        if set(vals) & set(self.CHAMPS_SAISIS) and not self.env.context.get("cultiveau_compilation"):
            self._a_recompiler()
        return res

    def unlink(self):
        armoires = self.mapped("armoire_id")
        res = super().unlink()
        if not self.env.context.get("cultiveau_compilation"):
            armoires.filtered(lambda a: a.etat != "brouillon").with_context(cultiveau_sans_audit=True).write({"etat": "brouillon"})
        return res


class Depart(models.Model):
    _name = "cultiveau.armoire.depart"
    _inherit = "cultiveau.armoire.ligne.mixin"
    _description = "Départ de l'armoire"
    _order = "sequence, id"

    CHAMPS_SAISIS = ("genre", "name", "puissance_kw", "reseau", "demarrage", "regulation", "longueur_cable_m")

    armoire_id = fields.Many2one("cultiveau.armoire", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    genre = fields.Selection(GENRES, "Nature", required=True, default="pompe")
    name = fields.Char("Départ", required=True)
    puissance_kw = fields.Float("Puissance (kW)", digits=(6, 2))
    reseau = fields.Selection([("tri", "Tri 400 V"), ("mono", "Mono 230 V")], "Réseau", help="Vide : celui de l'armoire.")
    demarrage = fields.Selection(DEMARRAGES, "Démarrage", default="auto", required=True)
    regulation = fields.Boolean("Régulation (variateur)")
    longueur_cable_m = fields.Float("Câble (m)", digits=(8, 0), default=10, help="De l'armoire au moteur.")
    # calculé à la compilation
    courant_a = fields.Float("Courant (A)", digits=(6, 1), readonly=True)
    demarrage_retenu = fields.Selection([(k, v) for k, v in DEMARRAGES if k != "auto"], "Démarrage retenu", readonly=True)
    reseau_retenu = fields.Selection([("tri", "Tri"), ("mono", "Mono")], readonly=True)
    disjoncteur = fields.Char("Protection", readonly=True)
    contacteur_kw = fields.Float(readonly=True)
    variateur_kw = fields.Float(readonly=True)
    section_mm2 = fields.Float("Section (mm²)", digits=(6, 2), readonly=True)
    chute_pct = fields.Float("Chute (%)", digits=(5, 2), readonly=True)
    repere_q = fields.Char("Q", readonly=True)
    repere_km = fields.Char("KM / U", readonly=True)
    repere_f = fields.Char("F", readonly=True)
    repere = fields.Char("Repère", readonly=True)
    borne = fields.Char("Bornes", readonly=True)


class Sortie(models.Model):
    _name = "cultiveau.armoire.sortie"
    _inherit = "cultiveau.armoire.ligne.mixin"
    _description = "Électrovanne pilotée"
    _order = "sequence, id"

    CHAMPS_SAISIS = ("name", "secteur_id", "longueur_m")

    armoire_id = fields.Many2one("cultiveau.armoire", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char("Secteur / vanne", required=True)
    secteur_id = fields.Many2one("cultiveau.secteur", "Secteur de l'étude", ondelete="set null")
    longueur_m = fields.Float("Câble 24 V (m)", digits=(8, 0), default=100, help="De l'armoire à l'électrovanne.")
    voie = fields.Integer("Sortie", readonly=True)
    repere = fields.Char("Repère", readonly=True)
    section_mm2 = fields.Float("Section (mm²)", digits=(4, 2), readonly=True)
    chute_v = fields.Float("Chute (V)", digits=(4, 2), readonly=True)
    borne = fields.Char("Borne", readonly=True)


class Borne(models.Model):
    _name = "cultiveau.armoire.borne"
    _description = "Borne"
    _order = "bornier, numero"

    armoire_id = fields.Many2one("cultiveau.armoire", required=True, ondelete="cascade", index=True)
    bornier = fields.Selection([("XA", "XA puissance"), ("XB", "XB 24 V"), ("XC", "XC entrées")], required=True)
    numero = fields.Integer("N°")
    repere = fields.Char("Repère")
    destination = fields.Char("Vers")
    cable = fields.Char("Câble")
    longueur = fields.Char("Longueur")
    note = fields.Char("Note")


class Ligne(models.Model):
    _name = "cultiveau.armoire.ligne"
    _description = "Ligne de nomenclature"
    _order = "sequence, id"

    armoire_id = fields.Many2one("cultiveau.armoire", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    repere = fields.Char("Rep.")
    designation = fields.Char("Désignation", required=True)
    caracteristiques = fields.Char("Caractéristiques")
    quantite = fields.Float("Qté", default=1.0)
    unite = fields.Char("Unité", default="u")
    folio = fields.Char("Folio")
    product_id = fields.Many2one("product.product", "Article du catalogue")


class LigneDevis(models.Model):
    _inherit = "sale.order.line"

    cultiveau_armoire_id = fields.Many2one("cultiveau.armoire", "Dossier de câblage", ondelete="set null", index=True)


class Installation(models.Model):
    _inherit = "cultiveau.installation"

    armoire_ids = fields.One2many("cultiveau.armoire", "installation_id", "Dossiers de câblage")
    nb_armoires = fields.Integer(compute="_compute_nb_armoires")

    def _compute_nb_armoires(self):
        for i in self:
            i.nb_armoires = len(i.armoire_ids)

    def action_cablage(self):
        self.ensure_one()
        a = self.env["cultiveau.armoire"].depuis_installation(self)
        return {"type": "ir.actions.act_window", "res_model": "cultiveau.armoire", "res_id": a.id, "view_mode": "form", "target": "current"}
