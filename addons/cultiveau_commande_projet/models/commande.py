"""La commande fait le projet : les prestations deviennent des tâches, le questionnaire de financement part et se relance, la pro
forma et le « sans suite »."""
from datetime import timedelta

from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.exceptions import UserError

MOTS_MISE_EN_SERVICE = ("mise en service", "mise en route", "réception", "formation")
FINANCEMENTS = [("comptant", "Comptant"), ("credit", "Crédit bancaire"), ("location", "Location / crédit-bail"), ("usage", "Irrigation à l'usage"), ("indecis", "À conseiller")]


class Societe(models.Model):
    _inherit = "res.company"

    cultiveau_decl_taches = fields.Boolean("Créer une tâche par prestation du devis à la confirmation", default=True)
    cultiveau_decl_financement = fields.Boolean("Envoyer le questionnaire de financement après la signature", default=True)
    cultiveau_financement_seuil = fields.Float("À partir de (€ HT)", default=3000.0, help="En dessous, pas de questionnaire : on ne finance pas un dépannage.")


class Reglages(models.TransientModel):
    _inherit = "res.config.settings"

    cultiveau_decl_taches = fields.Boolean(related="company_id.cultiveau_decl_taches", readonly=False)
    cultiveau_decl_financement = fields.Boolean(related="company_id.cultiveau_decl_financement", readonly=False)
    cultiveau_financement_seuil = fields.Float(related="company_id.cultiveau_financement_seuil", readonly=False)


class Template(models.Model):
    _inherit = "sale.order.template"

    @api.model
    def cultiveau_ajouter_bloc_projet(self):
        """En tête de chaque modèle du réseau : le bloc « Projet » (ce qu'on a compris, ce qui est inclus, ce qui ne l'est pas, les pièces en annexe)."""
        texte = ("PROJET : [ce que nous avons compris du besoin : surface, culture de pointe, ressource, énergie]. "
                 "La prestation inclut la fourniture, la pose, le rinçage, les essais de pression, la mise en service avec PV des pressions de référence, "
                 "la fiche de réglage et la formation de l'exploitant. Hors prestation : terrassement hors tranchées des réseaux, raccordement au réseau électrique, "
                 "démarches de prélèvement. Les éléments techniques (note de dimensionnement, fiches constructeurs) sont en annexe de cette offre.")
        n = 0
        for t in self.search([("cultiveau_type_systeme", "!=", False)]):
            if any(l.display_type == "line_note" and l.name and l.name.startswith("PROJET") for l in t.sale_order_template_line_ids):
                continue
            t.write({"sale_order_template_line_ids": [(0, 0, {"display_type": "line_note", "name": texte, "sequence": 1})]})
            n += 1
        return n


class Order(models.Model):
    _inherit = "sale.order"

    cultiveau_tache_ids = fields.One2many("project.task", "cultiveau_sale_order_id", string="Tâches de la commande")
    cultiveau_nb_taches = fields.Integer("Tâches", compute="_compute_taches")
    cultiveau_heures_pointees = fields.Float("Heures pointées", compute="_compute_taches", help="Les pointages des chantiers de la commande.")
    cultiveau_financement = fields.Selection(FINANCEMENTS, "Financement", copy=False, tracking=True)
    cultiveau_financement_detail = fields.Char("Détail du financement", copy=False)
    cultiveau_date_pose_souhaitee = fields.Date("Pose souhaitée", copy=False, tracking=True)
    cultiveau_questionnaire_id = fields.Many2one("survey.user_input", "Questionnaire de financement", readonly=True, copy=False)
    cultiveau_questionnaire_envoye_le = fields.Date("Questionnaire envoyé le", readonly=True, copy=False)
    cultiveau_questionnaire_relances = fields.Integer("Relances du questionnaire", readonly=True, copy=False)
    cultiveau_sans_suite_raison_id = fields.Many2one("crm.lost.reason", "Raison du sans suite", copy=False)

    @api.depends("cultiveau_tache_ids", "cultiveau_chantier_ids.pointage_ids.heures")
    def _compute_taches(self):
        for o in self:
            o.cultiveau_nb_taches = len(o.cultiveau_tache_ids)
            o.cultiveau_heures_pointees = sum(o.cultiveau_chantier_ids.mapped("pointage_ids.heures")) if "pointage_ids" in self.env["cultiveau.chantier"]._fields else 0.0

    # ---------------------------------------------------------------- les prestations deviennent des tâches
    def _cultiveau_declencher(self):
        res = super()._cultiveau_declencher()
        c = self.company_id
        faits = []
        if c.cultiveau_decl_taches:
            n = self._cultiveau_taches_depuis_prestations()
            if n:
                faits.append(f"{n} tâche(s) créée(s) depuis les prestations du devis")
        if c.cultiveau_decl_financement and self.amount_untaxed >= (c.cultiveau_financement_seuil or 0) and not self.cultiveau_questionnaire_id and (self.origin or "") != "Comptoir":
            try:
                if self._cultiveau_envoyer_questionnaire():
                    faits.append("questionnaire de financement envoyé au client, tâche « Financement » ouverte")
            except Exception as e:  # noqa: BLE001
                faits.append(f"questionnaire de financement non envoyé ({e})")
        if faits:
            self.message_post(body="Et aussi : " + " ; ".join(faits) + ".")
        return res

    def _cultiveau_taches_depuis_prestations(self):
        """Une tâche par ligne de service (hors main-d'œuvre de pose calculée et acompte), datée par sa phase."""
        self.ensure_one()
        Task = self.env["project.task"].with_company(self.company_id)
        projet = self.env["project.project"].cultiveau_projet_interventions(self.company_id)
        deja = set(self.cultiveau_tache_ids.mapped("sale_line_id").ids)
        phases = {}
        for p in self.cultiveau_phases():
            for l in p["lignes"]:
                phases[l.id] = p
        chantier = self.cultiveau_chantier_ids[:1]
        n = 0
        for l in self.order_line.filtered(lambda l: l.product_id and l.product_id.type == "service" and not l.display_type and not l.is_downpayment and l.id not in deja):
            if ("cultiveau_ligne_pose" in l._fields and l.cultiveau_ligne_pose) or "acompte" in (l.name or "").lower():
                continue
            nom = (l.name or l.product_id.display_name).split("\n")[0][:120]
            est_mes = any(m in nom.lower() for m in MOTS_MISE_EN_SERVICE)
            if est_mes and self.cultiveau_mise_en_service_id:
                # la mise en service existe déjà : on la relie à sa ligne plutôt que d'en créer une seconde
                self.cultiveau_mise_en_service_id.write({"sale_line_id": l.id, "cultiveau_sale_order_id": self.id})
                continue
            uom_heure = self.env.ref("uom.product_uom_hour", raise_if_not_found=False)
            en_heures = l.product_uom and (l.product_uom == uom_heure or any(m in (l.product_uom.name or "").lower() for m in ("heure", "hour")))
            heures = l.product_uom_qty if en_heures else 0.0
            phase = phases.get(l.id)
            debut = False
            if phase and chantier:
                ph = chantier.phase_ids.filtered(lambda x: x.name == phase["nom"])[:1]
                if ph and ph.date_debut:
                    debut = fields.Datetime.to_datetime(ph.date_debut).replace(hour=7)
            vals = {"name": f"{nom} — {self.partner_id.name}", "project_id": projet.id, "partner_id": self.partner_id.id, "sale_line_id": l.id, "cultiveau_sale_order_id": self.id,
                    "cultiveau_installation_id": self.cultiveau_installation_id.id, "cultiveau_nature": "mise_en_service" if est_mes else "autre",
                    "description": l.name or "", "user_ids": [(6, 0, self.user_id.ids)] if self.user_id else False}
            if heures:
                vals["cultiveau_duree_prevue"] = heures
            if debut:
                vals["cultiveau_debut"] = debut
            Task.create(vals)
            n += 1
        return n

    def action_voir_taches(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "name": f"Tâches — {self.name}", "res_model": "project.task", "view_mode": "list,kanban,form",
                "domain": [("cultiveau_sale_order_id", "=", self.id)], "context": {"default_cultiveau_sale_order_id": self.id, "default_partner_id": self.partner_id.id}}

    # ---------------------------------------------------------------- le financement
    def _cultiveau_envoyer_questionnaire(self, relance=False):
        self.ensure_one()
        if not self.partner_id.email:
            self.message_post(body="Questionnaire de financement non envoyé : le client n'a pas d'e-mail.")
            return False
        survey = self.env.ref("cultiveau_commande_projet.questionnaire_financement")
        ui = self.cultiveau_questionnaire_id
        if not ui or ui.state == "done":
            ui = survey.sudo()._create_answer(partner=self.partner_id, email=self.partner_id.email, check_attempts=False, cultiveau_sale_order_id=self.id)
            self.cultiveau_questionnaire_id = ui
        lien = ui.get_start_url()
        base = self.env["ir.config_parameter"].sudo().get_param("web.base.url") or ""
        if lien.startswith("/"):
            lien = base + lien
        societe = self.company_id
        qui = self.user_id or self.env.user
        corps = Markup(
            "<p>Bonjour,</p><p>Vous venez d'accepter notre devis <b>%s</b> (%s € HT), merci de votre confiance.</p>"
            "<p>Pour préparer la commande et la date de pose, dites-nous en deux minutes comment vous financez le projet : "
            "<a href='%s'>répondre au questionnaire</a>.</p>"
            "<p>Cette étape conditionne la suite : nous ne commandons le matériel qu'une fois le financement choisi.</p><p>%s<br/>%s</p>"
        ) % (self.name, f"{self.amount_untaxed:,.2f}".replace(",", " ").replace(".", ","), lien, escape(qui.name), escape(societe.name))
        self.with_context(mail_notify_force_send=True).message_post(body=corps, subject=f"{'Rappel : ' if relance else ''}Votre financement et votre date de pose — devis {self.name}",
                                                                     message_type="comment", subtype_xmlid="mail.mt_comment", partner_ids=self.partner_id.ids)
        if relance:
            self.cultiveau_questionnaire_relances += 1
        else:
            self.cultiveau_questionnaire_envoye_le = fields.Date.context_today(self)
            if not self.activity_ids.filtered(lambda a: a.summary and a.summary.startswith("Financement")):
                self.activity_schedule("mail.mail_activity_data_todo", date_deadline=fields.Date.context_today(self) + timedelta(days=7), user_id=qui.id,
                                       summary=f"Financement : attendre la réponse de {self.partner_id.name}", note="Le questionnaire est parti ; relance automatique à J+15 ; appeler si rien à J+21.")
        return True

    def action_envoyer_questionnaire(self):
        for o in self:
            o._cultiveau_envoyer_questionnaire(relance=bool(o.cultiveau_questionnaire_envoye_le))
        return True

    def _cultiveau_reponse_financement(self, ui):
        """La réponse du client s'écrit sur la commande, la tâche « Financement » se ferme."""
        self.ensure_one()
        lignes = ui.user_input_line_ids
        q = lambda xmlid: self.env.ref(f"cultiveau_commande_projet.{xmlid}")  # noqa: E731
        choix = lambda xmlid: lignes.filtered(lambda l: l.question_id == q(xmlid) and l.suggested_answer_id).suggested_answer_id.value or ""  # noqa: E731
        mode = choix("q_mode").lower()
        code = "comptant" if "comptant" in mode else "credit" if "crédit" in mode else "location" if "location" in mode else "usage" if "usage" in mode else "indecis" if mode else False
        aide = choix("q_aide")
        banque = lignes.filtered(lambda l: l.question_id == q("q_banque")).value_char_box or ""
        date = lignes.filtered(lambda l: l.question_id == q("q_date")).value_date
        commentaire = lignes.filtered(lambda l: l.question_id == q("q_commentaire")).value_text_box or ""
        self.write({"cultiveau_financement": code, "cultiveau_financement_detail": " · ".join(x for x in (banque, aide) if x)[:255], "cultiveau_date_pose_souhaitee": date or False})
        self.message_post(body=Markup("<p><b>Réponse du client au questionnaire de financement</b> : %s%s%s%s%s</p>") % (
            escape(choix("q_mode") or "?"), Markup(" · banque : %s") % escape(banque) if banque else "", Markup(" · aide : %s") % escape(aide) if aide else "",
            Markup(" · pose souhaitée : %s") % date.strftime("%d/%m/%Y") if date else "", Markup("<br/>%s") % escape(commentaire) if commentaire else ""))
        for a in self.activity_ids.filtered(lambda a: a.summary and a.summary.startswith("Financement")):
            a.action_feedback(feedback=f"Réponse reçue : {choix('q_mode')}")
        if "accompagn" in aide.lower() or code == "indecis":
            self.activity_schedule("mail.mail_activity_data_call", date_deadline=fields.Date.context_today(self) + timedelta(days=2), user_id=(self.user_id or self.env.user).id,
                                   summary=f"Appeler {self.partner_id.name} : conseil financement ou aides", note="Le client demande à être accompagné (aides, choix du financement).")
        if date and self.cultiveau_chantier_ids and not self.cultiveau_chantier_ids[0].date_debut:
            self.cultiveau_chantier_ids[0].date_debut = date
        return True

    @api.model
    def _cultiveau_cron_relance_financement(self):
        limite = fields.Date.today() - timedelta(days=15)
        n = 0
        for o in self.search([("cultiveau_questionnaire_id", "!=", False), ("cultiveau_questionnaire_relances", "<", 2), ("cultiveau_financement", "=", False), ("state", "in", ("sale", "done"))]):
            repere = o.cultiveau_questionnaire_envoye_le
            if not repere or repere + timedelta(days=15 * (o.cultiveau_questionnaire_relances + 1)) > fields.Date.today():
                continue
            if o.cultiveau_questionnaire_id.state == "done":
                continue
            o._cultiveau_envoyer_questionnaire(relance=True)
            n += 1
        return n

    # ---------------------------------------------------------------- sans suite, pro forma
    def action_sans_suite(self):
        for o in self:
            if o.state not in ("draft", "sent"):
                raise UserError("Un devis confirmé ne se classe pas sans suite : annulez la commande.")
            if not o.cultiveau_sans_suite_raison_id:
                raise UserError("Indiquez la raison du sans suite (comme pour une affaire perdue).")
            o.with_context(disable_cancel_warning=True)._action_cancel()
            o.message_post(body=f"Devis classé sans suite : {o.cultiveau_sans_suite_raison_id.name}.")
            if o.opportunity_id and o.opportunity_id.active and o.opportunity_id.probability < 100:
                o.opportunity_id.action_set_lost(lost_reason_id=o.cultiveau_sans_suite_raison_id.id)
        return True


class Task(models.Model):
    _inherit = "project.task"

    cultiveau_sale_order_id = fields.Many2one("sale.order", "Commande Cultiveau", index=True, copy=False)


class UserInput(models.Model):
    _inherit = "survey.user_input"

    cultiveau_sale_order_id = fields.Many2one("sale.order", "Commande", index=True)

    def _mark_done(self):
        res = super()._mark_done()
        for ui in self.filtered("cultiveau_sale_order_id"):
            try:
                ui.cultiveau_sale_order_id.sudo()._cultiveau_reponse_financement(ui)
            except Exception as e:  # noqa: BLE001
                ui.cultiveau_sale_order_id.sudo().message_post(body=f"Réponse au questionnaire reçue mais non lue : {e}")
        return res
