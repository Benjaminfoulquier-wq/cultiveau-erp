"""Le climat de chaque département, pour adapter la frise culturale et les Kc (addons/cultiveau_frise/data/climat_departements.xml).

Par département : l'ETo de référence (Penman-Monteith, mm/j) et la pluie (mm) de chaque mois, le vent à 2 m et l'humidité relative
minimale de l'été (qui corrigent le Kc de mi-saison et de fin de cycle, FAO-56 équations 62 et 65), et le décalage du calendrier
cultural par rapport à la frise France (jours, négatif = en avance).

Les valeurs sont celles de la zone climatique du département (moyennes établies d'après les normales 1991-2020) : un point de
départ, à remplacer dans l'ERP par les normales de la station Météo-France la plus proche quand on les a.

    python3 scripts/generer_climat.py
"""
import os
from xml.sax.saxutils import escape

ICI = os.path.dirname(os.path.abspath(__file__))
SORTIE = os.path.join(ICI, "..", "addons", "cultiveau_frise", "data", "climat_departements.xml")

# zone : (libellé, ETo mm/j x 12, pluie mm x 12, vent u2 m/s, HR min %, décalage jours)
ZONES = {
    "med_littoral": ("Méditerranée littorale", [1.2, 1.8, 2.8, 3.8, 4.8, 5.8, 6.3, 5.5, 3.9, 2.4, 1.4, 1.0],
                     [55, 50, 40, 55, 45, 25, 15, 30, 75, 95, 70, 60], 3.0, 40, -15),
    "med_interieur": ("Provence et vallée du Rhône méridionale", [0.9, 1.5, 2.6, 3.6, 4.6, 5.6, 6.2, 5.3, 3.6, 2.1, 1.1, 0.8],
                      [50, 45, 45, 60, 65, 40, 30, 45, 80, 95, 75, 55], 2.5, 35, -10),
    "sud_ouest": ("Sud-Ouest (Garonne, Gers, Tarn)", [0.7, 1.2, 2.2, 3.1, 4.0, 4.9, 5.4, 4.7, 3.2, 1.8, 0.9, 0.6],
                  [55, 50, 50, 70, 75, 60, 40, 50, 55, 60, 60, 60], 2.0, 42, -10),
    "aquitaine": ("Aquitaine océanique (Landes, Gironde, Béarn)", [0.7, 1.2, 2.1, 3.0, 3.8, 4.6, 5.0, 4.4, 3.0, 1.7, 0.9, 0.6],
                  [90, 75, 70, 80, 80, 60, 50, 55, 75, 90, 100, 100], 1.8, 48, -10),
    "centre_ouest": ("Centre-Ouest (Charentes, Poitou, Vendée)", [0.6, 1.1, 2.0, 2.9, 3.8, 4.6, 5.0, 4.4, 2.9, 1.6, 0.8, 0.5],
                     [75, 60, 55, 60, 65, 45, 45, 45, 60, 80, 85, 85], 2.4, 45, -5),
    "centre_loire": ("Centre et Val de Loire", [0.5, 1.0, 1.9, 2.8, 3.6, 4.3, 4.7, 4.1, 2.7, 1.4, 0.7, 0.4],
                     [55, 50, 50, 50, 60, 50, 50, 45, 55, 65, 60, 65], 2.2, 45, 0),
    "nord_bassin": ("Bassin parisien et Champagne", [0.4, 0.9, 1.7, 2.6, 3.4, 4.0, 4.4, 3.8, 2.5, 1.3, 0.6, 0.4],
                    [50, 45, 50, 45, 60, 55, 60, 55, 50, 60, 55, 60], 2.4, 48, 5),
    "nord_manche": ("Nord et Manche", [0.4, 0.8, 1.5, 2.4, 3.1, 3.6, 3.9, 3.4, 2.2, 1.2, 0.6, 0.4],
                    [60, 50, 55, 50, 60, 60, 60, 65, 60, 75, 75, 75], 3.0, 55, 10),
    "bretagne": ("Bretagne", [0.5, 0.9, 1.6, 2.5, 3.2, 3.7, 3.9, 3.4, 2.4, 1.3, 0.7, 0.5],
                 [90, 70, 65, 55, 60, 45, 45, 50, 60, 90, 95, 100], 2.8, 55, 5),
    "est": ("Est continental (Lorraine, Alsace, Bourgogne, Franche-Comté)", [0.4, 0.8, 1.6, 2.6, 3.4, 4.0, 4.4, 3.8, 2.5, 1.2, 0.5, 0.3],
            [55, 50, 55, 55, 75, 80, 70, 70, 60, 65, 65, 65], 1.8, 48, 7),
    "rhone_alpes": ("Plaines de Rhône-Alpes et d'Auvergne", [0.5, 1.0, 1.9, 2.9, 3.7, 4.5, 5.0, 4.3, 2.9, 1.5, 0.6, 0.4],
                    [55, 50, 55, 70, 85, 75, 65, 75, 85, 95, 85, 65], 2.0, 42, 0),
    "limousin": ("Limousin, Rouergue (moyenne montagne)", [0.4, 0.8, 1.6, 2.5, 3.3, 4.0, 4.4, 3.8, 2.5, 1.3, 0.6, 0.4],
                 [100, 85, 80, 90, 100, 80, 65, 75, 85, 100, 105, 110], 2.0, 45, 10),
    "montagne": ("Montagne (Alpes, Massif central d'altitude)", [0.4, 0.8, 1.5, 2.4, 3.1, 3.8, 4.2, 3.6, 2.4, 1.2, 0.5, 0.3],
                 [90, 80, 80, 90, 110, 90, 70, 85, 90, 100, 105, 100], 2.0, 45, 20),
    "tropical": ("Tropical humide (DOM)", [4.2, 4.5, 5.0, 5.0, 4.6, 4.3, 4.4, 4.8, 5.0, 4.8, 4.4, 4.1],
                 [110, 90, 90, 110, 160, 140, 160, 190, 210, 220, 190, 140], 3.0, 60, 0),
}

DEPARTEMENTS = [
    ("01", "Ain", "rhone_alpes"), ("02", "Aisne", "nord_bassin"), ("03", "Allier", "centre_loire"), ("04", "Alpes-de-Haute-Provence", "med_interieur"),
    ("05", "Hautes-Alpes", "montagne"), ("06", "Alpes-Maritimes", "med_littoral"), ("07", "Ardèche", "med_interieur"), ("08", "Ardennes", "est"),
    ("09", "Ariège", "sud_ouest"), ("10", "Aube", "nord_bassin"), ("11", "Aude", "med_littoral"), ("12", "Aveyron", "limousin"),
    ("13", "Bouches-du-Rhône", "med_littoral"), ("14", "Calvados", "nord_manche"), ("15", "Cantal", "montagne"), ("16", "Charente", "centre_ouest"),
    ("17", "Charente-Maritime", "centre_ouest"), ("18", "Cher", "centre_loire"), ("19", "Corrèze", "limousin"), ("21", "Côte-d'Or", "est"),
    ("22", "Côtes-d'Armor", "bretagne"), ("23", "Creuse", "limousin"), ("24", "Dordogne", "sud_ouest"), ("25", "Doubs", "est"),
    ("26", "Drôme", "med_interieur"), ("27", "Eure", "nord_bassin"), ("28", "Eure-et-Loir", "centre_loire"), ("29", "Finistère", "bretagne"),
    ("2A", "Corse-du-Sud", "med_littoral"), ("2B", "Haute-Corse", "med_littoral"), ("30", "Gard", "med_littoral"), ("31", "Haute-Garonne", "sud_ouest"),
    ("32", "Gers", "sud_ouest"), ("33", "Gironde", "aquitaine"), ("34", "Hérault", "med_littoral"), ("35", "Ille-et-Vilaine", "bretagne"),
    ("36", "Indre", "centre_loire"), ("37", "Indre-et-Loire", "centre_loire"), ("38", "Isère", "rhone_alpes"), ("39", "Jura", "est"),
    ("40", "Landes", "aquitaine"), ("41", "Loir-et-Cher", "centre_loire"), ("42", "Loire", "rhone_alpes"), ("43", "Haute-Loire", "montagne"),
    ("44", "Loire-Atlantique", "centre_loire"), ("45", "Loiret", "centre_loire"), ("46", "Lot", "sud_ouest"), ("47", "Lot-et-Garonne", "sud_ouest"),
    ("48", "Lozère", "montagne"), ("49", "Maine-et-Loire", "centre_loire"), ("50", "Manche", "nord_manche"), ("51", "Marne", "nord_bassin"),
    ("52", "Haute-Marne", "est"), ("53", "Mayenne", "centre_loire"), ("54", "Meurthe-et-Moselle", "est"), ("55", "Meuse", "est"),
    ("56", "Morbihan", "bretagne"), ("57", "Moselle", "est"), ("58", "Nièvre", "est"), ("59", "Nord", "nord_manche"), ("60", "Oise", "nord_bassin"),
    ("61", "Orne", "nord_manche"), ("62", "Pas-de-Calais", "nord_manche"), ("63", "Puy-de-Dôme", "rhone_alpes"), ("64", "Pyrénées-Atlantiques", "aquitaine"),
    ("65", "Hautes-Pyrénées", "sud_ouest"), ("66", "Pyrénées-Orientales", "med_littoral"), ("67", "Bas-Rhin", "est"), ("68", "Haut-Rhin", "est"),
    ("69", "Rhône", "rhone_alpes"), ("70", "Haute-Saône", "est"), ("71", "Saône-et-Loire", "est"), ("72", "Sarthe", "centre_loire"),
    ("73", "Savoie", "montagne"), ("74", "Haute-Savoie", "montagne"), ("75", "Paris", "nord_bassin"), ("76", "Seine-Maritime", "nord_manche"),
    ("77", "Seine-et-Marne", "nord_bassin"), ("78", "Yvelines", "nord_bassin"), ("79", "Deux-Sèvres", "centre_ouest"), ("80", "Somme", "nord_bassin"),
    ("81", "Tarn", "sud_ouest"), ("82", "Tarn-et-Garonne", "sud_ouest"), ("83", "Var", "med_littoral"), ("84", "Vaucluse", "med_interieur"),
    ("85", "Vendée", "centre_ouest"), ("86", "Vienne", "centre_ouest"), ("87", "Haute-Vienne", "limousin"), ("88", "Vosges", "est"),
    ("89", "Yonne", "nord_bassin"), ("90", "Territoire de Belfort", "est"), ("91", "Essonne", "nord_bassin"), ("92", "Hauts-de-Seine", "nord_bassin"),
    ("93", "Seine-Saint-Denis", "nord_bassin"), ("94", "Val-de-Marne", "nord_bassin"), ("95", "Val-d'Oise", "nord_bassin"),
    ("971", "Guadeloupe", "tropical"), ("972", "Martinique", "tropical"), ("973", "Guyane", "tropical"), ("974", "La Réunion", "tropical"), ("976", "Mayotte", "tropical"),
]


def generer():
    lignes = ['<?xml version="1.0" encoding="utf-8"?>', "<!-- Généré par scripts/generer_climat.py : modifier le script, pas ce fichier. -->",
              "<odoo>", '    <data noupdate="1">']
    for code, nom, zone in DEPARTEMENTS:
        libelle, eto, pluie, u2, hr, decalage = ZONES[zone]
        champs = [("code", code), ("name", nom), ("zone", zone), ("vent_u2", u2), ("hr_min", hr), ("decalage_jours", decalage)]
        champs += [(f"eto_{m}", eto[m - 1]) for m in range(1, 13)] + [(f"pluie_{m}", pluie[m - 1]) for m in range(1, 13)]
        lignes.append(f'        <record id="climat_{code.lower()}" model="cultiveau.climat">')
        lignes += [f'            <field name="{k}">{escape(str(v))}</field>' for k, v in champs]
        lignes.append("        </record>")
    lignes += ["    </data>", "</odoo>", ""]
    with open(SORTIE, "w") as f:
        f.write("\n".join(lignes))
    return len(DEPARTEMENTS)


if __name__ == "__main__":
    print(f"{generer()} départements -> {os.path.relpath(SORTIE)}")
