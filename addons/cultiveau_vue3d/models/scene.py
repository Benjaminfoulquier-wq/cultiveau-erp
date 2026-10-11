"""Les données de la vue d'ensemble : l'entreprise d'irrigation telle qu'elle tourne, station par station.

Le parcours client d'un magasin d'irrigation : l'agriculteur appelle ou passe au comptoir (1), le bureau d'étude
diagnostique, dimensionne et chiffre (2), le magasin et la cour tiennent le stock et reçoivent les fournisseurs (3),
l'équipe de pose réalise le chantier et met en service (4), l'atelier répare et les camions dépannent en saison (5),
les parcelles en service vivent au rythme de la frise : hivernage, remise en route, entretien (6), la caisse encaisse (7).
Tout est calculé pour la société courante (l'adhérent).
"""
from odoo import api, fields, models

CLOTURES = ("1_done", "1_canceled")
CHANTIER = ("mise_en_service", "livraison", "modification")
ATELIER = ("depannage", "entretien", "remise_en_service", "hivernage", "diagnostic", "autre")


class Scene(models.AbstractModel):
    _name = "cultiveau.scene"
    _description = "Vue d'ensemble (données)"

    @api.model
    def donnees(self):
        company = self.env.company
        taches = self._taches(company)
        return {
            "societe": {"id": company.id, "nom": company.name, "adherent": company.cultiveau_adherent},
            "mois": fields.Date.context_today(self).month,
            "accueil": self._accueil(company),
            "bureau": self._bureau(company),
            "magasin": self._magasin(company),
            "cour": self._cour(company),
            "chantiers": self._chantiers(company, taches),
            "atelier": [t for t in taches if t["nature"] in ATELIER],
            "parcelles": self._parcelles(company),
            "caisse": self._caisse(company),
            "compteurs": self._compteurs(company, taches),
        }

    # ---------------------------------------------------------------- 1. l'accueil : appels et comptoir

    def _accueil(self, company):
        """Les opportunités ouvertes (appels de l'assistant, demandes) et les ventes de comptoir en cours."""
        Lead = self.env["crm.lead"]
        opportunites = Lead.search([("company_id", "in", [company.id, False]), ("type", "=", "opportunity"), ("probability", "<", 100), ("active", "=", True)],
                                   order="priority desc, create_date desc", limit=8)
        comptoir = self.env["sale.order"].search([("company_id", "=", company.id), ("state", "in", ("draft", "sent")), ("cultiveau_installation_id", "=", False)],
                                                 order="date_order desc", limit=6)
        return {
            "opportunites": [{"id": o.id, "nom": o.name, "client": o.partner_id.name or o.contact_name or "", "etape": o.stage_id.name or "", "montant": round(o.expected_revenue or 0)} for o in opportunites],
            "comptoir": [{"id": v.id, "nom": v.name, "client": v.partner_id.name, "montant": round(v.amount_total), "etat": v.state} for v in comptoir],
        }

    # ---------------------------------------------------------------- 2. le bureau d'étude

    def _bureau(self, company):
        """Les installations à l'étude et les devis d'installation (dimensionnement en cours)."""
        Inst = self.env["cultiveau.installation"]
        etudes = Inst.search([("company_id", "=", company.id), ("etat", "in", ("projet", "etude"))], order="etat desc, surface_ha desc", limit=8)
        types = dict(Inst._fields["type_systeme"].selection)
        devis = self.env["sale.order"].search([("company_id", "=", company.id), ("state", "in", ("draft", "sent")), ("cultiveau_installation_id", "!=", False)],
                                              order="date_order desc", limit=8)
        return {
            "etudes": [{"id": i.id, "nom": i.name, "client": i.partner_id.name, "type": i.type_systeme, "type_libelle": types.get(i.type_systeme, ""), "etat": i.etat,
                        "surface": i.surface_ha, "analyse_validee": bool(i.analyse_validee_le) if "analyse_validee_le" in i._fields else False} for i in etudes],
            "devis": [{"id": v.id, "nom": v.name, "client": v.partner_id.name, "montant": round(v.amount_total), "etat": v.state, "installation": v.cultiveau_installation_id.name} for v in devis],
        }

    # ---------------------------------------------------------------- 3. le magasin et la cour

    def _magasin(self, company):
        """Une étagère par famille (catégorie racine), avec la quantité en stock et le nombre d'articles."""
        groupes = self.env["stock.quant"]._read_group([("company_id", "=", company.id), ("location_id.usage", "=", "internal"), ("quantity", ">", 0)],
                                                      ["product_id"], ["quantity:sum"])
        familles = {}
        for produit, quantite in groupes:
            racine = produit.categ_id
            while racine.parent_id and racine.parent_id.parent_id:
                racine = racine.parent_id
            f = familles.setdefault(racine.id, {"id": racine.id, "nom": racine.name, "quantite": 0.0, "articles": 0})
            f["quantite"] += quantite
            f["articles"] += 1
        rayons = sorted(familles.values(), key=lambda f: -f["quantite"])[:8]
        for r in rayons:
            r["quantite"] = round(r["quantite"])
        return rayons

    def _cour(self, company):
        """Les commandes fournisseurs attendues (camions à recevoir) et les livraisons clients à préparer."""
        Achat = self.env["purchase.order"]
        attendues = Achat.search([("company_id", "=", company.id), ("state", "=", "purchase")], order="date_planned asc", limit=12)
        attendues = attendues.filtered(lambda a: any(p.state not in ("done", "cancel") for p in a.picking_ids))[:6]
        Picking = self.env["stock.picking"]
        a_preparer = Picking.search([("company_id", "=", company.id), ("picking_type_code", "=", "outgoing"), ("state", "in", ("confirmed", "assigned", "waiting"))],
                                    order="scheduled_date asc", limit=6)
        return {
            "receptions": [{"id": a.id, "nom": a.name, "fournisseur": a.partner_id.name, "montant": round(a.amount_total),
                            "date": fields.Date.to_string(a.date_planned.date()) if a.date_planned else ""} for a in attendues],
            "preparations": [{"id": p.id, "nom": p.name, "client": p.partner_id.name or "", "date": fields.Date.to_string(p.scheduled_date.date()) if p.scheduled_date else ""} for p in a_preparer],
        }

    # ---------------------------------------------------------------- 4 et 5. les chantiers, l'atelier et le SAV

    def _taches(self, company):
        Task = self.env["project.task"]
        taches = Task.search([("company_id", "=", company.id), ("cultiveau_intervention", "=", True), ("state", "not in", CLOTURES)],
                             order="date_deadline asc, priority desc", limit=20)
        natures = dict(Task._fields["cultiveau_nature"].selection)
        urgences = dict(Task._fields["cultiveau_urgence"].selection)
        return [{"id": t.id, "nom": t.name, "client": t.partner_id.name or "", "technicien": t.user_ids[:1].name or "",
                 "nature": t.cultiveau_nature or "autre", "nature_libelle": natures.get(t.cultiveau_nature, ""), "urgence": t.cultiveau_urgence or "semaine",
                 "urgence_libelle": urgences.get(t.cultiveau_urgence, ""), "date": fields.Date.to_string(t.date_deadline.date()) if t.date_deadline else "",
                 "installation": t.cultiveau_installation_id.name or ""} for t in taches]

    def _chantiers(self, company, taches):
        """Les installations en réalisation (équipe de pose sur place) et les mises en service, livraisons, extensions à faire."""
        Inst = self.env["cultiveau.installation"]
        en_cours = Inst.search([("company_id", "=", company.id), ("etat", "=", "realisation")], order="surface_ha desc", limit=6)
        types = dict(Inst._fields["type_systeme"].selection)
        return {
            "installations": [{"id": i.id, "nom": i.name, "client": i.partner_id.name, "type": i.type_systeme, "type_libelle": types.get(i.type_systeme, ""),
                               "surface": i.surface_ha, "commune": i.commune or ""} for i in en_cours],
            "taches": [t for t in taches if t["nature"] in CHANTIER],
        }

    # ---------------------------------------------------------------- 6. les parcelles en service

    def _parcelles(self, company):
        Inst = self.env["cultiveau.installation"]
        inst = Inst.search([("company_id", "=", company.id), ("etat", "in", ("en_service", "arretee"))], order="etat, surface_ha desc", limit=12)
        types = dict(Inst._fields["type_systeme"].selection)
        etats = dict(Inst._fields["etat"].selection)
        mois = fields.Date.context_today(self).month
        return [{"id": i.id, "nom": i.name, "client": i.partner_id.name, "type": i.type_systeme, "type_libelle": types.get(i.type_systeme, ""),
                 "etat": i.etat, "etat_libelle": etats.get(i.etat, ""), "surface": i.surface_ha, "commune": i.commune or "",
                 "echeance": self._echeance(i, mois)} for i in inst]

    def _echeance(self, installation, mois):
        """Ce que la saison demande sur cette installation : hivernage à l'automne, remise en route au printemps."""
        if installation.etat != "en_service":
            return ""
        champs = installation._fields
        if mois in (10, 11) and "hivernage_le" in champs and not (installation.hivernage_le and installation.hivernage_le.year == fields.Date.context_today(self).year):
            return "hivernage à faire"
        if mois in (3, 4) and "remise_en_service_le" in champs and not (installation.remise_en_service_le and installation.remise_en_service_le.year == fields.Date.context_today(self).year):
            return "remise en route à faire"
        return ""

    # ---------------------------------------------------------------- 7. la caisse

    def _caisse(self, company):
        Move = self.env["account.move"]
        factures = Move.search([("company_id", "=", company.id), ("move_type", "=", "out_invoice"), ("state", "=", "posted"), ("payment_state", "in", ("not_paid", "partial"))],
                               order="invoice_date_due asc", limit=8)
        aujourdhui = fields.Date.context_today(self)
        return [{"id": f.id, "nom": f.name, "client": f.partner_id.name, "montant": round(f.amount_residual), "echeance": fields.Date.to_string(f.invoice_date_due) if f.invoice_date_due else "",
                 "en_retard": bool(f.invoice_date_due and f.invoice_date_due < aujourdhui)} for f in factures]

    # ---------------------------------------------------------------- les compteurs

    def _compteurs(self, company, taches):
        Partner = self.env["res.partner"]
        devis = self.env["sale.order"].search([("company_id", "=", company.id), ("state", "in", ("draft", "sent"))])
        factures = self.env["account.move"].search([("company_id", "=", company.id), ("move_type", "=", "out_invoice"), ("state", "=", "posted"), ("payment_state", "in", ("not_paid", "partial"))])
        a_contacter = Partner.search_count([("cultiveau_a_contacter", "=", True), ("company_id", "in", [company.id, False])]) if "cultiveau_a_contacter" in Partner._fields else 0
        return {
            "agriculteurs": Partner.search_count([("company_id", "in", [company.id, False]), ("cultiveau_type", "=", "agriculteur"), ("parent_id", "=", False)]),
            "a_contacter": a_contacter,
            "articles_en_stock": len(self.env["stock.quant"]._read_group([("company_id", "=", company.id), ("location_id.usage", "=", "internal"), ("quantity", ">", 0)], ["product_id"])),
            "devis": len(devis), "devis_montant": round(sum(devis.mapped("amount_total"))),
            "interventions": len(taches),
            "installations": self.env["cultiveau.installation"].search_count([("company_id", "=", company.id)]),
            "factures": len(factures), "factures_montant": round(sum(factures.mapped("amount_residual"))),
        }
