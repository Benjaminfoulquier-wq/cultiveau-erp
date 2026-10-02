from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.exceptions import UserError

TYPES = [
    ("couverture_integrale", "Aspersion — couverture intégrale"),
    ("couverture_partielle", "Aspersion — couverture partielle déplacée"),
    ("enrouleur", "Enrouleur"),
    ("pivot", "Pivot / rampe frontale"),
    ("goutte_surface", "Goutte à goutte de surface"),
    ("goutte_enterre", "Goutte à goutte enterré"),
    ("micro_aspersion", "Micro-aspersion"),
    ("mixte", "Mixte"),
]
# Ordres de grandeur économiques du référentiel (§ 3.3.1), « à confronter à des devis ».
ORDRES_DE_GRANDEUR = {
    "couverture_integrale": (3000, 6000, "€/ha"), "couverture_partielle": (3000, 6000, "€/ha"),
    "enrouleur": (25000, 60000, "€ l'enrouleur"), "pivot": (1500, 3500, "€/ha"),
    "goutte_surface": (2000, 4500, "€/ha"), "goutte_enterre": (3500, 6500, "€/ha"), "micro_aspersion": (2500, 5000, "€/ha"),
}
STATION = (15000, 80000)  # station de pompage + filtration
EFFICIENCE = {"couverture_integrale": "70-80 %", "couverture_partielle": "70-80 %", "enrouleur": "65-75 % (énergie élevée)",
              "pivot": "80-90 %", "goutte_surface": "85-95 %", "goutte_enterre": "85-95 %", "micro_aspersion": "80-90 %"}
UNIFORMITE_CIBLE = {"goutte_surface": "DU ≥ 85", "goutte_enterre": "DU ≥ 85", "micro_aspersion": "DU ≥ 82", "pivot": "CU ≥ 90",
                    "couverture_integrale": "CU 84-88", "couverture_partielle": "CU 84-88", "enrouleur": "CU 75-85"}


def _fr(n):
    return f"{n:,.0f}".replace(",", " ")


class Installation(models.Model):
    _name = "cultiveau.installation"
    _description = "Installation d'irrigation (site chez un agriculteur)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "partner_id, name"

    name = fields.Char("Installation", required=True, tracking=True, help="Ex. « Pivot des Grandes Terres », « Goutte à goutte vigne Mas Neuf ».")
    partner_id = fields.Many2one("res.partner", "Agriculteur", required=True, index=True, tracking=True,
                                 domain="[('cultiveau_type', 'in', ('agriculteur', False))]")
    company_id = fields.Many2one("res.company", "Adhérent", required=True, default=lambda self: self.env.company, index=True)
    user_id = fields.Many2one("res.users", "Suivie par", default=lambda self: self.env.user, tracking=True)
    type_systeme = fields.Selection(TYPES, "Type d'installation", required=True, tracking=True)
    etat = fields.Selection([("projet", "Projet"), ("etude", "Étude et dimensionnement"), ("realisation", "Réalisation"),
                             ("en_service", "En service"), ("arretee", "Arrêtée / démontée")], "Phase", default="projet", tracking=True)
    surface_ha = fields.Float("Surface irriguée (ha)", digits=(8, 2))
    culture_ids = fields.Many2many("cultiveau.culture", string="Cultures", help="Les cultures irriguées par cette installation.")
    culture_pointe_id = fields.Many2one("cultiveau.culture", "Culture la plus exigeante (pointe)",
                                        help="On dimensionne pour la culture la plus exigeante de la rotation, pas pour la moyenne (§ 3.2.1).")
    parcelle = fields.Char("Parcelle(s) / lieu-dit")
    commune = fields.Char("Commune")
    notes = fields.Text("Notes")
    active = fields.Boolean(default=True)

    # ---- A1.1 analyse des besoins (§ 3.2) : cinq domaines, huit données d'entrée
    ressource = fields.Selection([("forage", "Forage"), ("retenue", "Retenue / réserve"), ("cours_eau", "Cours d'eau"),
                                  ("reseau_collectif", "Réseau collectif (ASA, concession)"), ("reut", "Eaux usées traitées (REUT)"), ("autre", "Autre")],
                                 "Ressource en eau")
    debit_mobilisable_m3h = fields.Float("Débit réellement mobilisable en pointe (m³/h)", digits=(8, 1),
                                         help="La donnée dimensionnante : pas le débit instantané maximal du forage (§ 3.2.3).")
    volume_autorise_m3 = fields.Float("Volume autorisé (m³/an)", digits=(12, 0))
    titre_prelevement = fields.Selection([("declaration", "Déclaration"), ("autorisation", "Autorisation"), ("collectif", "Via le réseau collectif"),
                                          ("aucun", "Aucun"), ("inconnu", "À vérifier")], "Titre de prélèvement")
    titre_organisme = fields.Char("Organisme / référence du titre")
    analyse_eau_date = fields.Date("Analyse d'eau du", help="Indispensable avant de concevoir un réseau de micro-irrigation (§ 5.4).")
    analyse_eau_resume = fields.Char("Qualité d'eau (MES, fer, CE…)")
    energie = fields.Selection([("reseau", "Réseau électrique"), ("thermique", "Groupe thermique"), ("solaire", "Solaire"), ("mixte", "Mixte")], "Énergie")
    puissance_souscrite_kva = fields.Float("Puissance souscrite / disponible (kVA)", digits=(8, 1),
                                           help="Une puissance insuffisante impose un fractionnement ou un stockage tampon (§ 3.2.4).")
    tarif_energie = fields.Char("Tarif et plages horaires")
    sol_texture = fields.Selection([("sableux", "Sableux"), ("limono_sableux", "Limono-sableux"), ("limoneux", "Limoneux"),
                                    ("limono_argileux", "Limono-argileux"), ("argileux", "Argileux"), ("battant", "Battant")], "Texture du sol")
    ru_mm = fields.Float("Réserve utile (mm)", digits=(6, 0))
    profondeur_sol_cm = fields.Float("Profondeur exploitable (cm)", digits=(6, 0))
    pente_moyenne_pct = fields.Float("Pente moyenne (%)", digits=(5, 1))
    pente_max_pct = fields.Float("Pente maximale (%)", digits=(5, 1))
    distance_ressource_m = fields.Float("Distance à la ressource (m)", digits=(8, 0))
    obstacles = fields.Char("Obstacles (haies, cours d'eau, bâtiments, lignes)")
    assolement = fields.Text("Assolement actuel et prévisible")
    main_d_oeuvre = fields.Char("Main-d'œuvre disponible")
    horaires = fields.Char("Horaires d'arrosage possibles (tarifs, voisinage, bruit)")
    acces = fields.Char("Accès au site")
    niveau_automatisme = fields.Selection([("manuel", "Manuel"), ("programmateur", "Programmateur"), ("pilote", "Piloté (sondes, régulation)"),
                                           ("connecte", "Connecté, suivi à distance")], "Niveau d'automatisme souhaité")
    hierarchie = fields.Selection([("eau", "L'eau d'abord (ressource limitée)"), ("energie", "L'énergie d'abord (coût, puissance)"),
                                   ("rendement", "Le rendement d'abord")], "Hiérarchie des enjeux (validée avec l'exploitant)")
    analyse_validee_le = fields.Date("Analyse validée par l'exploitant le", tracking=True)
    analyse_completude = fields.Integer("Données d'entrée renseignées (sur 8)", compute="_compute_analyse")
    analyse_html = fields.Html("Check-list A1.1", compute="_compute_analyse", sanitize=False)

    # ---- A1.2 note de dimensionnement (§ 3.3, douze lignes)
    besoin_pointe_mm_j = fields.Float("1. Besoin de pointe (mm/j)", digits=(5, 1))
    dfc_l_s_ha = fields.Float("2. Débit fictif continu (l/s/ha)", digits=(6, 3))
    temps_fonctionnement_h_j = fields.Float("Temps de fonctionnement (h/j)", digits=(4, 1), default=20)
    debit_equipement_m3_h = fields.Float("Débit d'équipement (m³/h)", digits=(8, 1))
    secteurs = fields.Integer("3. Nombre de secteurs")
    simultaneite = fields.Integer("Secteurs simultanés", default=1)
    technique_organes = fields.Char("4. Technique et organes de distribution (pression, débit unitaire)")
    pression_service_bar = fields.Float("Pression de service (bar)", digits=(5, 1))
    diametres_vitesses = fields.Char("5. Diamètres et vitesses principaux (0,5-2 m/s)")
    pertes_charge_m = fields.Float("6. Pertes de charge jusqu'au point défavorable (m)", digits=(6, 1))
    hmt_m = fields.Float("7. HMT (m)", digits=(6, 1))
    pompe = fields.Char("Pompe retenue et point de fonctionnement (Q, H)")
    filtration = fields.Char("8. Filtration (type, finesse) et protections")
    uniformite_visee_pct = fields.Float("9. Uniformité de conception visée (%)", digits=(4, 0))
    energie_specifique_kwh_m3 = fields.Float("Énergie spécifique attendue (kWh/m³)", digits=(5, 2))
    dfc_calc = fields.Float("DFC calculé", compute="_compute_calculs", digits=(6, 3))
    debit_calc = fields.Float("Débit d'équipement calculé", compute="_compute_calculs", digits=(8, 1))
    chiffrage_indicatif = fields.Char("Ordre de grandeur (§ 3.3.1)", compute="_compute_calculs")
    efficience_typique = fields.Char("Efficience typique", compute="_compute_calculs")
    uniformite_cible = fields.Char("Uniformité cible (§ 4.3.1)", compute="_compute_calculs")
    alerte_dimensionnement = fields.Html("Cohérences", compute="_compute_calculs", sanitize=False)

    # ---- A1.3 PV de mise en service et A1.4 certificat (§ 3.4-3.5)
    pv_date = fields.Date("Mise en service le", tracking=True)
    pv_intervenant = fields.Char("Intervenant")
    pv_rincage = fields.Boolean("Rinçage réalisé (§ 13.5.2)")
    pv_essai_pression_bar = fields.Float("Essai de pression (bar)", digits=(5, 1))
    pv_essai_resultat = fields.Char("Résultat de l'essai")
    pv_pression_sortie_pompe_bar = fields.Float("Pression en sortie de pompe (bar)", digits=(5, 2))
    pv_pression_point_defavorable_bar = fields.Float("Pression au point défavorable (bar)", digits=(5, 2))
    pv_debits_secteurs = fields.Text("Débit mesuré par secteur")
    pv_uniformite_pct = fields.Float("Uniformité mesurée (CU / DU, %)", digits=(4, 0))
    pv_kwh_m3 = fields.Float("kWh/m³ mesuré", digits=(5, 2))
    pv_securites_testees = fields.Boolean("Sécurités testées (marche à sec, pressostats, niveau)")
    pv_antiretour = fields.Boolean("Protection sanitaire présente (anti-retour / disconnexion)",
                                   help="Point d'arrêt : son absence est une non-conformité bloquante (§ 3.5).")
    pv_reserves = fields.Text("Réserves")
    certificat_date = fields.Date("Certificat de conformité (A1.4) le", tracking=True)
    certificat_reserves = fields.Text("Réserves du certificat")

    # ---- A1.5 fiche de réglage (§ 3.6)
    reglage_sequencement = fields.Text("Séquencement des secteurs")
    reglage_durees = fields.Text("Durées et fréquences par culture")
    reglage_pressions = fields.Char("Pressions de consigne")
    reglage_contre_lavage = fields.Char("Seuils de contre-lavage de la filtration")
    reglage_pilotage = fields.Char("Outils de pilotage")
    reglage_surveillance = fields.Text("Consignes de surveillance")
    reglage_contacts = fields.Char("Contacts et dépannage")

    # ---- suivi et maintenance (§ 3.7, ch. 18)
    equipement_ids = fields.One2many("cultiveau.equipement", "installation_id", string="Équipements")
    registre_ids = fields.One2many("cultiveau.registre", "installation_id", string="Registre (A1.8)")
    nb_equipements = fields.Integer(compute="_compute_compteurs")
    nb_a_renouveler = fields.Integer(compute="_compute_compteurs")
    nb_registre = fields.Integer(compute="_compute_compteurs")
    remise_en_service_le = fields.Date("Dernière remise en service (§ 18.3)")
    hivernage_le = fields.Date("Dernier hivernage (§ 18.5)")
    prochaine_visite = fields.Date("Prochaine visite")
    contrat_maintenance = fields.Boolean("Contrat d'entretien")
    dossier_completude = fields.Integer("Pièces du dossier (sur 8)", compute="_compute_dossier")
    dossier_html = fields.Html("Dossier technique (§ 3.10)", compute="_compute_dossier", sanitize=False)

    # ---------------------------------------------------------------- calculs

    @api.depends("surface_ha", "pente_moyenne_pct", "distance_ressource_m", "assolement", "culture_pointe_id", "culture_ids", "sol_texture", "ru_mm",
                 "ressource", "debit_mobilisable_m3h", "volume_autorise_m3", "titre_prelevement", "energie", "puissance_souscrite_kva",
                 "main_d_oeuvre", "horaires", "acces", "niveau_automatisme", "hierarchie", "analyse_validee_le")
    def _compute_analyse(self):
        for i in self:
            points = [
                ("Parcellaire : surface, pentes, distance à la ressource, obstacles", bool(i.surface_ha and (i.pente_moyenne_pct or i.distance_ressource_m))),
                ("Assolement prévisible et culture la plus exigeante", bool((i.assolement or i.culture_ids) and i.culture_pointe_id)),
                ("Sol : texture, réserve utile", bool(i.sol_texture and i.ru_mm)),
                ("Ressource : débit mobilisable en pointe, volume autorisé", bool(i.ressource and i.debit_mobilisable_m3h and i.volume_autorise_m3)),
                ("Titre de prélèvement", bool(i.titre_prelevement and i.titre_prelevement != "inconnu")),
                ("Énergie : type et puissance disponible", bool(i.energie and (i.puissance_souscrite_kva or i.energie == "thermique"))),
                ("Contraintes : main-d'œuvre, horaires, accès, automatisme", bool((i.main_d_oeuvre or i.horaires or i.acces) and i.niveau_automatisme)),
                ("Hiérarchie eau / énergie / rendement validée", bool(i.hierarchie)),
            ]
            i.analyse_completude = sum(1 for _l, ok in points if ok)
            lignes = "".join(f"<li style='list-style:none'>{'✅' if ok else '⬜'} {escape(l)}</li>" for l, ok in points)
            etat = (f"<p><b>Validée avec l'exploitant le {i.analyse_validee_le.strftime('%d/%m/%Y')}.</b></p>" if i.analyse_validee_le
                    else "<p class='text-warning'><b>Non validée</b> : le référentiel demande la validation avant tout dimensionnement (§ 3.2).</p>")
            i.analyse_html = Markup(f"<ul style='padding-left:0'>{lignes}</ul>{etat}")

    @api.depends("besoin_pointe_mm_j", "surface_ha", "temps_fonctionnement_h_j", "type_systeme", "debit_mobilisable_m3h", "debit_equipement_m3_h",
                 "puissance_souscrite_kva", "pv_antiretour", "uniformite_visee_pct", "volume_autorise_m3")
    def _compute_calculs(self):
        for i in self:
            # 1 mm/j sur 1 ha = 10 m³/j ; en l/s/ha : × 1000 / 86 400.
            dfc = (i.besoin_pointe_mm_j or 0.0) * 10 * 1000 / 86400
            i.dfc_calc = dfc
            heures = i.temps_fonctionnement_h_j or 20
            i.debit_calc = dfc * (i.surface_ha or 0.0) * 24 / heures * 3.6  # l/s → m³/h
            i.efficience_typique = EFFICIENCE.get(i.type_systeme, "")
            i.uniformite_cible = UNIFORMITE_CIBLE.get(i.type_systeme, "")
            odg = ORDRES_DE_GRANDEUR.get(i.type_systeme)
            if odg and i.surface_ha and odg[2] == "€/ha":
                bas, haut = odg[0] * i.surface_ha, odg[1] * i.surface_ha
                i.chiffrage_indicatif = (f"Équipement {_fr(bas)} – {_fr(haut)} € ({odg[0]}-{odg[1]} €/ha) ; station de pompage et filtration "
                                         f"{_fr(STATION[0])} – {_fr(STATION[1])} €. Ordre de grandeur, à confronter à des devis.")
            elif odg:
                i.chiffrage_indicatif = f"{_fr(odg[0])} – {_fr(odg[1])} {odg[2]} ; station {_fr(STATION[0])} – {_fr(STATION[1])} €. Ordre de grandeur."
            else:
                i.chiffrage_indicatif = ""
            alertes = []
            if i.debit_equipement_m3_h and i.debit_mobilisable_m3h and i.debit_equipement_m3_h > i.debit_mobilisable_m3h:
                alertes.append("Le débit d'équipement dépasse le débit mobilisable en pointe : fractionner, stocker ou réduire la surface (§ 3.2.3).")
            if i.besoin_pointe_mm_j and i.surface_ha and i.volume_autorise_m3:
                # Une saison de pointe de 60 jours à ce besoin : vite comparée au volume autorisé.
                besoin_saison = i.besoin_pointe_mm_j * 10 * i.surface_ha * 60
                if besoin_saison > i.volume_autorise_m3:
                    alertes.append(f"60 jours au besoin de pointe = {_fr(besoin_saison)} m³, plus que le volume autorisé ({_fr(i.volume_autorise_m3)} m³) : "
                                   "ne pas confondre débit de forage et volume disponible (ch. 5).")
            if i.type_systeme in ("goutte_surface", "goutte_enterre", "micro_aspersion") and not i.analyse_eau_date:
                alertes.append("Micro-irrigation sans analyse d'eau : indispensable avant de concevoir (§ 5.4).")
            if i.etat == "en_service" and not i.pv_antiretour:
                alertes.append("Protection sanitaire (anti-retour / disconnexion) non cochée : point d'arrêt du référentiel (§ 3.5).")
            i.alerte_dimensionnement = Markup("".join(f"<p class='text-danger'>⚠ {escape(a)}</p>" for a in alertes)) if alertes else Markup("")

    def _compute_compteurs(self):
        for i in self:
            i.nb_equipements = len(i.equipement_ids)
            i.nb_a_renouveler = len(i.equipement_ids.filtered("a_renouveler"))
            i.nb_registre = len(i.registre_ids)

    @api.depends("analyse_validee_le", "besoin_pointe_mm_j", "pompe", "pv_date", "certificat_date", "reglage_pressions", "reglage_durees",
                 "equipement_ids.product_id.cultiveau_fiche_url", "registre_ids")
    def _compute_dossier(self):
        for i in self:
            pieces = [
                ("A1.1 analyse des besoins validée", bool(i.analyse_validee_le)),
                ("A1.2 note de dimensionnement (besoin de pointe et pompe)", bool(i.besoin_pointe_mm_j and i.pompe)),
                ("Plans (réseau, secteurs, station, points de livraison)", bool(i.message_attachment_count)),
                ("A1.3 PV de mise en service", bool(i.pv_date)),
                ("A1.4 certificat de conformité", bool(i.certificat_date)),
                ("A1.5 fiche de réglage", bool(i.reglage_pressions or i.reglage_durees)),
                ("Notices constructeurs (fiches techniques des équipements)", bool(i.equipement_ids and all(e.product_id.cultiveau_fiche_url or e.notice_url for e in i.equipement_ids))),
                ("A1.8 registre tenu", bool(i.registre_ids)),
            ]
            i.dossier_completude = sum(1 for _l, ok in pieces if ok)
            i.dossier_html = Markup("<ul style='padding-left:0'>" + "".join(
                f"<li style='list-style:none'>{'✅' if ok else '⬜'} {escape(l)}</li>" for l, ok in pieces) + "</ul>")

    # ---------------------------------------------------------------- actions

    def action_valider_analyse(self):
        for i in self:
            if i.analyse_completude < 8:
                raise UserError(f"L'analyse des besoins compte {i.analyse_completude} point(s) sur 8 : compléter la check-list avant de la faire valider "
                                "par l'exploitant (§ 3.2, pièce A1.1).")
            i.write({"analyse_validee_le": fields.Date.context_today(self), "etat": "etude" if i.etat == "projet" else i.etat})
            i.message_post(body="Analyse des besoins (A1.1) validée avec l'exploitant : le dimensionnement peut commencer.")

    def action_reprendre_calculs(self):
        for i in self:
            i.write({"dfc_l_s_ha": i.dfc_calc, "debit_equipement_m3_h": i.debit_calc})

    def action_mettre_en_service(self):
        for i in self:
            if not i.pv_antiretour:
                raise UserError("Point d'arrêt (§ 3.5) : la protection sanitaire (anti-retour / disconnexion) doit être présente et cochée dans le PV.")
            if not (i.pv_pression_sortie_pompe_bar and i.pv_pression_point_defavorable_bar):
                raise UserError("Le PV doit fixer les pressions de référence (sortie de pompe, point défavorable) : sans référence, on ne dépanne pas, on tâtonne (§ 18.9).")
            i.write({"etat": "en_service", "pv_date": i.pv_date or fields.Date.context_today(self)})
            if not i.reglage_pressions and i.pression_service_bar:
                i.reglage_pressions = f"Consigne {i.pression_service_bar:g} bar en tête ; référence PV : {i.pv_pression_sortie_pompe_bar:g} bar sortie pompe, {i.pv_pression_point_defavorable_bar:g} bar au point défavorable."
            i.registre_ids.create({"installation_id": i.id, "date": i.pv_date, "genre": "mise_en_service", "description": "Mise en service (PV A1.3)",
                                   "releves": f"{i.pv_pression_sortie_pompe_bar:g} bar sortie pompe / {i.pv_pression_point_defavorable_bar:g} bar point défavorable"
                                              + (f" / {i.pv_uniformite_pct:g} % uniformité" if i.pv_uniformite_pct else ""), "intervenant": i.pv_intervenant})

    def action_voir_equipements(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "name": "Équipements", "res_model": "cultiveau.equipement", "view_mode": "list,form",
                "domain": [("installation_id", "=", self.id)], "context": {"default_installation_id": self.id}}

    def action_voir_registre(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "name": "Registre", "res_model": "cultiveau.registre", "view_mode": "list,form",
                "domain": [("installation_id", "=", self.id)], "context": {"default_installation_id": self.id}}

    def resume_pour_api(self):
        """Ce que l'assistant téléphonique dit du parc d'un client qui appelle."""
        return [{"nom": i.name, "type": dict(TYPES).get(i.type_systeme, i.type_systeme), "etat": i.etat, "surface_ha": i.surface_ha,
                 "mise_en_service": i.pv_date.isoformat() if i.pv_date else None,
                 "reference_pressions": {"sortie_pompe_bar": i.pv_pression_sortie_pompe_bar, "point_defavorable_bar": i.pv_pression_point_defavorable_bar},
                 "equipements": [e.display_name for e in i.equipement_ids[:8]]} for i in self]

    # ---------------------------------------------------------------- rappels saisonniers (ch. 18)

    @api.model
    def _cron_saisons(self):
        """Février : remise en service (§ 18.3). Octobre : hivernage (§ 18.5). Une activité par installation en service."""
        aujourd_hui = fields.Date.context_today(self)
        if aujourd_hui.month not in (2, 10):
            return 0
        hiver = aujourd_hui.month == 10
        resume = "Hivernage : vidange, mise hors gel, rinçage, obturation, relevés au registre (§ 18.5)" if hiver else \
            "Remise en service : contrôle visuel, point de fonctionnement (P, Q), sécurités, filtration, pressions aux points clés (§ 18.3)"
        n = 0
        for i in self.search([("etat", "=", "en_service")]):
            fait = (i.hivernage_le if hiver else i.remise_en_service_le)
            if fait and fait.year == aujourd_hui.year:
                continue
            if i.activity_ids.filtered(lambda a: a.summary == resume and a.date_deadline.year == aujourd_hui.year):
                continue
            i.activity_schedule("mail.mail_activity_data_todo", summary=resume, user_id=i.user_id.id or self.env.user.id,
                                note=f"<p>{escape(i.partner_id.display_name)} — {escape(i.name)}. Comparer les mesures au PV de mise en service.</p>")
            n += 1
        return n
