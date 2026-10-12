"""Le rapport du lundi : chaque lundi matin, le gérant reçoit la semaine écoulée en chiffres et ce qui attend.

Chiffre d'affaires facturé et encaissé, devis envoyés et signés, interventions faites, heures de chantier, nouveaux clients,
courriels et délai de réponse ; puis les tuiles de l'écran « Aujourd'hui » vues par le gérant, et les absents de la semaine.
"""
from datetime import datetime, time, timedelta

from markupsafe import Markup, escape

from odoo import api, fields, models

from .aujourdhui import _euros

COULEURS = {"rouge": "#c9473d", "ambre": "#d99a1e", "bleu": "#3b7dd8", "vert": "#2e9d63"}


class Rapport(models.AbstractModel):
    _name = "cultiveau.rapport"
    _description = "Le rapport du lundi"

    @api.model
    def semaine(self, company, lundi=None):
        """Les chiffres de la semaine du lundi donné (la semaine écoulée par défaut)."""
        aujourd_hui = fields.Date.context_today(self)
        lundi = lundi or (aujourd_hui - timedelta(days=aujourd_hui.weekday() + 7))
        dimanche = lundi + timedelta(days=6)
        debut, fin = datetime.combine(lundi, time.min), datetime.combine(dimanche, time.max)
        env = self.sudo().with_company(company).with_context(allowed_company_ids=[company.id]).env
        Move = env["account.move"]
        factures = Move.search([("company_id", "=", company.id), ("move_type", "in", ("out_invoice", "out_refund")), ("state", "=", "posted"),
                                ("invoice_date", ">=", lundi), ("invoice_date", "<=", dimanche)])
        paiements = env["account.payment"].search([("company_id", "=", company.id), ("payment_type", "=", "inbound"), ("state", "not in", ("draft", "canceled")),
                                                    ("date", ">=", lundi), ("date", "<=", dimanche)])
        Order = env["sale.order"]
        envoyes = Order.search_count([("company_id", "=", company.id), ("state", "in", ("sent", "sale")), ("date_order", ">=", debut), ("date_order", "<=", fin)])
        signes = Order.search([("company_id", "=", company.id), ("state", "=", "sale"), ("date_order", ">=", debut), ("date_order", "<=", fin)])
        Task = env["project.task"]
        faites = Task.search_count([("company_id", "=", company.id), ("state", "=", "1_done"), ("date_last_stage_update", ">=", debut), ("date_last_stage_update", "<=", fin)]
                                   + ([("cultiveau_intervention", "=", True)] if "cultiveau_intervention" in Task._fields else []))
        heures = sum(env["cultiveau.chantier.pointage"].search([("company_id", "=", company.id), ("date", ">=", lundi), ("date", "<=", dimanche)]).mapped("heures"))
        clients = env["res.partner"].search_count([("create_date", ">=", debut), ("create_date", "<=", fin), ("company_id", "in", (company.id, False)), ("customer_rank", ">", 0)])
        res = {"lundi": lundi, "dimanche": dimanche, "facture": sum(factures.mapped("amount_untaxed_signed")), "encaisse": sum(paiements.mapped("amount_company_currency_signed")),
               "devis_envoyes": envoyes, "devis_signes": len(signes), "signe_montant": sum(signes.mapped("amount_untaxed")), "interventions": faites,
               "heures_chantier": heures, "nouveaux_clients": clients}
        if "cultiveau.courriel" in env:
            C = env["cultiveau.courriel"]
            recus = C.search([("company_id", "=", company.id), ("date_reception", ">=", debut), ("date_reception", "<=", fin), ("masse", "=", False)])
            repondus = recus.filtered(lambda c: c.date_reponse)
            delais = [(c.date_reponse - c.date_reception).total_seconds() / 3600 for c in repondus if c.date_reponse >= c.date_reception]
            res.update({"courriels": len(recus), "courriels_repondus": len(repondus), "delai_reponse_h": round(sum(delais) / len(delais)) if delais else 0})
        return res

    def _corps(self, company, gerant):
        s = self.semaine(company)
        tuiles = self.env["cultiveau.aujourdhui"].with_user(gerant).with_company(company).tuiles()
        absents = []
        if "cultiveau.conges" in self.env:
            lundi = fields.Date.context_today(self) + timedelta(days=(7 - fields.Date.context_today(self).weekday()) % 7)
            absents = [a for a in self.env["cultiveau.conges"].with_user(gerant).with_company(company).absences(lundi, lundi + timedelta(days=4), company) if a["etat"] == "validate"]
        chiffres = [("Facturé", _euros(s["facture"]) + " HT"), ("Encaissé", _euros(s["encaisse"])),
                    ("Devis signés", f"{s['devis_signes']} · {_euros(s['signe_montant'])} HT"), ("Devis envoyés", str(s["devis_envoyes"])),
                    ("Interventions faites", str(s["interventions"])), ("Heures de chantier", f"{s['heures_chantier']:g} h"),
                    ("Nouveaux clients", str(s["nouveaux_clients"]))]
        if "courriels" in s:
            chiffres.append(("Courriels reçus", f"{s['courriels']} · {s['courriels_repondus']} répondus" + (f" en {s['delai_reponse_h']} h en moyenne" if s["delai_reponse_h"] else "")))
        style_cellule = "padding:8px 10px;border-bottom:1px solid #e3e9eb;"
        lignes = Markup("").join(Markup('<tr><td style="%s color:#5d6b78">%s</td><td style="%s font-weight:700">%s</td></tr>') % (style_cellule, n, style_cellule, v) for n, v in chiffres)
        blocs = Markup("")
        for t in tuiles:
            items = Markup("").join(Markup("<li>%s<span style='color:#5d6b78'>%s</span></li>") % (l["texte"], f" · {l['detail']}" if l["detail"] else "") for l in t["lignes"])
            blocs += Markup('<div style="border-left:4px solid %s;padding:6px 12px;margin:10px 0"><b>%s : %s</b>%s<ul style="margin:6px 0 0;padding-left:18px">%s</ul></div>') % (
                COULEURS.get(t["couleur"], "#3b7dd8"), t["titre"], t["nombre"], Markup(" <span style='color:#5d6b78'>· %s</span>") % t["detail"] if t["detail"] else "", items)
        if not tuiles:
            blocs = Markup("<p>Rien en retard : tout est à jour.</p>")
        abs_html = Markup("")
        if absents:
            abs_html = Markup("<h3 style='color:#183840'>Absents cette semaine</h3><ul>%s</ul>") % Markup("").join(
                Markup("<li>%s · %s</li>") % (a["employe"], a["periode"]) for a in absents)
        base = self.env["ir.config_parameter"].sudo().get_param("web.base.url") or ""
        return Markup("""<div style="font-family:Arial,sans-serif;color:#1d2a30;max-width:640px">
<h2 style="color:#183840;margin-bottom:2px">Bonjour %s,</h2>
<p style="color:#5d6b78;margin-top:0">La semaine du %s au %s chez %s.</p>
<table style="border-collapse:collapse;width:100%%">%s</table>
<h3 style="color:#183840;margin-top:22px">À traiter</h3>%s%s
<p style="margin-top:22px"><a href="%s/odoo/action-cultiveau_quotidien.action_aujourdhui" style="background:#0b8aa3;color:#fff;padding:10px 16px;border-radius:8px;text-decoration:none">Ouvrir « Aujourd'hui »</a></p>
<p style="color:#8796a0;font-size:12px">Le rapport du lundi de l'ERP Cultiveau. Pour ne plus le recevoir : Réglages → Cultiveau → Pilotage au quotidien.</p>
</div>""") % (escape(gerant.name.split(" ")[0]), s["lundi"].strftime("%d/%m"), s["dimanche"].strftime("%d/%m"), company.name, lignes, blocs, abs_html, base)

    @api.model
    def envoyer(self, company=None, gerants=None):
        """Envoie le rapport aux gérants (ou aux personnes données). Renvoie le nombre de courriels préparés."""
        n = 0
        for c in company or self.env["res.company"].sudo().search([]):
            destinataires = gerants or self.env["cultiveau.equipe"].gerants(c)
            for g in destinataires.filtered("email"):
                self.env["mail.mail"].sudo().create({
                    "subject": f"Votre semaine chez {c.name} — rapport du lundi", "body_html": self._corps(c, g), "email_to": g.email_formatted,
                    "email_from": c.email_formatted or self.env.user.email_formatted, "auto_delete": True})
                n += 1
        return n

    @api.model
    def _cron_lundi(self):
        if self.env["ir.config_parameter"].sudo().get_param("cultiveau.rapport_lundi", "True") in ("False", "0", ""):
            return
        self.envoyer()
