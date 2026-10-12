"""Les automatisations « si… alors… » : des règles du métier que le gérant active d'un clic, sans rien programmer.

Chaque règle a un délai réglable, un responsable par défaut et, quand c'est possible, l'envoi automatique au client (sinon :
une activité pour la bonne personne, avec ce qu'il faut pour agir). Une règle n'agit qu'une fois par document (ou une fois par
période pour les règles qui se répètent) : la trace est gardée.
"""
import logging
from datetime import timedelta

from markupsafe import Markup

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# clé : (nom, description, jours par défaut, envoi au client possible, se répète après N jours (0 : jamais))
MODELES = {
    "relance_devis": ("Devis sans réponse → relance", "Un devis envoyé reste sans réponse {jours} jours : le commercial a une activité « Relancer », ou le client reçoit la relance.", 7, True, 0),
    "devis_signe_chantier": ("Devis signé avec pose → chantier préparé", "Une commande d'installation est confirmée : le chantier est créé (matériel d'après la commande, équipe à planifier).", 0, False, 0),
    "reassort": ("Stock sous le minimum → commande fournisseur", "Un article passe sous son minimum de réassort : la commande fournisseur est préparée en brouillon.", 0, False, 7),
    "facture_echue": ("Facture échue → relance", "Une facture est échue depuis {jours} jours : le client reçoit la relance (ou la comptabilité a une activité).", 7, True, 0),
    "bon_a_facturer": ("Bon signé non facturé → rappel", "Un bon d'intervention signé n'est pas facturé après {jours} jours : rappel à la facturation.", 3, False, 0),
    "intervention_sans_bon": ("Intervention terminée sans bon signé → rappel", "Une intervention est terminée depuis {jours} jours sans bon signé : rappel au technicien.", 1, False, 0),
    "entretien_annuel": ("Un an après la mise en service → proposer l'entretien", "Une installation fête bientôt sa mise en service (dans {jours} jours) sans contrat d'entretien : le commercial propose l'entretien.", 30, False, 330),
    "client_dormant": ("Client sans commande → reprendre contact", "Un client n'a rien commandé depuis {jours} jours : son commercial a une activité « Reprendre contact ».", 365, False, 180),
    "courriel_escalade": ("Courriel toujours sans réponse → prévenir le gérant", "Un courriel attend une réponse depuis {jours} jours ouvrés : le gérant est prévenu.", 5, False, 0),
    "paiement_merci": ("Facture payée → remerciement", "Une facture est réglée : le client reçoit un mot de remerciement.", 0, True, 0),
}


class Regle(models.Model):
    _name = "cultiveau.regle"
    _description = "Automatisation (si… alors…)"
    _order = "sequence, id"

    name = fields.Char("Règle", required=True)
    cle = fields.Selection([(k, v[0]) for k, v in MODELES.items()], "Modèle", required=True, readonly=True)
    description = fields.Char("Ce qu'elle fait", compute="_compute_description")
    sequence = fields.Integer(default=10)
    actif = fields.Boolean("Active", default=False)
    jours = fields.Integer("Délai (jours)")
    a_un_delai = fields.Boolean(compute="_compute_description")
    envoi_auto = fields.Boolean("Envoyer au client", help="Le courriel part tout seul au client ; sinon, une activité pour le responsable.")
    peut_envoyer = fields.Boolean(compute="_compute_description")
    responsable_id = fields.Many2one("res.users", "Responsable par défaut", domain=[("share", "=", False)],
                                     help="Quand le document n'a pas de commercial ou de technicien : à qui revient l'activité.")
    company_id = fields.Many2one("res.company", "Société", required=True, default=lambda self: self.env.company)
    derniere_execution = fields.Datetime("Dernier passage", readonly=True)
    dernier_resultat = fields.Char("Résultat", readonly=True)
    nb_total = fields.Integer("Actions faites", readonly=True)
    trace_ids = fields.One2many("cultiveau.regle.trace", "regle_id", "Traces")

    _sql_constraints = [("cle_unique", "unique(cle, company_id)", "Cette règle existe déjà pour la société.")]

    @api.depends("cle", "jours")
    def _compute_description(self):
        for r in self:
            m = MODELES.get(r.cle)
            r.description = m[1].format(jours=r.jours) if m else ""
            r.peut_envoyer = bool(m and m[3])
            r.a_un_delai = bool(m and "{jours}" in m[1])

    @api.model
    def preparer(self, companies=None):
        """Les règles du métier, inactives, pour chaque société qui ne les a pas encore."""
        for company in companies or self.env["res.company"].sudo().search([]):
            existantes = set(self.sudo().search([("company_id", "=", company.id)]).mapped("cle"))
            gerant = self.env["cultiveau.equipe"].gerants(company)[:1] if "cultiveau.equipe" in self.env else self.env["res.users"]
            for i, (cle, (nom, _d, jours, envoi, _r)) in enumerate(MODELES.items()):
                if cle not in existantes:
                    self.sudo().create({"name": nom, "cle": cle, "jours": jours, "envoi_auto": False, "company_id": company.id,
                                        "responsable_id": gerant.id or False, "sequence": i * 10})
        return True

    # ---------------------------------------------------------------- l'exécution

    def action_executer(self):
        n = 0
        for r in self:
            n += r._executer()
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"title": "Règles passées", "message": f"{n} action(s) faite(s).", "type": "success", "sticky": False}}

    def _executer(self):
        self.ensure_one()
        regle = self.sudo().with_company(self.company_id).with_context(allowed_company_ids=[self.company_id.id])
        try:
            with self.env.cr.savepoint():
                n = getattr(regle, f"_r_{self.cle}")()
            resultat = f"{n} action(s)" if n else "Rien à faire"
        except Exception as e:  # noqa: BLE001 — une règle en échec n'arrête pas les autres
            _logger.warning("Règle %s (%s) : %s", self.cle, self.company_id.name, e)
            n, resultat = 0, f"Erreur : {str(e)[:150]}"
        self.sudo().write({"derniere_execution": fields.Datetime.now(), "dernier_resultat": resultat, "nb_total": self.nb_total + n})
        return n

    @api.model
    def _cron(self):
        for r in self.sudo().search([("actif", "=", True)]):
            r._executer()
            self.env.cr.commit()

    # ---------------------------------------------------------------- les outils des règles

    def _deja(self, record):
        """Vrai si la règle a déjà agi sur ce document (dans la période de répétition, si elle se répète)."""
        repete = MODELES[self.cle][4]
        domaine = [("regle_id", "=", self.id), ("modele", "=", record._name), ("res_id", "=", record.id)]
        if repete:
            domaine.append(("create_date", ">", fields.Datetime.now() - timedelta(days=repete)))
        return bool(self.env["cultiveau.regle.trace"].sudo().search_count(domaine))

    def _tracer(self, record, note=""):
        self.env["cultiveau.regle.trace"].sudo().create({"regle_id": self.id, "modele": record._name, "res_id": record.id, "note": note[:250]})

    def _activite(self, record, user, resume, note=""):
        user = user if user and not user.share and user.active else self.responsable_id
        if not user:
            return
        record.activity_schedule(activity_type_id=self.env.ref("mail.mail_activity_data_todo").id, user_id=user.id, summary=resume,
                                 note=Markup("%s<br/><i>Automatisation : %s</i>") % (note or resume, self.name))

    def _envoyer(self, record, gabarit):
        record.message_post_with_source(self.env.ref(gabarit), subtype_xmlid="mail.mt_comment", message_type="comment")

    def _limite(self):
        return fields.Datetime.now() - timedelta(days=self.jours or 0)

    # ---------------------------------------------------------------- les règles

    def _r_relance_devis(self):
        n = 0
        for d in self.env["sale.order"].search([("state", "=", "sent"), ("write_date", "<", self._limite()), ("company_id", "=", self.company_id.id)], limit=100):
            if self._deja(d):
                continue
            if self.envoi_auto and d.partner_id.email:
                self._envoyer(d, "cultiveau_quotidien.mail_relance_devis")
            else:
                self._activite(d, d.user_id, f"Relancer le devis {d.name}", f"Envoyé il y a plus de {self.jours} jours, toujours sans réponse de {d.partner_id.name}.")
            self._tracer(d)
            n += 1
        return n

    def _r_devis_signe_chantier(self):
        Order = self.env["sale.order"]
        if "cultiveau_installation_id" not in Order._fields:
            return 0
        n = 0
        domaine = [("state", "=", "sale"), ("cultiveau_installation_id", "!=", False), ("cultiveau_chantier_ids", "=", False), ("company_id", "=", self.company_id.id),
                   ("date_order", ">", fields.Datetime.now() - timedelta(days=60))]
        if "cultiveau_heures_pose" in Order._fields:
            domaine.append(("cultiveau_heures_pose", ">", 0))
        for o in Order.search(domaine, limit=50):
            if self._deja(o):
                continue
            o.action_lancer_chantier()
            chantier = o.cultiveau_chantier_ids[:1]
            if chantier:
                self._activite(chantier, chantier.chef_id or o.user_id, "Planifier le chantier", f"Créé depuis la commande {o.name} : équipe et dates à fixer.")
            self._tracer(o)
            n += 1
        return n

    def _r_reassort(self):
        n = 0
        points = self.env["stock.warehouse.orderpoint"].search([("company_id", "=", self.company_id.id), ("trigger", "in", ("auto", "manual"))])
        for p in points.filtered(lambda p: p.qty_forecast < p.product_min_qty and p.product_id.seller_ids):
            if self._deja(p):
                continue
            try:
                with self.env.cr.savepoint():
                    p.action_replenish()
                self._tracer(p, f"{p.product_id.display_name} : {p.qty_forecast:g} / mini {p.product_min_qty:g}")
                n += 1
            except Exception as e:  # noqa: BLE001
                _logger.info("Réassort %s impossible : %s", p.product_id.display_name, e)
        return n

    def _r_facture_echue(self):
        n = 0
        echeance = fields.Date.context_today(self) - timedelta(days=self.jours or 0)
        for f in self.env["account.move"].search([("move_type", "=", "out_invoice"), ("state", "=", "posted"), ("payment_state", "in", ("not_paid", "partial")),
                                                  ("invoice_date_due", "<", echeance), ("company_id", "=", self.company_id.id)], limit=100):
            if self._deja(f):
                continue
            if self.envoi_auto and f.partner_id.email and hasattr(f, "action_relancer"):
                f.action_relancer()
            else:
                self._activite(f, f.invoice_user_id, f"Relancer le paiement de {f.name}", f"{f.partner_id.name} : {f.amount_residual:.2f} € dus depuis le {f.invoice_date_due:%d/%m/%Y}.")
            self._tracer(f)
            n += 1
        return n

    def _r_bon_a_facturer(self):
        if "cultiveau.bon" not in self.env:
            return 0
        n = 0
        for b in self.env["cultiveau.bon"].search([("etat", "=", "signe"), ("signe_le", "<", self._limite()), ("company_id", "=", self.company_id.id)], limit=100):
            if self._deja(b):
                continue
            self._activite(b, self.responsable_id, f"Facturer le bon {b.name}", f"Signé par {b.partner_id.name} il y a plus de {self.jours} jours.")
            self._tracer(b)
            n += 1
        return n

    def _r_intervention_sans_bon(self):
        Task = self.env["project.task"]
        if "cultiveau_bon_ids" not in Task._fields:
            return 0
        n = 0
        for t in Task.search([("cultiveau_intervention", "=", True), ("state", "=", "1_done"), ("date_last_stage_update", "<", self._limite()),
                              ("date_last_stage_update", ">", fields.Datetime.now() - timedelta(days=60)), ("company_id", "=", self.company_id.id)], limit=100):
            if t.cultiveau_bon_ids.filtered("signe_le") or self._deja(t):
                continue
            self._activite(t, t.user_ids[:1], f"Faire signer le bon de « {t.name} »", "L'intervention est terminée mais aucun bon n'est signé par le client.")
            self._tracer(t)
            n += 1
        return n

    def _r_entretien_annuel(self):
        Inst = self.env["cultiveau.installation"]
        if "pv_date" not in Inst._fields:
            return 0
        n = 0
        aujourd_hui = fields.Date.context_today(self)
        horizon = aujourd_hui + timedelta(days=self.jours or 30)
        sous_contrat = set()
        if "cultiveau.contrat" in self.env:
            sous_contrat = set(self.env["cultiveau.contrat"].search([("etat", "=", "actif")]).mapped("installation_ids").ids)
        for i in Inst.search([("pv_date", "!=", False), ("pv_date", "<", aujourd_hui - timedelta(days=300)), ("company_id", "=", self.company_id.id)], limit=300):
            jour = min(i.pv_date.day, 28) if i.pv_date.month == 2 else i.pv_date.day
            anniversaire = i.pv_date.replace(year=aujourd_hui.year, day=jour)
            if anniversaire < aujourd_hui:
                anniversaire = anniversaire.replace(year=aujourd_hui.year + 1)
            if anniversaire > horizon or i.id in sous_contrat or self._deja(i):
                continue
            commercial = i.partner_id.commercial_partner_id.user_id
            self._activite(i, commercial, f"Proposer l'entretien de « {i.name} »", f"Mise en service le {i.pv_date:%d/%m/%Y}, sans contrat d'entretien.")
            self._tracer(i)
            n += 1
        return n

    def _r_client_dormant(self):
        n = 0
        limite = self._limite()
        commandes = self.env["sale.order"].read_group([("state", "=", "sale"), ("company_id", "=", self.company_id.id)], ["date_order:max"], ["partner_id"])
        for g in commandes:
            if not g.get("partner_id") or not g.get("date_order") or g["date_order"] >= limite:
                continue
            p = self.env["res.partner"].browse(g["partner_id"][0]).commercial_partner_id
            if not p.active or self._deja(p):
                continue
            self._activite(p, p.user_id, f"Reprendre contact avec {p.name}", f"Dernière commande le {g['date_order']:%d/%m/%Y}.")
            self._tracer(p)
            n += 1
            if n >= 50:
                break
        return n

    def _r_courriel_escalade(self):
        if "cultiveau.courriel" not in self.env:
            return 0
        n = 0
        gerants = self.env["cultiveau.equipe"].gerants(self.company_id) if "cultiveau.equipe" in self.env else self.responsable_id
        for c in self.env["cultiveau.courriel"].search([("etat", "=", "a_traiter"), ("sans_reponse", "=", True), ("company_id", "=", self.company_id.id)], limit=100):
            if c.attente_jours < (self.jours or 5) or self._deja(c):
                continue
            for g in gerants[:1]:
                self._activite(c, g, f"Courriel en souffrance : {c.name}", f"{c.expediteur_nom} attend depuis {c.attente_jours} jours ouvrés (responsable : {c.user_id.name or '—'}).")
            self._tracer(c)
            n += 1
        return n

    def _r_paiement_merci(self):
        n = 0
        for f in self.env["account.move"].search([("move_type", "=", "out_invoice"), ("state", "=", "posted"), ("payment_state", "in", ("paid", "in_payment")),
                                                  ("write_date", ">", fields.Datetime.now() - timedelta(days=7)), ("company_id", "=", self.company_id.id)], limit=100):
            if self._deja(f) or not f.partner_id.email:
                continue
            if self.envoi_auto:
                self._envoyer(f, "cultiveau_quotidien.mail_merci_paiement")
            self._tracer(f)
            n += 1 if self.envoi_auto else 0
        return n


class Trace(models.Model):
    _name = "cultiveau.regle.trace"
    _description = "Trace d'une automatisation"
    _order = "id desc"

    regle_id = fields.Many2one("cultiveau.regle", required=True, ondelete="cascade", index=True)
    modele = fields.Char(required=True, index=True)
    res_id = fields.Integer(required=True, index=True)
    note = fields.Char()
    document = fields.Char("Document", compute="_compute_document")

    def _compute_document(self):
        for t in self:
            r = self.env[t.modele].browse(t.res_id).exists() if t.modele in self.env else None
            t.document = r.display_name if r else f"{t.modele} n° {t.res_id}"
