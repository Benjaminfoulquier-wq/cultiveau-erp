"""L'analyse des besoins (A1.1) menée comme un entretien : les huit données d'entrée du référentiel (§ 3.2, check-list p. 23) deviennent
huit questions, et les parcelles déclarées à la PAC par le client remplissent d'elles-mêmes le parcellaire et l'assolement."""
from collections import Counter
from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.exceptions import UserError

# Les huit étapes de l'entretien, dans l'ordre où elles viennent à la ferme. Chaque étape : clé, titre, section du référentiel.
ETAPES = [
    ("parcellaire", "Ses parcelles", "check-list § 3.2.5, p. 23"),
    ("cultures", "Ce qu'il cultive, aujourd'hui et demain", "§ 3.2.1, p. 22"),
    ("sol", "Son sol", "§ 3.2.2, p. 22"),
    ("eau", "Son eau", "§ 3.2.3, p. 23"),
    ("titre", "Son droit de prélever", "check-list § 3.2.5, p. 23"),
    ("energie", "Son énergie", "§ 3.2.4, p. 23"),
    ("travail", "Comment il travaille", "§ 3.2.5, p. 23"),
    ("priorite", "Ce qui compte le plus pour lui", "check-list § 3.2.5, p. 23"),
]


class Installation(models.Model):
    _inherit = "cultiveau.installation"

    parcelle_ids = fields.Many2many("cultiveau.parcelle", "cultiveau_installation_parcelle_rel", "installation_id", "parcelle_id", string="Parcelles concernées",
                                    domain="[('partner_id', '=', partner_id)]", help="Les parcelles déclarées à la PAC (Telepac) que ce projet doit arroser.")
    nb_parcelles_client = fields.Integer("Parcelles déclarées par le client", compute="_compute_parcelles_client")
    campagne_client = fields.Integer("Dernière campagne PAC", compute="_compute_parcelles_client")
    entretien_notes = fields.Text("Ses mots", help="Ce qu'il dit pendant la visite, en vrac : vous rangerez dans les cartes après.")
    etape_parcellaire_ok = fields.Boolean(compute="_compute_etapes")
    etape_cultures_ok = fields.Boolean(compute="_compute_etapes")
    etape_sol_ok = fields.Boolean(compute="_compute_etapes")
    etape_eau_ok = fields.Boolean(compute="_compute_etapes")
    etape_titre_ok = fields.Boolean(compute="_compute_etapes")
    etape_energie_ok = fields.Boolean(compute="_compute_etapes")
    etape_travail_ok = fields.Boolean(compute="_compute_etapes")
    etape_priorite_ok = fields.Boolean(compute="_compute_etapes")
    entretien_html = fields.Html("Où en est l'entretien", compute="_compute_etapes", sanitize=False)

    @api.depends("partner_id", "partner_id.cultiveau_parcelle_ids")
    def _compute_parcelles_client(self):
        for i in self:
            parcelles = i.partner_id.cultiveau_parcelle_ids
            i.campagne_client = max(parcelles.mapped("campagne") or [0])
            i.nb_parcelles_client = len(parcelles.filtered(lambda p: p.campagne == i.campagne_client)) if parcelles else 0

    def _etapes_faites(self):
        """Pour une installation : {clé: fait ?}, avec les mêmes critères que la check-list A1.1 du module installation."""
        self.ensure_one()
        i = self
        return {
            "parcellaire": bool(i.surface_ha and (i.pente_moyenne_pct or i.distance_ressource_m or i.parcelle_ids)),
            "cultures": bool((i.assolement or i.culture_ids) and i.culture_pointe_id),
            "sol": bool(i.sol_texture and i.ru_mm),
            "eau": bool(i.ressource and i.debit_mobilisable_m3h and i.volume_autorise_m3),
            "titre": bool(i.titre_prelevement and i.titre_prelevement != "inconnu"),
            "energie": bool(i.energie and (i.puissance_souscrite_kva or i.energie == "thermique")),
            "travail": bool((i.main_d_oeuvre or i.horaires or i.acces) and i.niveau_automatisme),
            "priorite": bool(i.hierarchie),
        }

    @api.depends("surface_ha", "pente_moyenne_pct", "distance_ressource_m", "parcelle_ids", "assolement", "culture_pointe_id", "culture_ids", "sol_texture", "ru_mm",
                 "ressource", "debit_mobilisable_m3h", "volume_autorise_m3", "titre_prelevement", "energie", "puissance_souscrite_kva",
                 "main_d_oeuvre", "horaires", "acces", "niveau_automatisme", "hierarchie", "analyse_validee_le")
    def _compute_etapes(self):
        for i in self:
            faites = i._etapes_faites()
            for cle, _titre, _ref in ETAPES:
                i[f"etape_{cle}_ok"] = faites[cle]
            n = sum(1 for v in faites.values() if v)
            manque = [titre for cle, titre, _ref in ETAPES if not faites[cle]]
            pct = int(n / len(ETAPES) * 100)
            if i.analyse_validee_le:
                etat = Markup("<span class='cv-entretien-etat cv-ok'>Validée avec l'exploitant le %s</span>") % i.analyse_validee_le.strftime("%d/%m/%Y")
            elif not manque:
                etat = Markup("<span class='cv-entretien-etat cv-ok'>Tout est là : relisez-la avec lui et validez (bouton en haut).</span>")
            else:
                etat = Markup("<span class='cv-entretien-etat'>Reste à voir : %s.</span>") % escape(" · ".join(manque).lower())
            i.entretien_html = Markup(
                "<div class='cv-entretien-avancement'><div class='cv-entretien-barre'><div class='cv-entretien-rempli' style='width:%s%%'></div></div>"
                "<div class='cv-entretien-chiffre'>%s / %s</div></div>%s") % (pct, n, len(ETAPES), etat)

    # ---------------------------------------------------------------- les parcelles du client
    def action_reprendre_parcelles(self):
        """Ouvre le choix des parcelles du client ; sans déclaration importée, propose l'import Telepac."""
        self.ensure_one()
        if not self.partner_id:
            raise UserError("Choisissez d'abord l'agriculteur.")
        if not self.nb_parcelles_client:
            return self.action_importer_telepac()
        return {"type": "ir.actions.act_window", "name": f"Les parcelles de {self.partner_id.display_name}", "res_model": "cultiveau.installation.parcelles",
                "view_mode": "form", "target": "new", "context": {"default_installation_id": self.id}}

    def action_importer_telepac(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "name": "Importer sa déclaration PAC", "res_model": "cultiveau.import.telepac", "view_mode": "form",
                "target": "new", "context": {"default_partner_id": self.partner_id.id, "default_installation_id": self.id}}

    def action_demander_telepac(self):
        self.ensure_one()
        return self.partner_id.action_demander_telepac()

    def action_voir_parcelles(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("cultiveau_parcelles.action_parcelles")
        action["domain"] = [("id", "in", self.parcelle_ids.ids)] if self.parcelle_ids else [("partner_id", "=", self.partner_id.id)]
        action["context"] = {"default_partner_id": self.partner_id.id}
        return action

    def appliquer_parcelles(self, parcelles):
        """Pose les parcelles choisies sur le projet et en déduit ce que la trame A1.1 demande : surface, cultures, culture de pointe,
        lieux-dits, commune, assolement de la campagne. Ne remplace jamais ce que l'installateur a déjà écrit lui-même."""
        self.ensure_one()
        parcelles = parcelles.filtered(lambda p: p.partner_id == self.partner_id)
        if not parcelles:
            raise UserError("Aucune parcelle de ce client à reprendre.")
        valeurs = {"parcelle_ids": [(6, 0, parcelles.ids)], "surface_ha": round(sum(parcelles.mapped("surface_ha")), 2)}
        cultures = parcelles.mapped("culture_id")
        if cultures:
            valeurs["culture_ids"] = [(4, c.id) for c in cultures]
            if not self.culture_pointe_id:
                valeurs["culture_pointe_id"] = self._culture_de_pointe(cultures).id
        lieux, par_ilot = [], {}
        for p in parcelles:
            par_ilot.setdefault(p.ilot or "?", []).append(p.numero or "?")
        for ilot in sorted(par_ilot, key=lambda x: (len(x), x)):
            nums = sorted(set(par_ilot[ilot]), key=lambda x: (len(x), x))
            lieux.append(f"îlot {ilot} p. {', '.join(nums)}")
        texte_lieux = " · ".join(lieux)
        if not self.parcelle or self.parcelle.startswith("îlot "):
            valeurs["parcelle"] = texte_lieux[:255] if len(texte_lieux) <= 255 else f"{len(parcelles)} parcelles, {len(par_ilot)} îlots"
        communes = Counter(p.commune for p in parcelles if p.commune)
        if communes and not self.commune:
            insee, _n = communes.most_common(1)[0]
            valeurs["commune"] = f"INSEE {insee}" + (f" (+{len(communes) - 1} autre(s))" if len(communes) > 1 else "")
        campagne = max(parcelles.mapped("campagne") or [0])
        if not self.assolement:
            surfaces = Counter()
            for p in parcelles:
                surfaces[p.culture_id.name if p.culture_id else (p.code_id.libelle or p.code_id.code or "sans culture")] += p.surface_ha
            lignes = [f"{nom} {round(s, 2):g} ha" for nom, s in surfaces.most_common()]
            valeurs["assolement"] = f"Campagne PAC {campagne} : " + " · ".join(lignes) + ".\nPrévisible (à demander) : "
        self.write(valeurs)
        self.message_post(body=Markup("<p>Parcelles reprises de la déclaration PAC %s : %s parcelle(s), %s ha, %s.</p>") % (
            campagne, len(parcelles), valeurs["surface_ha"], escape(texte_lieux)), subtype_xmlid="mail.mt_note")
        return True

    def _culture_de_pointe(self, cultures):
        """La culture la plus exigeante en pointe (§ 3.2.1) : d'après le besoin de pointe calculé pour ce client, sinon le Kc de mi-saison."""
        self.ensure_one()
        cc = self.partner_id.cultiveau_culture_ids.filtered(lambda c: c.culture_id in cultures and c.besoin_pointe_mm)
        if cc:
            return max(cc, key=lambda c: c.besoin_pointe_mm).culture_id
        return max(cultures, key=lambda c: c.kc_mi or 0)
