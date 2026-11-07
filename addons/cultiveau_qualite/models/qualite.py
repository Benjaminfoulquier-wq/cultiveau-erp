"""La page Qualité des données : ce qui manque, ce qui doublonne, pourquoi ça compte, et la liste à corriger."""
import re
from collections import defaultdict
from datetime import timedelta

from markupsafe import Markup, escape

from odoo import api, fields, models


def _tel(t):
    return re.sub(r"\D", "", t or "")[-9:] if t else ""


class Qualite(models.TransientModel):
    _name = "cultiveau.qualite"
    _description = "Qualité des données"

    name = fields.Char(default="Qualité des données")
    company_id = fields.Many2one("res.company", "Société", required=True, default=lambda self: self.env.company)
    html = fields.Html("Qualité des données", compute="_compute_html", sanitize=False)
    score = fields.Integer("Score", compute="_compute_html")
    nb_points = fields.Integer("Points à corriger", compute="_compute_html")

    @api.model
    def action_ouvrir(self):
        q = self.create({"company_id": self.env.company.id})
        return {"type": "ir.actions.act_window", "res_model": self._name, "res_id": q.id, "view_mode": "form", "target": "current", "name": "Qualité des données"}

    # ---------------------------------------------------------------- les contrôles
    def controles(self):
        """[(groupe, libellé, nombre, pourquoi, modèle, domaine, contexte)] ; nombre 0 = rien à faire."""
        self.ensure_one()
        c = self.company_id
        env = self.env
        Partner = env["res.partner"].with_company(c)
        clients = [("company_id", "in", [c.id, False]), ("parent_id", "=", False), ("cultiveau_est_client", "=", True)]
        contacts = [("company_id", "in", [c.id, False]), ("parent_id", "=", False), ("is_company", "=", False), ("type", "=", "contact"), ("user_ids", "=", False), ("supplier_rank", "=", 0)]
        res = []
        # --- clients
        sans_type = contacts + [("cultiveau_type", "=", False), ("customer_rank", ">", 0)]
        res.append(("Clients", "Clients sans type de contact", Partner.search_count(sans_type), "Le type choisit le véhicule au parking, les newsletters et la grille de remises.",
                    "res.partner", sans_type, {}))
        types = Partner.read_group(clients, ["cultiveau_type"], ["cultiveau_type"])
        if len(types) == 1 and Partner.search_count(clients) >= 20:
            res.append(("Clients", f"Tous les clients ont le même type ({dict(Partner._fields['cultiveau_type'].selection).get(types[0]['cultiveau_type'], '')})", Partner.search_count(clients),
                        "Impossible que ce soit vrai : paysagistes, collectivités, plombiers, particuliers manquent. La map et les newsletters en dépendent.", "res.partner", clients, {}))
        res.append(("Clients", "Clients sans téléphone ni e-mail", Partner.search_count(clients + [("phone", "=", False), ("mobile", "=", False), ("email", "=", False)]),
                    "Injoignables depuis la map, le devis, la feuille de route du technicien.", "res.partner", clients + [("phone", "=", False), ("mobile", "=", False), ("email", "=", False)], {}))
        res.append(("Clients", "Clients sans e-mail", Partner.search_count(clients + [("email", "=", False)]), "Pas de devis signé en ligne, pas de newsletter, pas de facture par courriel.",
                    "res.partner", clients + [("email", "=", False)], {}))
        res.append(("Clients", "Clients sans commune", Partner.search_count(clients + [("city", "=", False)]), "Pas de département, donc pas de frise culturale ni d'itinéraire.",
                    "res.partner", clients + [("city", "=", False)], {}))
        # doublons : même téléphone, même e-mail, ou même nom et même commune
        tous = Partner.search(clients + [("active", "=", True)])
        par_tel, par_mail, par_nom = defaultdict(list), defaultdict(list), defaultdict(list)
        for p in tous:
            for t in (p.phone, p.mobile):
                if _tel(t):
                    par_tel[_tel(t)].append(p.id)
            if p.email:
                par_mail[p.email.strip().lower()].append(p.id)
            if p.name:
                par_nom[(re.sub(r"\s+", " ", p.name.strip().lower()), (p.city or "").strip().lower())].append(p.id)
        doublons = set()
        for d in (par_tel, par_mail, par_nom):
            for ids in d.values():
                if len(set(ids)) > 1:
                    doublons.update(ids)
        res.append(("Clients", "Clients en doublon probable (même téléphone, e-mail, ou nom et commune)", len(doublons), "Deux fiches, deux historiques, deux relances : fusionnez-les (Action › Fusionner).",
                    "res.partner", [("id", "in", list(doublons))], {"cultiveau_fusion": True}))
        # --- articles
        Produit = env["product.template"].with_company(c)
        miens = [("company_id", "=", c.id), ("sale_ok", "=", True)]
        res.append(("Articles", "Articles vendables sans prix", Produit.search_count(miens + [("list_price", "<=", 0)]), "Un devis qui sort à 0 € ; la ligne « à préciser » reste à préciser.",
                    "product.template", miens + [("list_price", "<=", 0)], {}))
        res.append(("Articles", "Articles sans référence", Produit.search_count(miens + [("default_code", "=", False)]), "Introuvables depuis Schéma 3D et les imports fournisseurs.",
                    "product.template", miens + [("default_code", "=", False)], {}))
        stockables = miens + [("is_storable", "=", True)]
        res.append(("Articles", "Articles stockables sans fournisseur", Produit.search_count(stockables + [("seller_ids", "=", False)]), "La liste de courses du devis ne sait pas à qui commander.",
                    "product.template", stockables + [("seller_ids", "=", False)], {}))
        # --- installations
        Inst = env["cultiveau.installation"]
        base_i = [("company_id", "=", c.id)]
        res.append(("Parc installé", "Installations en service sans pressions de référence (PV A1.3)", Inst.search_count(base_i + [("etat", "=", "en_service"), ("pv_pression_sortie_pompe_bar", "=", 0)]),
                    "Sans référence, on ne dépanne pas, on tâtonne (§ 18.9).", "cultiveau.installation", base_i + [("etat", "=", "en_service"), ("pv_pression_sortie_pompe_bar", "=", 0)], {}))
        res.append(("Parc installé", "Installations sans surface", Inst.search_count(base_i + [("surface_ha", "<=", 0)]), "Les ordres de grandeur à l'hectare et la frise en dépendent.",
                    "cultiveau.installation", base_i + [("surface_ha", "<=", 0)], {}))
        vieux = fields.Date.today() - timedelta(days=60)
        res.append(("Parc installé", "Études de plus de 60 jours sans analyse des besoins validée", Inst.search_count(base_i + [("etat", "in", ("projet", "etude")), ("analyse_validee_le", "=", False), ("create_date", "<", fields.Datetime.to_string(vieux))]),
                    "Un projet qui traîne sans A1.1 validée : à relancer ou à classer.", "cultiveau.installation", base_i + [("etat", "in", ("projet", "etude")), ("analyse_validee_le", "=", False)], {}))
        # --- interventions et bons
        Task = env["project.task"]
        base_t = [("company_id", "=", c.id), ("cultiveau_intervention", "=", True), ("state", "not in", ("1_done", "1_canceled"))]
        sans_tech = base_t + [("user_ids", "=", False), ("create_date", "<", fields.Datetime.to_string(fields.Datetime.now() - timedelta(days=7)))]
        if "cultiveau_salarie_ids" in Task._fields:
            sans_tech.append(("cultiveau_salarie_ids", "=", False))
        res.append(("Interventions", "Interventions ouvertes sans technicien depuis plus de 7 jours", Task.search_count(sans_tech), "Personne ne les verra dans Ma journée ni sur une feuille de route.",
                    "project.task", sans_tech, {}))
        sans_date = base_t + [("cultiveau_debut", "=", False)]
        res.append(("Interventions", "Interventions ouvertes sans date", Task.search_count(sans_date), "Absentes du planning et des feuilles de route.", "project.task", sans_date, {}))
        Bon = env["cultiveau.bon"]
        vieux_bons = [("company_id", "=", c.id), ("etat", "=", "brouillon"), ("date", "<", fields.Date.to_string(fields.Date.today() - timedelta(days=14)))]
        res.append(("Interventions", "Bons en brouillon depuis plus de 14 jours", Bon.search_count(vieux_bons), "Ni signés ni facturés : du chiffre d'affaires qui dort.", "cultiveau.bon", vieux_bons, {}))
        # --- devis
        Order = env["sale.order"]
        expires = [("company_id", "=", c.id), ("state", "in", ("draft", "sent")), ("validity_date", "<", fields.Date.to_string(fields.Date.today()))]
        res.append(("Devis", "Devis expirés sans décision", Order.search_count(expires), "Gagné, perdu, ou à prolonger : mais pas oublié.", "sale.order", expires, {}))
        sans_inst = [("company_id", "=", c.id), ("state", "in", ("draft", "sent", "sale")), ("cultiveau_type_systeme", "!=", False), ("cultiveau_installation_id", "=", False)]
        res.append(("Devis", "Devis d'installation sans installation reliée", Order.search_count(sans_inst), "Pas de dossier technique, pas de chantier déclenché, pas de registre.", "sale.order", sans_inst, {}))
        # --- la société
        manques = []
        if not c.bank_ids:
            manques.append("compte bancaire (RIB sur les factures, virement en ligne)")
        if not c.email:
            manques.append("e-mail de la société (expéditeur des devis et factures)")
        if not c.logo:
            manques.append("logo (devis, factures, map)")
        if "cultiveau_acompte_pct" in c._fields and not c.cultiveau_acompte_pct:
            manques.append("pourcentage d'acompte")
        if "cultiveau_cgv" in c._fields and not c.cultiveau_cgv:
            manques.append("conditions générales de vente")
        res.append(("Société", "Réglages de la société manquants : " + ", ".join(manques) if manques else "Réglages de la société", len(manques), "Ils s'impriment sur chaque document.",
                    "res.company", [("id", "=", c.id)], {"form": True}))
        return res

    @api.depends("company_id")
    def _compute_html(self):
        for q in self:
            ctrls = q.controles()
            a_faire = [x for x in ctrls if x[2]]
            q.nb_points = len(a_faire)
            q.score = max(0, round(100 - 100 * len(a_faire) / max(1, len(ctrls))))
            groupes = {}
            for i, (groupe, lib, n, pourquoi, modele, domaine, ctx) in enumerate(ctrls):
                groupes.setdefault(groupe, []).append((i, lib, n, pourquoi))
            parties = [f"<div class='d-flex align-items-baseline gap-3 mb-3'><div class='display-6 fw-bold'>{q.score} / 100</div><div class='text-muted'>{len(a_faire)} point(s) à corriger sur {len(ctrls)} contrôles, société {escape(q.company_id.name)}.</div></div>"]
            for groupe, lignes in groupes.items():
                corps = "".join(
                    f"<tr><td style='width:34px'>{'<span class=\"badge text-bg-success\">✓</span>' if not n else ('<span class=\"badge text-bg-danger\">' + str(n) + '</span>' if n >= 10 else '<span class=\"badge text-bg-warning\">' + str(n) + '</span>')}</td>"
                    f"<td><div>{escape(lib)}</div><div class='text-muted small'>{escape(pourquoi)}</div></td>"
                    f"<td class='text-end' style='width:140px'>{'<button class=\"btn btn-sm btn-secondary\" type=\"button\" data-controle=\"' + str(i) + '\">Voir et corriger</button>' if n else ''}</td></tr>"
                    for i, lib, n, pourquoi in lignes)
                parties.append(f"<h5 class='mt-3 mb-1'>{escape(groupe)}</h5><table class='table table-sm align-middle'><tbody>{corps}</tbody></table>")
            parties.append("<p class='small text-muted'>Les listes s'ouvrent avec le filtre du contrôle ; en vue liste, cochez plusieurs lignes pour modifier en masse (type, commune…). "
                           "Pour les doublons : sélectionnez-les puis Action › Fusionner.</p>")
            q.html = Markup("".join(parties))

    def action_voir(self, index):
        self.ensure_one()
        ctrls = self.controles()
        groupe, lib, n, pourquoi, modele, domaine, ctx = ctrls[int(index)]
        if ctx.get("form"):
            return {"type": "ir.actions.act_window", "res_model": modele, "res_id": self.company_id.id, "view_mode": "form", "target": "current"}
        return {"type": "ir.actions.act_window", "name": lib, "res_model": modele, "view_mode": "list,form", "views": [[False, "list"], [False, "form"]], "domain": domaine, "target": "current",
                "context": {"active_test": True, "search_default_cultiveau_qualite": 1}}
