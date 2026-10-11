"""Un adhérent qui rejoint le réseau : tout ce qu'il faut pour qu'il travaille dès ce soir, dans l'ordre, sans rien oublier."""

import base64

from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.exceptions import UserError

ETAPES = [("societe", "La société"), ("utilisateurs", "Les utilisateurs"), ("assistant", "L'assistant téléphonique"), ("clients", "Ses clients"),
          ("articles", "Ses articles"), ("compta", "La comptabilité"), ("efacture", "La facture électronique"), ("fini", "Prêt")]
ROLES = [("gerant", "Gérant (tout)"), ("commercial", "Commercial (clients, devis, factures)"), ("technicien", "Technicien (chantiers, interventions, stock)"),
         ("comptoir", "Magasin (comptoir, ventes, stock)"), ("comptable", "Comptable (lecture seule)")]
GROUPES = {
    "gerant": ["base.group_user", "cultiveau_base.group_adherent", "sales_team.group_sale_manager", "account.group_account_manager", "stock.group_stock_manager",
               "purchase.group_purchase_manager", "project.group_project_manager", "base.group_partner_manager"],
    "commercial": ["base.group_user", "cultiveau_base.group_adherent", "sales_team.group_sale_salesman_all_leads", "account.group_account_invoice", "stock.group_stock_user",
                   "base.group_partner_manager"],
    "technicien": ["base.group_user", "cultiveau_base.group_adherent", "project.group_project_user", "stock.group_stock_user", "sales_team.group_sale_salesman"],
    "comptoir": ["base.group_user", "cultiveau_base.group_adherent", "sales_team.group_sale_salesman", "account.group_account_invoice", "stock.group_stock_user"],
    "comptable": ["base.group_user", "account.group_account_readonly"],
}


class Adhesion(models.Model):
    _name = "cultiveau.adhesion"
    _description = "Mise en route d'un adhérent"
    _inherit = ["mail.thread"]
    _order = "create_date desc"

    name = fields.Char("Raison sociale", required=True)
    etat = fields.Selection(ETAPES, "Étape", default="societe", tracking=True)
    company_id = fields.Many2one("res.company", "Société créée", readonly=True, copy=False)
    progression = fields.Integer("Avancement (%)", compute="_compute_progression")
    bilan = fields.Html("Où en est-on", compute="_compute_progression", sanitize=False)
    # 1. la société
    siret = fields.Char("SIRET", size=17)
    tva = fields.Char("N° de TVA intracommunautaire")
    street = fields.Char("Adresse")
    zip = fields.Char("Code postal")
    city = fields.Char("Ville")
    phone = fields.Char("Téléphone")
    email = fields.Char("E-mail de la société")
    website = fields.Char("Site web")
    logo = fields.Binary("Logo")
    couleur = fields.Char("Couleur de la marque", default="#183840", help="Sur les devis, les factures et les e-mails de l'adhérent.")
    # 2. les utilisateurs
    utilisateur_ids = fields.One2many("cultiveau.adhesion.utilisateur", "adhesion_id", "Utilisateurs")
    # 3. l'assistant téléphonique
    numero_dedie = fields.Char("Numéro dédié de l'assistant", help="Le numéro que l'assistant téléphonique décroche pour cet adhérent.")
    assistant_id = fields.Integer("N° d'adhérent dans l'assistant", help="Dans l'assistant, l'adhérent est /adherents/<n>/.")
    # 4. et 5. les fichiers
    fichier_clients = fields.Binary("Fichier des clients")
    nom_fichier_clients = fields.Char()
    type_client_defaut = fields.Selection(lambda self: [(t, l) for t, l in self.env["res.partner"]._fields["cultiveau_type"].selection if t != "adherent"], "Type par défaut",
                                          default="agriculteur")
    bilan_clients = fields.Html("Clients importés", readonly=True, sanitize=False)
    fichier_articles = fields.Binary("Fichier des articles")
    nom_fichier_articles = fields.Char()
    bilan_articles = fields.Html("Articles importés", readonly=True, sanitize=False)
    # 6. la comptabilité
    regime_tva = fields.Selection([("mensuel", "CA3 chaque mois"), ("trimestriel", "CA3 chaque trimestre"), ("annuel", "CA12 une fois par an")], "Régime de TVA", default="mensuel")
    comptable_email = fields.Char("E-mail du comptable")
    compta_en_place = fields.Boolean(related="company_id.cultiveau_compta_en_place")
    # 7. la facture électronique
    efacture_etat = fields.Selection(related="company_id.cultiveau_efacture_etat")

    # ---------------------------------------------------------------- avancement

    @api.depends("etat", "company_id", "utilisateur_ids.user_id", "bilan_clients", "bilan_articles", "company_id.chart_template", "company_id.cultiveau_efacture_etat")
    def _compute_progression(self):
        for a in self:
            faits = [
                ("Société créée", bool(a.company_id)),
                ("Utilisateurs invités", bool(a.utilisateur_ids) and all(a.utilisateur_ids.mapped("user_id"))),
                ("Assistant téléphonique relié", bool(a.company_id and (a.company_id.cultiveau_numero_dedie or a.company_id.cultiveau_assistant_id))),
                ("Clients importés", bool(a.bilan_clients)),
                ("Articles importés", bool(a.bilan_articles)),
                ("Comptabilité en place", bool(a.company_id and a.company_id.cultiveau_compta_en_place)),
                ("Inscrite sur la plateforme agréée", bool(a.company_id and a.company_id.cultiveau_efacture_etat not in (False, "non"))),
            ]
            a.progression = int(100 * sum(1 for _, ok in faits if ok) / len(faits))
            a.bilan = Markup("".join(f"<div><i class='fa {'fa-check-circle text-success' if ok else 'fa-circle-o text-muted'}'></i> {escape(nom)}</div>" for nom, ok in faits))

    def _societe(self):
        self.ensure_one()
        if not self.company_id:
            raise UserError("Créez d'abord la société (étape 1).")
        return self.company_id

    def _etape_suivante(self, courante):
        cles = [c for c, _ in ETAPES]
        return cles[min(cles.index(courante) + 1, len(cles) - 1)]

    def action_etape(self):
        """Le bouton « Suivant » : passe à l'étape d'après sans rien exiger (on peut revenir)."""
        for a in self:
            a.etat = a._etape_suivante(a.etat)
        return True

    # ---------------------------------------------------------------- 1. la société

    def action_creer_societe(self):
        self.ensure_one()
        if self.company_id:
            self.company_id.write(self._valeurs_societe())
        else:
            societe = self.env["res.company"].create({"name": self.name, **self._valeurs_societe()})
            # ceux de l'équipe Cultiveau voient la nouvelle société tout de suite
            equipe = self.env.ref("cultiveau_base.group_equipe").users | self.env.user
            equipe.sudo().write({"company_ids": [(4, societe.id)]})
            self.company_id = societe
            societe.cultiveau_mettre_en_place_compta()
        self.etat = "utilisateurs"
        return True

    def _valeurs_societe(self):
        valeurs = {"street": self.street, "zip": self.zip, "city": self.city, "phone": self.phone, "email": self.email, "website": self.website,
                   "cultiveau_regime_tva": self.regime_tva, "cultiveau_adherent": True}
        if self.siret:
            siret = "".join(c for c in self.siret if c.isdigit())
            valeurs.update(company_registry=siret)
            if "siret" in self.env["res.company"]._fields:
                valeurs["siret"] = siret
        if self.tva:
            valeurs["vat"] = self.tva.replace(" ", "").upper()
        if self.logo:
            valeurs["logo"] = self.logo
        if self.couleur and "primary_color" in self.env["res.company"]._fields:
            valeurs["primary_color"] = self.couleur
        if self.numero_dedie:
            valeurs["cultiveau_numero_dedie"] = self.numero_dedie
        if self.assistant_id:
            valeurs["cultiveau_assistant_id"] = self.assistant_id
        return valeurs

    # ---------------------------------------------------------------- 2. les utilisateurs

    def action_inviter(self):
        self.ensure_one()
        societe = self._societe()
        if not self.utilisateur_ids:
            raise UserError("Ajoutez au moins un utilisateur (le gérant, par exemple).")
        for u in self.utilisateur_ids.filtered(lambda u: not u.user_id):
            u.inviter(societe)
        self.etat = "assistant"
        return True

    # ---------------------------------------------------------------- 3. l'assistant

    def action_assistant(self):
        self.ensure_one()
        societe = self._societe()
        societe.write({"cultiveau_numero_dedie": self.numero_dedie or False, "cultiveau_assistant_id": self.assistant_id or 0})
        self.etat = "clients"
        return True

    # ---------------------------------------------------------------- 4. et 5. les fichiers

    def action_importer_clients(self):
        self.ensure_one()
        societe = self._societe()
        if not self.fichier_clients:
            raise UserError("Choisissez le fichier des clients (Excel ou CSV, l'export de l'ancien logiciel ou de l'assistant).")
        try:
            bilan = self.env["cultiveau.import.clients.moteur"].with_company(societe).importer(
                self.nom_fichier_clients or "clients.csv", base64.b64decode(self.fichier_clients), self.type_client_defaut, societe)
        except ValueError as e:
            raise UserError(f"Fichier non reconnu : {e}.") from e
        self.bilan_clients = self._html_bilan(bilan, "clients")
        self.etat = "articles"
        return True

    def action_importer_articles(self):
        self.ensure_one()
        societe = self._societe()
        if not self.fichier_articles:
            raise UserError("Choisissez le fichier des articles (Excel ou CSV).")
        try:
            bilan = self.env["product.template"].with_company(societe).cultiveau_importer_articles(
                self.nom_fichier_articles or "articles.csv", base64.b64decode(self.fichier_articles), False, False, True)
        except ValueError as e:
            raise UserError(f"Fichier non reconnu : {e}.") from e
        self.bilan_articles = self._html_bilan(bilan, "articles")
        self.etat = "compta"
        return True

    @api.model
    def _html_bilan(self, bilan, quoi):
        texte = f"<p><b>{bilan.get('crees', 0)} {quoi} créés</b>, {bilan.get('maj', 0)} mis à jour, {bilan.get('ignores', 0)} ignorés.</p>"
        if bilan.get("erreurs"):
            texte += "<p>À regarder :</p><ul>" + "".join(f"<li>{escape(str(e))}</li>" for e in bilan["erreurs"][:30]) + "</ul>"
        return Markup(texte)

    # ---------------------------------------------------------------- 6. et 7.

    def action_compta(self):
        self.ensure_one()
        societe = self._societe()
        societe.cultiveau_regime_tva = self.regime_tva
        societe.cultiveau_mettre_en_place_compta()
        if self.comptable_email:
            societe.cultiveau_inviter_comptable(self.comptable_email.strip())
        self.etat = "efacture"
        return True

    def action_efacture(self):
        """Ouvre l'inscription sur la plateforme agréée pour cette société (démonstration, test ou réel)."""
        self.ensure_one()
        societe = self._societe()
        if not societe.siret and not societe.company_registry:
            raise UserError("Le SIRET manque : revenez à l'étape 1 pour le renseigner.")
        if not self.env["res.company"].cultiveau_double_authentification():
            raise UserError("La plateforme agréée exige la double authentification : activez-la dans Réglages → Cultiveau → Facture électronique, puis revenez ici.")
        assistant = self.env["pdp.registration"].with_company(societe).create({"company_id": societe.id})
        return assistant._action_open_pdp_form(reopen=False)

    def action_terminer(self):
        for a in self:
            a.etat = "fini"
            a.message_post(body=f"{a.name} est prêt : {a.progression} % des étapes faites.")
        return True

    def action_ouvrir_societe(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "res_model": "res.company", "res_id": self._societe().id, "view_mode": "form", "target": "current"}


class AdhesionUtilisateur(models.Model):
    _name = "cultiveau.adhesion.utilisateur"
    _description = "Utilisateur d'un nouvel adhérent"

    adhesion_id = fields.Many2one("cultiveau.adhesion", required=True, ondelete="cascade")
    name = fields.Char("Nom", required=True)
    email = fields.Char("E-mail", required=True)
    role = fields.Selection(ROLES, "Rôle", required=True, default="commercial")
    user_id = fields.Many2one("res.users", "Compte", readonly=True)

    def inviter(self, societe):
        self.ensure_one()
        login = self.email.strip().lower()
        groupes = self.env["res.groups"]
        for xmlid in GROUPES[self.role]:
            g = self.env.ref(xmlid, raise_if_not_found=False)
            if g:
                groupes |= g
        Utilisateur = self.env["res.users"].sudo()
        utilisateur = Utilisateur.with_context(active_test=False).search([("login", "=", login)], limit=1)
        if utilisateur:
            utilisateur.write({"active": True, "company_ids": [(4, societe.id)], "groups_id": [(4, g.id) for g in groupes]})
        else:
            utilisateur = Utilisateur.with_context(no_reset_password=True).create({
                "name": self.name, "login": login, "email": login, "company_id": societe.id, "company_ids": [(6, 0, [societe.id])],
                "groups_id": [(6, 0, groupes.ids)], "lang": "fr_FR", "tz": "Europe/Paris"})
            utilisateur.with_context(create_user=True).action_reset_password()
        self.user_id = utilisateur
        return utilisateur
