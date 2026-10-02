# Données de démonstration : un agriculteur (Jean Martin, Mas Neuf), ses cultures, son persona, son installation goutte à goutte
# avec son dossier A1.1 à A1.5, ses équipements, un dépannage urgent venu de l'assistant, une remise en service, un devis par lots, quatre opportunités.
# Relançable sans doublon.
Partner = env["res.partner"]
agri = Partner.search([("name", "=", "Jean Martin")], limit=1) or Partner.create({
    "name": "Jean Martin", "exploitation": "Mas Neuf", "zip": "30100", "city": "Alès", "mobile": "06 12 34 56 78",
    "email": "jean.martin@example.org", "cultiveau_type": "agriculteur", "company_id": env.company.id,
    "cultiveau_culture_ids": [(0, 0, {"culture_id": env.ref("cultiveau_frise.culture_vigne").id, "surface_ha": 12}),
                              (0, 0, {"culture_id": env.ref("cultiveau_frise.culture_pommier").id, "surface_ha": 4.5}),
                              (0, 0, {"culture_id": env.ref("cultiveau_frise.culture_melon").id, "surface_ha": 3})]})
env["cultiveau.persona.evaluation"].create({"partner_id": agri.id, "persona_id": env.ref("cultiveau_persona.persona_fidele").id,
    "reponses": {"surface": "petite", "relation": "historique", "priorite": "conseil", "materiel": "entretenu", "horizon": "renouveler",
                 "decision": "conseiller", "canal": "visite", "pilotage": "non"}, "scores": {"batisseur": 3, "pilote": 1, "fidele": 14, "pragmatique": 3}})
Inst = env["cultiveau.installation"]
inst = Inst.search([("name", "=", "Goutte à goutte vigne — Mas Neuf")], limit=1) or Inst.create({
    "name": "Goutte à goutte vigne — Mas Neuf", "partner_id": agri.id, "type_systeme": "goutte_surface", "surface_ha": 12,
    "culture_ids": [(6, 0, [env.ref("cultiveau_frise.culture_vigne").id])], "culture_pointe_id": env.ref("cultiveau_frise.culture_vigne").id,
    "commune": "Alès", "parcelle": "Les Grès", "pente_moyenne_pct": 3, "pente_max_pct": 8, "distance_ressource_m": 450, "obstacles": "haie, chemin communal",
    "sol_texture": "limono_argileux", "ru_mm": 90, "profondeur_sol_cm": 60, "ressource": "forage", "debit_mobilisable_m3h": 28, "volume_autorise_m3": 25000,
    "titre_prelevement": "declaration", "titre_organisme": "DDTM 30 — récépissé 2024-118", "analyse_eau_date": "2026-02-10", "analyse_eau_resume": "MES 30 mg/l, fer 0,3 mg/l, CE 0,8 dS/m",
    "energie": "reseau", "puissance_souscrite_kva": 24, "tarif_energie": "heures creuses 22h-6h", "assolement": "Vigne (12 ha), pas de changement prévu",
    "main_d_oeuvre": "exploitant + 1 saisonnier", "horaires": "nuit de préférence", "acces": "chemin carrossable", "niveau_automatisme": "programmateur", "hierarchie": "eau",
    "analyse_validee_le": "2026-03-04", "besoin_pointe_mm_j": 4.5, "temps_fonctionnement_h_j": 18, "secteurs": 6, "simultaneite": 2,
    "technique_organes": "goutteurs 2,2 l/h autorégulants, 0,75 m, 1 rampe par rang", "pression_service_bar": 1.5, "diametres_vitesses": "principale PEHD DN90 PN10 (1,2 m/s), secondaires DN63",
    "pertes_charge_m": 9.5, "hmt_m": 52, "pompe": "Caprari E6S 30 m³/h à 52 m", "filtration": "disques 120 mesh, contre-lavage automatique", "uniformite_visee_pct": 90,
    "etat": "en_service", "pv_date": "2026-04-18", "pv_intervenant": "Durand Irrigation — P. Roux", "pv_rincage": True, "pv_essai_pression_bar": 12, "pv_essai_resultat": "tenue 2 h, sans fuite",
    "pv_pression_sortie_pompe_bar": 4.2, "pv_pression_point_defavorable_bar": 1.3, "pv_uniformite_pct": 91, "pv_kwh_m3": 0.42, "pv_securites_testees": True, "pv_antiretour": True,
    "reglage_pressions": "1,5 bar en tête de secteur ; PV : 4,2 bar sortie pompe, 1,3 bar point défavorable", "reglage_contre_lavage": "ΔP 0,5 bar",
    "equipement_ids": [(0, 0, {"categorie": "pompe", "name": "Caprari E6S 30 m³/h", "annee_pose": 2019, "marque": "Caprari"}),
                       (0, 0, {"categorie": "filtration", "name": "Filtre à disques Arkal 3\"", "annee_pose": 2026}),
                       (0, 0, {"categorie": "gaine", "name": "Gaine Ø16 2,2 l/h 0,75 m — 12 ha", "annee_pose": 2023}),
                       (0, 0, {"categorie": "programmateur", "name": "Programmateur 8 voies", "annee_pose": 2015})]})
inst.action_reprendre_calculs()
if not inst.registre_ids:
    env["cultiveau.registre"].create({"installation_id": inst.id, "date": "2026-04-18", "genre": "mise_en_service", "description": "Mise en service (PV A1.3)", "releves": "4,2 bar / 1,3 bar / DU 91 %", "intervenant": "P. Roux"})
projet = env["project.project"].cultiveau_projet_interventions()
T = env["project.task"]
if not T.search([("name", "ilike", "Pompe disjoncte")]):
    T.create({"name": "Pompe disjoncte au démarrage — vigne en véraison", "project_id": projet.id, "partner_id": agri.id, "cultiveau_installation_id": inst.id,
              "cultiveau_nature": "depannage", "cultiveau_urgence": "immediate", "cultiveau_origine": "assistant", "cultiveau_reference_appel": "APL-2026-0042",
              "cultiveau_symptome": "disjoncteur saute 2 s après le démarrage", "priority": "1"})
    T.create({"name": "Remise en service de pré-saison", "project_id": projet.id, "partner_id": agri.id, "cultiveau_installation_id": inst.id,
              "cultiveau_nature": "remise_en_service", "cultiveau_urgence": "non_urgent", "stage_id": projet.type_ids[1].id})
env.cr.commit()
agri = env["res.partner"].search([("name", "=", "Jean Martin")], limit=1)
inst = env["cultiveau.installation"].search([("name", "ilike", "Mas Neuf")], limit=1)
SO = env["sale.order"]
devis = SO.search([("partner_id", "=", agri.id)], limit=1)
if not devis:
    ctx = inst.action_nouveau_devis()["context"]
    devis = SO.with_context(ctx).create({"partner_id": agri.id})
    devis._onchange_sale_order_template_id()
    P = env["product.product"]
    def art(nom, prix, code):
        return P.search([("default_code", "=", code)], limit=1) or P.create({"name": nom, "list_price": prix, "default_code": code, "type": "consu"})
    lignes = [("Lot 1", "Pompe immergée Caprari E6S 30 m³/h — 52 m", 3850, "POMPE-E6S-30"), ("Lot 1", "Armoire variateur 11 kW, marche à sec, pressostat", 2960, "ARM-VAR-11"),
              ("Lot 2", "Filtre à disques 3\" 120 mesh, contre-lavage automatique", 2420, "FIL-DISQ-3"), ("Lot 2", "Disconnecteur BA DN65", 890, "DISC-BA-65"),
              ("Lot 3", "Tube PEHD DN90 PN10 (420 m)", 2940, "PE-90-PN10"), ("Lot 4", "Gaine Ø16 goutteurs 2,2 l/h / 0,75 m (16 000 m)", 7680, "GAINE-16-22"),
              ("Lot 4", "Régulateur de pression 1,5 bar par secteur (6)", 540, "REG-15"), ("Lot 5", "Programmateur 8 voies + 6 électrovannes", 1890, "PROG-8V"),
              ("Lot 6", "Pose, tranchées, raccordements (forfait)", 6400, "POSE-GAG"), ("Lot 6", "Mise en service, PV A1.3, fiche de réglage A1.5, formation", 950, "MES-PV")]
    sections = {l.name: l for l in devis.order_line.filtered(lambda l: l.display_type == "line_section")}
    for lot, nom, prix, code in lignes:
        sect = next((s for n, s in sections.items() if n.startswith(lot)), None)
        env["sale.order.line"].create({"order_id": devis.id, "product_id": art(nom, prix, code).id, "product_uom_qty": 1, "sequence": (sect.sequence if sect else 0) + 5})
    devis.write({"cultiveau_installation_id": inst.id})
lead = env["crm.lead"].search([("partner_id", "=", agri.id)], limit=1)
if not lead:
    for nom, etape, qui in [("Goutte à goutte vigne Mas Neuf — extension 4 ha", "cultiveau_ventes.stage_etude", agri),
                             ("Pivot 40 ha — Gaec du Vidourle", "cultiveau_ventes.stage_analyse", None), ("Enrouleur maïs — Earl des Oliviers", "cultiveau_ventes.stage_devis", None),
                             ("Micro-aspersion pêchers — demande du 12/09", "cultiveau_ventes.stage_demande", None)]:
        env["crm.lead"].create({"name": nom, "type": "opportunity", "partner_id": qui.id if qui else False, "stage_id": env.ref(etape).id,
                                "cultiveau_type_systeme": "goutte_surface", "cultiveau_origine": "assistant", "expected_revenue": 25000})
env.cr.commit()
print("devis", devis.id, "installation", inst.id, "agri", agri.id)
