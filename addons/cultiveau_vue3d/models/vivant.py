"""Les données vivantes de la map : qui est où, les camions, les dossiers, le stock, les parcelles, les KPI, les tableaux, les fiches.

Tout est calculé pour la société courante (l'adhérent), depuis les mêmes tables que le back-office : jamais deux calculs
différents pour le même chiffre. Les positions sont des « places » du plan ; le moteur 3D y pose les objets.
"""
import random
from datetime import datetime, timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

from .secteur import PORTES, ROLES_GROUPES, SECTEUR

CLOTURES = ("1_done", "1_canceled")
ATELIER = ("depannage", "entretien", "remise_en_service", "hivernage", "diagnostic", "autre")
TYPES_CHAMP = {"pivot": "pivot", "enrouleur": "enrouleur", "couverture_integrale": "aspersion", "couverture_partielle": "aspersion",
               "goutte_surface": "goutte", "goutte_enterre": "goutte", "micro_aspersion": "goutte", "mixte": "aspersion"}


def _initiales(nom):
    morceaux = [m for m in (nom or "").replace("-", " ").split() if m]
    return "".join(m[0].upper() for m in morceaux[:2]) or "?"


class Map(models.AbstractModel):
    _name = "cultiveau.map"
    _description = "Map vivante (données)"

    # ---------------------------------------------------------------- tout d'un coup

    @api.model
    def vivant(self):
        company = self.env.company
        maintenant = fields.Datetime.now()
        local = fields.Datetime.context_timestamp(self.with_context(tz=company.partner_id.tz or "Europe/Paris"), maintenant)
        personnes = self._personnes(company, local)
        taches = self._interventions(company, local)
        dossiers = self._dossiers(company)
        chantiers = self._chantiers(company)
        stock = self._stock(company)
        plan = self.env["cultiveau.plan"].courant(company)
        return {
            "societe": {"id": company.id, "nom": company.name, "accent": self._accent(company), "demo": bool(company.cultiveau_map_demo),
                        "adherent": company.cultiveau_adherent, "logo": bool(company.logo)},
            "utilisateur": {"id": self.env.user.id, "nom": self.env.user.name, "role": self._role(self.env.user),
                            "editeur": self.env.user.has_group("base.group_system") or self.env.user.has_group("sales_team.group_sale_manager"),
                            "rh": self.env.user.has_group("sales_team.group_sale_manager")},
            "heure": local.strftime("%H:%M"), "date": self._date_fr(local),
            "secteur": SECTEUR, "plan": plan.layout, "plan_version": plan.version,
            "personnes": personnes, "vehicules": self._vehicules(company, personnes, taches), "clients": self._clients_presents(company, local),
            "interventions": taches, "dossiers": dossiers, "chantiers": chantiers, "stock": stock, "parcelles": self._parcelles(company, dossiers),
            "atelier": self._atelier(company, taches), "livraisons": self._livraisons(company, local),
            "kpi": self._kpi(company, taches, chantiers, local), "onglets": self._onglets(personnes, taches, dossiers, chantiers, stock, self._clients_recents(company)),
            "evenements": self.env["cultiveau.evenement"].recents(company, 20), "actions": sorted(self.env["cultiveau.scene"]._actions_disponibles()), "portes": self._portes(),
            "canal": self.env["cultiveau.evenement"].canal(company),
            "assistant": self._assistant(company),
        }

    def _assistant(self, company):
        """Mathis, s'il est installé : son prénom, ses derniers appels pour la société."""
        if "cultiveau.mathis" not in self.env:
            return None
        prenom = self.env["cultiveau.mathis"].prenom()
        appels = []
        if "cultiveau.appel" in self.env:
            for a in self.env["cultiveau.appel"].sudo().search([("company_id", "=", company.id)], order="date desc", limit=5):
                appels.append({"id": a.id, "sujet": a.sujet, "client": a.partner_id.name or a.numero or "", "date": fields.Datetime.to_string(a.date), "urgence": a.urgence or ""})
        return {"prenom": prenom, "pret": self.env["cultiveau.mathis"].pret(), "appels": appels}

    @api.model
    def _date_fr(self, d):
        jours = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
        mois = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
        return f"{jours[d.weekday()]} {d.day} {mois[d.month - 1]}"

    # ---------------------------------------------------------------- l'équipe

    @api.model
    def _role(self, user):
        for role, groupe in ROLES_GROUPES:
            if user.has_group(groupe):
                return role
        return "commercial"

    @api.model
    def _accent(self, company):
        for champ in ("cultiveau_couleur", "primary_color"):
            if champ in company._fields and company[champ]:
                return company[champ]
        return SECTEUR["accent_defaut"]

    def _utilisateurs(self, company):
        return self.env["res.users"].sudo().search([("share", "=", False), ("active", "=", True), ("company_ids", "in", company.id),
                                                    ("id", "!=", self.env.ref("base.user_root").id)], order="name", limit=40)

    def _personnes(self, company, local):
        Pointage = self.env["cultiveau.pointage"]
        users = self._utilisateurs(company)
        pointages = Pointage.du_jour(company, users)
        par_user = {}
        for p in pointages:
            par_user.setdefault(p.user_id.id, []).append(p)
        Task = self.env["project.task"].sudo()
        debut_jour = local.replace(hour=0, minute=0, second=0, microsecond=0)
        maintenant = fields.Datetime.now()
        en_cours = Task.search([("company_id", "=", company.id), ("cultiveau_intervention", "=", True), ("state", "not in", CLOTURES),
                                ("cultiveau_debut", "!=", False), ("cultiveau_debut", "<=", maintenant),
                                ("cultiveau_debut", ">=", fields.Datetime.to_string(debut_jour.astimezone(datetime.now().astimezone().tzinfo).replace(tzinfo=None)))]) \
            if "cultiveau_debut" in Task._fields else Task.browse()
        chantiers = self.env["cultiveau.chantier"].sudo().search([("company_id", "=", company.id), ("etat", "=", "en_cours")]) if "cultiveau.chantier" in self.env else []
        roles = {r["cle"]: r for r in SECTEUR["roles"]}
        statuts = SECTEUR["statuts"]
        compte_postes = {}
        resultat = []
        for u in users:
            role = self._role(u)
            statut, depuis, arrivee = Pointage.statut_depuis_pointages(par_user.get(u.id, []))
            tache = next((t for t in en_cours if u in t.user_ids), None)
            chantier = next((c for c in chantiers if u in c.equipe_ids or u == c.chef_id), None)
            if not statut:
                if tache and tache.cultiveau_debut and (not tache.cultiveau_fin or tache.cultiveau_fin >= maintenant):
                    statut, depuis = "en_intervention", tache.cultiveau_debut
                elif chantier:
                    statut, depuis = "sur_chantier", fields.Datetime.to_datetime(chantier.date_debut_reel or chantier.date_debut) if (chantier.date_debut_reel or chantier.date_debut) else None
                elif u.im_status in ("online", "away"):
                    statut = "au_poste"
                else:
                    statut = "pas_arrive" if local.hour < 12 else "absent"
            if not arrivee and statut in ("au_poste", "en_pause", "en_reunion", "en_intervention", "sur_chantier") and u.login_date and u.login_date.date() == maintenant.date():
                arrivee = u.login_date
            zone = roles.get(role, roles["commercial"])["zone"]
            compte_postes[zone] = compte_postes.get(zone, 0) + 1
            resultat.append({
                "id": u.id, "nom": u.name, "initiales": _initiales(u.name), "role": role, "role_nom": roles.get(role, roles["commercial"])["nom"],
                "zone": zone, "rang": compte_postes[zone], "statut": statut, "statut_nom": statuts[statut]["nom"], "couleur": statuts[statut]["couleur"],
                "depuis": fields.Datetime.to_string(depuis) if depuis else "", "arrivee": fields.Datetime.to_string(arrivee) if arrivee else "",
                "en_ligne": u.im_status == "online", "telephone": u.partner_id.mobile or u.partner_id.phone or "", "courriel": u.email or "",
                "tache": tache and {"id": tache.id, "nom": tache.name, "client": tache.partner_id.name or "", "installation": tache.cultiveau_installation_id.id} or None,
                "chantier": chantier and {"id": chantier.id, "nom": chantier.display_name, "client": chantier.partner_id.name or "", "installation": chantier.installation_id.id} or None,
                "camion": u.id if role == "technicien" else 0, "tenue": roles.get(role, roles["commercial"])["tenue"],
                "moi": u.id == self.env.user.id,
            })
        return resultat

    # ---------------------------------------------------------------- les camions et les voitures

    def _vehicules(self, company, personnes, taches):
        User = self.env["res.users"].sudo()
        resultat = []
        rang = 0
        for p in personnes:
            if p["role"] != "technicien":
                continue
            rang += 1
            u = User.browse(p["id"])
            emplacement = u.cultiveau_camion_id if "cultiveau_camion_id" in User._fields else None
            a_bord = manques = 0
            if emplacement:
                quants = self.env["stock.quant"].sudo().search([("location_id", "child_of", emplacement.id), ("quantity", ">", 0)])
                a_bord = len(quants)
                if "cultiveau_dotation_ids" in User._fields:
                    for d in u.cultiveau_dotation_ids:
                        if sum(quants.filtered(lambda q: q.product_id == d.product_id).mapped("quantity")) < d.quantite:
                            manques += 1
            parti = p["statut"] in ("en_intervention", "sur_chantier", "en_route")
            resultat.append({"id": p["id"], "nom": emplacement.name if emplacement else f"Camion {p['nom']}", "conducteur": p["nom"], "conducteur_id": p["id"],
                             "place": f"camion-{rang}", "parti": parti, "destination": (p["tache"] or p["chantier"] or {}).get("client", ""),
                             "installation": (p["tache"] or p["chantier"] or {}).get("installation") or 0,
                             "a_bord": a_bord, "manques": manques, "emplacement_id": emplacement.id if emplacement else 0})
        return resultat

    def _clients_presents(self, company, local):
        """Les clients « sur place » : une voiture par devis ou vente du jour au comptoir (et par rendez-vous du jour)."""
        Order = self.env["sale.order"].sudo()
        debut = local.replace(hour=0, minute=0, second=0, microsecond=0)
        debut_utc = fields.Datetime.to_string(debut.astimezone(datetime.now().astimezone().tzinfo).replace(tzinfo=None))
        commandes = Order.search([("company_id", "=", company.id), ("create_date", ">=", debut_utc), ("state", "in", ("draft", "sent", "sale"))], order="create_date desc", limit=5)
        resultat, vus = [], set()
        for c in commandes:
            if c.partner_id.id in vus:
                continue
            vus.add(c.partner_id.id)
            resultat.append({"id": c.partner_id.id, "nom": c.partner_id.name, "type": c.partner_id.cultiveau_type or "autre" if "cultiveau_type" in c.partner_id._fields else "autre",
                             "place": f"parking-{len(resultat) + 1}", "devis": {"id": c.id, "nom": c.name, "montant": round(c.amount_untaxed), "etat": c.state},
                             "depuis": fields.Datetime.to_string(c.create_date), "comptoir": c.origin == "Comptoir"})
        return resultat

    # ---------------------------------------------------------------- les interventions, les dossiers, les chantiers

    def _interventions(self, company, local):
        Task = self.env["project.task"].sudo()
        natures = dict(Task._fields["cultiveau_nature"].selection)
        urgences = dict(Task._fields["cultiveau_urgence"].selection)
        debut = local.replace(hour=0, minute=0, second=0, microsecond=0)
        fin = debut + timedelta(days=1)
        conv = lambda d: fields.Datetime.to_string(d.astimezone(datetime.now().astimezone().tzinfo).replace(tzinfo=None))  # noqa: E731
        domaine = [("company_id", "=", company.id), ("cultiveau_intervention", "=", True)]
        if "cultiveau_debut" in Task._fields:
            du_jour = Task.search(domaine + ["|", "&", ("cultiveau_debut", ">=", conv(debut)), ("cultiveau_debut", "<", conv(fin)),
                                             "&", ("state", "not in", CLOTURES), ("date_deadline", "<", conv(fin))], order="cultiveau_debut asc, priority desc", limit=30)
        else:
            du_jour = Task.search(domaine + [("state", "not in", CLOTURES)], order="date_deadline asc", limit=30)
        maintenant = fields.Datetime.now()
        resultat = []
        for t in du_jour:
            debut_t = t.cultiveau_debut if "cultiveau_debut" in Task._fields else None
            etat = "faite" if t.state in CLOTURES else ("en_cours" if debut_t and debut_t <= maintenant else "a_faire")
            resultat.append({"id": t.id, "nom": t.name, "client": t.partner_id.name or "", "client_id": t.partner_id.id, "technicien": t.user_ids[:1].name or "",
                             "technicien_id": t.user_ids[:1].id, "nature": t.cultiveau_nature or "autre", "nature_nom": natures.get(t.cultiveau_nature, ""),
                             "urgence": t.cultiveau_urgence or "semaine", "urgence_nom": urgences.get(t.cultiveau_urgence, ""), "etat": etat,
                             "debut": fields.Datetime.to_string(debut_t) if debut_t else "", "installation": t.cultiveau_installation_id.id,
                             "installation_nom": t.cultiveau_installation_id.name or "", "equipement": t.cultiveau_equipement_id.name or "",
                             "atelier": t.cultiveau_nature in ATELIER and not t.cultiveau_installation_id})
        return resultat

    def _etape(self, installation, devis, mise_en_service):
        """L'étape du dossier (index dans SECTEUR) et les étapes franchies, d'après l'état de l'installation et ses pièces."""
        etapes = SECTEUR["dossier"]["etapes"]
        etat = installation.etat
        if etat in ("en_service", "arretee"):
            courante = 5
        elif etat == "realisation":
            courante = 3
        elif etat == "etude":
            courante = 2 if devis else 1
        else:
            courante = 0
        if etat == "realisation" and mise_en_service:
            courante = 4
        return courante, [{"cle": e["cle"], "nom": e["nom"], "etat": "faite" if i < courante else ("en_cours" if i == courante else "a_venir")} for i, e in enumerate(etapes)]

    def _dossiers(self, company):
        Inst = self.env["cultiveau.installation"].sudo()
        Order = self.env["sale.order"].sudo()
        inst = Inst.search([("company_id", "=", company.id), ("etat", "in", ("projet", "etude", "realisation"))], order="write_date desc", limit=12)
        types = dict(Inst._fields["type_systeme"].selection)
        etats = dict(Inst._fields["etat"].selection)
        resultat = []
        for i in inst:
            devis = Order.search([("cultiveau_installation_id", "=", i.id)], order="date_order desc", limit=1) if "cultiveau_installation_id" in Order._fields else Order.browse()
            mes = bool(i.pv_date) if "pv_date" in Inst._fields else False
            courante, etapes = self._etape(i, devis, mes)
            resultat.append({"id": i.id, "nom": i.name, "client": i.partner_id.name, "client_id": i.partner_id.id, "type": i.type_systeme, "type_nom": types.get(i.type_systeme, ""),
                             "champ": TYPES_CHAMP.get(i.type_systeme, "aspersion"), "etat": i.etat, "etat_nom": etats.get(i.etat, ""), "etape": courante, "etapes": etapes,
                             "avancement": round(100 * (courante + 0.5) / len(etapes)), "surface": i.surface_ha, "commune": i.commune or "",
                             "devis": devis and {"id": devis.id, "nom": devis.name, "montant": round(devis.amount_total), "etat": devis.state} or None,
                             "responsable": i.user_id.name or "", "responsable_id": i.user_id.id, "echeance": fields.Date.to_string(i.analyse_validee_le) if i.analyse_validee_le else ""})
        return resultat

    def _chantiers(self, company):
        if "cultiveau.chantier" not in self.env:
            return []
        Ch = self.env["cultiveau.chantier"].sudo()
        chantiers = Ch.search([("company_id", "=", company.id), ("etat", "in", ("planifie", "en_cours"))], order="etat desc, date_debut asc", limit=8)
        etats = dict(Ch._fields["etat"].selection)
        return [{"id": c.id, "nom": c.display_name, "titre": c.titre, "client": c.partner_id.name or "", "client_id": c.partner_id.id, "etat": c.etat, "etat_nom": etats.get(c.etat, ""),
                 "avancement": c.avancement, "chef": c.chef_id.name or "", "equipe": c.equipe_ids.mapped("name"), "equipe_ids": c.equipe_ids.ids + c.chef_id.ids,
                 "installation": c.installation_id.id, "installation_nom": c.installation_id.name, "champ": TYPES_CHAMP.get(c.installation_id.type_systeme, "aspersion"),
                 "debut": fields.Date.to_string(c.date_debut) if c.date_debut else "", "fin": fields.Date.to_string(c.date_fin) if c.date_fin else "",
                 "materiel": len(c.ligne_ids), "pose": sum(c.ligne_ids.mapped("quantite_posee")), "prevu": sum(c.ligne_ids.mapped("quantite_prevue"))} for c in chantiers]

    # ---------------------------------------------------------------- le stock, l'atelier, les parcelles, les livraisons

    def _stock(self, company):
        familles = self.env["cultiveau.scene"]._familles(company)
        Orderpoint = self.env["stock.warehouse.orderpoint"].sudo()
        bas = {}
        for op in Orderpoint.search([("company_id", "=", company.id)], limit=300):
            if op.qty_forecast < 0:
                ids = [int(i) for i in (op.product_id.categ_id.parent_path or "").split("/") if i]
                if ids:
                    bas[ids[0]] = bas.get(ids[0], 0) + 1
        resultat = []
        for i, f in enumerate(familles[:6]):
            resultat.append({**f, "place": f"rayon-{i + 1}", "bas": bas.get(f["id"], 0), "taux": min(1.0, f["stock"] / 400.0) if f["stock"] else 0.0})
        return resultat

    def _atelier(self, company, taches):
        """Ce qui est sur les établis : les interventions d'atelier (dépannage, diagnostic sans installation) et les équipements."""
        resultat = []
        for i, t in enumerate([t for t in taches if t["atelier"]][:3]):
            resultat.append({**t, "place": f"etabli-{i + 1}", "objet": "pompe"})
        return resultat

    def _parcelles(self, company, dossiers):
        Inst = self.env["cultiveau.installation"].sudo()
        inst = Inst.search([("company_id", "=", company.id), ("etat", "in", ("en_service", "arretee"))], order="surface_ha desc", limit=4)
        types = dict(Inst._fields["type_systeme"].selection)
        resultat = []
        Parcelle = self.env["cultiveau.parcelle"].sudo() if "cultiveau.parcelle" in self.env else None
        for i in inst:
            eau = None
            if Parcelle is not None and "installation_id" in Parcelle._fields:
                p = Parcelle.search([("installation_id", "=", i.id)], limit=1)
                if p and "etat_eau" in p._fields:
                    eau = {"etat": p.etat_eau, "deficit": p.deficit_mm, "dose": p.dose_mm, "conseil": p.conseil or "", "parcelle_id": p.id}
            resultat.append({"id": i.id, "nom": i.name, "client": i.partner_id.name, "client_id": i.partner_id.id, "type": i.type_systeme, "type_nom": types.get(i.type_systeme, ""),
                             "champ": TYPES_CHAMP.get(i.type_systeme, "aspersion"), "etat": i.etat, "surface": i.surface_ha, "commune": i.commune or "", "eau": eau,
                             "arrose": i.etat == "en_service" and fields.Date.context_today(self).month in (5, 6, 7, 8, 9),
                             "echeance": self.env["cultiveau.scene"]._echeance(i, fields.Date.context_today(self).month)})
        # les places des champs : d'abord les chantiers et dossiers en réalisation, puis les parcelles en service
        return resultat

    def _livraisons(self, company, local):
        Picking = self.env["stock.picking"].sudo()
        debut = local.replace(hour=0, minute=0, second=0, microsecond=0)
        conv = lambda d: fields.Datetime.to_string(d.astimezone(datetime.now().astimezone().tzinfo).replace(tzinfo=None))  # noqa: E731
        entrantes = Picking.search([("company_id", "=", company.id), ("picking_type_code", "=", "incoming"), ("state", "in", ("assigned", "done")),
                                    ("scheduled_date", ">=", conv(debut - timedelta(days=1))), ("scheduled_date", "<", conv(debut + timedelta(days=1)))], order="scheduled_date", limit=3)
        return [{"id": p.id, "nom": p.name, "fournisseur": p.partner_id.name or "Fournisseur", "etat": p.state, "lignes": len(p.move_ids), "place": "livraison",
                 "recue": p.state == "done"} for p in entrantes]

    # ---------------------------------------------------------------- les KPI et les onglets

    def _kpi(self, company, taches, chantiers, local):
        Order = self.env["sale.order"].sudo()
        devis = Order.search([("company_id", "=", company.id), ("state", "in", ("draft", "sent"))])
        il_y_a_7j = fields.Datetime.now() - timedelta(days=7)
        relancer = len(devis.filtered(lambda d: d.state == "sent" and d.write_date < il_y_a_7j))
        faites = len([t for t in taches if t["etat"] == "faite"])
        heures = 0.0
        if "cultiveau.chantier.pointage" in self.env:
            P = self.env["cultiveau.chantier.pointage"].sudo()
            lundi = fields.Date.context_today(self) - timedelta(days=fields.Date.context_today(self).weekday())
            if "heures" in P._fields and "date" in P._fields:
                heures = sum(P.search([("chantier_id.company_id", "=", company.id), ("date", ">=", lundi)]).mapped("heures"))
        return [
            {"cle": "interventions", "nom": "Interventions du jour", "valeur": len(taches), "unite": "", "sous_titre": f"{faites} faite(s) · {len(taches) - faites} à faire",
             "action": "interventions"},
            {"cle": "devis", "nom": "Devis en attente", "valeur": round(sum(devis.mapped("amount_untaxed"))), "unite": "€", "sous_titre": f"{len(devis)} devis · {relancer} à relancer",
             "action": "devis"},
            {"cle": "chantiers", "nom": "Chantiers en cours", "valeur": len([c for c in chantiers if c["etat"] == "en_cours"]), "unite": "",
             "sous_titre": f"{len(chantiers)} planifié(s) · {heures:.0f} h pointées cette semaine", "action": "chantiers"},
        ]

    def _clients_recents(self, company, limite=40):
        """Les clients de l'adhérent, les derniers touchés d'abord : ceux d'avant la map comme ceux d'aujourd'hui."""
        Partner = self.env["res.partner"].sudo()
        domaine = [("company_id", "in", [company.id, False]), ("parent_id", "=", False)]
        if "cultiveau_est_client" in Partner._fields:
            domaine.append(("cultiveau_est_client", "=", True))
        Inst = self.env["cultiveau.installation"].sudo()
        types = dict(Partner._fields["cultiveau_type"].selection) if "cultiveau_type" in Partner._fields else {}
        resultat = []
        for p in Partner.search(domaine, order="write_date desc", limit=limite):
            n = Inst.search_count([("partner_id", "child_of", p.id), ("company_id", "=", company.id)])
            resultat.append({"id": p.id, "nom": p.name, "commune": p.city or "", "type": types.get(getattr(p, "cultiveau_type", ""), ""), "installations": n,
                             "a_contacter": bool(getattr(p, "cultiveau_a_contacter", False)), "telephone": p.mobile or p.phone or ""})
        return resultat

    def _onglets(self, personnes, taches, dossiers, chantiers, stock, clients=()):
        return {
            "clients": [{"id": c["id"], "code": _initiales(c["nom"]), "nom": c["nom"], "sous": " · ".join(x for x in (c["type"], c["commune"]) if x),
                         "badge": "À contacter" if c["a_contacter"] else (f"{c['installations']} install." if c["installations"] else "Client"),
                         "couleur": "ambre" if c["a_contacter"] else ("accent" if c["installations"] else "ardoise"), "cible": "client"} for c in clients],
            "equipe": [{"id": p["id"], "code": p["initiales"], "nom": p["nom"], "sous": p["role_nom"], "badge": p["statut_nom"], "couleur": p["couleur"],
                        "heure": p["arrivee"], "cible": "personne"} for p in personnes],
            "camions": [{"id": t["technicien_id"] or t["id"], "code": "INT", "nom": t["nom"], "sous": t["client"], "badge": {"a_faire": "À faire", "en_cours": "En cours", "faite": "Faite"}[t["etat"]],
                        "couleur": {"a_faire": "ardoise", "en_cours": "accent", "faite": "vert"}[t["etat"]], "heure": t["debut"], "cible": "intervention", "res_id": t["id"]} for t in taches],
            "dossiers": [{"id": d["id"], "code": d["champ"][:3].upper(), "nom": d["nom"], "sous": d["client"], "badge": d["etapes"][d["etape"]]["nom"], "couleur": "accent",
                          "progression": d["avancement"], "cible": "dossier"} for d in dossiers] +
                        [{"id": c["id"], "code": "CHT", "nom": c["nom"], "sous": c["client"], "badge": c["etat_nom"], "couleur": "accent" if c["etat"] == "en_cours" else "ardoise",
                          "progression": c["avancement"], "cible": "chantier"} for c in chantiers],
            "stock": [{"id": s["id"], "code": f"R{i + 1}", "nom": s["nom"], "sous": f"{s['mien']} article(s)", "badge": f"{s['bas']} en alerte" if s["bas"] else "OK",
                       "couleur": "ambre" if s["bas"] else "vert", "progression": round(100 * s["taux"]), "cible": "rayon"} for i, s in enumerate(stock)],
        }

    def _portes(self):
        """Les écrans que chaque zone ouvre, parmi ceux qui existent dans cet ERP."""
        dispo = self.env["cultiveau.scene"]._actions_disponibles()
        return {zone: [{"cle": cle, "nom": nom, "icone": icone} for cle, nom, icone in portes if cle in dispo] for zone, portes in PORTES.items()}

    # ---------------------------------------------------------------- la recherche

    @api.model
    def chercher(self, q, limite=6):
        """Ce que la map ne tient pas sous la main : tous les clients, tous les articles, toutes les installations de l'adhérent."""
        q = (q or "").strip()
        company = self.env.company
        if len(q) < 2:
            return []
        resultat = []
        Partner = self.env["res.partner"].sudo()
        domaine = [("company_id", "in", [company.id, False]), ("parent_id", "=", False), "|", "|", ("name", "ilike", q), ("city", "ilike", q), ("phone", "ilike", q)]
        if "cultiveau_est_client" in Partner._fields:
            domaine = [("cultiveau_est_client", "=", True)] + domaine
        for p in Partner.search(domaine, limit=limite):
            resultat.append({"groupe": "Clients", "genre": "client", "id": p.id, "nom": p.name, "sous": " · ".join(x for x in (p.city or "", p.mobile or p.phone or "") if x), "icone": "fa-user-o"})
        Produit = self.env["product.template"].sudo().with_company(company)
        dom_p = [("sale_ok", "=", True), ("company_id", "in", [company.id, False]), "|", ("name", "ilike", q), ("default_code", "ilike", q)]
        for a in Produit.search(dom_p, limit=limite, order="company_id desc, name"):
            ids = [int(i) for i in (a.categ_id.parent_path or "").split("/") if i]
            resultat.append({"groupe": "Articles", "genre": "article", "id": a.id, "nom": a.display_name, "sous": f"{a.categ_id.name} · {a.qty_available:g} en stock" if "qty_available" in a._fields else a.categ_id.name,
                             "icone": "fa-cube", "rayon": ids[0] if ids else 0})
        Inst = self.env["cultiveau.installation"].sudo()
        for i in Inst.search([("company_id", "=", company.id), "|", "|", ("name", "ilike", q), ("partner_id.name", "ilike", q), ("commune", "ilike", q)], limit=limite):
            resultat.append({"groupe": "Installations", "genre": "dossier", "id": i.id, "nom": i.name, "sous": f"{i.partner_id.name} · {dict(Inst._fields['etat'].selection).get(i.etat, '')}", "icone": "fa-leaf"})
        Task = self.env["project.task"].sudo()
        for t in Task.search([("company_id", "=", company.id), ("cultiveau_intervention", "=", True), ("state", "not in", CLOTURES), "|", ("name", "ilike", q), ("partner_id.name", "ilike", q)], limit=limite):
            resultat.append({"groupe": "Interventions", "genre": "intervention", "id": t.id, "nom": t.name, "sous": t.partner_id.name or "", "icone": "fa-bolt"})
        return resultat

    # ---------------------------------------------------------------- les fiches

    @api.model
    def fiche(self, genre, res_id, cle=None):
        """La fiche résumée d'un objet de la map (une zone se désigne par sa clé)."""
        company = self.env.company
        methode = getattr(self, f"_fiche_{genre}", None)
        if not methode:
            raise UserError(f"Pas de fiche pour « {genre} ».")
        if genre == "zone":
            return methode(company, 0, cle=cle)
        return methode(company, int(res_id or 0))

    def _fiche_personne(self, company, uid):
        u = self.env["res.users"].sudo().browse(uid)
        local = fields.Datetime.context_timestamp(self.with_context(tz=company.partner_id.tz or "Europe/Paris"), fields.Datetime.now())
        p = next((p for p in self._personnes(company, local) if p["id"] == uid), None)
        if not p:
            raise UserError("Cette personne n'est pas dans l'équipe.")
        pointages = self.env["cultiveau.pointage"].du_jour(company, u)
        Task = self.env["project.task"].sudo()
        agenda = []
        if "cultiveau_debut" in Task._fields:
            debut = local.replace(hour=0, minute=0, second=0, microsecond=0)
            conv = lambda d: fields.Datetime.to_string(d.astimezone(datetime.now().astimezone().tzinfo).replace(tzinfo=None))  # noqa: E731
            for t in Task.search([("user_ids", "in", uid), ("cultiveau_debut", ">=", conv(debut)), ("cultiveau_debut", "<", conv(debut + timedelta(days=1)))], order="cultiveau_debut"):
                agenda.append({"id": t.id, "titre": t.name, "client": t.partner_id.name or "", "debut": fields.Datetime.to_string(t.cultiveau_debut),
                               "fin": fields.Datetime.to_string(t.cultiveau_fin) if t.cultiveau_fin else "", "fait": t.state in CLOTURES})
        presence_min = 0
        if p["arrivee"]:
            presence_min = int((fields.Datetime.now() - fields.Datetime.to_datetime(p["arrivee"])).total_seconds() // 60)
        semaine = []
        lundi = fields.Date.context_today(self) - timedelta(days=fields.Date.context_today(self).weekday())
        Pointage = self.env["cultiveau.pointage"].sudo()
        for j in range(5):
            jour = lundi + timedelta(days=j)
            pts = Pointage.search([("user_id", "=", uid), ("horodatage", ">=", fields.Datetime.to_string(jour)), ("horodatage", "<", fields.Datetime.to_string(jour + timedelta(days=1)))], order="horodatage")
            arr = next((x.horodatage for x in pts if x.genre == "arrivee"), None)
            dep = next((x.horodatage for x in reversed(pts) if x.genre == "depart"), None)
            semaine.append({"jour": jour.strftime("%a"), "heures": round(((dep or (fields.Datetime.now() if jour == fields.Date.context_today(self) else arr)) - arr).total_seconds() / 3600, 1) if arr else 0})
        return {**p, "pointages": [{"genre": x.genre, "nom": dict(x._fields["genre"].selection)[x.genre], "heure": fields.Datetime.to_string(x.horodatage)} for x in pointages[:8]],
                "agenda": agenda, "presence_min": presence_min, "semaine": semaine, "camion_id": u.cultiveau_camion_id.id if "cultiveau_camion_id" in u._fields else 0,
                "actions": [{"cle": "fiche", "nom": "Fiche complète", "modele": "res.users", "id": uid}, {"cle": "interventions_de", "nom": "Ses interventions"},
                            {"cle": "appeler", "nom": "Appeler", "tel": p["telephone"]}] +
                           ([{"cle": "badger", "nom": "Badger sa pause" if p["statut"] == "au_poste" else "Badger son retour", "genre": "pause_debut" if p["statut"] == "au_poste" else "pause_fin"}]
                            if p["moi"] or self.env.user.has_group("sales_team.group_sale_manager") else [])}

    def _fiche_dossier(self, company, iid):
        d = next((d for d in self._dossiers(company) + self._parcelles(company, []) if d["id"] == iid), None)
        i = self.env["cultiveau.installation"].sudo().browse(iid)
        if not i.exists():
            raise UserError("Installation introuvable.")
        Order = self.env["sale.order"].sudo()
        devis = Order.search([("cultiveau_installation_id", "=", iid)], order="date_order desc", limit=3) if "cultiveau_installation_id" in Order._fields else Order.browse()
        taches = self.env["project.task"].sudo().search([("cultiveau_installation_id", "=", iid)], order="date_deadline desc", limit=6)
        equipements = i.equipement_ids[:8] if "equipement_ids" in i._fields else []
        if not d:
            types = dict(i._fields["type_systeme"].selection)
            courante, etapes = self._etape(i, devis[:1], bool(i.pv_date) if "pv_date" in i._fields else False)
            d = {"id": i.id, "nom": i.name, "client": i.partner_id.name, "client_id": i.partner_id.id, "type": i.type_systeme, "type_nom": types.get(i.type_systeme, ""),
                 "etat": i.etat, "etape": courante, "etapes": etapes, "surface": i.surface_ha, "commune": i.commune or "", "responsable": i.user_id.name or ""}
        if "etapes" not in d:
            courante, etapes = self._etape(i, devis[:1], bool(i.pv_date) if "pv_date" in i._fields else False)
            d = {**d, "etape": courante, "etapes": etapes, "avancement": round(100 * (courante + 0.5) / len(etapes))}
        return {**d, "genre": "dossier", "ressource": dict(i._fields["ressource"].selection).get(i.ressource, "") if i.ressource else "",
                "devis": [{"id": o.id, "nom": o.name, "montant": round(o.amount_total), "etat": o.state, "date": fields.Date.to_string(o.date_order.date())} for o in devis],
                "historique": [{"id": t.id, "nom": t.name, "date": fields.Date.to_string(t.date_deadline.date()) if t.date_deadline else "", "fait": t.state in CLOTURES,
                                "technicien": t.user_ids[:1].name or ""} for t in taches],
                "equipements": [{"id": e.id, "nom": e.name, "categorie": e.categorie} for e in equipements],
                "pv": {"date": fields.Date.to_string(i.pv_date) if "pv_date" in i._fields and i.pv_date else "", "intervenant": getattr(i, "pv_intervenant", "") or ""},
                "actions": [{"cle": "fiche", "nom": "Fiche complète", "modele": "cultiveau.installation", "id": iid},
                            {"cle": "client", "nom": "Le client", "modele": "res.partner", "id": i.partner_id.id},
                            {"cle": "notifier", "nom": "Prévenir le client", "modele": "res.partner", "id": i.partner_id.id, "courriel": i.partner_id.email or ""}]}

    def _fiche_chantier(self, company, cid):
        c = self.env["cultiveau.chantier"].sudo().browse(cid)
        if not c.exists():
            raise UserError("Chantier introuvable.")
        d = next((x for x in self._chantiers(company) if x["id"] == cid), None) or {"id": cid, "nom": c.display_name, "client": c.partner_id.name or "", "etat": c.etat, "avancement": c.avancement}
        return {**d, "genre": "chantier", "lignes": [{"nom": l.product_id.display_name, "prevu": l.quantite_prevue, "pose": l.quantite_posee} for l in c.ligne_ids[:10]],
                "reserves": c.reserves or "", "acces": c.acces or "", "pv": {"date": fields.Date.to_string(c.mise_en_service_le) if c.mise_en_service_le else ""},
                "dossier": self._fiche_dossier(company, c.installation_id.id) if c.installation_id else None,
                "actions": [{"cle": "fiche", "nom": "Fiche complète", "modele": "cultiveau.chantier", "id": cid},
                            {"cle": "installation", "nom": "L'installation", "modele": "cultiveau.installation", "id": c.installation_id.id}]}

    def _fiche_intervention(self, company, tid):
        t = self.env["project.task"].sudo().browse(tid)
        if not t.exists():
            raise UserError("Intervention introuvable.")
        local = fields.Datetime.context_timestamp(self.with_context(tz=company.partner_id.tz or "Europe/Paris"), fields.Datetime.now())
        i = next((x for x in self._interventions(company, local) if x["id"] == tid), None)
        natures = dict(t._fields["cultiveau_nature"].selection)
        if not i:
            i = {"id": tid, "nom": t.name, "client": t.partner_id.name or "", "client_id": t.partner_id.id, "technicien": t.user_ids[:1].name or "", "technicien_id": t.user_ids[:1].id,
                 "nature": t.cultiveau_nature, "nature_nom": natures.get(t.cultiveau_nature, ""), "etat": "faite" if t.state in CLOTURES else "a_faire", "installation": t.cultiveau_installation_id.id,
                 "installation_nom": t.cultiveau_installation_id.name or ""}
        bons = []
        if "cultiveau_bon_ids" in t._fields:
            bons = [{"id": b.id, "nom": b.name, "etat": b.etat, "signe": bool(b.signe_le), "montant": round(b.montant_ht)} for b in t.cultiveau_bon_ids]
        pieces = [{"nom": p.product_id.display_name, "quantite": p.quantite} for p in t.cultiveau_piece_ids[:8]] if "cultiveau_piece_ids" in t._fields else []
        return {**i, "genre": "intervention", "description": (t.description and str(t.description)[:400]) or "", "adresse": getattr(t, "cultiveau_adresse", "") or "",
                "bons": bons, "pieces": pieces, "equipement": t.cultiveau_equipement_id.name or "",
                "actions": [{"cle": "fiche", "nom": "Fiche complète", "modele": "project.task", "id": tid},
                            {"cle": "client", "nom": "Le client", "modele": "res.partner", "id": t.partner_id.id}] +
                           ([{"cle": "installation", "nom": "L'installation", "modele": "cultiveau.installation", "id": t.cultiveau_installation_id.id}] if t.cultiveau_installation_id else [])}

    def _fiche_client(self, company, pid):
        p = self.env["res.partner"].sudo().browse(pid)
        if not p.exists():
            raise UserError("Client introuvable.")
        Order = self.env["sale.order"].sudo()
        devis = Order.search([("partner_id", "child_of", pid), ("company_id", "=", company.id)], order="date_order desc", limit=5)
        factures = self.env["account.move"].sudo().search([("partner_id", "child_of", pid), ("company_id", "=", company.id), ("move_type", "=", "out_invoice"), ("state", "=", "posted")])
        inst = self.env["cultiveau.installation"].sudo().search([("partner_id", "child_of", pid), ("company_id", "=", company.id)])
        return {"genre": "client", "id": pid, "nom": p.name, "telephone": p.mobile or p.phone or "", "courriel": p.email or "", "commune": p.city or "",
                "type": getattr(p, "cultiveau_type", "") or "", "ca": round(sum(factures.mapped("amount_untaxed"))), "impayes": round(sum(factures.mapped("amount_residual"))),
                "persona": getattr(p, "cultiveau_persona_id", None) and p.cultiveau_persona_id.name or "",
                "devis": [{"id": o.id, "nom": o.name, "montant": round(o.amount_total), "etat": o.state} for o in devis],
                "installations": [{"id": i.id, "nom": i.name, "etat": i.etat} for i in inst[:6]], "note": (p.comment and str(p.comment)[:300]) or "",
                "actions": [{"cle": "fiche", "nom": "Fiche complète", "modele": "res.partner", "id": pid}, {"cle": "devis_nouveau", "nom": "Nouveau devis", "contexte": {"default_partner_id": pid}},
                            {"cle": "appeler", "nom": "Appeler", "tel": p.mobile or p.phone or ""}]}

    def _fiche_article(self, company, pid):
        a = self.env["product.template"].sudo().with_company(company).browse(pid)
        if not a.exists():
            raise UserError("Article introuvable.")
        ids = [int(i) for i in (a.categ_id.parent_path or "").split("/") if i]
        famille = self.env["product.category"].sudo().browse(ids[0]) if ids else a.categ_id
        fournisseur = a.seller_ids[:1]
        carac = []
        if "cultiveau_caracteristiques" in a._fields and a.cultiveau_caracteristiques:
            libelles = dict(a.cultiveau_famille_carac_id.liste()) if "cultiveau_famille_carac_id" in a._fields and a.cultiveau_famille_carac_id else {}
            for cle, v in list(a.cultiveau_caracteristiques.items())[:8]:
                valeur = v.get("valeur") if isinstance(v, dict) else v
                if valeur not in (None, ""):
                    carac.append({"nom": libelles.get(cle, cle.replace("_", " ")), "valeur": str(valeur)})
        return {"genre": "article", "id": pid, "nom": a.name, "code": a.default_code or "", "famille": famille.name, "famille_id": famille.id, "categorie": a.categ_id.name,
                "stock": a.qty_available if "qty_available" in a._fields else 0.0, "prix_vente": a.list_price, "prix_achat": fournisseur.price if fournisseur else a.standard_price,
                "fournisseur": fournisseur.partner_id.name if fournisseur else "", "dn": getattr(a, "cultiveau_dn", 0) or 0, "pn": getattr(a, "cultiveau_pn", 0) or 0,
                "matiere": getattr(a, "cultiveau_matiere", "") or "", "reseau": bool(getattr(a, "cultiveau_reseau", False)), "mien": bool(getattr(a, "cultiveau_mon_catalogue", False)),
                "fiche_technique": bool(getattr(a, "cultiveau_fiche_id", False) and a.cultiveau_fiche_id.fichier), "fiche_id": a.cultiveau_fiche_id.id if getattr(a, "cultiveau_fiche_id", False) else 0,
                "caracteristiques": carac,
                "actions": [{"cle": "fiche", "nom": "Fiche complète", "modele": "product.template", "id": pid}, {"cle": "famille_stock", "nom": "Le rayon en stock", "parametre": famille.id}] +
                           ([{"cle": "fiche_technique", "nom": "Fiche technique (PDF)", "url": f"/web/content/cultiveau.fiche/{a.cultiveau_fiche_id.id}/fichier?download=false"}] if getattr(a, "cultiveau_fiche_id", False) and a.cultiveau_fiche_id.fichier else [])}

    def _fiche_camion(self, company, uid):
        local = fields.Datetime.context_timestamp(self.with_context(tz=company.partner_id.tz or "Europe/Paris"), fields.Datetime.now())
        personnes = self._personnes(company, local)
        taches = self._interventions(company, local)
        v = next((v for v in self._vehicules(company, personnes, taches) if v["id"] == uid), None)
        if not v:
            raise UserError("Camion introuvable.")
        quants = []
        if v["emplacement_id"]:
            for q in self.env["stock.quant"].sudo().search([("location_id", "child_of", v["emplacement_id"]), ("quantity", ">", 0)], limit=12):
                quants.append({"nom": q.product_id.display_name, "quantite": q.quantity})
        tournee = [t for t in taches if t["technicien_id"] == uid]
        return {**v, "genre": "camion", "a_bord_detail": quants, "tournee": tournee,
                "actions": [{"cle": "fiche", "nom": "Le technicien", "modele": "res.users", "id": uid}] +
                           ([{"cle": "stock_camion", "nom": "Le stock à bord", "modele": "stock.quant", "domaine": [["location_id", "child_of", v["emplacement_id"]]]}] if v["emplacement_id"] else []) +
                           [{"cle": "interventions_de", "nom": "Sa tournée"}]}

    def _fiche_rayon(self, company, categ_id):
        s = next((s for s in self._stock(company) if s["id"] == categ_id), None)
        categ = self.env["product.category"].sudo().browse(categ_id)
        Quant = self.env["stock.quant"].sudo()
        groupes = Quant._read_group([("company_id", "=", company.id), ("location_id.usage", "=", "internal"), ("product_id.categ_id", "child_of", categ_id)],
                                    ["product_id"], ["quantity:sum"], order="quantity:sum desc", limit=10) if categ.exists() else []
        produits = [(p, q) for p, q in groupes if q > 0]
        bas = []
        for op in self.env["stock.warehouse.orderpoint"].sudo().search([("company_id", "=", company.id), ("product_id.categ_id", "child_of", categ_id)], limit=100):
            if op.qty_forecast < 0 and len(bas) < 10:
                bas.append({"nom": op.product_id.display_name, "manque": round(-op.qty_forecast, 1)})
        return {**(s or {"id": categ_id, "nom": categ.name, "stock": 0, "mien": 0, "bas": len(bas)}), "genre": "rayon",
                "articles": [{"id": p.id, "nom": p.display_name, "quantite": q} for p, q in produits], "manquants": bas,
                "valeur": round(sum(q * p.with_company(company).standard_price for p, q in produits)),
                "actions": [{"cle": "famille_stock", "nom": "Le rayon en stock", "parametre": categ_id}, {"cle": "reappro", "nom": "Commander le manquant"},
                            {"cle": "famille_fiches", "nom": "Fiches techniques", "parametre": categ_id}]}

    def _fiche_zone(self, company, _id, cle=None):
        local = fields.Datetime.context_timestamp(self.with_context(tz=company.partner_id.tz or "Europe/Paris"), fields.Datetime.now())
        personnes = self._personnes(company, local)
        zone = next((z for z in SECTEUR["zones"] if z["cle"] == cle), None)
        presents = [p for p in personnes if (p["zone"] == cle and p["statut"] == "au_poste") or (cle == "pause" and p["statut"] == "en_pause") or (cle == "reunion" and p["statut"] == "en_reunion")]
        return {"genre": "zone", "cle": cle, "nom": zone["nom"] if zone else cle, "presents": [{"id": p["id"], "nom": p["nom"], "statut": p["statut_nom"], "depuis": p["depuis"]} for p in presents],
                "clients": self._clients_presents(company, local) if cle in ("accueil", "parking") else [],
                "actions": [{"cle": p["cle"], "nom": p["nom"], "icone": p["icone"]} for p in self._portes().get(cle, [])]}

    def _fiche_borne(self, company, _id):
        pointages = self.env["cultiveau.pointage"].du_jour(company)
        return {"genre": "borne", "nom": "Badgeuse", "journal": [{"nom": p.user_id.name, "genre": dict(p._fields["genre"].selection)[p.genre], "heure": fields.Datetime.to_string(p.horodatage)}
                                                                  for p in pointages[:15]],
                "actions": [{"cle": "badger", "nom": "Badger mon arrivée", "genre": "arrivee"}, {"cle": "badger", "nom": "Badger mon départ", "genre": "depart"}]}

    def _fiche_livraison(self, company, pid):
        p = self.env["stock.picking"].sudo().browse(pid)
        if not p.exists():
            raise UserError("Réception introuvable.")
        return {"genre": "livraison", "id": pid, "nom": p.name, "fournisseur": p.partner_id.name or "", "etat": p.state, "origine": p.origin or "",
                "lignes": [{"nom": m.product_id.display_name, "quantite": m.product_uom_qty, "recue": m.quantity} for m in p.move_ids[:10]],
                "actions": [{"cle": "fiche", "nom": "La réception", "modele": "stock.picking", "id": pid}]}

    def _fiche_poste(self, company, uid):
        """Un poste de travail : qui y est connecté, depuis quand, ce qu'il a ouvert."""
        u = self.env["res.users"].sudo().browse(uid)
        if not u.exists():
            return {"genre": "poste", "nom": "Poste libre", "actions": []}
        Order = self.env["sale.order"].sudo()
        recents = Order.search([("company_id", "=", company.id), ("user_id", "=", uid)], order="write_date desc", limit=3)
        return {"genre": "poste", "id": uid, "nom": f"Poste de {u.name}", "personne": u.name, "session": "active" if u.im_status == "online" else ("inactive" if u.im_status == "away" else "verrouillee"),
                "depuis": fields.Datetime.to_string(u.login_date) if u.login_date else "", "ouverts": [{"id": o.id, "nom": o.name, "client": o.partner_id.name} for o in recents],
                "actions": [{"cle": "fiche", "nom": "La personne", "modele": "res.users", "id": uid}]}

    def _fiche_appel(self, company, aid):
        if "cultiveau.appel" not in self.env:
            raise UserError("Les appels ne sont pas installés.")
        a = self.env["cultiveau.appel"].browse(aid)
        if not a.exists():
            raise UserError("Appel introuvable.")
        return {"genre": "appel", "id": aid, "nom": a.sujet, "client": a.partner_id.name or "", "client_id": a.partner_id.id, "numero": a.numero or "", "date": fields.Datetime.to_string(a.date),
                "duree": a.duree, "sens": a.sens, "urgence": a.urgence or "", "categorie": a.categorie or "", "resume": a.resume or "", "lien": a.lien_assistant or "",
                "intervention": a.task_id.id, "intervention_nom": a.task_id.name or "", "opportunite": a.lead_id.id, "opportunite_nom": a.lead_id.name or "",
                "actions": [{"cle": "fiche", "nom": "L'appel (résumé, transcription, audio)", "modele": "cultiveau.appel", "id": aid}] +
                           ([{"cle": "client", "nom": "Le client", "modele": "res.partner", "id": a.partner_id.id}] if a.partner_id else []) +
                           ([{"cle": "intervention", "nom": "L'intervention créée", "modele": "project.task", "id": a.task_id.id}] if a.task_id else []) +
                           ([{"cle": "opportunite", "nom": "L'opportunité créée", "modele": "crm.lead", "id": a.lead_id.id}] if a.lead_id else [])}

    def _fiche_machine(self, company, tid):
        return self._fiche_intervention(company, tid)

    # ---------------------------------------------------------------- les actions depuis la map

    @api.model
    def badger(self, genre, user_id=None):
        """Un pointage depuis la map : le mien, ou celui d'une autre personne si je suis gérant."""
        user = self.env["res.users"].browse(user_id) if user_id else self.env.user
        if user != self.env.user and not self.env.user.has_group("sales_team.group_sale_manager"):
            raise UserError("Seul le gérant peut badger pour quelqu'un d'autre.")
        self.env["cultiveau.pointage"].badger(genre, user=user, source="map")
        return True

    @api.model
    def ouvrir(self, modele, res_id, domaine=None, nom=None):
        """Le lien profond vers le back-office."""
        if domaine:
            return {"type": "ir.actions.act_window", "res_model": modele, "view_mode": "list,form", "name": nom or modele, "domain": domaine, "target": "current"}
        return {"type": "ir.actions.act_window", "res_model": modele, "res_id": int(res_id), "views": [[False, "form"]], "target": "current"}

    @api.model
    def focus(self, modele, res_id):
        """Depuis le back-office : l'objet de la map qui représente cet enregistrement (genre, id)."""
        res_id = int(res_id)
        if modele == "res.users":
            return {"genre": "personne", "id": res_id}
        if modele == "cultiveau.installation":
            i = self.env["cultiveau.installation"].sudo().browse(res_id)
            return {"genre": "dossier", "id": res_id, "champ": True}
        if modele == "cultiveau.chantier":
            return {"genre": "chantier", "id": res_id}
        if modele == "project.task":
            t = self.env["project.task"].sudo().browse(res_id)
            return {"genre": "intervention", "id": res_id, "technicien": t.user_ids[:1].id}
        if modele == "res.partner":
            return {"genre": "client", "id": res_id}
        if modele == "stock.location":
            u = self.env["res.users"].sudo().search([("cultiveau_camion_id", "=", res_id)], limit=1) if "cultiveau_camion_id" in self.env["res.users"]._fields else None
            return {"genre": "camion", "id": u.id if u else 0}
        if modele == "product.category":
            return {"genre": "rayon", "id": res_id}
        return {"genre": "zone", "id": 0}

    @api.model
    def action_voir_sur_la_map(self, modele, res_id):
        return {"type": "ir.actions.client", "tag": "cultiveau_vue3d.vue", "name": "Map vivante", "params": {"focus": f"{modele}:{int(res_id)}"}}

    # ---------------------------------------------------------------- le scénario de démonstration

    @api.model
    def scenario_demo(self):
        """Les étapes du scénario (75 s), tirées des vraies données de la société de démonstration. Chaque étape est jouée
        par `jouer_demo`, qui écrit dans les tables (pointages, événements) : la map, le fil et les KPI en vivent."""
        company = self.env.company
        if not company.cultiveau_map_demo:
            return []
        local = fields.Datetime.context_timestamp(self.with_context(tz=company.partner_id.tz or "Europe/Paris"), fields.Datetime.now())
        personnes = self._personnes(company, local)
        techniciens = [p for p in personnes if p["role"] == "technicien"] or personnes
        bureau = [p for p in personnes if p["role"] != "technicien"] or personnes
        if not personnes:
            return []
        taches = self._interventions(company, local)
        dossiers = self._dossiers(company)
        Order = self.env["sale.order"].sudo()
        devis = Order.search([("company_id", "=", company.id), ("state", "in", ("draft", "sent"))], order="amount_total desc", limit=1)
        fournisseur = self.env["res.partner"].sudo().search([("supplier_rank", ">", 0)], limit=1)
        t1, t2 = techniciens[0], techniciens[-1]
        b1 = bureau[0]
        tache = taches[0] if taches else None
        etapes = [
            {"t": 3, "genre": "arrivee", "user_id": t1["id"], "titre": "Arrivée au dépôt", "texte": f"{t1['nom']} badge à l'entrée et rejoint l'atelier.", "chemin": "entree_vers_poste"},
            {"t": 16, "genre": "depart_intervention", "user_id": t1["id"], "task_id": tache and tache["id"], "titre": "Départ en dépannage",
             "texte": f"{t1['nom']} part chez {tache['client'] if tache else 'un client'}" + (f" : {tache['nom']}." if tache else "."), "chemin": "poste_vers_camion"},
            {"t": 30, "genre": "livraison", "titre": "Livraison fournisseur", "texte": f"Un camion de {fournisseur.name if fournisseur else 'votre fournisseur'} se présente à la cour.", "vehicule": "fournisseur"},
            {"t": 44, "genre": "pause_debut", "user_id": b1["id"], "titre": "Pause", "texte": f"{b1['nom']} badge sa pause et passe à la salle de pause.", "chemin": "poste_vers_pause"},
            {"t": 56, "genre": "bon_signe", "user_id": t1["id"], "titre": "Bon signé sur place", "texte": f"{tache['client'] if tache else 'Le client'} a signé le bon d'intervention : 318 € HT.",
             "task_id": tache and tache["id"], "kpi": "interventions"},
            {"t": 68, "genre": "devis_signe", "titre": "Devis signé", "texte": f"{devis.partner_id.name if devis else 'Un client'} accepte le devis" + (f" {devis.name} : {round(devis.amount_untaxed):,} € HT.".replace(",", " ") if devis else "."),
             "kpi": "devis", "res_id": devis.id if devis else 0, "dossier": dossiers[0]["id"] if dossiers else 0},
        ]
        if t2 is not t1:
            etapes.insert(3, {"t": 38, "genre": "arrivee", "user_id": t2["id"], "titre": "Arrivée", "texte": f"{t2['nom']} arrive et badge.", "chemin": "entree_vers_poste"})
        return etapes

    @api.model
    def jouer_demo(self, etape):
        """Joue une étape du scénario : le pointage ou l'événement est écrit, puis poussé à tous les écrans de la société."""
        company = self.env.company
        if not company.cultiveau_map_demo:
            raise UserError("Le mode démonstration n'est pas activé pour cette société.")
        genre = etape.get("genre")
        user = self.env["res.users"].sudo().browse(etape.get("user_id")) if etape.get("user_id") else None
        task = self.env["project.task"].sudo().browse(etape["task_id"]) if etape.get("task_id") else None
        if genre in ("arrivee", "pause_debut", "pause_fin", "depart_intervention", "retour_intervention", "depart") and user:
            return self.env["cultiveau.pointage"].badger(genre, user=user, source="demo", task=task).evenement_id.charge_utile()
        e = self.env["cultiveau.evenement"].publier(genre, task or None, etape.get("titre", ""), etape.get("texte", ""), {k: v for k, v in etape.items() if k not in ("titre", "texte")},
                                                     company=company, demo=True)
        return e.charge_utile()

    @api.model
    def ambiance_demo(self):
        """Des notifications d'ambiance, construites sur les vraies données."""
        company = self.env.company
        local = fields.Datetime.context_timestamp(self.with_context(tz=company.partner_id.tz or "Europe/Paris"), fields.Datetime.now())
        personnes = self._personnes(company, local)
        stock = self._stock(company)
        clients = self.env["res.partner"].sudo().search([("company_id", "in", [company.id, False]), ("cultiveau_est_client", "=", True)], limit=20) if "cultiveau_est_client" in self.env["res.partner"]._fields else self.env["res.partner"].browse()
        fournisseurs = self.env["res.partner"].sudo().search([("supplier_rank", ">", 0)], limit=10)
        factures = self.env["account.move"].sudo().search([("company_id", "=", company.id), ("move_type", "=", "out_invoice"), ("state", "=", "posted")], limit=10)
        articles = self.env["product.product"].sudo().search([("sale_ok", "=", True)], limit=30)
        taches = self._interventions(company, local)
        rnd = random.Random()
        valeurs = {
            "personne": [p["nom"] for p in personnes] or ["l'équipe"], "article": [a.display_name for a in articles] or ["un article"], "client": [c.name for c in clients] or ["un client"],
            "fournisseur": [f.name for f in fournisseurs] or ["votre fournisseur"], "facture": [f.name for f in factures] or ["F-2026-0001"],
            "intervention": [t["nom"] for t in taches] or ["une intervention"],
        }
        resultat = []
        for modele in SECTEUR["ambiance"]:
            texte = modele
            for cle, liste in valeurs.items():
                texte = texte.replace("{" + cle + "}", rnd.choice(liste))
            resultat.append(texte)
        rnd.shuffle(resultat)
        return resultat


class Company(models.Model):
    _inherit = "res.company"

    cultiveau_map_demo = fields.Boolean("Mode démonstration de la map", default=False,
                                       help="La map rejoue un scénario (arrivées, départs, bons et devis signés) et des notifications d'ambiance. Pour présenter l'ERP.")


class Settings(models.TransientModel):
    _inherit = "res.config.settings"

    cultiveau_map_demo = fields.Boolean(related="company_id.cultiveau_map_demo", readonly=False)

    def action_cultiveau_regenerer_plan(self):
        plan = self.env["cultiveau.plan"].courant(self.env.company)
        plan.action_regenerer()
        return {"type": "ir.actions.client", "tag": "display_notification", "params": {"title": "Plan", "message": "Le plan du site a été régénéré.", "sticky": False}}

    def action_cultiveau_ouvrir_map(self):
        return {"type": "ir.actions.client", "tag": "cultiveau_vue3d.vue", "name": "Map vivante"}
