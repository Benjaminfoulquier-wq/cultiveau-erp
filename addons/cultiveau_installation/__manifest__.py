{
    "name": "Cultiveau — parc installé (référentiel V4)",
    "summary": "Chaque installation d'irrigation, du besoin au suivi : analyse des besoins, dimensionnement, mise en service, fiche de réglage, équipements, registre.",
    "description": """
Le parc installé, selon le référentiel technique Cultiveau V4
=============================================================

Un installateur d'irrigation vit de son parc installé : les stations, réseaux, pivots, enrouleurs et
goutte-à-goutte posés chez ses clients, à dépanner en été, à visiter avant la saison, à hiverner, à
renouveler. Odoo n'en a aucune notion. Ce module ajoute l'**installation** (un site d'irrigation chez
un agriculteur) et déroule les six phases du référentiel (§ 3.1) avec les pièces du dossier technique :

- **A1.1 analyse des besoins**, validée avec l'exploitant avant tout dimensionnement : parcellaire,
  assolement et culture la plus exigeante, sol, ressource (débit mobilisable, volume autorisé, titre
  de prélèvement), énergie (puissance souscrite), contraintes, hiérarchie eau / énergie / rendement ;
- **A1.2 note de dimensionnement** en douze lignes, avec le calcul du débit fictif continu et du
  débit d'équipement, et les ordres de grandeur économiques (§ 3.3.1) ;
- **A1.3 PV de mise en service** et **A1.4 certificat** : la protection sanitaire (anti-retour) est
  un point d'arrêt ; le PV fixe les valeurs de référence sans lesquelles « on ne dépanne pas, on tâtonne » ;
- **A1.5 fiche de réglage** ; **A1.8 registre** ; équipements posés avec leur durée de vie (§ 3.9)
  et l'alerte de renouvellement ; rappels de remise en service (§ 18.3) et d'hivernage (§ 18.5) ;
- le **dossier technique** imprimable (§ 3.10).
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "license": "LGPL-3",
    "depends": ["cultiveau_base", "cultiveau_frise", "cultiveau_catalogue"],
    "data": [
        "security/ir.model.access.csv",
        "security/regles.xml",
        "data/cron.xml",
        "report/dossier_technique.xml",
        "views/installation_views.xml",
        "views/equipement_views.xml",
        "views/res_partner_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
}
