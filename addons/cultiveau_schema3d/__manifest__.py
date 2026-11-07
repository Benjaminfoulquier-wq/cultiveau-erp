{
    "name": "Cultiveau — Schéma 3D vers devis",
    "summary": "L'étude dessinée dans Schéma 3D (format d'échange Cultiveau) devient l'analyse des besoins, la note de dimensionnement et le devis par lots",
    "description": """
Schéma 3D vers devis
====================

L'installateur dessine son réseau dans Schéma 3D (schema3d.cultiveau.fr) et exporte l'étude au format d'échange Cultiveau.
L'ERP importe ce fichier sur l'installation :

- les trames A1.1 (analyse des besoins) et A1.2 (note de dimensionnement) remplissent les champs vides de l'installation,
  chaque valeur avec son origine ;
- la nomenclature du schéma (tubes au mètre, raccords, vannes, filtration, pompe, automatisme) devient un devis par lots,
  chaque ligne rapprochée du catalogue par sa référence, sinon « à préciser » avec sa désignation et son fournisseur ;
- le fichier reste attaché à l'installation (pièce du dossier technique, § 3.10.1) ; les non-conformités du contrôle avant
  émission et les avertissements de l'étude sont rappelés sur le devis.
""",
    "version": "18.0.1.0.0",
    "category": "Cultiveau",
    "author": "Cultiveau",
    "website": "https://cultiveau.fr",
    "license": "LGPL-3",
    "depends": ["cultiveau_dimensionnement", "cultiveau_ventes", "cultiveau_catalogue"],
    "data": ["security/ir.model.access.csv", "views/importer_views.xml"],
    "installable": True,
    "auto_install": False,
}
