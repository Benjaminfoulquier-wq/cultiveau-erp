"""Les secteurs d'une installation et le dimensionnement qui en découle, écrit dans la note A1.2."""

import math

from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.exceptions import UserError

from . import hydraulique as hy

ORGANES = [("goutteur", "Goutteurs (l/h)"), ("micro", "Micro-asperseurs (l/h)"), ("asperseur", "Asperseurs (m³/h)"), ("canon", "Canon / enrouleur (m³/h)"),
           ("pivot", "Pivot / rampe (débit total m³/h)")]
PAR_TYPE = {"goutte_surface": "goutteur", "goutte_enterre": "goutteur", "micro_aspersion": "micro", "couverture_integrale": "asperseur",
            "couverture_partielle": "asperseur", "enrouleur": "canon", "pivot": "pivot", "mixte": "asperseur"}
DEFAUTS = {  # débit unitaire, pression de service (bar), espacement, écartement : des valeurs courantes pour démarrer
    "goutteur": (1.6, 1.0, 0.5, 1.5), "micro": (40.0, 1.5, 4.0, 5.0), "asperseur": (1.2, 3.5, 18.0, 18.0), "canon": (60.0, 6.0, 0, 0), "pivot": (120.0, 2.5, 0, 0)}
MATERIAUX = [("pe", "PE (polyéthylène)"), ("pvc", "PVC pression")]


class Secteur(models.Model):
    _name = "cultiveau.secteur"
    _description = "Secteur d'arrosage d'une installation"
    _order = "installation_id, sequence, id"

    installation_id = fields.Many2one("cultiveau.installation", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="installation_id.company_id", store=True)
    sequence = fields.Integer(default=10)
    name = fields.Char("Secteur", required=True, default="Secteur")
    surface_ha = fields.Float("Surface (ha)", digits=(8, 2), required=True)
    organe = fields.Selection(ORGANES, "Organes", required=True, default="asperseur")
    debit_unitaire = fields.Float("Débit unitaire", digits=(8, 2), help="l/h pour un goutteur ou un micro-asperseur ; m³/h pour un asperseur, un canon ou le pivot entier.")
    pression_organe_bar = fields.Float("Pression de service (bar)", digits=(4, 1), default=3.0)
    espacement_m = fields.Float("Espacement sur la ligne (m)", digits=(5, 2))
    ecartement_m = fields.Float("Écartement des lignes (m)", digits=(5, 2))
    nb_saisi = fields.Integer("Nombre d'organes (si connu)")
    longueur_m = fields.Float("Conduite d'amenée (m)", digits=(8, 0), help="De la conduite principale (ou de la station) jusqu'au secteur.")
    denivele_m = fields.Float("Dénivelé (m)", digits=(5, 1), help="Positif si le secteur est plus haut que la station.")
    materiau = fields.Selection(MATERIAUX, "Matériau", default="pe")
    diametre_mm = fields.Integer("Diamètre extérieur (mm)", help="Vide : le diamètre est choisi pour une vitesse sous 1,5 m/s.")
    # calculs
    nb_organes = fields.Integer("Nombre d'organes", compute="_compute_calculs")
    debit_m3h = fields.Float("Débit (m³/h)", digits=(8, 1), compute="_compute_calculs")
    pluviometrie_mm_h = fields.Float("Pluviométrie (mm/h)", digits=(5, 2), compute="_compute_calculs")
    diametre_calc = fields.Integer("Ø conseillé (mm)", compute="_compute_calculs")
    vitesse_m_s = fields.Float("Vitesse (m/s)", digits=(4, 2), compute="_compute_calculs")
    pertes_m = fields.Float("Pertes de charge (m)", digits=(6, 1), compute="_compute_calculs")
    pression_tete_bar = fields.Float("Pression en tête (bar)", digits=(4, 1), compute="_compute_calculs")
    longueur_rampes_m = fields.Float("Rampes / lignes (m)", digits=(10, 0), compute="_compute_calculs")

    @api.onchange("organe")
    def _onchange_organe(self):
        if self.organe and self.organe in DEFAUTS and not self.debit_unitaire:
            self.debit_unitaire, self.pression_organe_bar, self.espacement_m, self.ecartement_m = DEFAUTS[self.organe]

    @api.depends("surface_ha", "organe", "debit_unitaire", "pression_organe_bar", "espacement_m", "ecartement_m", "nb_saisi", "longueur_m", "denivele_m", "materiau", "diametre_mm")
    def _compute_calculs(self):
        for s in self:
            if s.organe in ("canon", "pivot"):
                nb = s.nb_saisi or 1
                debit = nb * (s.debit_unitaire or 0.0)
                rampes = 0.0
            else:
                nb = s.nb_saisi or (int(s.surface_ha * 10000 / (s.espacement_m * s.ecartement_m)) if s.surface_ha and s.espacement_m and s.ecartement_m else 0)
                unitaire = s.debit_unitaire or 0.0
                debit = nb * unitaire / (1000 if s.organe in ("goutteur", "micro") else 1)
                rampes = s.surface_ha * 10000 / s.ecartement_m if s.surface_ha and s.ecartement_m else 0.0
            ext, interieur = hy.diametre_conseille(debit, s.materiau or "pe")
            if s.diametre_mm and s.diametre_mm in hy.diametres(s.materiau or "pe"):
                ext, interieur = s.diametre_mm, hy.diametres(s.materiau or "pe")[s.diametre_mm]
            pertes = hy.pertes_de_charge(debit, interieur, s.longueur_m)
            s.nb_organes = nb
            s.debit_m3h = debit
            s.pluviometrie_mm_h = debit / (10 * s.surface_ha) if s.surface_ha else 0.0
            s.diametre_calc = ext if debit else 0
            s.vitesse_m_s = hy.vitesse(debit, interieur) if debit else 0.0
            s.pertes_m = pertes
            # 20 % de variation de pression admise dans les rampes (règle de conception) + conduite d'amenée + dénivelé
            s.pression_tete_bar = (s.pression_organe_bar or 0.0) * 1.2 + (pertes + (s.denivele_m or 0.0)) / hy.METRE_PAR_BAR if debit else 0.0
            s.longueur_rampes_m = rampes


class Installation(models.Model):
    _inherit = "cultiveau.installation"

    secteur_ids = fields.One2many("cultiveau.secteur", "installation_id", "Secteurs")
    longueur_principale_m = fields.Float("Conduite principale (m)", digits=(8, 0), help="De la station au point de départ des secteurs.")
    denivele_station_m = fields.Float("Dénivelé station → réseau (m)", digits=(5, 1), help="Hauteur géométrique entre la pompe et le départ des secteurs (positif en montée).")
    hauteur_aspiration_m = fields.Float("Hauteur d'aspiration (m)", digits=(5, 1), help="Du plan d'eau à l'axe de la pompe ; 0 pour une pompe immergée.")
    materiau_principal = fields.Selection(MATERIAUX, "Matériau de la principale", default="pe")
    diametre_principal_mm = fields.Integer("Ø principale (mm)", help="Vide : choisi pour une vitesse sous 1,5 m/s.")
    rendement_pompe = fields.Float("Rendement de la pompe", digits=(3, 2), default=0.65)
    puissance_kw = fields.Float("Puissance de pompe (kW)", digits=(6, 1), readonly=True)
    dimensionnement_html = fields.Html("Note de calcul", readonly=True, sanitize=False)

    def action_dimensionner(self):
        """Des secteurs à la pompe : débit d'équipement, diamètre de la principale, pertes, HMT, puissance ; la note A1.2 se remplit."""
        for i in self:
            secteurs = i.secteur_ids
            if not secteurs:
                raise UserError("Décrivez d'abord les secteurs (surface, organes, conduite d'amenée).")
            simult = max(1, i.simultaneite or 1)
            debits = sorted(secteurs.mapped("debit_m3h"), reverse=True)
            debit = sum(debits[:simult])
            if i.type_systeme == "mixte" and i.debit_equipement_m3_h:
                debit = max(debit, i.debit_equipement_m3_h)
            materiau = i.materiau_principal or "pe"
            ext, interieur = hy.diametre_conseille(debit, materiau)
            if i.diametre_principal_mm and i.diametre_principal_mm in hy.diametres(materiau):
                ext, interieur = i.diametre_principal_mm, hy.diametres(materiau)[i.diametre_principal_mm]
            pertes_principale = hy.pertes_de_charge(debit, interieur, i.longueur_principale_m)
            pire = max(secteurs, key=lambda s: s.pression_tete_bar)
            hmt = (pire.pression_tete_bar * hy.METRE_PAR_BAR + pertes_principale + (i.denivele_station_m or 0.0) + (i.hauteur_aspiration_m or 0.0)) * 1.05
            puissance = hy.puissance_kw(debit, hmt, i.rendement_pompe)
            dose = i.besoin_pointe_mm_j or 0.0
            lignes = []
            for s in secteurs:
                duree = (dose / s.pluviometrie_mm_h) if (dose and s.pluviometrie_mm_h) else 0.0
                lignes.append(f"<tr><td>{escape(s.name)}</td><td>{s.surface_ha:g} ha</td><td>{s.nb_organes}</td><td>{s.debit_m3h:.1f}</td><td>{s.pluviometrie_mm_h:.2f}</td>"
                              f"<td>{duree:.1f}</td><td>Ø {s.diametre_calc} {dict(MATERIAUX).get(s.materiau, '')[:3]} · {s.vitesse_m_s:.2f} m/s</td><td>{s.pertes_m:.1f}</td><td>{s.pression_tete_bar:.1f}</td></tr>")
            tableau = ("<table class='table table-sm'><tr><th>Secteur</th><th>Surface</th><th>Organes</th><th>Débit m³/h</th><th>mm/h</th><th>h pour la dose du jour</th>"
                       f"<th>Conduite</th><th>Pertes m</th><th>Pression tête bar</th></tr>{''.join(lignes)}</table>")
            resume = (f"<p><b>Débit d'équipement</b> {debit:.1f} m³/h ({simult} secteur(s) à la fois) · <b>principale</b> Ø {ext} {dict(MATERIAUX)[materiau]} sur {i.longueur_principale_m:g} m, "
                      f"{hy.vitesse(debit, interieur):.2f} m/s, pertes {pertes_principale:.1f} m · <b>secteur le plus exigeant</b> {escape(pire.name)} ({pire.pression_tete_bar:.1f} bar en tête)</p>"
                      f"<p><b>HMT</b> {hmt:.0f} m (marge 5 %) · <b>pompe</b> {debit:.0f} m³/h à {hmt:.0f} m, environ {puissance:.1f} kW à l'arbre (rendement {i.rendement_pompe:.0%})</p>")
            alertes = []
            if i.debit_mobilisable_m3h and debit > i.debit_mobilisable_m3h:
                alertes.append(f"Le débit d'équipement ({debit:.0f} m³/h) dépasse le débit mobilisable ({i.debit_mobilisable_m3h:g} m³/h) : augmenter le nombre de secteurs ou réduire la surface par secteur.")
            if i.puissance_souscrite_kva and i.energie == "reseau" and puissance / 0.9 > i.puissance_souscrite_kva:
                alertes.append(f"La pompe demande environ {puissance / 0.9:.0f} kVA, plus que la puissance souscrite ({i.puissance_souscrite_kva:g} kVA).")
            for s in secteurs:
                if s.vitesse_m_s > hy.VITESSE_MAX + 0.01:
                    alertes.append(f"{s.name} : vitesse {s.vitesse_m_s:.2f} m/s dans la conduite d'amenée, au-dessus de 1,5 m/s (coups de bélier, pertes) : passer au diamètre supérieur.")
                if dose and s.pluviometrie_mm_h and s.organe in ("asperseur", "canon", "pivot") and s.pluviometrie_mm_h > 12:
                    alertes.append(f"{s.name} : pluviométrie {s.pluviometrie_mm_h:.1f} mm/h, à comparer à l'infiltration du sol (ruissellement sur sol battant ou en pente).")
            note = Markup(resume + tableau + "".join(f"<p class='text-danger'>⚠ {escape(a)}</p>" for a in alertes))
            i.write({"secteurs": len(secteurs), "debit_equipement_m3_h": round(debit, 1), "pression_service_bar": round(pire.pression_tete_bar, 1),
                     "pertes_charge_m": round(pertes_principale + pire.pertes_m, 1), "hmt_m": round(hmt), "puissance_kw": round(puissance, 1),
                     "pompe": f"{debit:.0f} m³/h à {hmt:.0f} m HMT, ≈ {puissance:.1f} kW",
                     "diametres_vitesses": f"Principale Ø {ext} ({hy.vitesse(debit, interieur):.2f} m/s) ; secteurs " + ", ".join(f"Ø {s.diametre_calc}" for s in secteurs),
                     "technique_organes": ", ".join(f"{s.name} : {s.nb_organes} × {dict(ORGANES)[s.organe].split(' (')[0].lower()} {s.debit_unitaire:g} à {s.pression_organe_bar:g} bar" for s in secteurs),
                     "dimensionnement_html": note, "diametre_principal_mm": ext})
        return True
