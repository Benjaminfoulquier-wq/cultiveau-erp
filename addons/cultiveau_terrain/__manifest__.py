{
    "name": "Cultiveau — terrain (bons d'intervention, planning, stock camion)",
    "summary": "Le technicien chez le client : planning, bon d'intervention signé sur place, pièces sorties de son camion, facture en un clic.",
    "description": """
Le terrain dans l'ERP
=====================

- **Planning des techniciens** : chaque intervention a son créneau (début, fin) ; calendrier par technicien,
  « Ma journée » sur le téléphone.
- **Bon d'intervention** : ouvert depuis l'intervention (« Arrivé sur place »), heures d'arrivée et de départ, temps de
  trajet et kilomètres, pièces posées, main-d'œuvre et déplacement chiffrés, relevés de pression comparés au PV de mise
  en service, photos, signature du client et du technicien sur l'écran ; PDF au nom de l'adhérent, envoyé par e-mail.
- **Facture en un clic** : un bon signé devient une facture ; plusieurs bons d'un même client se regroupent sur une
  facture (fin de mois).
- **Stock camion** : chaque technicien a son camion (un emplacement de stock) ; les pièces du bon signé en sortent ;
  le réassort remet le camion à sa dotation.
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "license": "LGPL-3",
    "depends": ["cultiveau_interventions", "cultiveau_chantier", "stock", "account"],
    "data": [
        "security/ir.model.access.csv",
        "data/donnees.xml",
        "report/bon_report.xml",
        "data/mail.xml",
        "views/bon_views.xml",
        "views/intervention_views.xml",
        "views/camion_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
}
