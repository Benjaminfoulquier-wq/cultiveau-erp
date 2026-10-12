"""L'écran « Aujourd'hui » : une tuile par chose à traiter, avec ses premières lignes et un lien vers la liste complète.

Chaque tuile est calculée avec les droits de la personne : elle ne voit que ce qu'elle peut ouvrir. Les tuiles vides
disparaissent ; l'ordre va du plus pressant au moins pressant. Mathis lit les mêmes tuiles (« qu'est-ce que j'ai à faire ? »)
et le rapport du lundi les reprend pour le gérant.
"""
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError


def _euros(m):
    return f"{m:,.0f}".replace(",", " ") + " €"


def _liste(nom, modele, domaine, vue="list"):
    return {"type": "ir.actions.act_window", "name": nom, "res_model": modele, "domain": domaine,
            "views": [[False, vue], [False, "form"]], "target": "current"}


class Aujourdhui(models.AbstractModel):
    _name = "cultiveau.aujourdhui"
    _description = "L'écran Aujourd'hui"

    @api.model
    def tuiles(self):
        """[{cle, titre, nombre, detail, couleur, icone, lignes: [{texte, detail, modele, id}], action}] dans l'ordre d'urgence."""
        res = []
        for methode in self._sources():
            try:
                t = methode()
            except AccessError:
                t = None
            if t and t.get("nombre"):
                res.append(t)
        ordre = {"rouge": 0, "ambre": 1, "bleu": 2, "vert": 3}
        return sorted(res, key=lambda t: ordre.get(t.get("couleur"), 2))

    def _sources(self):
        return [self._t_courriels, self._t_factures_echues, self._t_devis_a_relancer, self._t_interventions_retard, self._t_chantiers_budget,
                self._t_conges, self._t_frais, self._t_stock_bas, self._t_bons_a_facturer, self._t_rdv_du_jour]

    def _gerant(self):
        return self.env.user.has_group("sales_team.group_sale_manager")

    def _tuile(self, cle, titre, records, texte, detail=None, couleur="ambre", icone="fa-circle", action=None, total=None, resume=""):
        lignes = [{"texte": texte(r), "detail": detail(r) if detail else "", "modele": r._name, "id": r.id} for r in records[:5]]
        return {"cle": cle, "titre": titre, "nombre": total if total is not None else len(records), "detail": resume, "couleur": couleur, "icone": icone,
                "lignes": lignes, "action": action}

    # ---------------------------------------------------------------- les tuiles

    def _t_courriels(self):
        if "cultiveau.courriel" not in self.env:
            return None
        C = self.env["cultiveau.courriel"]
        domaine = [("etat", "=", "a_traiter"), ("sans_reponse", "=", True), ("company_id", "=", self.env.company.id)]
        if not self._gerant():
            domaine.append(("user_id", "=", self.env.user.id))
        recs = C.search(domaine, order="date_reception")
        return self._tuile("courriels", "Courriels sans réponse", recs, lambda c: f"{c.expediteur_nom} · {c.name}", lambda c: f"{c.attente_jours} j",
                           couleur="rouge", icone="fa-envelope", action=_liste("Courriels sans réponse", "cultiveau.courriel", domaine),
                           resume=f"{C.search_count([('etat', '=', 'a_traiter'), ('company_id', '=', self.env.company.id)])} à traiter en tout")

    def _t_factures_echues(self):
        if not (self._gerant() or self.env.user.has_group("account.group_account_invoice")):
            return None
        aujourd_hui = fields.Date.context_today(self)
        domaine = [("move_type", "=", "out_invoice"), ("state", "=", "posted"), ("payment_state", "in", ("not_paid", "partial")),
                   ("invoice_date_due", "<", aujourd_hui), ("company_id", "=", self.env.company.id)]
        recs = self.env["account.move"].search(domaine, order="invoice_date_due")
        du = sum(recs.mapped("amount_residual"))
        return self._tuile("factures", "Factures échues", recs, lambda f: f"{f.partner_id.name} · {f.name}",
                           lambda f: f"{_euros(f.amount_residual)} · {(aujourd_hui - f.invoice_date_due).days} j", couleur="rouge", icone="fa-euro",
                           action=_liste("Factures échues", "account.move", domaine), resume=f"{_euros(du)} à encaisser")

    def _t_devis_a_relancer(self):
        il_y_a = fields.Datetime.now() - timedelta(days=int(self.env["ir.config_parameter"].sudo().get_param("cultiveau.jours_relance_devis") or 7))
        domaine = [("state", "=", "sent"), ("write_date", "<", il_y_a), ("company_id", "=", self.env.company.id)]
        if not self._gerant():
            domaine.append(("user_id", "=", self.env.user.id))
        recs = self.env["sale.order"].search(domaine, order="write_date")
        return self._tuile("devis", "Devis à relancer", recs, lambda d: f"{d.partner_id.name} · {d.name}", lambda d: _euros(d.amount_untaxed) + " HT",
                           icone="fa-file-text-o", action=_liste("Devis à relancer", "sale.order", domaine), resume=f"{_euros(sum(recs.mapped('amount_untaxed')))} HT en jeu")

    def _t_interventions_retard(self):
        Task = self.env["project.task"]
        if "cultiveau_intervention" not in Task._fields:
            return None
        aujourd_hui = fields.Date.context_today(self)
        domaine = [("cultiveau_intervention", "=", True), ("state", "not in", ("1_done", "1_canceled")), ("date_deadline", "<", fields.Datetime.now().replace(hour=0, minute=0, second=0)),
                   ("company_id", "=", self.env.company.id)]
        if not self._gerant():
            domaine.append(("user_ids", "in", self.env.user.id))
        recs = Task.search(domaine, order="date_deadline")
        return self._tuile("interventions", "Interventions en retard", recs, lambda t: f"{t.partner_id.name or ''} · {t.name}",
                           lambda t: f"{(aujourd_hui - t.date_deadline.date()).days} j" if t.date_deadline else "", couleur="rouge", icone="fa-bolt",
                           action=_liste("Interventions en retard", "project.task", domaine))

    def _t_chantiers_budget(self):
        domaine = [("budget_etat", "in", ("attention", "depasse")), ("etat", "in", ("planifie", "en_cours")), ("company_id", "=", self.env.company.id)]
        recs = self.env["cultiveau.chantier"].search(domaine, order="budget_pct desc")
        couleur = "rouge" if any(c.budget_etat == "depasse" for c in recs) else "ambre"
        return self._tuile("chantiers", "Chantiers en dépassement", recs, lambda c: c.display_name, lambda c: f"{c.budget_pct} % des heures",
                           couleur=couleur, icone="fa-wrench", action=_liste("Chantiers en dépassement", "cultiveau.chantier", domaine))

    def _t_conges(self):
        if "cultiveau.conges" not in self.env or not self.env["cultiveau.equipe"].est_gerant():
            return None
        lignes = self.env["cultiveau.conges"].a_valider()
        recs = self.env["hr.leave"].browse([l["id"] for l in lignes])
        return self._tuile("conges", "Congés à valider", recs, lambda l: f"{l.employee_id.name} · {self.env['cultiveau.conges']._periode(l)}",
                           lambda l: f"{l.number_of_days:g} j", couleur="bleu", icone="fa-plane",
                           action=_liste("Congés à valider", "hr.leave", [("id", "in", recs.ids)]))

    def _t_frais(self):
        if "cultiveau.frais" not in self.env or not self.env["cultiveau.equipe"].est_gerant():
            return None
        lignes = self.env["cultiveau.frais"].a_valider()
        recs = self.env["hr.expense.sheet"].browse([l["id"] for l in lignes])
        return self._tuile("frais", "Notes de frais à valider", recs, lambda f: f.employee_id.name, lambda f: _euros(f.total_amount), couleur="bleu",
                           icone="fa-ticket", action=_liste("Notes de frais à valider", "hr.expense.sheet", [("id", "in", recs.ids)]),
                           resume=_euros(sum(recs.mapped("total_amount"))))

    def _t_stock_bas(self):
        if not self.env.user.has_group("stock.group_stock_user"):
            return None
        points = self.env["stock.warehouse.orderpoint"].search([("company_id", "=", self.env.company.id), ("trigger", "in", ("auto", "manual"))])
        bas = points.filtered(lambda p: p.qty_forecast < p.product_min_qty)
        return self._tuile("stock", "Stock sous le minimum", bas, lambda p: p.product_id.display_name, lambda p: f"{p.qty_forecast:g} / mini {p.product_min_qty:g}",
                           icone="fa-cubes", action=_liste("Stock sous le minimum", "stock.warehouse.orderpoint", [("id", "in", bas.ids)]))

    def _t_bons_a_facturer(self):
        if "cultiveau.bon" not in self.env or not (self._gerant() or self.env.user.has_group("account.group_account_invoice")):
            return None
        domaine = [("etat", "=", "signe"), ("company_id", "=", self.env.company.id)]
        recs = self.env["cultiveau.bon"].search(domaine, order="signe_le")
        return self._tuile("bons", "Bons signés à facturer", recs, lambda b: f"{b.partner_id.name} · {b.name}", lambda b: _euros(b.montant_ht),
                           icone="fa-pencil-square-o", action=_liste("Bons à facturer", "cultiveau.bon", domaine), resume=_euros(sum(recs.mapped("montant_ht"))) + " HT")

    def _t_rdv_du_jour(self):
        debut = fields.Datetime.now().replace(hour=0, minute=0, second=0)
        domaine = [("partner_ids", "in", self.env.user.partner_id.id), ("start", ">=", debut), ("start", "<", debut + timedelta(days=1))]
        recs = self.env["calendar.event"].search(domaine, order="start")
        return self._tuile("agenda", "Rendez-vous du jour", recs, lambda e: e.name,
                           lambda e: "journée" if e.allday else fields.Datetime.context_timestamp(e, e.start).strftime("%H:%M"), couleur="vert", icone="fa-calendar",
                           action={"type": "ir.actions.act_window", "name": "Agenda", "res_model": "calendar.event", "views": [[False, "calendar"], [False, "list"]], "target": "current"})

    @api.model
    def ecran(self):
        """L'écran complet : le bonjour, la date, les tuiles."""
        jours = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
        mois = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
        d = fields.Date.context_today(self)
        tuiles = self.tuiles()
        return {"bonjour": f"Bonjour {(self.env.user.name or '').split(' ')[0]}", "date": f"{jours[d.weekday()]} {d.day} {mois[d.month - 1]}",
                "societe": self.env.company.name, "tuiles": tuiles, "total": sum(t["nombre"] for t in tuiles),
                "urgent": sum(t["nombre"] for t in tuiles if t["couleur"] == "rouge")}
