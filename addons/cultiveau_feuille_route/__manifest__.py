{
    "name": "Cultiveau — Feuille de route des salariés",
    "summary": "Les salariés sans accès à l'ERP sont planifiés sur les interventions et les chantiers ; ils reçoivent leur journée la veille par e-mail et l'ouvrent sur leur téléphone par un simple lien",
    "description": """
Feuille de route des salariés
=============================

Un installateur n'achète pas un accès ERP pour chaque poseur. Pourtant il faut bien que chacun sache où aller demain, chez qui,
avec quoi dans le camion. Ici :

- les **salariés sans accès** (fiches employé sans utilisateur) s'affectent aux interventions et aux chantiers comme les autres ;
- chacun a sa **page du jour**, ouverte sur le téléphone par un lien personnel sans mot de passe : heure, client, téléphone,
  adresse et itinéraire, nature, consignes, produits à embarquer, chantier et phase du jour ;
- la **veille au soir**, un e-mail lui envoie sa journée du lendemain (et le vendredi, celle du lundi) ; le gérant peut
  l'envoyer à la main à tout moment.
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "website": "https://cultiveau.fr",
    "license": "LGPL-3",
    "depends": ["cultiveau_terrain", "cultiveau_chantier", "hr"],
    "data": ["data/cron.xml", "views/views.xml"],
    "installable": True,
    "auto_install": False,
}
