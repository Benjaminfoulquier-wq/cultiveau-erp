"""La feuille de route : la journée d'un salarié (avec ou sans accès à l'ERP), par lien personnel et par e-mail la veille."""
import secrets
from datetime import datetime, time, timedelta
from urllib.parse import quote_plus

import pytz
from markupsafe import Markup, escape

from odoo import api, fields, models


class Task(models.Model):
    _inherit = "project.task"

    cultiveau_salarie_ids = fields.Many2many("hr.employee", "cultiveau_task_salarie_rel", "task_id", "employee_id", string="Salariés sans accès",
                                             domain="[('company_id', '=', company_id), ('user_id', '=', False)]",
                                             help="Les poseurs et techniciens qui n'ont pas de compte dans l'ERP : ils reçoivent leur feuille de route.")
    cultiveau_consignes = fields.Char("Consignes pour l'équipe", help="Une ligne sur la feuille de route : où entrer, qui appeler, quoi prendre.")


class Chantier(models.Model):
    _inherit = "cultiveau.chantier"

    salarie_ids = fields.Many2many("hr.employee", "cultiveau_chantier_salarie_rel", "chantier_id", "employee_id", string="Salariés sans accès",
                                   domain="[('company_id', '=', company_id), ('user_id', '=', False)]")


class Employee(models.Model):
    _inherit = "hr.employee"

    cultiveau_jeton = fields.Char("Jeton de la feuille de route", copy=False, groups="hr.group_hr_user")
    cultiveau_feuille_url = fields.Char("Lien de sa feuille de route", compute="_compute_feuille_url")
    cultiveau_feuille_mail = fields.Boolean("Recevoir sa journée la veille par e-mail", default=True)
    cultiveau_feuille_derniere = fields.Datetime("Dernière feuille envoyée", readonly=True, copy=False)

    def _jeton(self):
        self.ensure_one()
        if not self.sudo().cultiveau_jeton:
            self.sudo().cultiveau_jeton = secrets.token_urlsafe(24)
        return self.sudo().cultiveau_jeton

    @api.depends("cultiveau_jeton")
    def _compute_feuille_url(self):
        base = self.env["ir.config_parameter"].sudo().get_param("web.base.url") or ""
        for e in self:
            e.cultiveau_feuille_url = f"{base}/journee/{e._jeton()}" if e.id else ""

    def action_nouveau_jeton(self):
        for e in self:
            e.sudo().cultiveau_jeton = secrets.token_urlsafe(24)
        return True

    def action_envoyer_feuille(self):
        """La journée de demain (ou du lundi le vendredi) tout de suite, par e-mail."""
        F = self.env["cultiveau.feuille.route"]
        n = 0
        for e in self:
            n += F.envoyer(e, F.prochain_jour(e.company_id))
        return {"type": "ir.actions.client", "tag": "display_notification", "params": {"title": "Feuille de route", "message": f"{n} e-mail(s) préparé(s).", "type": "success" if n else "warning", "sticky": False}}

    def action_voir_feuille(self):
        self.ensure_one()
        return {"type": "ir.actions.act_url", "url": self.cultiveau_feuille_url, "target": "new"}


class FeuilleRoute(models.AbstractModel):
    _name = "cultiveau.feuille.route"
    _description = "Feuille de route d'un salarié"

    # ---------------------------------------------------------------- la journée
    def _tz(self, company):
        return pytz.timezone(company.partner_id.tz or "Europe/Paris")

    @api.model
    def prochain_jour(self, company, depuis=None):
        tz = self._tz(company)
        aujourdhui = depuis or datetime.now(tz).date()
        jour = aujourdhui + timedelta(days=1)
        while jour.weekday() >= 5:  # samedi, dimanche : la feuille du vendredi soir est celle du lundi
            jour += timedelta(days=1)
        return jour

    @api.model
    def journee(self, employe, jour):
        """Les interventions et les phases de chantier du salarié ce jour-là, triées par heure."""
        company = employe.company_id
        tz = self._tz(company)
        debut = tz.localize(datetime.combine(jour, time.min)).astimezone(pytz.utc).replace(tzinfo=None)
        fin = tz.localize(datetime.combine(jour, time.max)).astimezone(pytz.utc).replace(tzinfo=None)
        Task = self.env["project.task"].sudo()
        domaine = [("company_id", "=", company.id), ("cultiveau_intervention", "=", True), ("state", "not in", ("1_done", "1_canceled")),
                   ("cultiveau_debut", ">=", debut), ("cultiveau_debut", "<=", fin)]
        qui = ["|", ("cultiveau_salarie_ids", "in", [employe.id]), ("user_ids", "in", [employe.user_id.id])] if employe.user_id else [("cultiveau_salarie_ids", "in", [employe.id])]
        taches = Task.search(domaine + qui, order="cultiveau_debut asc")
        natures = dict(Task._fields["cultiveau_nature"].selection)
        items = []
        for t in taches:
            p = t.partner_id
            adresse = t.cultiveau_adresse or ""
            heure = fields.Datetime.context_timestamp(t.with_context(tz=tz.zone), t.cultiveau_debut) if t.cultiveau_debut else None
            items.append({"genre": "intervention", "id": t.id, "heure": heure.strftime("%H:%M") if heure else "", "titre": t.name, "nature": natures.get(t.cultiveau_nature, ""),
                          "client": p.name or "", "telephone": p.mobile or p.phone or "", "adresse": adresse,
                          "itineraire": f"https://www.google.com/maps/dir/?api=1&destination={quote_plus(adresse)}" if adresse else "",
                          "duree": t.cultiveau_duree_prevue, "consignes": t.cultiveau_consignes or "", "installation": t.cultiveau_installation_id.name or "",
                          "produits": [f"{pc.quantite:g} × {pc.product_id.display_name}" for pc in t.cultiveau_piece_ids] if "cultiveau_piece_ids" in t._fields else [],
                          "equipe": ", ".join((t.user_ids.mapped("name") + t.cultiveau_salarie_ids.mapped("name")))})
        Chantier = self.env["cultiveau.chantier"].sudo()
        dom_ch = [("company_id", "=", company.id), ("etat", "in", ("planifie", "en_cours", "brouillon")), "|", ("date_debut", "=", False), ("date_debut", "<=", jour), "|", ("date_fin", "=", False), ("date_fin", ">=", jour)]
        qui_ch = ["|", ("salarie_ids", "in", [employe.id]), "|", ("equipe_ids", "in", [employe.user_id.id]), ("chef_id", "=", employe.user_id.id)] if employe.user_id else [("salarie_ids", "in", [employe.id])]
        for c in Chantier.search(dom_ch + qui_ch):
            if not c.date_debut:
                continue
            phase = c.phase_ids.filtered(lambda ph: ph.date_debut and ph.date_fin and ph.date_debut <= jour <= ph.date_fin)[:1] or c.phase_ids.filtered(lambda ph: ph.etat == "en_cours")[:1]
            p = c.partner_id
            adresse = ", ".join(x for x in (p.street, f"{p.zip or ''} {p.city or ''}".strip()) if x) if p else ""
            items.append({"genre": "chantier", "id": c.id, "heure": "", "titre": c.display_name, "nature": phase.name if phase else "Chantier", "client": p.name or "", "telephone": p.mobile or p.phone or "",
                          "adresse": adresse, "itineraire": f"https://www.google.com/maps/dir/?api=1&destination={quote_plus(adresse)}" if adresse else "", "duree": 0,
                          "consignes": c.acces or "", "installation": c.installation_id.name or "", "produits": [], "machines": c.machines or "",
                          "equipe": ", ".join(((c.equipe_ids | c.chef_id).mapped("name") + c.salarie_ids.mapped("name")))})
        items.sort(key=lambda i: (i["genre"] != "chantier", i["heure"] or "99"))
        return items

    # ---------------------------------------------------------------- le rendu
    @api.model
    def html(self, employe, jour, lien=True):
        company = employe.company_id
        items = self.journee(employe, jour)
        jours = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
        mois = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
        titre = f"{jours[jour.weekday()].capitalize()} {jour.day} {mois[jour.month - 1]}"
        couleur = getattr(company, "cultiveau_couleur", None) or "#1d6f85"
        cartes = []
        for i in items:
            lignes = []
            if i["client"]:
                tel = f" · <a href='tel:{escape(i['telephone'])}' style='color:{couleur}'>{escape(i['telephone'])}</a>" if i["telephone"] else ""
                lignes.append(f"<div><b>{escape(i['client'])}</b>{tel}</div>")
            if i["installation"]:
                lignes.append(f"<div style='color:#555'>{escape(i['installation'])}</div>")
            if i["adresse"]:
                lignes.append(f"<div>{escape(i['adresse'])}" + (f" · <a href='{escape(i['itineraire'])}' style='color:{couleur}'>Itinéraire</a>" if i["itineraire"] else "") + "</div>")
            if i.get("machines"):
                lignes.append(f"<div>Machines : {escape(i['machines'])}</div>")
            if i["produits"]:
                lignes.append("<div>À embarquer : " + ", ".join(escape(x) for x in i["produits"]) + "</div>")
            if i["consignes"]:
                lignes.append(f"<div style='background:#fff6d6;padding:4px 8px;border-radius:6px;margin-top:4px'>{escape(i['consignes'])}</div>")
            if i["equipe"]:
                lignes.append(f"<div style='color:#777;font-size:12px'>Avec : {escape(i['equipe'])}</div>")
            heure = f"<span style='display:inline-block;min-width:52px;font-weight:700;color:{couleur}'>{escape(i['heure'] or ('journée' if i['genre'] == 'chantier' else ''))}</span>"
            duree = f" <span style='color:#777;font-size:12px'>({i['duree']:g} h prévues)</span>" if i.get("duree") else ""
            cartes.append(f"<div style='border:1px solid #e3e3e3;border-left:4px solid {couleur};border-radius:8px;padding:10px 12px;margin:8px 0;background:#fff'>"
                          f"<div style='font-size:15px'>{heure}{escape(i['nature'])}{duree}</div><div style='font-size:14px;margin-top:2px'>{escape(i['titre'])}</div>{''.join(lignes)}</div>")
        corps = "".join(cartes) if cartes else "<p style='color:#777'>Rien de planifié ce jour-là.</p>"
        base = self.env["ir.config_parameter"].sudo().get_param("web.base.url") or ""
        pied = f"<p style='font-size:12px;color:#777;margin-top:16px'>Votre feuille de route est toujours à jour ici : <a href='{escape(employe.cultiveau_feuille_url)}' style='color:{couleur}'>{escape(employe.cultiveau_feuille_url)}</a></p>" if lien else ""
        return Markup(f"<div style='font-family:system-ui,sans-serif;max-width:620px;margin:auto;color:#222'><h2 style='margin:0 0 2px;color:{couleur}'>{escape(company.name)}</h2>"
                      f"<div style='color:#555;margin-bottom:10px'>Feuille de route de {escape(employe.name)} · {escape(titre)}</div>{corps}{pied}</div>")

    @api.model
    def page(self, employe, jour):
        """La page du téléphone : la journée, et les flèches vers la veille et le lendemain."""
        company = employe.company_id
        couleur = getattr(company, "cultiveau_couleur", None) or "#1d6f85"
        hier, demain = jour - timedelta(days=1), jour + timedelta(days=1)
        nav = (f"<div style='display:flex;justify-content:space-between;margin:8px 0 12px;font-family:system-ui,sans-serif'>"
               f"<a href='?date={hier}' style='color:{couleur};text-decoration:none'>← {hier.strftime('%d/%m')}</a><a href='?date=' style='color:{couleur};text-decoration:none'>Demain</a>"
               f"<a href='?date={demain}' style='color:{couleur};text-decoration:none'>{demain.strftime('%d/%m')} →</a></div>")
        contenu = self.html(employe, jour, lien=False)
        return (f"<!doctype html><html lang='fr'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><meta name='robots' content='noindex'>"
                f"<title>Feuille de route · {escape(employe.name)}</title></head><body style='margin:0;background:#f4f6f7;padding:12px'>"
                f"<div style='max-width:620px;margin:auto'>{nav}{contenu}</div></body></html>")

    # ---------------------------------------------------------------- l'envoi
    @api.model
    def envoyer(self, employe, jour, seulement_si_planifie=False):
        courriel = employe.work_email or employe.private_email
        if not courriel:
            return 0
        items = self.journee(employe, jour)
        if seulement_si_planifie and not items:
            return 0
        company = employe.company_id
        self.env["mail.mail"].sudo().create({
            "subject": f"Votre journée du {jour.strftime('%d/%m')} — {company.name}", "body_html": self.html(employe, jour), "email_to": courriel,
            "email_from": company.email_formatted or self.env.user.email_formatted, "auto_delete": True})
        employe.sudo().cultiveau_feuille_derniere = fields.Datetime.now()
        return 1

    @api.model
    def _cron_veille(self):
        n = 0
        for company in self.env["res.company"].sudo().search([]):
            jour = self.prochain_jour(company)
            employes = self.env["hr.employee"].sudo().search([("company_id", "=", company.id), ("cultiveau_feuille_mail", "=", True)])
            for e in employes:
                n += self.envoyer(e, jour, seulement_si_planifie=True)
        return n
