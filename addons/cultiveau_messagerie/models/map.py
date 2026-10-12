"""La messagerie sur la map, chez Mathis et dans les réglages."""
from odoo import fields, models


class Evenement(models.Model):
    _inherit = "cultiveau.evenement"

    genre = fields.Selection(selection_add=[("courriel", "Courriel reçu"), ("courriel_relance", "Courriel sans réponse")],
                             ondelete={"courriel": "cascade", "courriel_relance": "cascade"})


class Scene(models.AbstractModel):
    _inherit = "cultiveau.scene"

    def _actions(self):
        return {**super()._actions(),
                "courriels": ("cultiveau_messagerie.action_courriels", {"name": "Courriels à traiter", "domain": [("etat", "=", "a_traiter")]}),
                "courriels_sans_reponse": ("cultiveau_messagerie.action_courriels", {"name": "Courriels sans réponse", "domain": [("etat", "=", "a_traiter"), ("sans_reponse", "=", True)]}),
                "boites": ("cultiveau_messagerie.action_boites", {"name": "Boîtes mail"})}


class Map(models.AbstractModel):
    _inherit = "cultiveau.map"

    def _portes(self):
        portes = super()._portes()
        dispo = self.env["cultiveau.scene"]._actions_disponibles()
        ajouts = {"accueil": [("courriels", "Courriels à traiter", "fa-envelope")],
                  "administratif": [("courriels", "Courriels à traiter", "fa-envelope"), ("courriels_sans_reponse", "Courriels sans réponse", "fa-hourglass-half"),
                                    ("boites", "Boîtes mail", "fa-inbox")],
                  "bureau": [("courriels", "Courriels à traiter", "fa-envelope")]}
        for zone, liste in ajouts.items():
            deja = {p["cle"] for p in portes.get(zone, [])}
            portes.setdefault(zone, []).extend({"cle": c, "nom": n, "icone": i} for c, n, i in liste if c in dispo and c not in deja)
        return portes

    def _lignes_courriels(self, courriels, client=True):
        Courriel = self.env["cultiveau.courriel"]
        lignes = []
        for c in courriels:
            l = Courriel.ligne(c)
            badge, couleur = ("", "")
            if l["sans_reponse"]:
                badge, couleur = f"{l['attente_jours']} j sans réponse", "rouge"
            elif l["urgent"]:
                badge, couleur = "Urgent", "ambre"
            elif l["etat"] != "a_traiter":
                badge, couleur = dict(c._fields["etat"].selection)[l["etat"]], "vert" if l["etat"] == "repondu" else "ardoise"
            boutons = []
            if l["etat"] == "a_traiter":
                boutons = [{"cle": "appel", "nom": "Préparer la réponse avec Mathis", "icone": "fa-magic", "principal": True,
                            "appel": {"modele": "cultiveau.courriel", "methode": "preparer_reponse", "args": [c.id]}},
                           {"cle": "appel", "nom": "Classer (pas de réponse à faire)", "icone": "fa-check",
                            "appel": {"modele": "cultiveau.courriel", "methode": "classer", "args": [c.id]}}]
            qui = l["client"] or l["de"]
            lignes.append({"icone": "fa-envelope" if l["etat"] == "a_traiter" else "fa-envelope-open-o", "texte": f"{qui} · {l['objet']}" if client else l["objet"],
                           "detail": " · ".join(x for x in (l["dossier"] or l["categorie"], l["resume"]) if x), "badge": badge, "couleur": couleur, "boutons": boutons,
                           "ouvrir": {"cle": "fiche", "modele": "cultiveau.courriel", "id": c.id}})
        return lignes

    def _fiche_zone(self, company, _id, cle=None):
        f = super()._fiche_zone(company, _id, cle=cle)
        if cle in ("accueil", "administratif", "bureau"):
            Courriel = self.env["cultiveau.courriel"]
            courriels = Courriel.a_traiter(limite=6)
            total = Courriel.search_count([("etat", "=", "a_traiter"), ("company_id", "=", company.id)])
            titre = f"Courriels à traiter ({total})" if total else "Courriels à traiter"
            f["blocs"] = list(f.get("blocs", [])) + [{"titre": titre, "lignes": self._lignes_courriels(courriels), "vide": "Boîte à jour : rien en attente."}]
        return f

    def _fiche_client(self, company, pid):
        f = super()._fiche_client(company, pid)
        courriels = self.env["cultiveau.courriel"].search([("partner_id", "child_of", pid)], order="date_reception desc", limit=4)
        if courriels:
            f["blocs"] = list(f.get("blocs", [])) + [{"titre": "Courriels", "lignes": self._lignes_courriels(courriels, client=False)}]
        return f

    def _fiche_personne(self, company, uid):
        f = super()._fiche_personne(company, uid)
        if uid == self.env.user.id or self.env.user.has_group("sales_team.group_sale_manager"):
            Courriel = self.env["cultiveau.courriel"]
            domaine = [("etat", "=", "a_traiter"), ("user_id", "=", uid), ("company_id", "=", company.id)]
            n = Courriel.search_count(domaine)
            if n:
                retard = Courriel.search_count(domaine + [("sans_reponse", "=", True)])
                ligne = {"icone": "fa-envelope", "texte": f"{n} courriel(s) à traiter", "badge": f"{retard} sans réponse" if retard else "", "couleur": "rouge",
                         "ouvrir": {"cle": "courriels_de", "modele": "cultiveau.courriel", "domaine": domaine, "nom": f"Courriels de {f.get('nom', '')}"}}
                f["blocs"] = list(f.get("blocs", [])) + [{"titre": "Courriels", "lignes": [ligne]}]
        return f


class Mathis(models.AbstractModel):
    _inherit = "cultiveau.mathis"

    def _ecritures(self):
        return super()._ecritures() | {"classer_courriel"}

    def _titres(self):
        return {**super()._titres(), "classer_courriel": "Classer le courriel"}

    def _outils(self):
        objet = lambda props, requis=None: {"type": "object", "properties": props, **({"required": requis} if requis else {})}  # noqa: E731
        return super()._outils() + [
            {"type": "function", "function": {"name": "courriels", "description": "Les courriels reçus à traiter (les plus en retard d'abord) : expéditeur, client, dossier lié, résumé, "
                                                                                 "jours d'attente. Filtrer sur un client, sur ceux de la personne connectée, ou sur ceux sans réponse.",
                                              "parameters": objet({"client_id": {"type": "integer"}, "les_miens": {"type": "boolean"}, "sans_reponse": {"type": "boolean"}})}},
            {"type": "function", "function": {"name": "lire_courriel", "description": "Le contenu d'un courriel et de ses échanges, avec le client et le dossier lié.",
                                              "parameters": objet({"id": {"type": "integer"}}, ["id"])}},
            {"type": "function", "function": {"name": "preparer_reponse", "description": "Prépare la réponse à un courriel (avec le contexte du client et du dossier) et l'ouvre pour que la "
                                                                                        "personne la relise et l'envoie. consignes : ce que la réponse doit dire.",
                                              "parameters": objet({"id": {"type": "integer"}, "consignes": {"type": "string"}}, ["id"])}},
            {"type": "function", "function": {"name": "classer_courriel", "description": "Classe un courriel qui n'appelle pas de réponse (après confirmation).",
                                              "parameters": objet({"id": {"type": "integer"}}, ["id"])}},
        ]

    def _executer(self, nom, args):
        Courriel = self.env["cultiveau.courriel"]
        if nom == "courriels":
            courriels = Courriel.a_traiter(user=self.env.user if args.get("les_miens") else None, client_id=args.get("client_id"), limite=15)
            if args.get("sans_reponse"):
                courriels = courriels.filtered("sans_reponse")
            return [Courriel.ligne(c) for c in courriels], None
        if nom == "lire_courriel":
            c = Courriel.browse(int(args.get("id") or 0)).exists()
            if not c:
                return {"erreur": "Courriel introuvable."}, None
            return {**Courriel.ligne(c), "echanges": c._historique(limite=4)[:6000],
                    "dossier_detail": Courriel._resume_document(c.document.sudo()) if c.document else ""}, None
        if nom == "preparer_reponse":
            action = Courriel.preparer_reponse(args.get("id"), args.get("consignes") or "")
            return {"brouillon": "réponse prête à relire"}, {"type": "action", "action": action}
        if nom == "classer_courriel":
            return Courriel.classer(args.get("id")), None
        return super()._executer(nom, args)

    def _resumer(self, nom, args):
        if nom == "classer_courriel":
            c = self.env["cultiveau.courriel"].browse(int(args.get("id") or 0)).exists()
            return f"Classer « {c.name} »" if c else f"Classer le courriel n° {args.get('id')}"
        return super()._resumer(nom, args)


class Settings(models.TransientModel):
    _inherit = "res.config.settings"

    cultiveau_courriel_jours = fields.Integer("Délai de réponse (jours ouvrés)", config_parameter="cultiveau.courriel_jours_sans_reponse", default=3,
                                              help="Au-delà, le courriel est signalé « sans réponse » et le responsable reçoit une activité.")
    cultiveau_url_retour_gmail = fields.Char("Adresse de retour Gmail", compute="_compute_urls_retour_messagerie")
    cultiveau_url_retour_outlook = fields.Char("Adresse de retour Outlook", compute="_compute_urls_retour_messagerie")
    cultiveau_nb_boites = fields.Integer("Boîtes branchées", compute="_compute_urls_retour_messagerie")

    def _compute_urls_retour_messagerie(self):
        base = self.env["ir.config_parameter"].sudo().get_param("web.base.url") or ""
        n = self.env["cultiveau.boite"].sudo().search_count([("etat", "=", "connectee")])
        for s in self:
            s.cultiveau_url_retour_gmail = f"{base}/google_gmail/confirm"
            s.cultiveau_url_retour_outlook = f"{base}/microsoft_outlook/confirm"
            s.cultiveau_nb_boites = n
