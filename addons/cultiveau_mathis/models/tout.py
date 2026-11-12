"""Mathis fait tout ce que la personne peut faire dans l'ERP, à sa place, en lui écrivant.

Cinq outils généraux s'ajoutent aux outils métier : trouver le type de fiche, lire ses champs et ses boutons, chercher,
compter, puis créer, modifier ou appuyer sur un bouton. Tout passe par les droits de la personne connectée (les mêmes
refus que dans les écrans), rien n'est écrit sans son clic, rien n'est supprimé (on archive), et les réglages
techniques, les comptes et les mots de passe restent hors de portée.
"""
import json

from lxml import etree

from odoo import Command, models
from odoo.exceptions import AccessError, UserError

# ce que Mathis ne touche jamais, même pour un administrateur
INTERDITS = ("ir.", "base.", "res.users", "res.groups", "res.config", "res.lang", "auth", "bus.", "mail.mail", "mail.template", "sms.", "fetchmail", "payment.provider",
             "payment.token", "iap.", "digest.", "report.", "change.password", "cultiveau.api", "cultiveau.mathis", "cultiveau.connecteur", "website.")
SECRETS = ("password", "passwd", "secret", "token", "api_key", "apikey", "_cle", "cle_", "signup_", "totp")
TECHNIQUES = ("message_", "activity_", "website_message", "access_", "__", "rating_", "my_activity", "has_message")
LECTURE_MAX = 40
OPERATEURS = ("=", "!=", ">", ">=", "<", "<=", "ilike", "not ilike", "in", "not in", "child_of")

# les mots du métier, quand le nom de l'ERP ne les contient pas
MOTS = {"devis": "sale.order", "commande": "sale.order", "vente": "sale.order", "facture": "account.move", "avoir": "account.move", "client": "res.partner",
        "fournisseur": "res.partner", "contact": "res.partner", "achat": "purchase.order", "intervention": "project.task", "depannage": "project.task",
        "dépannage": "project.task", "tache": "project.task", "tâche": "project.task", "article": "product.product", "produit": "product.product",
        "livraison": "stock.picking", "reception": "stock.picking", "réception": "stock.picking", "stock": "stock.quant", "opportunite": "crm.lead",
        "opportunité": "crm.lead", "rendez-vous": "calendar.event", "reunion": "calendar.event", "réunion": "calendar.event", "paiement": "account.payment",
        "reglement": "account.payment", "règlement": "account.payment", "conge": "hr.leave", "congé": "hr.leave", "salarie": "hr.employee", "salarié": "hr.employee",
        "employe": "hr.employee", "employé": "hr.employee", "vehicule": "fleet.vehicle", "véhicule": "fleet.vehicle", "camion": "fleet.vehicle",
        "chantier": "cultiveau.chantier", "installation": "cultiveau.installation"}

ECRITURES_TOUT = {"creer_fiche", "modifier_fiche", "appuyer_bouton"}
TITRES_TOUT = {"creer_fiche": "Créer", "modifier_fiche": "Modifier", "appuyer_bouton": "Lancer l'action"}

AIDE = """
Tu peux aussi faire TOUT ce que {utilisateur} peut faire dans l'ERP, à sa place, avec les outils généraux :
1. types_de_fiche : trouve le nom technique du type de fiche (« facture fournisseur », « bon de livraison », « congé »…) ;
2. champs_et_boutons : ses champs (nom technique, libellé, type, obligatoire) et ses boutons ; appelle-le avant d'écrire sur un type
   de fiche que tu n'as pas encore vu dans la conversation ;
3. trouver_fiches et compter_fiches : pour lire ; ne devine jamais un identifiant, cherche-le ;
4. creer_fiche, modifier_fiche, appuyer_bouton : pour agir. L'ERP montre la proposition à la personne, qui confirme d'un clic.
   Une seule étape à la fois quand la suivante dépend de la précédente (créer le devis, puis le confirmer) : tu continues après la confirmation.
Repères : devis et commandes client = sale.order (lignes : order_line avec product_id, product_uom_qty, price_unit ; confirmer : action_confirm) ;
factures = account.move (move_type out_invoice pour une facture client, in_invoice pour un fournisseur ; lignes : invoice_line_ids avec
product_id, quantity, price_unit ; valider : action_post) ; achats = purchase.order (order_line avec product_id, product_qty ; button_confirm) ;
clients et fournisseurs = res.partner ; interventions et tâches = project.task ; opportunités = crm.lead ; articles = product.product ;
livraisons et réceptions = stock.picking ; rendez-vous = calendar.event.
Dans les valeurs : un lien vers une autre fiche se donne par son identifiant (ou son nom exact), des lignes par une liste d'objets.
On ne supprime rien : pour retirer une fiche, on l'archive (modifier_fiche avec active à false). Les comptes d'utilisateur, les droits
et les réglages techniques ne te sont pas ouverts : dis-le simplement si on te le demande.
Pour citer une fiche d'un autre type, écris [[nom.technique:id|Libellé]].
Si la demande est floue (quel client, quel article, quelle quantité), pose la question avant de proposer."""


class MathisTout(models.AbstractModel):
    _inherit = "cultiveau.mathis"

    # ---------------------------------------------------------------- les garde-fous

    def _modele_ouvert(self, nom, operation="read"):
        """Le type de fiche, s'il est ouvert à Mathis et si la personne a le droit demandé."""
        nom = (nom or "").strip()
        if nom not in self.env or any(nom.startswith(p) for p in INTERDITS):
            raise UserError(f"Le type de fiche « {nom} » n'existe pas ou ne m'est pas ouvert. Cherchez-le avec types_de_fiche.")
        Modele = self.env[nom]
        if Modele._abstract or Modele._transient:
            raise UserError(f"« {nom} » n'est pas un type de fiche (c'est un écran de saisie passager).")
        if not Modele.has_access(operation):
            verbe = {"read": "consulter", "create": "créer", "write": "modifier"}.get(operation, operation)
            raise UserError(f"{self.env.user.name} n'a pas le droit de {verbe} les fiches « {Modele._description} ».")
        return Modele

    def _champ_ouvert(self, nom):
        return not any(s in nom for s in SECRETS) and not nom.startswith(TECHNIQUES)

    def _fiches(self, Modele, ids):
        ids = [int(i) for i in (ids if isinstance(ids, (list, tuple)) else [ids]) if str(i).lstrip("-").isdigit()]
        fiches = Modele.browse(ids).exists()
        if not fiches:
            raise UserError("Fiche introuvable : cherchez d'abord son identifiant avec trouver_fiches.")
        if len(fiches) > 50:
            raise UserError("Trop de fiches d'un coup : 50 au plus.")
        return fiches

    def _objet(self, valeur):
        """Le modèle envoie parfois un objet en texte : on l'accepte."""
        if isinstance(valeur, str):
            try:
                valeur = json.loads(valeur)
            except ValueError as e:
                raise UserError("Les valeurs doivent être un objet {champ: valeur}.") from e
        return valeur

    def _domaine(self, Modele, filtres):
        domaine = []
        for f in self._objet(filtres) or []:
            if isinstance(f, dict):
                champ, op, val = f.get("champ"), f.get("operateur") or "=", f.get("valeur")
            elif isinstance(f, (list, tuple)) and len(f) == 3:
                champ, op, val = f
            else:
                raise UserError("Un filtre s'écrit {champ, operateur, valeur}.")
            racine = str(champ or "").split(".")[0]
            if racine not in Modele._fields or not self._champ_ouvert(racine):
                raise UserError(f"Le champ « {champ} » n'existe pas sur {Modele._name} : voyez champs_et_boutons.")
            if op not in OPERATEURS:
                raise UserError(f"Opérateur inconnu : {op}. Possibles : {', '.join(OPERATEURS)}.")
            if isinstance(val, str) and op not in ("ilike", "not ilike"):
                # « 12 », « true », « [1, 2] » arrivent en texte
                try:
                    val = json.loads(val)
                except ValueError:
                    pass
            domaine.append((champ, op, val))
        return domaine

    def _valeurs(self, Modele, valeurs):
        """Les valeurs données par le modèle, traduites pour l'ERP : liens par identifiant ou par nom, lignes en liste d'objets."""
        valeurs = self._objet(valeurs)
        if not isinstance(valeurs, dict) or not valeurs:
            raise UserError("Donnez les valeurs à écrire : un objet {champ: valeur}.")
        vals = {}
        for nom, v in valeurs.items():
            champ = Modele._fields.get(nom)
            if not champ or not self._champ_ouvert(nom):
                raise UserError(f"Le champ « {nom} » n'existe pas sur {Modele._name} : voyez champs_et_boutons.")
            if champ.type == "many2one":
                vals[nom] = self._lien(champ, v)
            elif champ.type in ("one2many", "many2many"):
                Autre = self.env[champ.comodel_name]
                commandes = []
                elements = v if isinstance(v, list) else [v]
                if champ.type == "many2many" and all(isinstance(e, (int, str)) for e in elements):
                    commandes = [Command.set([self._lien(champ, e) for e in elements])]
                else:
                    for e in elements:
                        if isinstance(e, dict) and e.get("id") and len(e) == 1 and champ.type == "many2many":
                            commandes.append(Command.link(int(e["id"])))
                        elif isinstance(e, dict) and e.get("id"):
                            commandes.append(Command.update(int(e["id"]), self._valeurs(Autre, {k: x for k, x in e.items() if k != "id"})))
                        elif isinstance(e, dict):
                            commandes.append(Command.create(self._valeurs(Autre, e)))
                        else:
                            raise UserError(f"« {nom} » attend une liste d'objets (une ligne par objet).")
                vals[nom] = commandes
            else:
                vals[nom] = v
        return vals

    def _lien(self, champ, v):
        if v in (None, False, "", 0):
            return False
        if isinstance(v, (list, tuple)) and v:
            v = v[0]
        if isinstance(v, dict):
            v = v.get("id") or v.get("nom") or v.get("name")
        if isinstance(v, int) or (isinstance(v, str) and v.isdigit()):
            fiche = self.env[champ.comodel_name].browse(int(v)).exists()
            if not fiche:
                raise UserError(f"« {champ.string} » : la fiche n° {v} n'existe pas.")
            return fiche.id
        trouves = self.env[champ.comodel_name].name_search(str(v), limit=6)
        exacts = [t for t in trouves if t[1].strip().lower() == str(v).strip().lower()]
        if len(exacts) == 1 or len(trouves) == 1:
            return (exacts or trouves)[0][0]
        if not trouves:
            raise UserError(f"« {champ.string} » : rien ne s'appelle « {v} ».")
        raise UserError(f"« {champ.string} » : plusieurs fiches pour « {v} » ({' ; '.join(f'{i} = {n}' for i, n in trouves)}). Donnez l'identifiant.")

    def _boutons(self, Modele):
        """Les boutons de la fiche : ce que la personne peut cliquer, donc ce que Mathis peut lancer."""
        boutons = {}
        for genre in ("form", "list"):
            try:
                arch = etree.fromstring(Modele.get_view(view_type=genre)["arch"])
            except Exception:  # noqa: BLE001 — pas de vue de ce genre
                continue
            for b in arch.xpath("//button[@type='object'][@name]"):
                nom = b.get("name")
                if nom.startswith("_") or not hasattr(type(Modele), nom):
                    continue
                boutons.setdefault(nom, (b.get("string") or b.get("title") or b.get("aria-label") or nom).strip())
        return boutons

    # ---------------------------------------------------------------- les outils

    def _outils(self):
        filtres = {"type": "array", "description": "Filtres, tous vrais ensemble. Exemple : [{\"champ\": \"state\", \"operateur\": \"=\", \"valeur\": \"draft\"}]",
                   "items": {"type": "object", "properties": {"champ": {"type": "string"}, "operateur": {"type": "string", "enum": list(OPERATEURS)},
                                                              "valeur": {"type": "string", "description": "La valeur, en texte (un nombre, une date AAAA-MM-JJ, true/false, ou une liste [1, 2])"}},
                             "required": ["champ", "valeur"]}}
        modele = {"type": "string", "description": "Nom technique du type de fiche (ex. sale.order)"}
        ids = {"type": "array", "items": {"type": "integer"}, "description": "Identifiants des fiches"}

        def outil(nom, description, proprietes, requis):
            return {"type": "function", "function": {"name": nom, "description": description, "parameters": {"type": "object", "properties": proprietes, "required": requis}}}

        return super()._outils() + [
            outil("types_de_fiche", "Trouve le nom technique d'un type de fiche de l'ERP à partir de mots (facture, congé, véhicule, bon de livraison…).",
                  {"texte": {"type": "string"}}, ["texte"]),
            outil("champs_et_boutons", "Les champs d'un type de fiche (nom technique, libellé, type, obligatoire, choix possibles) et les boutons de la fiche.",
                  {"modele": modele, "texte": {"type": "string", "description": "Pour ne garder que les champs dont le nom ou le libellé contient ce mot"}}, ["modele"]),
            outil("trouver_fiches", "Cherche et lit des fiches de n'importe quel type : par texte (le nom), par filtres, ou par identifiants.",
                  {"modele": modele, "texte": {"type": "string"}, "filtres": filtres, "ids": ids,
                   "champs": {"type": "array", "items": {"type": "string"}, "description": "Champs à lire (noms techniques)"},
                   "ordre": {"type": "string", "description": "ex. create_date desc"}, "limite": {"type": "integer", "description": f"1 à {LECTURE_MAX} (10 par défaut)"}}, ["modele"]),
            outil("compter_fiches", "Compte des fiches, au besoin regroupées par un champ et avec la somme d'un champ numérique.",
                  {"modele": modele, "filtres": filtres, "regrouper_par": {"type": "string"}, "somme": {"type": "string"}}, ["modele"]),
            outil("creer_fiche", "Crée une fiche de n'importe quel type (devis, facture, commande fournisseur, rendez-vous, article…). Proposé à la personne, fait après son clic.",
                  {"modele": modele, "valeurs": {"type": "object", "description": "{champ: valeur}. Lien : identifiant ou nom exact. Lignes : liste d'objets."}}, ["modele", "valeurs"]),
            outil("modifier_fiche", "Modifie une ou plusieurs fiches. Archiver : active à false. Modifier une ligne : {\"id\": n, …} dans la liste ; ajouter une ligne : un objet sans id.",
                  {"modele": modele, "ids": ids, "valeurs": {"type": "object", "description": "{champ: nouvelle valeur}"}}, ["modele", "ids", "valeurs"]),
            outil("appuyer_bouton", "Appuie sur un bouton de la fiche (confirmer un devis, valider une facture, annuler, marquer fait…). Les boutons sont donnés par champs_et_boutons.",
                  {"modele": modele, "ids": ids, "bouton": {"type": "string", "description": "Nom technique du bouton (ex. action_confirm)"}}, ["modele", "ids", "bouton"]),
        ]

    def _ecritures(self):
        return super()._ecritures() | ECRITURES_TOUT

    def _titres(self):
        return {**super()._titres(), **TITRES_TOUT}

    def _systeme(self):
        return super()._systeme() + AIDE.format(utilisateur=self.env.user.name)

    def _lire(self, fiches, champs):
        res = []
        for ligne in fiches.read(champs):
            propre = {}
            for k, v in ligne.items():
                if v in (False, None, "", []) and not isinstance(v, (int, float)):
                    continue
                if isinstance(v, (bytes, bytearray)):
                    v = "(fichier)"
                elif isinstance(v, list) and len(v) > 12 and all(isinstance(i, int) for i in v):
                    v = v[:12] + [f"… {len(v) - 12} de plus"]
                elif isinstance(v, str) and len(v) > 600:
                    v = v[:600] + "…"
                propre[k] = v
            res.append(propre)
        return res

    def _champs_par_defaut(self, Modele):
        voulus = ["display_name", "state", "partner_id", "date", "date_order", "invoice_date", "amount_total", "amount_residual", "user_id", "stage_id", "date_deadline",
                  "phone", "email", "city", "default_code", "list_price", "qty_available", "product_id", "quantity", "product_uom_qty", "price_unit", "active"]
        return [c for c in voulus if c in Modele._fields]

    def _verifier(self, nom, args):
        """Avant de proposer une écriture : ce qui ne tient pas debout est rendu au modèle, pas montré à la personne."""
        if nom == "creer_fiche":
            self._valeurs(self._modele_ouvert(args.get("modele"), "create"), args.get("valeurs"))
        elif nom == "modifier_fiche":
            Modele = self._modele_ouvert(args.get("modele"), "write")
            self._fiches(Modele, args.get("ids"))
            self._valeurs(Modele, args.get("valeurs"))
        elif nom == "appuyer_bouton":
            Modele = self._modele_ouvert(args.get("modele"), "write")
            self._fiches(Modele, args.get("ids"))
            boutons = self._boutons(Modele)
            if args.get("bouton") not in boutons:
                raise UserError(f"Pas de bouton « {args.get('bouton')} » sur cette fiche. Boutons : {', '.join(f'{k} ({v})' for k, v in boutons.items()) or 'aucun'}.")
        else:
            return super()._verifier(nom, args)

    def _executer(self, nom, args):
        if nom == "types_de_fiche":
            mots = [m for m in (args.get("texte") or "").lower().split() if len(m) > 2] or [""]
            domaine = [("transient", "=", False)]
            for m in mots[:3]:
                domaine += ["|", ("name", "ilike", m), ("model", "ilike", m)]
            res, vus = [], set()
            for m in mots:
                cible = MOTS.get(m) or MOTS.get(m.rstrip("s"))
                if cible and cible not in vus and cible in self.env and self.env[cible].has_access("read"):
                    vus.add(cible)
                    res.append({"modele": cible, "nom": self.env[cible]._description})
            connus = len(res)
            for im in self.env["ir.model"].sudo().with_context(lang=self.env.user.lang or "fr_FR").search(domaine, limit=200):
                if im.model in self.env and not any(im.model.startswith(p) for p in INTERDITS) and not self.env[im.model]._abstract and self.env[im.model].has_access("read") \
                        and im.model not in vus:
                    res.append({"modele": im.model, "nom": im.name})
            res[connus:] = sorted(res[connus:], key=lambda r: (r["modele"].count("."), len(r["modele"])))
            return res[:25] or {"rien": "aucun type de fiche pour ces mots ; essayez un autre mot"}, None
        if nom == "champs_et_boutons":
            Modele = self._modele_ouvert(args.get("modele"))
            mot = (args.get("texte") or "").lower()
            champs = []
            for c, d in Modele.fields_get(attributes=["string", "type", "required", "readonly", "relation", "selection", "store"]).items():
                if not self._champ_ouvert(c) or c in ("id", "write_uid", "write_date", "create_uid", "display_name"):
                    continue
                if mot and mot not in c.lower() and mot not in (d.get("string") or "").lower():
                    continue
                ligne = {"champ": c, "libelle": d.get("string"), "type": d["type"]}
                if d.get("required"):
                    ligne["obligatoire"] = True
                if d.get("readonly"):
                    ligne["calcule"] = True
                if d.get("relation"):
                    ligne["vers"] = d["relation"]
                if d.get("selection"):
                    ligne["choix"] = {k: v for k, v in d["selection"][:20]}
                champs.append(ligne)
            # d'abord ce qu'il faut remplir, puis ce qui se saisit, puis le reste
            champs.sort(key=lambda l: (not l.get("obligatoire"), bool(l.get("calcule")), l["champ"]))
            return {"type_de_fiche": Modele._description, "champs": champs[:90], "autres_champs": max(0, len(champs) - 90),
                    "boutons": [{"bouton": k, "libelle": v} for k, v in self._boutons(Modele).items()]}, None
        if nom == "trouver_fiches":
            Modele = self._modele_ouvert(args.get("modele"))
            champs = [c for c in (args.get("champs") or []) if c in Modele._fields and self._champ_ouvert(c)] or self._champs_par_defaut(Modele)
            limite = max(1, min(int(args.get("limite") or 10), LECTURE_MAX))
            if args.get("ids"):
                fiches = self._fiches(Modele, args["ids"])
            else:
                domaine = self._domaine(Modele, args.get("filtres"))
                if args.get("texte"):
                    domaine.append(("id", "in", [i for i, _n in Modele.name_search(args["texte"], limit=200)]))
                fiches = Modele.search(domaine, limit=limite, order=args.get("ordre") or None)
            return {"type_de_fiche": Modele._description, "fiches": self._lire(fiches[:limite], champs), "total": len(fiches) if args.get("ids") else Modele.search_count(domaine)}, None
        if nom == "compter_fiches":
            Modele = self._modele_ouvert(args.get("modele"))
            domaine = self._domaine(Modele, args.get("filtres"))
            groupe, somme = args.get("regrouper_par"), args.get("somme")
            if somme and (somme not in Modele._fields or Modele._fields[somme].type not in ("integer", "float", "monetary")):
                raise UserError(f"« {somme} » n'est pas un champ numérique de {Modele._name}.")
            if not groupe:
                res = {"nombre": Modele.search_count(domaine)}
                if somme:
                    res["somme"] = round(sum(Modele.search(domaine, limit=5000).mapped(somme)), 2)
                return res, None
            if groupe.split(":")[0] not in Modele._fields:
                raise UserError(f"« {groupe} » n'est pas un champ de {Modele._name}.")
            lignes = Modele.read_group(domaine, [somme] if somme else [], [groupe], limit=40, lazy=True)
            cle = groupe.split(":")[0]
            return [{"groupe": (l.get(groupe) or l.get(cle) or "(vide)") if not isinstance(l.get(groupe) or l.get(cle), (list, tuple)) else (l.get(groupe) or l.get(cle))[1],
                     "nombre": l.get(f"{cle}_count", l.get("__count")), **({"somme": round(l.get(somme) or 0, 2)} if somme else {})} for l in lignes], None
        if nom == "creer_fiche":
            Modele = self._modele_ouvert(args.get("modele"), "create")
            fiche = Modele.create(self._valeurs(Modele, args.get("valeurs")))
            return ({"cree": True, "modele": Modele._name, "id": fiche.id, "nom": fiche.display_name},
                    {"type": "lien", "modele": Modele._name, "id": fiche.id, "libelle": fiche.display_name or "Ouvrir"})
        if nom == "modifier_fiche":
            Modele = self._modele_ouvert(args.get("modele"), "write")
            fiches = self._fiches(Modele, args.get("ids"))
            fiches.write(self._valeurs(Modele, args.get("valeurs")))
            return {"modifie": True, "modele": Modele._name, "fiches": [{"id": f.id, "nom": f.display_name} for f in fiches]}, None
        if nom == "appuyer_bouton":
            self._verifier(nom, args)
            Modele = self._modele_ouvert(args.get("modele"), "write")
            fiches = self._fiches(Modele, args.get("ids"))
            retour = getattr(fiches, args["bouton"])()
            action = None
            if isinstance(retour, dict) and retour.get("type", "").startswith("ir.actions."):
                # le bouton ouvre un écran (un courriel à relire, un assistant) : la personne le voit et finit elle-même
                action = {"type": "action", "action": json.loads(json.dumps(retour, default=str))}
            fiches.invalidate_recordset()
            etat = {f.id: f.state for f in fiches} if "state" in Modele._fields else {}
            return {"fait": True, "bouton": args["bouton"], "fiches": [{"id": f.id, "nom": f.display_name, **({"etat": etat[f.id]} if etat else {})} for f in fiches],
                    **({"ecran_ouvert": "la personne doit terminer dans l'écran qui s'ouvre"} if action else {})}, action
        return super()._executer(nom, args)

    # ---------------------------------------------------------------- ce que la personne lit avant de confirmer

    def _dire(self, Modele, valeurs, niveau=0):
        morceaux = []
        for nom, v in (self._objet(valeurs) or {}).items():
            champ = Modele._fields.get(nom)
            if not champ:
                continue
            if champ.type == "many2one":
                try:
                    v = self.env[champ.comodel_name].browse(self._lien(champ, v)).display_name or "(vide)"
                except (UserError, AccessError):
                    pass
            elif champ.type in ("one2many", "many2many") and isinstance(v, list):
                Autre = self.env[champ.comodel_name]
                if niveau == 0 and all(isinstance(e, dict) for e in v):
                    v = f"{len(v)} ligne{'s' if len(v) > 1 else ''} (" + " | ".join(self._dire(Autre, {k: x for k, x in e.items() if k != 'id'}, 1) for e in v[:6]) + ("…" if len(v) > 6 else "") + ")"
                else:
                    v = f"{len(v)} élément{'s' if len(v) > 1 else ''}"
            elif champ.type == "selection":
                v = dict(champ._description_selection(self.env)).get(v, v)
            elif champ.type == "boolean":
                v = "oui" if v else "non"
            morceaux.append(f"{champ.string} : {v}")
        return " · ".join(morceaux)

    def _resumer(self, nom, args):
        if nom not in ECRITURES_TOUT:
            return super()._resumer(nom, args)
        try:
            Modele = self.env[args.get("modele")]
            if nom == "creer_fiche":
                return f"{Modele._description} · {self._dire(Modele, args.get('valeurs'))}"[:600]
            fiches = self._fiches(Modele, args.get("ids"))
            noms = ", ".join(f.display_name or f"n° {f.id}" for f in fiches[:8]) + (f" et {len(fiches) - 8} autres" if len(fiches) > 8 else "")
            if nom == "modifier_fiche":
                return f"{Modele._description} {noms} · {self._dire(Modele, args.get('valeurs'))}"[:600]
            return f"« {self._boutons(Modele).get(args.get('bouton'), args.get('bouton'))} » sur {Modele._description} {noms}"[:600]
        except Exception:  # noqa: BLE001 — le résumé ne doit jamais empêcher la proposition
            return json.dumps(args, ensure_ascii=False, default=str)[:300]
