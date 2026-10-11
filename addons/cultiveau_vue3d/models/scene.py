"""Les données de la vue d'ensemble : l'entreprise d'irrigation telle qu'elle tourne, station par station.

Le parcours client d'un magasin d'irrigation : l'agriculteur appelle ou passe au comptoir (1), le bureau d'étude
diagnostique, dimensionne et chiffre (2), le magasin et la cour tiennent le stock et reçoivent les fournisseurs (3),
l'équipe de pose réalise le chantier et met en service (4), l'atelier répare et les camions dépannent en saison (5),
les parcelles en service vivent au rythme de la frise : hivernage, remise en route, entretien (6), la caisse encaisse (7).
Tout est calculé pour la société courante (l'adhérent).
"""
from odoo import api, fields, models
from odoo.exceptions import UserError

# type de client -> (singulier, pluriel) : un véhicule par type au parking clients
TYPES_CLIENTS = {
    "agriculteur": ("Agriculteur", "Agriculteurs"), "collectivite": ("Collectivité", "Collectivités"), "particulier": ("Particulier", "Particuliers"),
    "industrie": ("Industrie", "Industries"), "plombier": ("Plombier", "Plombiers"), "paysagiste": ("Paysagiste", "Paysagistes"),
    "pisciniste": ("Pisciniste", "Piscinistes"), "autre": ("Autre", "Autres clients"),
}

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
            "familles": self._familles(company),
            "actions": sorted(self._actions_disponibles()),
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
            "agriculteurs": Partner.search_count([("company_id", "in", [company.id, False]), ("cultiveau_est_client", "=", True), ("parent_id", "=", False)]),
            "clients_par_type": {t: n for t, n in Partner._read_group(
                [("company_id", "in", [company.id, False]), ("cultiveau_est_client", "=", True), ("parent_id", "=", False)], ["cultiveau_type"], ["__count"])},
            "a_contacter": a_contacter,
            "articles_en_stock": len(self.env["stock.quant"]._read_group([("company_id", "=", company.id), ("location_id.usage", "=", "internal"), ("quantity", ">", 0)], ["product_id"])),
            "devis": len(devis), "devis_montant": round(sum(devis.mapped("amount_total"))),
            "interventions": len(taches),
            "installations": self.env["cultiveau.installation"].search_count([("company_id", "=", company.id)]),
            "factures": len(factures), "factures_montant": round(sum(factures.mapped("amount_residual"))),
            **self._compteurs_catalogue(),
        }

    def _compteurs_catalogue(self):
        Produit = self.env["product.template"]
        res = {"fiches": self.env["cultiveau.fiche"].search_count([]) if "cultiveau.fiche" in self.env else 0}
        if "cultiveau_reseau" in Produit._fields:
            res["catalogue"] = Produit.search_count([("cultiveau_reseau", "=", True)])
            res["mon_catalogue"] = Produit.search_count([("cultiveau_mon_catalogue", "=", True), ("sale_ok", "=", True)])
        return res

    # ---------------------------------------------------------------- les familles de produits (les rayons du magasin)

    def _familles(self, company):
        """Les familles du catalogue (catégories racines) : articles dans mon catalogue, au catalogue Cultiveau, en stock."""
        Produit = self.env["product.template"].with_company(company)
        racines = {}

        def racine(categorie):
            if not categorie:
                return None
            ids = [int(i) for i in (categorie.parent_path or "").split("/") if i]
            r = self.env["product.category"].browse(ids[0]) if ids else categorie
            return racines.setdefault(r.id, {"id": r.id, "nom": "Divers" if r == self.env.ref("product.product_category_all", raise_if_not_found=False) else r.name,
                                             "mien": 0, "reseau": 0, "stock": 0})

        if "cultiveau_mon_catalogue" in Produit._fields:
            for categorie, n in Produit._read_group([("cultiveau_mon_catalogue", "=", True), ("sale_ok", "=", True)], ["categ_id"], ["__count"]):
                if (f := racine(categorie)):
                    f["mien"] += n
        if "cultiveau_reseau" in Produit._fields:
            for categorie, n in Produit._read_group([("cultiveau_reseau", "=", True)], ["categ_id"], ["__count"]):
                if (f := racine(categorie)):
                    f["reseau"] += n
        for produit, quantite in self.env["stock.quant"]._read_group([("company_id", "=", company.id), ("location_id.usage", "=", "internal"), ("quantity", ">", 0)],
                                                                     ["product_id"], ["quantity:sum"]):
            if (f := racine(produit.categ_id)):
                f["stock"] += quantite
        familles = [f for f in racines.values() if f["mien"] or f["reseau"] or f["stock"]]
        for f in familles:
            f["stock"] = round(f["stock"])
        return sorted(familles, key=lambda f: (f["nom"] == "Divers", -(f["mien"] + f["reseau"]), f["nom"]))

    # ---------------------------------------------------------------- les portes : ce que chaque poste du plan ouvre

    def _actions(self):
        """clé -> (action de référence, réglages). Réglages : name, domain, context, form (ouvrir un formulaire vierge),
        famille (filtrer sur la famille passée en paramètre), url (paramètre système, lien ouvert dans un onglet)."""
        nature = lambda *n: [("cultiveau_intervention", "=", True), ("cultiveau_nature", "in", list(n))]  # noqa: E731
        ouvertes = [("state", "not in", list(CLOTURES))]
        return {
            # l'administratif
            "facture_nouvelle": ("account.action_move_out_invoice_type", {"name": "Nouvelle facture", "form": True, "context": {"default_move_type": "out_invoice"}}),
            "factures": ("account.action_move_out_invoice_type", {}),
            "factures_a_encaisser": ("account.action_move_out_invoice_type", {"name": "Factures à encaisser",
                                     "domain": [("state", "=", "posted"), ("payment_state", "in", ("not_paid", "partial"))]}),
            "avoirs": ("account.action_move_out_refund_type", {}),
            "factures_fournisseurs": ("account.action_move_in_invoice_type", {}),
            "a_payer": ("account.action_move_in_invoice_type", {"name": "Fournisseurs à payer",
                        "domain": [("state", "=", "posted"), ("payment_state", "in", ("not_paid", "partial"))]}),
            "paiements": ("account.action_account_payments", {}),
            "journaux": ("account.action_account_journal_form", {}),
            "ecritures": ("account.action_account_moves_all", {}),
            "ventes_analyse": ("sale.action_order_report_all", {}),
            "achats_analyse": ("purchase.action_purchase_order_report_all", {}),
            "crm_analyse": ("crm.crm_opportunity_report_action", {}),
            "reglages": ("cultiveau_base.action_cultiveau_config_settings", {}),
            "import_reseau": ("cultiveau_base.action_import_reseau", {}),
            "utilisateurs": ("base.action_res_users", {}),
            # le bureau d'étude et la salle de réunion
            "etudes": ("cultiveau_installation.action_installations", {"name": "Études en cours", "domain": [("etat", "in", ("projet", "etude"))]}),
            "etude_nouvelle": ("cultiveau_installation.action_installations", {"name": "Nouvelle étude", "form": True, "context": {"default_etat": "etude"}}),
            "installations": ("cultiveau_installation.action_installations", {}),
            "usages": ("cultiveau_ventes.action_usages", {}),
            "schema3d": (None, {"url": ("cultiveau.url_schema3d", "https://schema3d.cultiveau.fr"), "name": "Cultiveau 3D"}),
            "pipeline": ("crm.crm_lead_action_pipeline", {}),
            "devis": ("sale.action_quotations_with_onboarding", {}),
            "devis_nouveau": ("sale.action_quotations_with_onboarding", {"name": "Nouveau devis", "form": True}),
            "commandes": ("sale.action_orders", {}),
            "rendez_vous": ("calendar.action_calendar_event", {}),
            # le magasin
            "comptoir": ("cultiveau_comptoir.action_comptoir", {}),
            "ventes_comptoir": ("sale.action_orders", {"name": "Ventes au comptoir", "domain": [("origin", "=", "Comptoir")]}),
            "agriculteurs": ("cultiveau_base.action_agriculteurs", {}),
            "clients_type": ("cultiveau_base.action_agriculteurs", {"type_client": True}),
            "client_type_nouveau": ("cultiveau_base.action_agriculteurs", {"type_client": True, "form": True}),
            "agriculteur_nouveau": ("cultiveau_base.action_agriculteurs", {"name": "Nouveau client", "form": True,
                                    "context": {"default_cultiveau_type": "agriculteur", "default_is_company": False}}),
            "a_contacter": ("cultiveau_frise.action_a_contacter", {}),
            "import_clients": ("cultiveau_base.action_import_clients", {}),
            "cultures": ("cultiveau_frise.action_cultures", {}),
            "personas": ("cultiveau_persona.action_personas", {}),
            "fiches": ("cultiveau_catalogue.action_fiches", {}),
            "catalogue": ("cultiveau_catalogue.action_catalogue", {}),
            "mon_catalogue": ("cultiveau_catalogue.action_mon_catalogue", {}),
            "import_articles": ("cultiveau_catalogue.action_import_articles", {}),
            "fournisseurs": ("cultiveau_catalogue.action_fournisseurs", {}),
            "categories": ("product.product_category_action_form", {}),
            "occasion": ("cultiveau_catalogue.action_mon_catalogue", {"name": "Occasion et reprises",
                         "domain": ["|", ("name", "ilike", "occasion"), ("name", "ilike", "reprise")]}),
            # une famille de produits (paramètre : la catégorie)
            "famille_mien": ("cultiveau_catalogue.action_mon_catalogue", {"famille": "categ_id"}),
            "famille_stock": ("cultiveau_catalogue.action_mon_catalogue", {"famille": "categ_id", "domain": [("qty_available", ">", 0)], "suffixe": "en stock"}),
            "famille_reseau": ("cultiveau_catalogue.action_catalogue", {"famille": "categ_id", "suffixe": "au catalogue Cultiveau"}),
            "famille_fiches": ("cultiveau_catalogue.action_fiches", {"famille": "produit_ids.categ_id", "suffixe": "fiches techniques"}),
            # le stockage, la cour
            "livraisons": ("stock.action_picking_tree_outgoing", {}),
            "receptions": ("stock.action_picking_tree_incoming", {}),
            "inventaire": ("stock.action_view_inventory_tree", {}),
            "reappro": ("stock.action_orderpoint", {}),
            "mouvements": ("stock.stock_move_line_action", {}),
            "achats": ("purchase.purchase_form_action", {}),
            "achat_nouveau": ("purchase.purchase_rfq", {"name": "Nouvelle commande fournisseur", "form": True}),
            "demandes_prix": ("purchase.purchase_rfq", {}),
            # l'atelier et le SAV
            "interventions": ("cultiveau_interventions.action_interventions", {}),
            "depannage_nouveau": ("cultiveau_interventions.action_interventions", {"name": "Nouveau dépannage", "form": True,
                                  "context": {"default_cultiveau_nature": "depannage"}}),
            "entretiens": ("cultiveau_interventions.action_interventions", {"name": "Entretiens et diagnostics",
                           "domain": nature("entretien", "diagnostic", "hivernage", "remise_en_service") + ouvertes}),
            "depannages": ("cultiveau_interventions.action_interventions", {"name": "Dépannages", "domain": nature("depannage") + ouvertes}),
            "equipements_a_renouveler": ("cultiveau_installation.action_equipements_a_renouveler", {}),
            "registre": ("cultiveau_installation.action_registre", {}),
            # chez les agriculteurs
            "chantiers": ("cultiveau_chantier.action_chantiers", {}),
            "planning": ("cultiveau_chantier.action_planning", {}),
            "chantier_nouveau": ("cultiveau_chantier.action_chantiers", {"name": "Nouveau chantier", "form": True}),
            "parc": ("cultiveau_installation.action_installations", {"name": "Parc installé", "domain": [("etat", "in", ("en_service", "arretee"))]}),
        }

    def _actions_disponibles(self):
        dispo = set()
        for cle, (xmlid, reglages) in self._actions().items():
            if reglages.get("url") or (xmlid and self.env.ref(xmlid, raise_if_not_found=False)):
                dispo.add(cle)
        return dispo

    @api.model
    def action(self, cle, parametre=None):
        """L'action à ouvrir pour un poste du plan : l'action standard, filtrée ou en formulaire vierge selon la clé."""
        actions = self._actions()
        if cle not in actions:
            raise UserError(f"Rien n'est relié à « {cle} ».")
        xmlid, r = actions[cle]
        if r.get("url"):
            param, defaut = r["url"]
            url = self.env["ir.config_parameter"].sudo().get_param(param) or defaut
            return {"type": "ir.actions.act_url", "url": url, "target": "new", "name": r.get("name", "")}
        record = self.env.ref(xmlid, raise_if_not_found=False)
        if not record:
            raise UserError(f"« {cle} » n'est pas installé sur cette base.")
        action = self.env[record._name]._for_xml_id(xmlid)
        if action.get("type") != "ir.actions.act_window":
            return action
        contexte = action.get("context") or {}
        if isinstance(contexte, str):
            try:
                from odoo.tools.safe_eval import safe_eval
                contexte = safe_eval(contexte, {"uid": self.env.uid, "active_id": False, "allowed_company_ids": self.env.companies.ids})
            except Exception:  # noqa: BLE001 — un contexte calculé côté client : on repart de zéro
                contexte = {}
        contexte = {k: v for k, v in contexte.items() if not k.startswith("search_default_")}
        contexte.update(r.get("context", {}))
        domaine = list(r.get("domain", []))
        if action.get("domain") and isinstance(action["domain"], (list, tuple)):
            domaine = list(action["domain"]) + domaine
        elif action.get("domain") and isinstance(action["domain"], str) and "uid" not in action["domain"]:
            try:
                from odoo.tools.safe_eval import safe_eval
                domaine = list(safe_eval(action["domain"])) + domaine
            except Exception:  # noqa: BLE001
                pass
        if r.get("famille"):
            categorie = self.env["product.category"].browse(int(parametre or 0)).exists()
            if not categorie:
                raise UserError("Famille introuvable.")
            domaine.append((r["famille"], "child_of", categorie.id))
            action["name"] = f"{categorie.name} — {r['suffixe']}" if r.get("suffixe") else categorie.name
        if r.get("type_client"):
            if parametre not in TYPES_CLIENTS:
                raise UserError("Type de client inconnu.")
            domaine.append(("cultiveau_type", "=", parametre))
            contexte["default_cultiveau_type"] = parametre
            contexte["default_is_company"] = parametre not in ("particulier", "agriculteur")
            action["name"] = (f"Nouveau client — {TYPES_CLIENTS[parametre][0]}" if r.get("form") else TYPES_CLIENTS[parametre][1])
        if r.get("name"):
            action["name"] = r["name"]
        action["display_name"] = action["name"]
        action["domain"] = domaine
        action["context"] = contexte
        if r.get("form"):
            formulaire = next((v for v in action.get("views") or [] if v[1] == "form"), [False, "form"])
            action.update({"views": [formulaire], "view_mode": "form", "res_id": False, "target": "current"})
        return action
