"""Les congés et les notes de frais sur la map, dans les créneaux de réunion et chez Mathis."""
from datetime import timedelta

from odoo import api, fields, models

from .equipe import euros


class Evenement(models.Model):
    _inherit = "cultiveau.evenement"

    genre = fields.Selection(selection_add=[("conge", "Congés"), ("frais", "Note de frais")], ondelete={"conge": "cascade", "frais": "cascade"})


class Scene(models.AbstractModel):
    _inherit = "cultiveau.scene"

    def _actions(self):
        return {**super()._actions(),
                "conges_equipe": ("hr_holidays.action_hr_holidays_dashboard", {"name": "Planning des congés"}),
                "conges_a_valider": ("hr_holidays.hr_leave_action_action_approve_department", {"name": "Congés à valider"}),
                "mes_conges": ("hr_holidays.hr_leave_action_new_request", {"name": "Mes congés"}),
                "soldes_conges": ("hr_holidays.hr_leave_allocation_action_approve_department", {"name": "Soldes de congés"}),
                "notes_de_frais": ("hr_expense.action_hr_expense_sheet_all", {"name": "Notes de frais"}),
                "notes_a_valider": ("hr_expense.action_hr_expense_sheet_all", {"name": "Notes de frais à valider", "domain": [("state", "=", "submit")]}),
                "mes_frais": ("hr_expense.hr_expense_actions_my_all", {"name": "Mes dépenses"}),
                "mon_espace": (None, {"url": ("cultiveau.url_moi", "/moi"), "name": "Mon espace"})}


class Map(models.AbstractModel):
    _inherit = "cultiveau.map"

    # ---------------------------------------------------------------- les personnes en congés

    def _personnes(self, company, local):
        personnes = super()._personnes(company, local)
        users = self.env["res.users"].browse([p["id"] for p in personnes])
        absents = self.env["cultiveau.conges"].absents_maintenant(users)
        for p in personnes:
            a = absents.get(p["id"])
            if not a or p["statut"] in ("en_intervention", "sur_chantier", "en_pause", "en_route", "parti"):
                continue
            # un congé de l'agenda n'est pas une réunion : la personne n'est pas là
            p.update({"statut": "en_conges", "statut_nom": f"{'Absent' if a['cle'] in ('maladie', 'absence') else 'En congés'} · retour {a['retour']}",
                      "couleur": "ardoise", "reunion": None, "conge": a})
        return personnes

    def _portes(self):
        portes = super()._portes()
        dispo = self.env["cultiveau.scene"]._actions_disponibles()
        ajouts = {"administratif": [("conges_a_valider", "Congés à valider", "fa-plane"), ("notes_a_valider", "Notes de frais à valider", "fa-ticket"),
                                    ("conges_equipe", "Planning des congés", "fa-calendar-times-o"), ("notes_de_frais", "Notes de frais", "fa-file-text-o")],
                  "reunion": [("conges_equipe", "Planning des congés", "fa-calendar-times-o")],
                  "accueil": [("mon_espace", "Mon espace : congés et frais", "fa-mobile")],
                  "atelier": [("mon_espace", "Mon espace : congés et frais", "fa-mobile")]}
        for zone, liste in ajouts.items():
            deja = {p["cle"] for p in portes.get(zone, [])}
            portes.setdefault(zone, []).extend({"cle": c, "nom": n, "icone": i} for c, n, i in liste if c in dispo and c not in deja)
        return portes

    # ---------------------------------------------------------------- les fiches

    def _bouton(self, modele, methode, args, nom, icone, principal=False, message=""):
        return {"cle": "appel", "nom": nom, "icone": icone, "principal": principal, "message": message, "appel": {"modele": modele, "methode": methode, "args": args}}

    def _lignes_conges(self, conges, gerant):
        lignes = []
        for c in conges:
            boutons = []
            if gerant and c["etat"] in ("confirm", "validate1"):
                boutons = [self._bouton("cultiveau.conges", "decider", [c["id"], True], "Valider", "fa-check", principal=True),
                           self._bouton("cultiveau.conges", "decider", [c["id"], False], "Refuser", "fa-times")]
            lignes.append({"icone": "fa-plane", "texte": f"{c['employe']} · {c['periode']}" if gerant else c["periode"].capitalize(),
                           "detail": f"{c['type']} · {c['jours']:g} j", "badge": c["etat_nom"], "couleur": c["couleur"], "boutons": boutons})
        return lignes

    def _lignes_frais(self, feuilles, gerant):
        lignes = []
        for f in feuilles:
            boutons = []
            if gerant and f["etat"] == "submit":
                boutons = [self._bouton("cultiveau.frais", "decider", [f["id"], True], "Valider", "fa-check", principal=True),
                           self._bouton("cultiveau.frais", "decider", [f["id"], False], "Refuser", "fa-times")]
            lignes.append({"icone": "fa-ticket", "texte": f"{f['employe']} · {len(f['lignes'])} dépense(s)", "detail": ", ".join(x["categorie"] for x in f["lignes"][:3]),
                           "badge": f["montant_texte"] if boutons else f["etat_nom"], "couleur": "accent" if boutons else f["couleur"], "boutons": boutons,
                           "ouvrir": {"cle": "fiche", "modele": "hr.expense.sheet", "id": f["id"]}})
        return lignes

    def _fiche_personne(self, company, uid):
        f = super()._fiche_personne(company, uid)
        Conges, Frais, Equipe = self.env["cultiveau.conges"], self.env["cultiveau.frais"], self.env["cultiveau.equipe"]
        user = self.env["res.users"].sudo().browse(uid)
        moi = uid == self.env.user.id
        gerant = Equipe.est_gerant()
        aujourd_hui = fields.Date.context_today(self)
        blocs = list(f.get("blocs", []))
        conges = [c for c in Conges.demandes(user, limite=8) if c["au"] >= fields.Date.to_string(aujourd_hui) and c["etat"] not in ("refuse", "cancel")]
        lignes = self._lignes_conges(sorted(conges, key=lambda c: c["du"]), gerant and not moi)
        if moi or gerant:
            for s in Conges.soldes(user):
                lignes.append({"icone": "fa-pie-chart", "texte": s["nom"], "detail": f"{s['restant']:g} j restants sur {s['acquis']:g}"})
        if lignes or moi:
            blocs.append({"titre": "Congés", "lignes": lignes, "vide": "Aucun congé prévu."})
        if moi or gerant:
            frais = Frais.mes_frais(user, limite=30)
            a_envoyer = [x for x in frais if x["etat"] in ("draft", "reported")]
            feuilles = {x["note_id"] for x in frais if x["etat"] == "submitted" and x["note_id"]}
            lignes = self._lignes_frais([Frais._feuille(s) for s in self.env["hr.expense.sheet"].sudo().browse(list(feuilles))], gerant and not moi)
            if a_envoyer:
                total = sum(x["montant"] for x in a_envoyer)
                boutons = [self._bouton("cultiveau.frais", "envoyer", [], "Envoyer", "fa-paper-plane", principal=True)] if moi else []
                lignes.insert(0, {"icone": "fa-camera", "texte": f"{len(a_envoyer)} dépense(s) à envoyer", "badge": euros(total), "couleur": "ambre", "boutons": boutons})
            if lignes:
                blocs.append({"titre": "Notes de frais", "lignes": lignes})
        f["blocs"] = blocs
        if moi:
            f["actions"] = f["actions"] + [
                {"cle": "demander_conge", "nom": "Demander un congé", "icone": "fa-plane",
                 "doaction": {"type": "ir.actions.act_window", "res_model": "hr.leave", "views": [[False, "form"]], "target": "new", "name": "Demander un congé",
                              "context": {"default_employee_id": Equipe.employe(creer=False).id}}},
                {"cle": "mon_espace", "nom": "Mon espace sur le téléphone", "icone": "fa-mobile", "url": "/moi"}]
        return f

    def _fiche_zone(self, company, _id, cle=None):
        f = super()._fiche_zone(company, _id, cle=cle)
        if cle in ("administratif", "reunion"):
            Conges, Frais, Equipe = self.env["cultiveau.conges"], self.env["cultiveau.frais"], self.env["cultiveau.equipe"]
            blocs = list(f.get("blocs", []))
            if cle == "administratif" and Equipe.est_gerant():
                lignes = self._lignes_conges(Conges.a_valider(), True) + self._lignes_frais(Frais.a_valider(), True)
                blocs.append({"titre": "À valider", "lignes": lignes, "vide": "Rien à valider : congés et notes de frais sont à jour."})
            aujourd_hui = fields.Date.context_today(self)
            absences = [c for c in Conges.absences(aujourd_hui, aujourd_hui + timedelta(days=6)) if c["etat"] == "validate"]
            if absences:
                blocs.append({"titre": "Absents dans les 7 jours", "lignes": [{"icone": "fa-plane", "texte": f"{c['employe']} · {c['periode']}", "detail": c["type"]} for c in absences]})
            f["blocs"] = blocs
        return f


class Reunion(models.AbstractModel):
    _inherit = "cultiveau.reunion"

    def _occupations(self, partners, users, debut, fin, salle=False):
        """Les congés (validés ou demandés) occupent aussi : pas de réunion proposée pendant une absence."""
        plages = super()._occupations(partners, users, debut, fin, salle=salle)
        if users:
            plages += self.env["cultiveau.conges"].plages_absence(users, debut, fin)
        return plages


class Mathis(models.AbstractModel):
    _inherit = "cultiveau.mathis"

    def _ecritures(self):
        return super()._ecritures() | {"demander_conge", "decider_conge", "creer_frais", "envoyer_frais", "decider_frais"}

    def _titres(self):
        return {**super()._titres(), "demander_conge": "Envoyer la demande", "decider_conge": "Confirmer la décision", "creer_frais": "Créer la dépense",
                "envoyer_frais": "Envoyer au gérant", "decider_frais": "Confirmer la décision"}

    def _outils(self):
        types = [t["cle"] for t in self.env["cultiveau.conges"].types()]
        categories = [c["cle"] for c in self.env["cultiveau.frais"].categories()]
        objet = lambda props, requis=None: {"type": "object", "properties": props, **({"required": requis} if requis else {})}  # noqa: E731
        return super()._outils() + [
            {"type": "function", "function": {"name": "conges", "description": "Les congés et absences : les soldes et demandes de la personne connectée, qui est absent dans l'équipe "
                                                                               "sur la période (aujourd'hui par défaut), et pour le gérant les demandes à valider.",
                                              "parameters": objet({"du": {"type": "string", "description": "AAAA-MM-JJ"}, "au": {"type": "string", "description": "AAAA-MM-JJ"}})}},
            {"type": "function", "function": {"name": "demander_conge", "description": "Demande un congé pour la personne connectée (après confirmation). demi : am (matin) ou pm (après-midi) pour une demi-journée.",
                                              "parameters": objet({"type": {"type": "string", "enum": types}, "du": {"type": "string", "description": "AAAA-MM-JJ"},
                                                                   "au": {"type": "string", "description": "AAAA-MM-JJ"}, "demi": {"type": "string", "enum": ["am", "pm"]},
                                                                   "motif": {"type": "string"}}, ["type", "du"])}},
            {"type": "function", "function": {"name": "decider_conge", "description": "Valide ou refuse une demande de congé (gérant, après confirmation). id : celui renvoyé par l'outil conges.",
                                              "parameters": objet({"id": {"type": "integer"}, "valider": {"type": "boolean"}, "motif": {"type": "string"}}, ["id", "valider"])}},
            {"type": "function", "function": {"name": "frais", "description": "Les notes de frais de la personne connectée (à envoyer, envoyées, validées, remboursées) et, pour le gérant, celles à valider.",
                                              "parameters": objet({})}},
            {"type": "function", "function": {"name": "creer_frais", "description": "Crée une dépense pour la personne connectée (après confirmation) : montant TTC et catégorie, ou des kilomètres "
                                                                                    "(indemnités kilométriques). Pour un ticket, mieux vaut la photo sur la page Mon espace (/moi).",
                                              "parameters": objet({"montant": {"type": "number"}, "categorie": {"type": "string", "enum": categories}, "date": {"type": "string", "description": "AAAA-MM-JJ"},
                                                                   "kilometres": {"type": "number"}, "description": {"type": "string"}}, ["description"])}},
            {"type": "function", "function": {"name": "envoyer_frais", "description": "Envoie au gérant toutes les dépenses à envoyer de la personne connectée (après confirmation).", "parameters": objet({})}},
            {"type": "function", "function": {"name": "decider_frais", "description": "Valide ou refuse une note de frais (gérant, après confirmation). id : celui de la note renvoyé par l'outil frais.",
                                              "parameters": objet({"id": {"type": "integer"}, "valider": {"type": "boolean"}, "motif": {"type": "string"}}, ["id", "valider"])}},
        ]

    def _executer(self, nom, args):
        Conges, Frais, Equipe = self.env["cultiveau.conges"], self.env["cultiveau.frais"], self.env["cultiveau.equipe"]
        if nom == "conges":
            du = args.get("du") or fields.Date.to_string(fields.Date.context_today(self))
            res = {"mes_soldes": Conges.soldes(), "mes_demandes": Conges.demandes(limite=6), "absences": Conges.absences(du, args.get("au") or du)}
            if Equipe.est_gerant():
                res["a_valider"] = Conges.a_valider()
            return res, None
        if nom == "demander_conge":
            c = Conges.demander(args.get("type") or "conges_payes", args.get("du"), args.get("au"), args.get("demi") or False, args.get("motif") or "")
            return c, {"type": "lien", "modele": "hr.leave", "id": c["id"], "libelle": f"{c['type']} {c['periode']}"}
        if nom == "decider_conge":
            return Conges.decider(args.get("id"), bool(args.get("valider")), args.get("motif") or ""), None
        if nom == "frais":
            res = {"mes_depenses": Frais.mes_frais(limite=15)}
            if Equipe.est_gerant():
                res["a_valider"] = Frais.a_valider()
            return res, None
        if nom == "creer_frais":
            x = Frais.depuis_photo(None, None, montant=args.get("montant") or 0, categorie=args.get("categorie"), kilometres=args.get("kilometres") or 0,
                                   note=args.get("description") or "")
            if args.get("date"):
                self.env["hr.expense"].browse(x["id"]).date = fields.Date.to_date(args["date"])
                x = Frais._ligne(self.env["hr.expense"].browse(x["id"]))
            return x, {"type": "lien", "modele": "hr.expense", "id": x["id"], "libelle": f"{x['nom']} · {x['montant_texte']}"}
        if nom == "envoyer_frais":
            return Frais.envoyer(), None
        if nom == "decider_frais":
            return Frais.decider(args.get("id"), bool(args.get("valider")), args.get("motif") or ""), None
        return super()._executer(nom, args)

    def _resumer(self, nom, args):
        if nom == "demander_conge":
            demi = {"am": " (matin)", "pm": " (après-midi)"}.get(args.get("demi") or "", "")
            au = f" au {args['au']}" if args.get("au") and args.get("au") != args.get("du") else ""
            return f"{dict((t['cle'], t['nom']) for t in self.env['cultiveau.conges'].types()).get(args.get('type'), 'Congé')} : {args.get('du', '')}{au}{demi}"
        if nom in ("decider_conge", "decider_frais"):
            return f"{'Valider' if args.get('valider') else 'Refuser'} la demande n° {args.get('id')}" + (f" ({args['motif']})" if args.get("motif") else "")
        if nom == "creer_frais":
            if args.get("kilometres"):
                return f"{args['kilometres']:g} km · {args.get('description', '')}"
            return f"{euros(float(args.get('montant') or 0))} · {args.get('categorie') or 'autre'} · {args.get('description', '')}"
        if nom == "envoyer_frais":
            return "Envoyer mes dépenses à envoyer au gérant"
        return super()._resumer(nom, args)
