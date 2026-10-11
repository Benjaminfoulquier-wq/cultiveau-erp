"""Du dimensionnement au devis : la nomenclature par lots, prise dans le catalogue quand il l'a, à préciser sinon."""

import math

from odoo import Command, api, fields, models
from odoo.exceptions import UserError

from .secteur import MATERIAUX, ORGANES

LOTS = {"station": "Lot 1 — Station de pompage et énergie", "filtration": "Lot 2 — Filtration et protection sanitaire", "reseau": "Lot 3 — Réseau principal, vannes, raccords",
        "secteurs": "Lot 4 — Secteurs : conduites, rampes, organes", "automatisme": "Lot 5 — Automatisme et pilotage", "pose": "Lot 6 — Pose, mise en service, réception et formation"}
NOM_ORGANE = {"goutteur": "Gaine / tube goutte à goutte", "micro": "Micro-asperseur", "asperseur": "Asperseur", "canon": "Canon / enrouleur", "pivot": "Pivot"}


class Installation(models.Model):
    _inherit = "cultiveau.installation"

    def _article(self, mots, dn=None, matiere=None, metre=False):
        """Le premier article du catalogue de l'adhérent (puis du réseau) qui répond aux mots, au DN et à la matière ; sinon rien."""
        Produit = self.env["product.template"].with_company(self.company_id)
        base = [("sale_ok", "=", True), ("company_id", "in", [self.company_id.id, False])]
        for exiger_matiere in (True, False):
            domaine = list(base)
            for mot in mots:
                domaine.append(("name", "ilike", mot))
            if dn:
                domaine.append(("cultiveau_dn", "=", dn))
            if matiere and exiger_matiere:
                domaine.append(("cultiveau_matiere", "ilike", matiere))
            trouve = Produit.search(domaine, order="company_id desc, list_price", limit=1)
            if trouve:
                return trouve
            if not matiere:
                break
        return Produit

    def _a_preciser(self):
        """L'article « à préciser » de la société : une ligne de devis qui attend son article et son prix."""
        Produit = self.env["product.product"].with_company(self.company_id)
        p = Produit.search([("default_code", "=", "A-PRECISER"), ("company_id", "in", [self.company_id.id, False])], limit=1)
        if not p:
            p = Produit.create({"name": "Article à préciser (nomenclature)", "default_code": "A-PRECISER", "type": "service", "list_price": 0.0, "sale_ok": True,
                               "purchase_ok": False, "company_id": self.company_id.id})
        return p

    def action_generer_devis(self):
        """Le devis par lots avec la nomenclature calculée. Chaque ligne a son article du catalogue, ou attend d'être précisée."""
        self.ensure_one()
        if not self.secteur_ids or not self.debit_equipement_m3_h:
            raise UserError("Lancez d'abord « Calculer le dimensionnement » : la nomenclature en découle.")
        i = self
        lignes = []
        seq = [0]
        unite = self.env.ref("uom.product_uom_unit")
        metre = self.env.ref("uom.product_uom_meter")
        a_preciser = self._a_preciser()

        def section(cle):
            seq[0] += 10
            lignes.append(Command.create({"display_type": "line_section", "name": LOTS[cle], "sequence": seq[0]}))

        def ligne(nom, qte, mots=(), dn=None, matiere=None, au_metre=False, note=None):
            seq[0] += 1
            # seul ce qui se reconnaît à coup sûr (un DN, une matière) est pris au catalogue ; une pompe ou un filtre se choisissent à la main
            article = self._article(mots, dn, matiere) if (mots and dn) else self.env["product.template"]
            produit = article.product_variant_id if article else a_preciser
            libelle = nom if not article else f"{article.name} — {nom}"
            valeurs = {"product_id": produit.id, "name": libelle, "product_uom_qty": max(1, math.ceil(qte)) if not au_metre else round(qte),
                       "product_uom": (metre if au_metre else unite).id, "sequence": seq[0]}
            if not article:
                valeurs["price_unit"] = 0.0
            lignes.append(Command.create(valeurs))
            if note:
                seq[0] += 1
                lignes.append(Command.create({"display_type": "line_note", "name": note, "sequence": seq[0]}))

        debit, hmt = i.debit_equipement_m3_h, i.hmt_m
        principale = i.diametre_principal_mm
        mat = dict(MATERIAUX).get(i.materiau_principal or "pe", "PE").split(" ")[0]
        # Lot 1
        section("station")
        if i.type_systeme == "enrouleur":
            ligne(f"Enrouleur {debit:.0f} m³/h, tuyau PE, canon ou rampe", 1, ("enrouleur",))
        if i.type_systeme == "pivot":
            ligne(f"Pivot / rampe frontale pour {i.surface_ha:g} ha, {debit:.0f} m³/h", 1, ("pivot",))
        ligne(f"Pompe {debit:.0f} m³/h à {hmt:.0f} m HMT (≈ {i.puissance_kw:g} kW), {dict(i._fields['energie'].selection).get(i.energie, '').lower() or 'énergie à préciser'}", 1, ("pompe",),
              note=f"Point de fonctionnement calculé : Q = {debit:.0f} m³/h, H = {hmt:.0f} m, {i.simultaneite or 1} secteur(s) simultané(s). Vérifier la courbe de la pompe retenue.")
        if i.energie in ("reseau", "mixte", "solaire"):
            ligne(f"Armoire électrique / variateur {i.puissance_kw:g} kW, protection marche à sec, pressostat", 1, ("armoire",))
        ligne("Anti-bélier, clapet, manomètres, compteur d'eau", 1, ("anti-bélier",))
        # Lot 2
        section("filtration")
        organe_principal = i.secteur_ids[0].organe
        if organe_principal in ("goutteur", "micro"):
            ligne(f"Filtration à disques ou à tamis 130 µm, {debit:.0f} m³/h, avec contre-lavage", 1, ("filtre",), note="Finesse selon le goutteur et l'analyse d'eau (§ 5.4).")
        else:
            ligne(f"Filtre à tamis {debit:.0f} m³/h", 1, ("filtre",))
        ligne("Disconnecteur / clapet anti-retour (protection sanitaire, point d'arrêt à la réception)", 1, ("disconnecteur",))
        ligne("Ventouses (points hauts) et purges (points bas)", max(2, len(i.secteur_ids)), ("ventouse",))
        # Lot 3
        section("reseau")
        lp = i.longueur_principale_m or 0.0
        if lp:
            ligne(f"Conduite principale {mat} Ø {principale} PN10, {lp:g} m", lp, ("tube",), dn=principale, matiere=mat, au_metre=True)
            ligne(f"Raccords de la principale : coudes, manchons, tés Ø {principale}", max(2, round(lp / 100 * 3)), ("raccord",), dn=principale)
        for s in i.secteur_ids:
            ligne(f"Vanne de secteur Ø {s.diametre_calc} — {s.name}", 1, ("vanne",), dn=s.diametre_calc)
            ligne(f"Té de piquage Ø {principale} / Ø {s.diametre_calc} — {s.name}", 1, ("té",), dn=principale)
        ligne("Butées béton aux changements de direction, grillage avertisseur", 1, ())
        # Lot 4
        section("secteurs")
        for s in i.secteur_ids:
            smat = dict(MATERIAUX).get(s.materiau or "pe", "PE").split(" ")[0]
            if s.longueur_m:
                ligne(f"Conduite d'amenée {smat} Ø {s.diametre_calc}, {s.longueur_m:g} m — {s.name}", s.longueur_m, ("tube",), dn=s.diametre_calc, matiere=smat, au_metre=True)
            if s.organe == "goutteur":
                ligne(f"{NOM_ORGANE[s.organe]} {s.debit_unitaire:g} l/h tous les {s.espacement_m:g} m, lignes tous les {s.ecartement_m:g} m — {s.name} ({s.surface_ha:g} ha)",
                      s.longueur_rampes_m, ("goutte",), au_metre=True)
                ligne(f"Raccords de rampes (départs, bouchons, jonctions) — {s.name}", max(10, round(s.longueur_rampes_m / s.ecartement_m / 10)) if s.ecartement_m else 10, ("raccord goutte",))
            elif s.organe in ("micro", "asperseur"):
                ligne(f"{NOM_ORGANE[s.organe]} {s.debit_unitaire:g} {'l/h' if s.organe == 'micro' else 'm³/h'} à {s.pression_organe_bar:g} bar, maille {s.espacement_m:g} × {s.ecartement_m:g} m — {s.name}",
                      s.nb_organes, ("asperseur" if s.organe == "asperseur" else "micro",))
                ligne(f"Rampes PE et raccords des organes — {s.name}", s.longueur_rampes_m, ("tube",), matiere="PE", au_metre=True)
            elif s.organe == "canon":
                ligne(f"Bornes / hydrants d'alimentation — {s.name}", max(1, s.nb_organes), ("hydrant",))
            ligne(f"Régulateur de pression {s.pression_organe_bar:g} bar en tête — {s.name}", 1, ("régulateur",))
        # Lot 5
        section("automatisme")
        if (i.niveau_automatisme or "manuel") != "manuel":
            ligne(f"Programmateur {len(i.secteur_ids)} voies" + (" piloté (sondes, régulation)" if i.niveau_automatisme == "pilote" else ""), 1, ("programmateur",))
            ligne(f"Électrovannes de secteur Ø {max(s.diametre_calc for s in i.secteur_ids)}", len(i.secteur_ids), ("électrovanne",))
            ligne("Câble de commande et accessoires", lp + sum(i.secteur_ids.mapped("longueur_m")), ("câble",), au_metre=True)
        else:
            ligne("Vannes manuelles de secteur (déjà comptées) — aucun automatisme demandé", 1, ())
        # Lot 6
        section("pose")
        tranchee = lp + sum(i.secteur_ids.mapped("longueur_m"))
        if tranchee:
            ligne(f"Tranchée mécanique hors gel, pose et remblai, {tranchee:g} m", tranchee, (), au_metre=True)
        ligne("Pose, raccordements, rinçage, essais de pression avant remblaiement", 1, ())
        ligne("Mise en service, PV A1.3 avec pressions de référence, fiche de réglage A1.5, formation de l'exploitant", 1, ())
        modele = self.env["sale.order.template"].search([("cultiveau_type_systeme", "=", i.type_systeme)], limit=1)
        devis = self.env["sale.order"].with_company(i.company_id).create({
            "partner_id": i.partner_id.id, "company_id": i.company_id.id, "cultiveau_installation_id": i.id, "cultiveau_type_systeme": i.type_systeme,
            "origin": i.name, "note": modele.note if modele else False, "order_line": lignes})
        devis.message_post(body=f"Nomenclature générée depuis le dimensionnement de « {i.name} » : {len(i.secteur_ids)} secteurs, {debit:.0f} m³/h, HMT {hmt:.0f} m. "
                                "Les lignes « Article à préciser » attendent leur article et leur prix.")
        return {"type": "ir.actions.act_window", "res_model": "sale.order", "res_id": devis.id, "view_mode": "form", "target": "current"}
