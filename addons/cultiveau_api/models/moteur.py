"""Le moteur de l'API : ce que chaque ressource montre, comment on la cherche, ce qu'on peut y écrire.

Utilisé par l'API REST (controllers/api_v1.py) et par le connecteur Claude (MCP). Tout passe par ici, avec la clé
qui appelle : ses droits (lecture, écriture) et ses adhérents (les données des autres sociétés ne sortent pas).
"""
from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import html2plaintext

LIMITE_MAX = 200


def _date(v):
    if not v:
        return None
    return fields.Datetime.to_string(v) if isinstance(v, fields.datetime) else fields.Date.to_string(v)


def _ref(rec):
    return {"id": rec.id, "nom": rec.display_name} if rec else None


def _choix(rec, champ):
    v = rec[champ]
    if not v:
        return None
    return {"code": v, "libelle": dict(rec._fields[champ]._description_selection(rec.env)).get(v, v)}


class ApiMoteur(models.AbstractModel):
    _name = "cultiveau.api.moteur"
    _description = "API de l'ERP (moteur)"

    # ---------------------------------------------------------------- les ressources

    def _ressources(self):
        """nom -> réglages : modele, domaine, recherche (champs), societe (champ société), titre, ecriture (bool)."""
        R = {
            "clients": {"modele": "res.partner", "titre": "Clients (agriculteurs et entreprises clientes)",
                        "domaine": [("parent_id", "=", False), "|", ("cultiveau_type", "=", "agriculteur"), ("customer_rank", ">", 0)],
                        "recherche": ["name", "exploitation", "email", "phone", "mobile", "city", "zip"], "ecriture": True, "ordre": "name"},
            "interventions": {"modele": "project.task", "titre": "Interventions (dépannages, entretiens, mises en service…)",
                              "domaine": [("cultiveau_intervention", "=", True)], "recherche": ["name", "cultiveau_symptome", "partner_id.name"],
                              "ecriture": True, "ordre": "create_date desc"},
            "chantiers": {"modele": "cultiveau.chantier", "titre": "Chantiers de pose", "domaine": [], "recherche": ["name", "titre", "partner_id.name"],
                          "ordre": "date_debut desc, id desc"},
            "installations": {"modele": "cultiveau.installation", "titre": "Installations (parc installé et projets)", "domaine": [],
                              "recherche": ["name", "partner_id.name", "commune"], "ordre": "name"},
            "registre": {"modele": "cultiveau.registre", "titre": "Registre de maintenance", "domaine": [], "recherche": ["description", "installation_id.name"],
                         "ordre": "date desc, id desc"},
            "devis": {"modele": "sale.order", "titre": "Devis en cours", "domaine": [("state", "in", ("draft", "sent"))],
                      "recherche": ["name", "partner_id.name", "client_order_ref"], "ordre": "date_order desc"},
            "commandes": {"modele": "sale.order", "titre": "Commandes confirmées", "domaine": [("state", "=", "sale")],
                          "recherche": ["name", "partner_id.name", "client_order_ref"], "ordre": "date_order desc"},
            "factures": {"modele": "account.move", "titre": "Factures et avoirs clients", "domaine": [("move_type", "in", ("out_invoice", "out_refund")), ("state", "!=", "cancel")],
                         "recherche": ["name", "partner_id.name", "ref"], "ordre": "invoice_date desc, id desc"},
            "opportunites": {"modele": "crm.lead", "titre": "Demandes et opportunités", "domaine": [("type", "=", "opportunity")],
                             "recherche": ["name", "partner_id.name", "contact_name", "email_from"], "ecriture": True, "ordre": "create_date desc"},
            "articles": {"modele": "product.template", "titre": "Articles (mon catalogue ; ?catalogue=reseau pour le catalogue Cultiveau)",
                         "domaine": [("sale_ok", "=", True)], "recherche": ["name", "default_code", "barcode"], "ordre": "name", "societe": None},
            "fiches": {"modele": "cultiveau.fiche", "titre": "Fiches techniques", "domaine": [], "recherche": ["name", "fournisseur_nom", "famille"], "ordre": "name",
                       "societe": None},
            "adherents": {"modele": "res.company", "titre": "Le réseau : Cultiveau et ses adhérents", "domaine": [], "recherche": ["name", "city"], "ordre": "name",
                          "societe": "id"},
        }
        return {k: v for k, v in R.items() if v["modele"] in self.env}

    def ressources_publiques(self):
        return [{"nom": k, "titre": v["titre"], "ecriture": bool(v.get("ecriture"))} for k, v in self._ressources().items()]

    # ---------------------------------------------------------------- les droits de la clé

    def _par_utilisateur(self, cle):
        """Sans clé et hors de l'API (appel depuis l'ERP : assistant, écran), on travaille avec les droits de la personne connectée."""
        return not cle and not self.env.su

    def _societes(self, cle):
        """Les sociétés visibles : celles de la clé ; celles où la personne connectée travaille ; sinon (API sans restriction) tout le réseau."""
        if self._par_utilisateur(cle):
            return self.env.companies
        return cle.company_ids if cle and cle.company_ids else self.env["res.company"].sudo().search([])

    def _domaine_societe(self, reglages, modele, cle):
        champ = reglages.get("societe", "company_id")
        if champ is None or champ not in modele._fields and champ != "id":
            return []
        societes = self._societes(cle)
        if champ == "id":
            return [("id", "in", societes.ids)]
        if not modele._fields[champ].required:
            return ["|", (champ, "in", societes.ids), (champ, "=", False)]
        return [(champ, "in", societes.ids)]

    def _verifier_ecriture(self, cle):
        if cle and cle.droits != "ecriture":
            raise AccessError("Cette clé est en lecture seule.")

    def _env(self, cle):
        """Pour l'API : le superutilisateur, sur les sociétés de la clé (les règles d'accès sont remplacées par le filtre des adhérents).
        Depuis l'ERP : la personne connectée, avec ses propres droits."""
        societes = self._societes(cle)
        contexte = {"allowed_company_ids": societes.ids, "active_test": True}
        if self.env["res.lang"].sudo().search_count([("code", "=", "fr_FR"), ("active", "=", True)]):
            contexte["lang"] = "fr_FR"
        if self._par_utilisateur(cle):
            return self.with_context(**contexte).env
        return self.sudo().with_context(**contexte).env

    # ---------------------------------------------------------------- lire

    @api.model
    def lister(self, ressource, params=None, cle=None):
        params = dict(params or {})
        reglages = self._reglages(ressource)
        env = self._env(cle)
        Modele = env[reglages["modele"]]
        domaine = list(reglages["domaine"]) + self._domaine_societe(reglages, Modele, cle)
        texte = (params.get("q") or params.get("recherche") or "").strip()
        if texte:
            champs = [c for c in reglages["recherche"] if c.split(".")[0] in Modele._fields]
            domaine += ["|"] * (len(champs) - 1) + [(c, "ilike", texte) for c in champs]
        if params.get("modifie_depuis"):
            domaine.append(("write_date", ">=", params["modifie_depuis"]))
        for cle_param, champ in (("client_id", "partner_id"), ("installation_id", "installation_id"), ("adherent_id", "company_id")):
            if params.get(cle_param):
                if reglages["modele"] == "project.task" and champ == "installation_id":
                    champ = "cultiveau_installation_id"
                if reglages["modele"] == "sale.order" and champ == "installation_id":
                    champ = "cultiveau_installation_id"
                if champ in Modele._fields:
                    domaine.append((champ, "child_of" if champ == "partner_id" else "=", int(params[cle_param])))
        if params.get("etat"):
            champ = {"cultiveau.chantier": "etat", "cultiveau.installation": "etat", "project.task": "state", "sale.order": "state",
                     "account.move": "payment_state", "crm.lead": "stage_id.name"}.get(reglages["modele"])
            if champ:
                domaine.append((champ, "ilike" if champ.endswith(".name") else "=", params["etat"]))
        if ressource == "interventions" and params.get("ouvertes") in ("1", "true", True):
            domaine.append(("state", "not in", ("1_done", "1_canceled")))
        if ressource == "factures" and params.get("a_encaisser") in ("1", "true", True):
            domaine += [("state", "=", "posted"), ("payment_state", "in", ("not_paid", "partial"))]
        if ressource == "articles":
            if params.get("catalogue") == "reseau" and "cultiveau_reseau" in Modele._fields:
                domaine.append(("cultiveau_reseau", "=", True))
            elif "cultiveau_mon_catalogue" in Modele._fields:
                # « mon catalogue » : celui du premier adhérent de la clé (ou de l'adhérent demandé)
                societe = self._societes(cle).filtered(lambda c: not params.get("adherent_id") or c.id == int(params["adherent_id"]))[:1]
                Modele = Modele.with_company(societe)
                domaine.append(("cultiveau_mon_catalogue", "=", True))
            if params.get("en_stock") in ("1", "true", True):
                domaine.append(("qty_available", ">", 0))
        limite = max(1, min(LIMITE_MAX, int(params.get("limite") or 50)))
        decalage = max(0, int(params.get("decalage") or (int(params.get("page") or 1) - 1) * limite))
        total = Modele.search_count(domaine)
        enregistrements = Modele.search(domaine, order=reglages.get("ordre"), limit=limite, offset=decalage)
        return {"ressource": ressource, "total": total, "limite": limite, "decalage": decalage,
                "suivant": decalage + limite if decalage + limite < total else None,
                "resultats": [self._serialiser(ressource, r, detail=False) for r in enregistrements]}

    @api.model
    def lire(self, ressource, ident, cle=None):
        reglages = self._reglages(ressource)
        env = self._env(cle)
        Modele = env[reglages["modele"]]
        domaine = list(reglages["domaine"]) + self._domaine_societe(reglages, Modele, cle) + [("id", "=", int(ident))]
        rec = Modele.search(domaine, limit=1)
        if not rec:
            raise UserError(f"{ressource} n°{ident} introuvable (ou hors des adhérents de cette clé).")
        return self._serialiser(ressource, rec, detail=True)

    @api.model
    def resume(self, cle=None):
        """Le tableau de bord en une réponse : ce qui attend, adhérent par adhérent."""
        env = self._env(cle)
        res = []
        for societe in self._societes(cle):
            factures = env["account.move"].search([("company_id", "=", societe.id), ("move_type", "=", "out_invoice"), ("state", "=", "posted"),
                                                   ("payment_state", "in", ("not_paid", "partial"))])
            devis = env["sale.order"].search([("company_id", "=", societe.id), ("state", "in", ("draft", "sent"))])
            ligne = {
                "adherent": _ref(societe),
                "interventions_ouvertes": env["project.task"].search_count([("company_id", "=", societe.id), ("cultiveau_intervention", "=", True), ("state", "not in", ("1_done", "1_canceled"))]),
                "urgences": env["project.task"].search_count([("company_id", "=", societe.id), ("cultiveau_intervention", "=", True), ("state", "not in", ("1_done", "1_canceled")),
                                                              ("cultiveau_urgence", "in", ("immediate", "journee"))]),
                "devis_en_cours": len(devis), "devis_montant": round(sum(devis.mapped("amount_total")), 2),
                "factures_a_encaisser": len(factures), "reste_a_encaisser": round(sum(factures.mapped("amount_residual")), 2),
                "opportunites_ouvertes": env["crm.lead"].search_count([("company_id", "in", (societe.id, False)), ("type", "=", "opportunity"), ("probability", "<", 100)]),
                "installations_en_service": env["cultiveau.installation"].search_count([("company_id", "=", societe.id), ("etat", "=", "en_service")]),
            }
            if "cultiveau.chantier" in env:
                ligne["chantiers_actifs"] = env["cultiveau.chantier"].search_count([("company_id", "=", societe.id), ("etat", "in", ("planifie", "en_cours"))])
            res.append(ligne)
        return {"adherents": res, "le": _date(fields.Datetime.now())}

    def _reglages(self, ressource):
        r = self._ressources().get(ressource)
        if not r:
            raise UserError(f"Ressource inconnue : {ressource}. Ressources : {', '.join(self._ressources())}.")
        return r

    # ---------------------------------------------------------------- ce que chaque ressource montre

    def _serialiser(self, ressource, r, detail):
        base = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "").rstrip("/")
        f = getattr(self, f"_s_{ressource}")
        donnees = {"id": r.id, **f(r, detail), "modifie_le": _date(r.write_date)}
        donnees["url"] = f"{base}/app/{r._name}/{r.id}" if ressource != "adherents" else None
        return donnees

    def _s_clients(self, p, detail):
        d = {"nom": p.name, "exploitation": p.exploitation or None, "est_entreprise": p.is_company, "type": _choix(p, "cultiveau_type"),
             "email": p.email or None, "telephone": p.phone or None, "mobile": p.mobile or None,
             "adresse": {"rue": p.street or None, "complement": p.street2 or None, "code_postal": p.zip or None, "commune": p.city or None,
                         "departement": p.departement or None, "pays": p.country_id.code or None},
             "adherent": _ref(p.company_id), "commercial": _ref(p.user_id), "etiquettes": p.category_id.mapped("name")}
        if "cultiveau_persona_id" in p._fields:
            d["persona"] = {"code": p.cultiveau_persona_id.code, "nom": p.cultiveau_persona_id.name} if p.cultiveau_persona_id else None
        if detail:
            d["contacts"] = [{"id": c.id, "nom": c.name, "fonction": c.function or None, "email": c.email or None, "telephone": c.mobile or c.phone or None} for c in p.child_ids]
            if "cultiveau_culture_ids" in p._fields:
                d["cultures"] = [{"culture": c.culture_id.name, "surface_ha": c.surface_ha} for c in p.cultiveau_culture_ids]
            d["installations"] = [_ref(i) for i in p.cultiveau_installation_ids] if "cultiveau_installation_ids" in p._fields else []
            Task = self.env["project.task"]
            d["interventions_ouvertes"] = [_ref(t) for t in Task.search([("partner_id", "child_of", p.id), ("cultiveau_intervention", "=", True),
                                                                         ("state", "not in", ("1_done", "1_canceled"))], limit=20)]
            d["devis_en_cours"] = [_ref(o) for o in self.env["sale.order"].search([("partner_id", "child_of", p.id), ("state", "in", ("draft", "sent"))], limit=20)]
            d["notes"] = p.comment or None
        return d

    def _s_interventions(self, t, detail):
        d = {"titre": t.name, "nature": _choix(t, "cultiveau_nature"), "urgence": _choix(t, "cultiveau_urgence"), "origine": _choix(t, "cultiveau_origine"),
             "etape": t.stage_id.name or None, "etat": t.state, "client": _ref(t.partner_id), "installation": _ref(t.cultiveau_installation_id),
             "techniciens": [_ref(u) for u in t.user_ids], "echeance": _date(t.date_deadline), "adherent": _ref(t.company_id),
             "symptome": t.cultiveau_symptome or None, "cree_le": _date(t.create_date), "reference_appel": t.cultiveau_reference_appel or None}
        if detail:
            d.update({"description": html2plaintext(t.description or "") or None,
                      "releves": t.cultiveau_releves or None, "references_pv": t.cultiveau_reference_pressions or None,
                      "pieces": [{"article": _ref(x.product_id), "quantite": x.quantite, "precision": x.note or None} for x in t.cultiveau_piece_ids],
                      "devis": _ref(t.cultiveau_sale_order_id)})
        return d

    def _s_chantiers(self, c, detail):
        d = {"numero": c.name, "titre": c.titre, "etat": _choix(c, "etat"), "client": _ref(c.partner_id), "installation": _ref(c.installation_id),
             "commande": _ref(c.sale_order_id), "adherent": _ref(c.company_id), "chef": _ref(c.chef_id), "equipe": [_ref(u) for u in c.equipe_ids],
             "debut_prevu": _date(c.date_debut), "fin_prevue": _date(c.date_fin), "demarre_le": _date(c.date_debut_reel), "termine_le": _date(c.date_fin_reel),
             "avancement": c.avancement, "mis_en_service_le": _date(c.mise_en_service_le)}
        if detail:
            d.update({"materiel": [{"article": _ref(l.product_id), "prevu": l.quantite_prevue, "pose": l.quantite_posee, "unite": l.uom_id.name, "manque": l.manque,
                                    "precision": l.note or None} for l in c.ligne_ids],
                      "bon_de_sortie": _ref(c.picking_id), "acces": c.acces or None, "preparation": c.notes or None, "machines": c.machines or None,
                      "reserves": c.reserves or None,
                      "pv": {"date": _date(c.pv_date), "intervenant": c.pv_intervenant or None, "rincage": c.pv_rincage, "essai_pression_bar": c.pv_essai_pression_bar,
                             "pression_sortie_pompe_bar": c.pv_pression_sortie_pompe_bar, "pression_point_defavorable_bar": c.pv_pression_point_defavorable_bar,
                             "uniformite_pct": c.pv_uniformite_pct, "kwh_m3": c.pv_kwh_m3, "securites_testees": c.pv_securites_testees, "antiretour": c.pv_antiretour,
                             "signe_par": c.pv_signe_par or None, "signe_le": _date(c.pv_signe_le)}})
        return d

    def _s_installations(self, i, detail):
        d = {"nom": i.name, "client": _ref(i.partner_id), "type": _choix(i, "type_systeme"), "etat": _choix(i, "etat"), "surface_ha": i.surface_ha,
             "commune": i.commune or None, "adherent": _ref(i.company_id)}
        if detail:
            d.update({"pv": {"date": _date(i.pv_date), "pression_sortie_pompe_bar": i.pv_pression_sortie_pompe_bar,
                             "pression_point_defavorable_bar": i.pv_pression_point_defavorable_bar, "uniformite_pct": i.pv_uniformite_pct, "kwh_m3": i.pv_kwh_m3},
                      "equipements": [{"id": e.id, "nom": e.display_name} for e in i.equipement_ids] if "equipement_ids" in i._fields else [],
                      "registre": [{"id": l.id, "date": _date(l.date), "genre": _choix(l, "genre"), "description": l.description} for l in i.registre_ids[:30]]
                      if "registre_ids" in i._fields else []})
        return d

    def _s_registre(self, l, detail):
        return {"date": _date(l.date), "installation": _ref(l.installation_id), "genre": _choix(l, "genre"), "description": l.description or None,
                "releves": l.releves or None, "intervenant": l.intervenant or None}

    def _s_commandes(self, o, detail):
        d = {"numero": o.name, "client": _ref(o.partner_id), "etat": o.state, "date": _date(o.date_order), "montant_ht": o.amount_untaxed,
             "montant_ttc": o.amount_total, "adherent": _ref(o.company_id), "commercial": _ref(o.user_id),
             "installation": _ref(o.cultiveau_installation_id) if "cultiveau_installation_id" in o._fields else None, "origine": o.origin or None}
        if detail:
            d["lignes"] = [{"article": _ref(l.product_id), "description": l.name, "quantite": l.product_uom_qty, "prix_unitaire_ht": l.price_unit,
                            "remise_pct": l.discount, "total_ht": l.price_subtotal} for l in o.order_line if not l.display_type]
        return d

    _s_devis = _s_commandes

    def _s_factures(self, m, detail):
        d = {"numero": m.name, "type": "avoir" if m.move_type == "out_refund" else "facture", "client": _ref(m.partner_id), "date": _date(m.invoice_date),
             "echeance": _date(m.invoice_date_due), "etat": m.state, "paiement": m.payment_state, "montant_ht": m.amount_untaxed, "montant_ttc": m.amount_total,
             "reste_du": m.amount_residual, "adherent": _ref(m.company_id)}
        if detail:
            d["lignes"] = [{"article": _ref(l.product_id), "description": l.name, "quantite": l.quantity, "prix_unitaire_ht": l.price_unit, "total_ht": l.price_subtotal}
                           for l in m.invoice_line_ids if not l.display_type]
        return d

    def _s_opportunites(self, l, detail):
        d = {"titre": l.name, "client": _ref(l.partner_id), "contact": l.contact_name or None, "email": l.email_from or None, "telephone": l.phone or None,
             "etape": l.stage_id.name or None, "montant_espere": l.expected_revenue, "probabilite": l.probability, "commercial": _ref(l.user_id),
             "origine": _choix(l, "cultiveau_origine") if "cultiveau_origine" in l._fields else None,
             "urgence": _choix(l, "cultiveau_urgence") if "cultiveau_urgence" in l._fields else None, "adherent": _ref(l.company_id), "cree_le": _date(l.create_date)}
        if detail:
            d["description"] = html2plaintext(l.description or "") or None
        return d

    def _s_articles(self, p, detail):
        d = {"reference": p.default_code or None, "nom": p.name, "code_barres": p.barcode or None, "famille": p.categ_id.complete_name, "prix_vente_ht": p.list_price,
             "unite": p.uom_id.name, "stock": p.qty_available if p.is_storable else None, "catalogue_cultiveau": bool(p.cultiveau_reseau) if "cultiveau_reseau" in p._fields else None,
             "fiche_technique": _ref(p.cultiveau_fiche_id) if "cultiveau_fiche_id" in p._fields else None}
        if detail:
            for champ, nom in (("cultiveau_dn", "dn"), ("cultiveau_pn", "pn_bar"), ("cultiveau_matiere", "matiere"), ("cultiveau_raccordement", "raccordement"),
                               ("cultiveau_conditionnement", "conditionnement"), ("cultiveau_caracteristiques", "caracteristiques")):
                if champ in p._fields:
                    d[nom] = p[champ] or None
            d["fournisseurs"] = [{"fournisseur": _ref(s.partner_id), "reference": s.product_code or None, "prix_achat": s.price, "delai_jours": s.delay} for s in p.seller_ids]
            d["description"] = p.description_sale or None
        return d

    def _s_fiches(self, f, detail):
        return {"titre": f.name, "type": _choix(f, "type_doc"), "fournisseur": f.fournisseur_nom or None, "famille": f.famille or None,
                "sous_famille": f.sous_famille or None, "lien": f.url or None, "articles": f.nb_produits}

    def _s_adherents(self, c, detail):
        return {"nom": c.name, "commune": c.city or None, "code_postal": c.zip or None, "telephone": c.phone or None, "email": c.email or None,
                "siret": c.company_registry or None, "tva": c.vat or None, "site": c.website or None,
                "numero_dedie": c.cultiveau_numero_dedie or None if "cultiveau_numero_dedie" in c._fields else None}

    # ---------------------------------------------------------------- écrire

    @api.model
    def creer(self, ressource, donnees, cle=None):
        self._verifier_ecriture(cle)
        if not self._reglages(ressource).get("ecriture"):
            raise UserError(f"On ne crée pas de {ressource} par l'API.")
        donnees = dict(donnees or {})
        env = self._env(cle)
        societe = self._societe_pour(donnees, cle)
        if ressource == "clients":
            return self._creer_client(env, societe, donnees)
        partner = self._client_de(env, societe, donnees)
        if ressource == "interventions":
            t = env["project.task"].cultiveau_creer_depuis_appel(societe, partner, {
                "resume": donnees.get("titre") or donnees.get("resume"), "symptome": donnees.get("symptome"), "urgence": donnees.get("urgence"),
                "transcription": donnees.get("description"), "reference": donnees.get("reference")})
            nature = donnees.get("nature")
            valeurs = {"cultiveau_origine": self._origine(t, donnees)}
            if nature in dict(t._fields["cultiveau_nature"].selection):
                valeurs["cultiveau_nature"] = nature
            if donnees.get("installation_id"):
                valeurs["cultiveau_installation_id"] = int(donnees["installation_id"])
            t.write(valeurs)
            return self.lire("interventions", t.id, cle)
        if ressource == "opportunites":
            lead = env["crm.lead"].with_company(societe).create({
                "name": (donnees.get("titre") or donnees.get("resume") or "Demande")[:200], "type": "opportunity", "partner_id": partner.id, "company_id": societe.id,
                "description": donnees.get("description") or "", "expected_revenue": float(donnees.get("montant_espere") or 0),
                "cultiveau_origine": self._origine(env["crm.lead"], donnees),
                "cultiveau_surface_ha": float(donnees.get("surface_ha") or 0)})
            return self.lire("opportunites", lead.id, cle)
        raise UserError(f"On ne crée pas de {ressource} par l'API.")

    @api.model
    def noter(self, ressource, ident, texte, cle=None, auteur=None):
        """Une note sur la fiche (chatter), visible de l'équipe."""
        self._verifier_ecriture(cle)
        if not (texte or "").strip():
            raise UserError("La note est vide.")
        reglages = self._reglages(ressource)
        env = self._env(cle)
        Modele = env[reglages["modele"]]
        rec = Modele.search(list(reglages["domaine"]) + self._domaine_societe(reglages, Modele, cle) + [("id", "=", int(ident))], limit=1)
        if not rec or not hasattr(rec, "message_post"):
            raise UserError(f"{ressource} n°{ident} introuvable.")
        signature = auteur or (cle.name if cle else "API")
        message = rec.message_post(body=f"{texte.strip()}\n\n— {signature}", subtype_xmlid="mail.mt_note")
        return {"ok": True, "message_id": message.id}

    def _origine(self, modele, donnees):
        selection = dict(modele._fields["cultiveau_origine"].selection) if "cultiveau_origine" in modele._fields else {}
        origine = donnees.get("origine") or "autre"
        return origine if origine in selection else "autre"

    def _societe_pour(self, donnees, cle):
        societes = self._societes(cle)
        if donnees.get("adherent_id"):
            s = societes.filtered(lambda c: c.id == int(donnees["adherent_id"]))
            if not s:
                raise AccessError("Cet adhérent n'est pas accessible avec cette clé.")
            return s
        return societes[:1] if cle and cle.company_ids else self.env["res.company"].sudo().browse(1).exists() or societes[:1]

    def _client_de(self, env, societe, donnees):
        if donnees.get("client_id"):
            p = env["res.partner"].browse(int(donnees["client_id"])).exists()
            if not p or (p.company_id and p.company_id != societe):
                raise UserError("Client introuvable chez cet adhérent.")
            return p
        client = donnees.get("client") or {}
        if not client:
            raise UserError("Donnez client_id, ou client : {nom, telephone, email…}.")
        return env["res.partner"].browse(self._creer_client(env, societe, client)["id"])

    def _creer_client(self, env, societe, donnees):
        Partner = env["res.partner"].with_company(societe).with_context(mail_create_nolog=True, tracking_disable=True)
        telephone = donnees.get("telephone") or donnees.get("mobile")
        existant = Partner.browse()
        if telephone and hasattr(Partner, "cultiveau_par_telephone"):
            existant = Partner.cultiveau_par_telephone(telephone, societe)
        if not existant and donnees.get("email"):
            existant = Partner.search([("email", "=ilike", donnees["email"]), ("company_id", "in", (societe.id, False))], limit=1)
        valeurs = {k: v for k, v in {
            "name": donnees.get("nom"), "exploitation": donnees.get("exploitation"), "email": donnees.get("email"), "mobile": telephone,
            "street": donnees.get("rue"), "zip": donnees.get("code_postal"), "city": donnees.get("commune"), "comment": donnees.get("notes"),
        }.items() if v}
        if existant:
            existant.write({k: v for k, v in valeurs.items() if not existant[k]})
            return {**self._serialiser("clients", existant, detail=False), "cree": False}
        if not valeurs.get("name"):
            raise UserError("client : le nom est requis.")
        p = Partner.create({**valeurs, "cultiveau_type": "agriculteur", "company_id": societe.id})
        return {**self._serialiser("clients", p, detail=False), "cree": True}
