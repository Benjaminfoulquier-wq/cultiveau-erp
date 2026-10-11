"""Le catalogue des cultures de France (et des DOM) : frise culturale nationale et coefficients culturaux FAO-56.

Produit addons/cultiveau_frise/data/cultures_france.xml :
- chaque culture avec ses Kc de référence (Kc ini, mi-saison, fin ; FAO-56, Allen et al. 1998, tableau 12), la durée indicative
  de ses quatre phases (tableau 11, adaptée à la France), sa hauteur, son enracinement et la fraction p (tableau 22) ;
- sa frise « France » (département vide : valable partout où il n'existe pas de frise locale, comme celle du Gard) : les stades
  mois par mois, avec Kc mini/maxi du stade, besoin en % de l'ETP, ETP de référence du mois et conseil d'irrigation ;
- ses fenêtres commerciales : le projet après la récolte, l'achat avant le premier besoin d'eau.

    python3 scripts/generer_cultures.py

Les valeurs marquées « ≈ » n'existent pas dans FAO-56 : elles sont estimées d'après la culture la plus proche (indiqué dans la note).
"""
import os
from xml.sax.saxutils import escape

ICI = os.path.dirname(os.path.abspath(__file__))
SORTIE = os.path.join(ICI, "..", "addons", "cultiveau_frise", "data", "cultures_france.xml")

# Les 14 cultures déjà décrites pour le Gard (frise_gard.xml) gardent leur identifiant ; elles reçoivent ici leurs Kc et leur frise France.
EXISTANTES = {"vigne", "ble_dur", "pecher", "olivier", "riz", "tournesol", "abricotier", "melon", "tomate", "prairies", "pommier", "colza",
              "asperge", "cerisier"}

# ETo de référence par mois, France (moyenne nationale, mm/j) : (mini, maxi). Le sud dépasse le maxi l'été ; le nord reste au mini.
ETP = {1: (0.4, 0.8), 2: (0.8, 1.4), 3: (1.5, 2.3), 4: (2.3, 3.3), 5: (3.0, 4.2), 6: (3.6, 5.0),
       7: (4.0, 5.6), 8: (3.5, 5.0), 9: (2.3, 3.5), 10: (1.2, 2.2), 11: (0.5, 1.1), 12: (0.3, 0.7)}

COULEURS = {"grandes_cultures": ["#c9a227", "#b8860b", "#d4a017", "#e1ad01", "#a67c00", "#cfa63d", "#9c7a2e"],
            "prairies": ["#5b8c2a", "#6fa03a", "#4f7d23", "#7cae4a"], "maraichage": ["#e4572e", "#d1495b", "#f28f3b", "#c8553d", "#e07a5f", "#ef8354"],
            "arbo": ["#a23b72", "#c0392b", "#8e44ad", "#d35400", "#6b8e23", "#b03a2e"], "petits_fruits": ["#7b2d8b", "#9b2c5a", "#5b2a86"],
            "vigne": ["#6b2d5c", "#8e3b74", "#4a6b2a"], "ppam": ["#8e7cc3", "#6c5ba7"], "sous_abri": ["#2a9d8f", "#3ab0a2", "#21867a"],
            "espaces_verts": ["#38a169", "#2f855a", "#48bb78"], "pepiniere": ["#319795", "#2c7a7b"], "tropicales": ["#dd6b20", "#c05621", "#b7791f"]}

# Le conseil d'irrigation par type de stade (une culture peut le remplacer).
IRRIGATION = {
    "repos": "Non : repos végétatif (vérifier la vidange et l'hivernage du réseau)",
    "ini": "Selon la pluie : apport de levée ou de reprise si le sol est sec, doses faibles et fréquentes",
    "dev": "Oui dès que la réserve baisse : apports réguliers, le besoin monte avec la couverture",
    "mi": "Oui, pleine période de besoin : ne jamais laisser la réserve se vider (période critique)",
    "fin": "Réduire progressivement, puis arrêter avant la récolte",
}
# La part du Kc de la phase prise par chaque type de stade : (Kc mini, Kc maxi)
def kc_du_stade(t, ini, mi, fin):
    return {"repos": (0.0, 0.0), "ini": (ini, ini), "dev": (min(ini, mi), max(ini, mi)), "mi": (mi, mi),
            "fin": (min(mi, fin), max(mi, fin))}[t]


def C(code, nom, cat, kc, durees, h, racines, p, stades, irr=None, note="", fenetres=None):
    return dict(code=code, nom=nom, cat=cat, kc=kc, durees=durees, h=h, racines=racines, p=p, stades=stades, irr=irr or {}, note=note,
                fenetres=fenetres)


# stades : (nom, mois de début, mois de fin, type) — type : repos, ini (initiale), dev (développement), mi (mi-saison), fin (arrière-saison)
CULTURES = [
    # ------------------------------------------------------------------ grandes cultures : céréales
    C("ble_tendre", "Blé tendre d'hiver", "grandes_cultures", (0.4, 1.15, 0.30), (30, 140, 40, 30), 1.0, (1.5, 1.8), 0.55,
      [("Semis – levée", 10, 11, "ini"), ("Tallage (hiver)", 12, 2, "ini"), ("Montaison", 3, 4, "dev"), ("Épiaison – floraison", 5, 5, "mi"),
       ("Remplissage du grain", 6, 6, "fin"), ("Moisson (récolte)", 7, 7, "fin")],
      irr={"mi": "Oui en printemps sec ou sol superficiel : 1 à 3 apports de la montaison au remplissage", "dev": "Selon la pluie : premier apport à la montaison si la réserve est entamée"}),
    C("ble_dur", "Blé dur", "grandes_cultures", (0.4, 1.15, 0.30), (30, 140, 40, 30), 1.0, (1.5, 1.8), 0.55,
      [("Semis – levée", 10, 11, "ini"), ("Tallage (hiver)", 12, 2, "ini"), ("Montaison", 3, 4, "dev"), ("Épiaison – floraison", 5, 5, "mi"),
       ("Remplissage du grain", 6, 6, "fin"), ("Moisson (récolte)", 7, 7, "fin")],
      irr={"mi": "Oui : 2 à 3 apports de la montaison au remplissage (qualité, mitadinage)"}),
    C("orge_hiver", "Orge d'hiver", "grandes_cultures", (0.3, 1.15, 0.25), (25, 135, 35, 25), 1.0, (1.0, 1.5), 0.55,
      [("Semis – levée", 9, 10, "ini"), ("Tallage (hiver)", 11, 2, "ini"), ("Montaison", 3, 4, "dev"), ("Épiaison – floraison", 4, 5, "mi"),
       ("Remplissage – moisson", 6, 7, "fin")],
      irr={"mi": "Rarement : 1 à 2 apports en sol superficiel si le printemps est sec"}),
    C("orge_printemps", "Orge de printemps", "grandes_cultures", (0.3, 1.15, 0.25), (15, 30, 65, 40), 1.0, (1.0, 1.5), 0.55,
      [("Semis – levée", 2, 3, "ini"), ("Tallage", 4, 4, "dev"), ("Montaison", 5, 5, "dev"), ("Épiaison – floraison", 6, 6, "mi"),
       ("Remplissage – moisson", 7, 7, "fin")], irr={"mi": "Oui en sol séchant : 1 à 3 apports de la montaison à la floraison (brasserie)"}),
    C("avoine", "Avoine", "grandes_cultures", (0.3, 1.15, 0.25), (15, 30, 65, 40), 1.0, (1.0, 1.5), 0.55,
      [("Semis – levée", 2, 3, "ini"), ("Tallage – montaison", 4, 5, "dev"), ("Épiaison – floraison", 6, 6, "mi"), ("Maturation – moisson", 7, 8, "fin")]),
    C("seigle", "Seigle", "grandes_cultures", (0.3, 1.15, 0.25), (30, 140, 40, 30), 1.2, (1.0, 1.5), 0.55,
      [("Semis – levée", 10, 10, "ini"), ("Tallage (hiver)", 11, 2, "ini"), ("Montaison", 3, 4, "dev"), ("Épiaison – floraison", 5, 5, "mi"),
       ("Maturation – moisson", 6, 7, "fin")], note="Kc des céréales à paille (FAO-56)."),
    C("triticale", "Triticale", "grandes_cultures", (0.3, 1.15, 0.25), (30, 140, 40, 30), 1.1, (1.0, 1.6), 0.55,
      [("Semis – levée", 10, 11, "ini"), ("Tallage (hiver)", 12, 2, "ini"), ("Montaison", 3, 4, "dev"), ("Épiaison – floraison", 5, 5, "mi"),
       ("Maturation – moisson", 6, 7, "fin")], note="Kc des céréales à paille (FAO-56)."),
    C("epeautre", "Épeautre", "grandes_cultures", (0.3, 1.15, 0.25), (30, 140, 40, 30), 1.2, (1.0, 1.5), 0.55,
      [("Semis – levée", 10, 11, "ini"), ("Tallage (hiver)", 12, 2, "ini"), ("Montaison", 3, 4, "dev"), ("Épiaison – floraison", 5, 6, "mi"),
       ("Maturation – moisson", 7, 8, "fin")], note="≈ Kc des céréales à paille."),
    C("mais_grain", "Maïs grain", "grandes_cultures", (0.3, 1.20, 0.35), (30, 40, 50, 30), 2.0, (1.0, 1.7), 0.55,
      [("Semis – levée", 4, 5, "ini"), ("Croissance végétative", 6, 6, "dev"), ("Floraison (sortie des soies)", 7, 7, "mi"),
       ("Remplissage du grain", 8, 8, "mi"), ("Maturation – récolte", 9, 10, "fin")],
      irr={"mi": "Oui, impératif : 15 jours avant à 15 jours après la floraison, puis jusqu'au stade 50 % d'humidité du grain",
           "dev": "Oui dès 8–10 feuilles si la réserve baisse : tours d'eau de 25–35 mm"}),
    C("mais_ensilage", "Maïs ensilage", "grandes_cultures", (0.3, 1.20, 0.60), (30, 40, 50, 20), 2.0, (1.0, 1.7), 0.55,
      [("Semis – levée", 4, 5, "ini"), ("Croissance végétative", 6, 6, "dev"), ("Floraison (sortie des soies)", 7, 7, "mi"),
       ("Remplissage du grain", 8, 8, "mi"), ("Récolte (ensilage)", 9, 9, "fin")],
      irr={"mi": "Oui, impératif autour de la floraison : c'est là que se fait le rendement"}),
    C("mais_semence", "Maïs semence", "grandes_cultures", (0.3, 1.20, 0.50), (30, 40, 50, 25), 2.0, (1.0, 1.7), 0.55,
      [("Semis – levée (décalés mâles / femelles)", 4, 5, "ini"), ("Croissance végétative", 6, 6, "dev"), ("Floraison – castration", 7, 7, "mi"),
       ("Remplissage du grain", 8, 8, "mi"), ("Récolte", 9, 9, "fin")],
      irr={"mi": "Oui, sans aucun manque : la floraison des lignées est très sensible (contrat semencier)"}),
    C("mais_doux", "Maïs doux", "grandes_cultures", (0.3, 1.15, 1.05), (20, 25, 25, 10), 1.5, (0.8, 1.2), 0.50,
      [("Semis – levée", 4, 6, "ini"), ("Croissance végétative", 6, 6, "dev"), ("Floraison", 7, 7, "mi"), ("Récolte", 8, 9, "fin")],
      irr={"fin": "Oui jusqu'à la récolte : le grain doit rester tendre"}),
    C("sorgho_grain", "Sorgho grain", "grandes_cultures", (0.3, 1.05, 0.55), (20, 35, 40, 30), 1.5, (1.0, 2.0), 0.55,
      [("Semis – levée", 5, 5, "ini"), ("Croissance végétative", 6, 6, "dev"), ("Floraison", 7, 7, "mi"), ("Remplissage du grain", 8, 8, "mi"),
       ("Maturation – récolte", 9, 10, "fin")], irr={"mi": "Selon le sol : 1 à 2 apports autour de la floraison suffisent souvent (culture rustique)"}),
    C("sorgho_fourrager", "Sorgho fourrager", "prairies", (0.3, 1.20, 1.05), (20, 30, 60, 15), 2.0, (1.0, 2.0), 0.55,
      [("Semis – levée", 5, 6, "ini"), ("Croissance", 6, 7, "dev"), ("Coupes ou pâturage", 7, 9, "mi"), ("Dernière coupe", 9, 10, "fin")],
      note="Kc du sorgho fourrager (FAO-56, sweet sorghum)."),
    C("millet", "Millet, moha", "grandes_cultures", (0.3, 1.00, 0.30), (15, 25, 40, 25), 1.5, (1.0, 2.0), 0.55,
      [("Semis – levée", 5, 6, "ini"), ("Croissance", 6, 7, "dev"), ("Floraison", 7, 8, "mi"), ("Récolte", 8, 9, "fin")]),
    C("riz", "Riz", "grandes_cultures", (1.05, 1.20, 0.90), (30, 30, 80, 40), 1.0, (0.5, 1.0), 0.20,
      [("Semis en eau – levée", 4, 5, "ini"), ("Tallage", 5, 6, "dev"), ("Montaison – floraison", 7, 8, "mi"), ("Maturation – récolte", 9, 10, "fin")],
      irr={"ini": "Oui : mise en eau des rizières (lame d'eau permanente)", "dev": "Oui : lame d'eau maintenue", "mi": "Oui : lame d'eau maintenue, ne jamais assécher à la floraison",
           "fin": "Assec 2 à 3 semaines avant la récolte"}),
    C("sarrasin", "Sarrasin", "grandes_cultures", (0.3, 1.00, 0.30), (15, 20, 30, 20), 1.0, (0.6, 1.0), 0.55,
      [("Semis – levée", 5, 6, "ini"), ("Croissance", 6, 7, "dev"), ("Floraison", 7, 8, "mi"), ("Récolte", 9, 9, "fin")], note="≈ Kc du millet (céréale de cycle court)."),
    C("quinoa", "Quinoa", "grandes_cultures", (0.3, 1.00, 0.50), (20, 40, 50, 30), 1.5, (0.8, 1.2), 0.60,
      [("Semis – levée", 3, 4, "ini"), ("Croissance", 5, 5, "dev"), ("Floraison", 6, 6, "mi"), ("Remplissage", 7, 7, "mi"), ("Récolte", 8, 8, "fin")],
      note="≈ Kc des céréales de printemps (valeurs publiées 0,5 / 1,0 / 0,7 selon les essais)."),
    # ------------------------------------------------------------------ oléagineux, protéagineux, textiles, industrielles
    C("colza", "Colza", "grandes_cultures", (0.35, 1.10, 0.35), (25, 60, 70, 35), 1.5, (1.0, 1.5), 0.60,
      [("Semis – levée", 8, 9, "ini"), ("Rosette (automne – hiver)", 10, 2, "ini"), ("Reprise – montaison", 3, 3, "dev"), ("Floraison", 4, 4, "mi"),
       ("Remplissage des siliques", 5, 6, "mi"), ("Maturation – récolte", 7, 7, "fin")],
      irr={"ini": "Oui si le sol est sec : 20 à 30 mm pour assurer la levée en fin d'été", "mi": "Rarement : 1 apport en floraison si le printemps est très sec"}),
    C("tournesol", "Tournesol", "grandes_cultures", (0.35, 1.10, 0.35), (25, 35, 45, 25), 2.0, (0.8, 1.5), 0.45,
      [("Semis – levée", 4, 5, "ini"), ("Croissance (bouton étoilé)", 5, 6, "dev"), ("Floraison", 7, 7, "mi"), ("Remplissage des graines", 8, 8, "mi"),
       ("Maturation – récolte", 9, 9, "fin")], irr={"mi": "Oui : 1 à 2 apports de 30–40 mm du bouton floral à la fin floraison"}),
    C("soja", "Soja", "grandes_cultures", (0.4, 1.15, 0.50), (20, 30, 60, 25), 0.8, (0.6, 1.3), 0.50,
      [("Semis – levée", 5, 5, "ini"), ("Croissance végétative", 6, 6, "dev"), ("Floraison", 7, 7, "mi"), ("Remplissage des gousses", 8, 8, "mi"),
       ("Maturation – récolte", 9, 10, "fin")], irr={"mi": "Oui : de la floraison au remplissage des gousses, c'est là que se joue le rendement"}),
    C("pois_proteagineux", "Pois protéagineux", "grandes_cultures", (0.5, 1.15, 0.30), (20, 30, 35, 15), 0.5, (0.6, 1.0), 0.40,
      [("Semis – levée", 2, 3, "ini"), ("Croissance", 4, 4, "dev"), ("Floraison", 5, 5, "mi"), ("Remplissage", 6, 6, "mi"), ("Récolte", 7, 7, "fin")]),
    C("feverole", "Féverole", "grandes_cultures", (0.5, 1.15, 0.30), (15, 25, 35, 15), 0.8, (0.5, 0.7), 0.45,
      [("Semis – levée", 11, 11, "ini"), ("Hiver", 12, 2, "ini"), ("Croissance", 3, 3, "dev"), ("Floraison", 4, 5, "mi"), ("Remplissage", 6, 6, "mi"),
       ("Récolte", 7, 7, "fin")]),
    C("lentille", "Lentille", "grandes_cultures", (0.4, 1.10, 0.30), (20, 30, 60, 40), 0.5, (0.6, 0.8), 0.50,
      [("Semis – levée", 3, 3, "ini"), ("Croissance", 4, 5, "dev"), ("Floraison", 6, 6, "mi"), ("Maturation – récolte", 7, 8, "fin")]),
    C("pois_chiche", "Pois chiche", "grandes_cultures", (0.4, 1.00, 0.35), (20, 30, 50, 20), 0.4, (0.6, 1.0), 0.50,
      [("Semis – levée", 3, 3, "ini"), ("Croissance", 4, 5, "dev"), ("Floraison", 6, 6, "mi"), ("Maturation – récolte", 7, 7, "fin")]),
    C("haricot_sec", "Haricot sec (lingot, flageolet)", "grandes_cultures", (0.4, 1.15, 0.35), (20, 30, 40, 20), 0.4, (0.6, 0.9), 0.45,
      [("Semis – levée", 5, 6, "ini"), ("Croissance", 6, 7, "dev"), ("Floraison", 7, 7, "mi"), ("Remplissage des gousses", 8, 8, "mi"), ("Récolte", 9, 9, "fin")],
      irr={"mi": "Oui, sans à-coups : floraison et remplissage très sensibles au stress"}),
    C("lupin", "Lupin", "grandes_cultures", (0.4, 1.10, 0.30), (20, 30, 50, 30), 0.8, (0.8, 1.5), 0.50,
      [("Semis – levée", 3, 3, "ini"), ("Croissance", 4, 5, "dev"), ("Floraison", 6, 6, "mi"), ("Maturation – récolte", 7, 8, "fin")], note="≈ Kc des légumineuses à graines."),
    C("lin_oleagineux", "Lin oléagineux", "grandes_cultures", (0.35, 1.10, 0.25), (25, 35, 50, 40), 1.2, (1.0, 1.5), 0.50,
      [("Semis – levée", 3, 3, "ini"), ("Croissance", 4, 5, "dev"), ("Floraison", 6, 6, "mi"), ("Maturation – récolte", 7, 8, "fin")]),
    C("lin_fibre", "Lin fibre (textile)", "grandes_cultures", (0.35, 1.10, 0.25), (25, 35, 40, 15), 1.2, (1.0, 1.5), 0.50,
      [("Semis – levée", 3, 4, "ini"), ("Croissance rapide", 5, 5, "dev"), ("Floraison", 6, 6, "mi"), ("Arrachage – rouissage", 7, 8, "fin")]),
    C("chanvre", "Chanvre", "grandes_cultures", (0.35, 1.15, 0.40), (20, 40, 50, 30), 3.0, (1.0, 2.0), 0.55,
      [("Semis – levée", 4, 5, "ini"), ("Croissance rapide", 6, 6, "dev"), ("Floraison", 7, 7, "mi"), ("Récolte (paille, graines)", 8, 9, "fin")],
      note="≈ Kc du lin et du maïs (pas de valeur FAO-56 publiée)."),
    C("betterave_sucriere", "Betterave sucrière", "grandes_cultures", (0.35, 1.20, 0.70), (40, 60, 70, 40), 0.5, (0.7, 1.2), 0.55,
      [("Semis – levée", 3, 4, "ini"), ("Croissance (couverture du sol)", 5, 6, "dev"), ("Pleine croissance", 7, 8, "mi"), ("Maturation", 9, 9, "fin"),
       ("Arrachage (récolte)", 10, 11, "fin")], irr={"mi": "Oui en été sec : tours d'eau de 30–40 mm, le sucre se fait en juillet–août"}),
    C("pomme_de_terre", "Pomme de terre de consommation", "grandes_cultures", (0.5, 1.15, 0.75), (25, 30, 45, 30), 0.6, (0.4, 0.6), 0.35,
      [("Plantation – levée", 3, 4, "ini"), ("Croissance", 5, 5, "dev"), ("Tubérisation – grossissement", 6, 7, "mi"), ("Maturation – défanage", 8, 8, "fin"),
       ("Récolte (arrachage)", 8, 9, "fin")], irr={"mi": "Oui, régulier : enracinement faible, la tubérisation ne supporte aucun manque (gale, déformations)"}),
    C("pdt_primeur", "Pomme de terre primeur", "maraichage", (0.5, 1.15, 0.75), (20, 25, 30, 15), 0.5, (0.4, 0.6), 0.35,
      [("Plantation – levée", 1, 2, "ini"), ("Croissance", 3, 3, "dev"), ("Tubérisation", 4, 5, "mi"), ("Récolte", 5, 6, "fin")]),
    C("pdt_plant", "Pomme de terre de plant", "grandes_cultures", (0.5, 1.15, 0.75), (25, 30, 40, 15), 0.5, (0.4, 0.6), 0.35,
      [("Plantation – levée", 3, 4, "ini"), ("Croissance", 5, 5, "dev"), ("Tubérisation", 6, 6, "mi"), ("Défanage – récolte", 7, 8, "fin")]),
    C("tabac", "Tabac", "grandes_cultures", (0.5, 1.10, 0.85), (20, 30, 40, 30), 1.5, (0.5, 1.0), 0.50,
      [("Plantation", 5, 5, "ini"), ("Croissance", 6, 6, "dev"), ("Pleine croissance – écimage", 7, 7, "mi"), ("Récolte des feuilles", 8, 9, "fin")],
      note="≈ Kc des cultures sarclées (FAO-56 n'a plus de ligne tabac)."),
    C("endive", "Endive (racines), chicorée industrielle", "grandes_cultures", (0.5, 1.10, 0.95), (20, 40, 60, 30), 0.4, (0.6, 1.0), 0.50,
      [("Semis – levée", 4, 5, "ini"), ("Croissance du feuillage", 6, 7, "dev"), ("Grossissement des racines", 8, 9, "mi"), ("Arrachage (récolte)", 10, 11, "fin")],
      note="≈ Kc des racines (navet, betterave)."),
    # ------------------------------------------------------------------ prairies et fourrages
    C("prairies", "Prairies", "prairies", (0.40, 0.95, 0.85), (10, 20, 120, 45), 0.3, (0.5, 1.0), 0.60,
      [("Repos hivernal", 12, 2, "repos"), ("Reprise de végétation", 3, 4, "dev"), ("Pousse de printemps (fauche, pâturage)", 5, 6, "mi"),
       ("Repousses d'été", 7, 8, "mi"), ("Pousse d'automne", 9, 11, "fin")], note="Prairie pâturée en rotation (FAO-56).",
      irr={"mi": "Selon la valeur de l'herbe : apports de 25–30 mm après chaque fauche ou passage des animaux"}),
    C("prairie_temporaire", "Prairie temporaire (ray-grass, fétuque, dactyle)", "prairies", (0.40, 1.00, 0.90), (10, 20, 120, 45), 0.3, (0.5, 1.0), 0.60,
      [("Repos hivernal", 12, 2, "repos"), ("Reprise de végétation", 3, 4, "dev"), ("Première fauche", 5, 5, "mi"), ("Repousses d'été", 6, 8, "mi"),
       ("Pousse d'automne", 9, 11, "fin")]),
    C("luzerne", "Luzerne", "prairies", (0.40, 0.95, 0.90), (10, 30, 150, 30), 0.7, (1.0, 2.0), 0.55,
      [("Repos hivernal", 12, 2, "repos"), ("Reprise de végétation", 3, 4, "dev"), ("Fauches de printemps (1re et 2e coupe)", 5, 6, "mi"),
       ("Fauches d'été", 7, 8, "mi"), ("Dernière fauche", 9, 10, "fin")],
      note="Kc moyen sur l'année ; entre deux coupes il va de 0,40 à 1,20.", irr={"mi": "Oui : un tour d'eau juste après chaque fauche, aucun avant la coupe"}),
    C("trefle", "Trèfle, sainfoin", "prairies", (0.40, 0.90, 0.85), (10, 30, 150, 30), 0.6, (0.6, 0.9), 0.50,
      [("Repos hivernal", 12, 2, "repos"), ("Reprise de végétation", 3, 4, "dev"), ("Fauches de printemps", 5, 6, "mi"), ("Repousses d'été", 7, 8, "mi"),
       ("Arrière-saison", 9, 10, "fin")], note="Kc du trèfle (FAO-56, Berseem)."),
    C("ray_grass", "Ray-grass (foin, ensilage d'herbe)", "prairies", (0.95, 1.05, 1.00), (10, 30, 130, 40), 0.3, (0.6, 1.0), 0.60,
      [("Repos hivernal", 12, 2, "ini"), ("Reprise de végétation", 3, 3, "dev"), ("Première coupe (ensilage, foin)", 4, 5, "mi"),
       ("Repousses", 6, 9, "mi"), ("Arrière-saison", 10, 11, "fin")]),
    C("betterave_fourragere", "Betterave fourragère", "prairies", (0.50, 1.05, 0.95), (25, 45, 70, 30), 0.5, (0.7, 1.2), 0.55,
      [("Semis – levée", 4, 4, "ini"), ("Croissance", 5, 6, "dev"), ("Grossissement des racines", 7, 9, "mi"), ("Arrachage (récolte)", 10, 11, "fin")]),
    # ------------------------------------------------------------------ maraîchage de plein champ
    C("tomate", "Tomate", "maraichage", (0.6, 1.15, 0.80), (30, 40, 45, 30), 0.6, (0.7, 1.5), 0.40,
      [("Plantation", 4, 5, "ini"), ("Croissance – floraison", 5, 6, "dev"), ("Grossissement des fruits", 7, 7, "mi"), ("Récolte", 8, 9, "fin")],
      irr={"mi": "Oui, goutte à goutte quotidien sans à-coups (cul noir, éclatement)", "fin": "Oui jusqu'à la dernière récolte, doses un peu réduites (goût, sucre)"}),
    C("tomate_industrie", "Tomate d'industrie", "maraichage", (0.6, 1.15, 0.80), (30, 40, 45, 30), 0.6, (0.7, 1.5), 0.40,
      [("Plantation", 4, 5, "ini"), ("Croissance", 6, 6, "dev"), ("Floraison – nouaison", 6, 7, "mi"), ("Maturation", 8, 8, "fin"), ("Récolte", 8, 9, "fin")],
      irr={"fin": "Arrêter 2 à 3 semaines avant la récolte mécanique (extrait sec)"}),
    C("poivron", "Poivron", "maraichage", (0.6, 1.05, 0.90), (30, 35, 40, 20), 0.7, (0.5, 1.0), 0.30,
      [("Plantation", 5, 5, "ini"), ("Croissance", 6, 6, "dev"), ("Floraison – nouaison", 7, 7, "mi"), ("Récolte", 8, 10, "fin")]),
    C("piment", "Piment (d'Espelette, de cuisine)", "maraichage", (0.6, 1.05, 0.90), (30, 35, 40, 20), 0.7, (0.5, 1.0), 0.30,
      [("Plantation", 5, 5, "ini"), ("Croissance", 6, 6, "dev"), ("Floraison – nouaison", 7, 7, "mi"), ("Récolte", 8, 10, "fin")], note="Kc du poivron (FAO-56)."),
    C("aubergine", "Aubergine", "maraichage", (0.6, 1.05, 0.90), (30, 40, 40, 20), 0.8, (0.7, 1.2), 0.45,
      [("Plantation", 5, 5, "ini"), ("Croissance", 6, 6, "dev"), ("Floraison – nouaison", 7, 7, "mi"), ("Récolte", 8, 10, "fin")]),
    C("concombre", "Concombre", "maraichage", (0.6, 1.00, 0.75), (20, 30, 40, 15), 0.3, (0.7, 1.2), 0.50,
      [("Plantation", 5, 5, "ini"), ("Croissance", 6, 6, "dev"), ("Récolte", 7, 9, "mi")]),
    C("cornichon", "Cornichon", "maraichage", (0.6, 1.00, 0.75), (20, 30, 30, 15), 0.3, (0.7, 1.2), 0.50,
      [("Semis – plantation", 5, 6, "ini"), ("Croissance", 6, 7, "dev"), ("Récolte (cueillette)", 7, 9, "mi")], note="Kc du concombre (FAO-56)."),
    C("courgette", "Courgette", "maraichage", (0.5, 0.95, 0.75), (25, 35, 25, 15), 0.3, (0.6, 1.0), 0.50,
      [("Semis – plantation", 5, 5, "ini"), ("Croissance", 6, 6, "dev"), ("Récolte", 7, 9, "mi")]),
    C("courge", "Courge, potiron, butternut", "maraichage", (0.5, 1.00, 0.80), (20, 30, 30, 20), 0.4, (1.0, 1.5), 0.35,
      [("Semis – plantation", 5, 5, "ini"), ("Croissance des tiges", 6, 7, "dev"), ("Grossissement des fruits", 8, 8, "mi"), ("Récolte", 9, 10, "fin")]),
    C("melon", "Melon", "maraichage", (0.5, 1.05, 0.75), (25, 35, 40, 20), 0.4, (0.8, 1.5), 0.40,
      [("Plantation", 4, 5, "ini"), ("Croissance", 5, 6, "dev"), ("Floraison – nouaison", 6, 7, "mi"), ("Récolte", 7, 8, "fin")],
      irr={"fin": "Réduire à l'approche de la récolte (sucre, éclatement)"}),
    C("pasteque", "Pastèque", "maraichage", (0.4, 1.00, 0.75), (20, 30, 30, 30), 0.4, (0.8, 1.5), 0.40,
      [("Plantation", 5, 5, "ini"), ("Croissance", 6, 6, "dev"), ("Floraison – nouaison", 7, 7, "mi"), ("Récolte", 8, 8, "fin")]),
    C("laitue", "Laitue, batavia, salades", "maraichage", (0.7, 1.00, 0.95), (20, 30, 15, 10), 0.3, (0.3, 0.5), 0.30,
      [("Plantation", 3, 4, "ini"), ("Croissance", 4, 5, "dev"), ("Pommaison – récoltes successives", 5, 10, "mi"), ("Dernières récoltes", 10, 11, "fin")],
      irr={"mi": "Oui, souvent et peu : enracinement très court (aspersion fine ou goutte à goutte)"}),
    C("chicoree", "Chicorée frisée, scarole", "maraichage", (0.7, 1.00, 0.95), (20, 30, 20, 10), 0.3, (0.3, 0.5), 0.30,
      [("Plantation", 7, 7, "ini"), ("Croissance", 8, 8, "dev"), ("Pommaison", 9, 9, "mi"), ("Récolte", 10, 11, "fin")], note="Kc de la laitue (FAO-56)."),
    C("epinard", "Épinard", "maraichage", (0.7, 1.00, 0.95), (20, 20, 15, 5), 0.3, (0.3, 0.5), 0.20,
      [("Semis de printemps", 3, 3, "ini"), ("Récolte de printemps", 4, 5, "mi"), ("Semis d'automne", 8, 9, "ini"), ("Récolte d'automne", 10, 11, "fin")]),
    C("mache", "Mâche", "maraichage", (0.7, 1.00, 0.95), (15, 20, 30, 10), 0.1, (0.2, 0.3), 0.30,
      [("Semis", 8, 9, "ini"), ("Croissance", 10, 11, "dev"), ("Récolte", 11, 3, "mi")], note="≈ Kc des petits légumes feuilles.",
      irr={"ini": "Oui : la levée en fin d'été demande un sol frais en surface (aspersion)"}),
    C("chou", "Chou pommé", "maraichage", (0.7, 1.05, 0.95), (40, 60, 50, 15), 0.4, (0.5, 0.8), 0.45,
      [("Plantation", 5, 6, "ini"), ("Croissance", 7, 7, "dev"), ("Pommaison", 8, 9, "mi"), ("Récolte", 10, 11, "fin")]),
    C("chou_fleur", "Chou-fleur", "maraichage", (0.7, 1.05, 0.95), (35, 50, 40, 15), 0.4, (0.4, 0.7), 0.45,
      [("Plantation", 6, 7, "ini"), ("Croissance", 8, 8, "dev"), ("Formation de la pomme", 9, 10, "mi"), ("Récolte", 10, 12, "fin")]),
    C("brocoli", "Brocoli", "maraichage", (0.7, 1.05, 0.95), (35, 45, 40, 15), 0.3, (0.4, 0.6), 0.45,
      [("Plantation", 7, 7, "ini"), ("Croissance", 8, 8, "dev"), ("Formation des têtes", 9, 9, "mi"), ("Récolte", 9, 10, "fin")]),
    C("chou_bruxelles", "Chou de Bruxelles", "maraichage", (0.7, 1.05, 0.95), (30, 35, 90, 40), 0.4, (0.4, 0.6), 0.45,
      [("Plantation", 5, 6, "ini"), ("Croissance", 7, 8, "dev"), ("Formation des pommes", 9, 10, "mi"), ("Récolte", 10, 1, "fin")]),
    C("carotte", "Carotte", "maraichage", (0.7, 1.05, 0.95), (20, 30, 50, 20), 0.3, (0.5, 1.0), 0.35,
      [("Semis – levée", 3, 5, "ini"), ("Croissance du feuillage", 5, 6, "dev"), ("Grossissement des racines", 7, 8, "mi"), ("Récolte", 8, 11, "fin")],
      irr={"ini": "Oui : la levée demande un sol frais en surface (aspersion légère et fréquente)"}),
    C("betterave_potagere", "Betterave potagère", "maraichage", (0.5, 1.05, 0.95), (15, 25, 20, 10), 0.4, (0.6, 1.0), 0.50,
      [("Semis – levée", 4, 5, "ini"), ("Croissance", 6, 6, "dev"), ("Grossissement", 7, 8, "mi"), ("Récolte", 8, 10, "fin")]),
    C("radis", "Radis", "maraichage", (0.7, 0.90, 0.85), (5, 10, 15, 5), 0.3, (0.3, 0.5), 0.30,
      [("Semis échelonnés", 3, 9, "ini"), ("Récoltes", 4, 10, "mi")]),
    C("navet", "Navet", "maraichage", (0.5, 1.10, 0.95), (15, 30, 25, 10), 0.6, (0.5, 1.0), 0.50,
      [("Semis – levée", 7, 8, "ini"), ("Croissance", 9, 9, "dev"), ("Récolte", 10, 11, "fin")]),
    C("panais", "Panais", "maraichage", (0.5, 1.05, 0.95), (25, 40, 60, 30), 0.4, (0.5, 1.0), 0.40,
      [("Semis – levée", 3, 5, "ini"), ("Croissance", 6, 7, "dev"), ("Grossissement des racines", 8, 9, "mi"), ("Récolte", 10, 2, "fin")]),
    C("poireau", "Poireau", "maraichage", (0.7, 1.00, 1.00), (30, 50, 70, 40), 0.5, (0.3, 0.6), 0.30,
      [("Plantation", 5, 6, "ini"), ("Croissance", 7, 8, "dev"), ("Grossissement du fût", 9, 10, "mi"), ("Récolte", 10, 3, "fin")], note="≈ Kc de l'oignon vert (FAO-56)."),
    C("oignon", "Oignon", "maraichage", (0.7, 1.05, 0.75), (15, 25, 70, 40), 0.4, (0.3, 0.6), 0.30,
      [("Semis – levée", 2, 3, "ini"), ("Croissance du feuillage", 4, 5, "dev"), ("Bulbaison", 6, 6, "mi"), ("Maturation – récolte", 7, 8, "fin")],
      irr={"mi": "Oui, régulier : la bulbaison demande un sol toujours frais", "fin": "Arrêter dès la tombaison des feuilles (conservation)"}),
    C("echalote", "Échalote", "maraichage", (0.7, 1.05, 0.75), (15, 30, 50, 20), 0.3, (0.3, 0.6), 0.30,
      [("Plantation", 2, 3, "ini"), ("Croissance", 4, 4, "dev"), ("Bulbaison", 5, 6, "mi"), ("Récolte", 7, 7, "fin")], note="Kc de l'oignon (FAO-56)."),
    C("ail", "Ail", "maraichage", (0.7, 1.00, 0.70), (30, 30, 70, 20), 0.3, (0.3, 0.5), 0.30,
      [("Plantation", 10, 11, "ini"), ("Hiver", 12, 2, "ini"), ("Croissance", 3, 4, "dev"), ("Bulbaison", 5, 5, "mi"), ("Récolte", 6, 7, "fin")],
      irr={"mi": "Oui si le printemps est sec : 2 à 3 apports pendant la bulbaison", "fin": "Arrêter 3 semaines avant l'arrachage"}),
    C("celeri", "Céleri (branche, rave)", "maraichage", (0.7, 1.05, 1.00), (25, 40, 45, 15), 0.6, (0.3, 0.5), 0.20,
      [("Plantation", 5, 6, "ini"), ("Croissance", 7, 7, "dev"), ("Grossissement", 8, 9, "mi"), ("Récolte", 9, 11, "fin")],
      irr={"mi": "Oui, très régulier : enracinement court et besoin élevé (cœur noir)"}),
    C("fenouil", "Fenouil", "maraichage", (0.7, 1.05, 1.00), (20, 30, 30, 10), 0.5, (0.3, 0.5), 0.30,
      [("Plantation", 6, 7, "ini"), ("Croissance", 8, 8, "dev"), ("Grossissement du bulbe", 9, 9, "mi"), ("Récolte", 9, 10, "fin")], note="≈ Kc du céleri."),
    C("artichaut", "Artichaut", "maraichage", (0.5, 1.00, 0.95), (40, 40, 250, 30), 0.7, (0.6, 0.9), 0.45,
      [("Repos hivernal", 12, 2, "ini"), ("Reprise – croissance", 3, 4, "dev"), ("Formation des capitules", 5, 6, "mi"), ("Récolte", 6, 9, "mi"),
       ("Œilletonnage – fin de cycle", 10, 11, "fin")]),
    C("asperge", "Asperge", "maraichage", (0.5, 0.95, 0.30), (50, 30, 100, 50), 0.2, (1.2, 1.8), 0.45,
      [("Repos hivernal", 11, 2, "repos"), ("Récolte des turions", 3, 5, "ini"), ("Croissance des tiges (fougère)", 6, 7, "dev"), ("Fougère adulte", 8, 9, "mi"),
       ("Sénescence", 10, 10, "fin")], irr={"ini": "Non pendant la récolte (sauf sol très sec)", "mi": "Oui : la fougère fait les réserves de la récolte suivante"}),
    C("haricot_vert", "Haricot vert", "maraichage", (0.5, 1.05, 0.90), (20, 30, 30, 10), 0.4, (0.5, 0.7), 0.45,
      [("Semis – levée", 5, 7, "ini"), ("Croissance", 6, 7, "dev"), ("Floraison", 7, 8, "mi"), ("Récolte", 7, 9, "fin")],
      irr={"mi": "Oui, sans manque : floraison et formation des gousses (coulure)"}),
    C("petit_pois", "Petit pois (légume)", "maraichage", (0.5, 1.15, 1.10), (20, 30, 35, 5), 0.5, (0.6, 1.0), 0.35,
      [("Semis – levée", 2, 3, "ini"), ("Croissance", 4, 4, "dev"), ("Floraison", 5, 5, "mi"), ("Récolte", 6, 6, "fin")]),
    C("feve", "Fève (légume)", "maraichage", (0.5, 1.15, 1.10), (15, 25, 35, 15), 0.8, (0.5, 0.7), 0.45,
      [("Semis – levée", 2, 3, "ini"), ("Croissance", 4, 4, "dev"), ("Floraison", 4, 5, "mi"), ("Récolte", 5, 6, "fin")]),
    C("patate_douce", "Patate douce", "maraichage", (0.5, 1.15, 0.65), (20, 30, 60, 40), 0.4, (1.0, 1.5), 0.65,
      [("Plantation", 5, 6, "ini"), ("Croissance", 7, 7, "dev"), ("Grossissement des tubercules", 8, 9, "mi"), ("Récolte", 10, 10, "fin")]),
    C("aromatiques", "Herbes aromatiques (persil, ciboulette, basilic, coriandre)", "maraichage", (0.6, 1.05, 0.95), (20, 30, 60, 20), 0.4, (0.3, 0.5), 0.35,
      [("Semis – plantation", 3, 5, "ini"), ("Croissance", 5, 6, "dev"), ("Coupes successives", 6, 10, "mi")], note="≈ Kc de la menthe et du céleri."),
    C("fraisier", "Fraisier (plein champ)", "petits_fruits", (0.4, 0.85, 0.75), (20, 30, 120, 60), 0.2, (0.2, 0.3), 0.20,
      [("Plantation", 8, 9, "ini"), ("Repos hivernal", 11, 2, "repos"), ("Reprise – floraison", 3, 4, "dev"), ("Récolte", 5, 6, "mi"),
       ("Été (variétés remontantes)", 7, 9, "fin")], irr={"mi": "Oui, goutte à goutte sous paillage : racines superficielles, besoins quotidiens"}),
    C("potager", "Potager familial", "maraichage", (0.6, 1.05, 0.85), (30, 40, 60, 30), 0.6, (0.3, 0.6), 0.40,
      [("Semis et plantations", 3, 5, "ini"), ("Croissance", 5, 6, "dev"), ("Récoltes d'été", 7, 8, "mi"), ("Récoltes d'automne", 9, 10, "fin")],
      note="Moyenne des légumes d'un potager (pour les particuliers)."),
    # ------------------------------------------------------------------ arboriculture
    C("pommier", "Pommier", "arbo", (0.50, 1.20, 0.95), (30, 50, 130, 30), 4.0, (1.0, 2.0), 0.50,
      [("Repos hivernal", 12, 2, "repos"), ("Débourrement – floraison", 3, 4, "ini"), ("Nouaison – croissance des fruits", 5, 5, "dev"),
       ("Grossissement des fruits", 6, 8, "mi"), ("Récolte", 9, 10, "fin"), ("Post-récolte – chute des feuilles", 10, 11, "fin")],
      note="Verger enherbé (FAO-56 : avec couverture active du sol).", irr={"mi": "Oui : pleine demande, le calibre se fait en été (goutte à goutte, micro-aspersion)",
                                                                         "ini": "Non sauf printemps sec ; aspersion antigel possible à la floraison"}),
    C("poirier", "Poirier", "arbo", (0.50, 1.20, 0.95), (30, 50, 120, 30), 4.0, (1.0, 2.0), 0.50,
      [("Repos hivernal", 12, 2, "repos"), ("Débourrement – floraison", 3, 4, "ini"), ("Nouaison – croissance des fruits", 5, 5, "dev"),
       ("Grossissement des fruits", 6, 7, "mi"), ("Récolte", 8, 9, "fin"), ("Post-récolte", 9, 11, "fin")], note="Verger enherbé (FAO-56)."),
    C("cerisier", "Cerisier", "arbo", (0.50, 1.20, 0.95), (20, 40, 150, 30), 4.0, (1.0, 2.0), 0.50,
      [("Repos hivernal", 12, 2, "repos"), ("Débourrement – floraison", 3, 4, "ini"), ("Croissance des fruits", 4, 5, "dev"), ("Récolte", 5, 6, "mi"),
       ("Post-récolte (induction florale)", 7, 9, "mi"), ("Chute des feuilles", 10, 11, "fin")],
      note="Verger enherbé (FAO-56).", irr={"mi": "Oui, y compris après la récolte : les bourgeons de l'an prochain se forment l'été"}),
    C("pecher", "Pêcher, nectarinier", "arbo", (0.50, 1.15, 0.90), (20, 70, 120, 60), 3.0, (1.0, 2.0), 0.50,
      [("Repos hivernal", 12, 2, "repos"), ("Floraison", 3, 3, "ini"), ("Nouaison – durcissement du noyau", 4, 5, "dev"), ("Grossissement des fruits", 6, 7, "mi"),
       ("Récolte", 7, 8, "mi"), ("Post-récolte", 9, 10, "fin"), ("Chute des feuilles", 11, 11, "fin")], note="Verger enherbé (FAO-56, fruits à noyau)."),
    C("abricotier", "Abricotier", "arbo", (0.50, 1.15, 0.90), (20, 70, 120, 60), 3.0, (1.0, 2.0), 0.50,
      [("Repos hivernal", 12, 2, "repos"), ("Floraison", 3, 3, "ini"), ("Nouaison – croissance des fruits", 4, 5, "dev"), ("Grossissement – récolte", 6, 7, "mi"),
       ("Post-récolte", 8, 10, "fin")], note="Verger enherbé (FAO-56, fruits à noyau)."),
    C("prunier", "Prunier (prune d'Ente, reine-claude)", "arbo", (0.50, 1.15, 0.90), (20, 70, 120, 60), 3.5, (1.0, 2.0), 0.50,
      [("Repos hivernal", 12, 2, "repos"), ("Floraison", 3, 4, "ini"), ("Croissance des fruits", 5, 6, "dev"), ("Grossissement des fruits", 7, 7, "mi"),
       ("Récolte", 8, 9, "mi"), ("Post-récolte", 9, 10, "fin")], note="Verger enherbé (FAO-56, fruits à noyau)."),
    C("kiwi", "Kiwi", "arbo", (0.40, 1.05, 1.05), (20, 70, 120, 60), 3.0, (0.7, 1.3), 0.35,
      [("Repos hivernal", 12, 2, "repos"), ("Débourrement", 3, 4, "ini"), ("Floraison", 5, 5, "dev"), ("Croissance des fruits", 6, 8, "mi"),
       ("Maturation", 9, 10, "mi"), ("Récolte", 10, 11, "fin")], irr={"mi": "Oui, abondant et régulier : le kiwi est la culture fruitière la plus gourmande en eau"}),
    C("olivier", "Olivier", "arbo", (0.65, 0.70, 0.70), (30, 90, 60, 90), 4.0, (1.2, 1.7), 0.65,
      [("Repos hivernal", 12, 2, "ini"), ("Reprise de végétation", 3, 4, "ini"), ("Floraison – nouaison", 5, 6, "mi"), ("Durcissement du noyau", 7, 7, "mi"),
       ("Grossissement – lipogenèse", 8, 9, "mi"), ("Récolte", 10, 12, "fin")], note="Verger de 40 à 60 % de couverture (FAO-56).",
      irr={"ini": "Non en général (réserves d'hiver)", "mi": "Oui en irrigation de complément : priorité floraison et grossissement ; on peut réduire au durcissement du noyau"}),
    C("amandier", "Amandier", "arbo", (0.40, 0.90, 0.65), (20, 70, 120, 60), 5.0, (1.0, 2.0), 0.40,
      [("Repos hivernal", 12, 1, "repos"), ("Floraison", 2, 3, "ini"), ("Croissance", 4, 5, "dev"), ("Remplissage des amandes", 6, 7, "mi"), ("Récolte", 8, 9, "fin"),
       ("Post-récolte", 9, 10, "fin")], note="Sans couverture du sol (FAO-56)."),
    C("noyer", "Noyer", "arbo", (0.50, 1.10, 0.65), (20, 10, 130, 30), 4.5, (1.7, 2.4), 0.50,
      [("Repos hivernal", 12, 3, "repos"), ("Débourrement", 4, 4, "ini"), ("Floraison", 5, 5, "dev"), ("Croissance des noix", 6, 7, "mi"),
       ("Remplissage des cerneaux", 8, 9, "mi"), ("Récolte", 9, 10, "fin")], irr={"mi": "Oui : remplissage du cerneau en août, c'est là que se fait la qualité"}),
    C("noisetier", "Noisetier", "arbo", (0.50, 1.05, 0.65), (20, 50, 110, 40), 5.0, (0.8, 1.5), 0.50,
      [("Floraison (hiver)", 1, 2, "repos"), ("Débourrement", 3, 4, "ini"), ("Croissance", 5, 6, "dev"), ("Remplissage des noisettes", 7, 8, "mi"),
       ("Récolte", 8, 9, "fin"), ("Repos", 11, 12, "repos")], note="≈ Kc du noyer et de l'amandier.", irr={"mi": "Oui : le remplissage de juillet–août décide du rendement"}),
    C("chataignier", "Châtaignier", "arbo", (0.50, 1.00, 0.65), (20, 50, 100, 40), 10.0, (1.0, 2.0), 0.50,
      [("Repos hivernal", 12, 3, "repos"), ("Débourrement", 4, 5, "ini"), ("Floraison", 6, 7, "dev"), ("Grossissement des bogues", 8, 9, "mi"), ("Récolte", 10, 10, "fin")],
      note="≈ Kc du noyer."),
    C("figuier", "Figuier", "arbo", (0.50, 0.95, 0.70), (20, 50, 110, 40), 4.0, (1.0, 2.0), 0.50,
      [("Repos hivernal", 12, 2, "repos"), ("Débourrement", 3, 4, "ini"), ("Figues-fleurs", 5, 6, "dev"), ("Grossissement des figues", 7, 7, "mi"),
       ("Récolte", 8, 9, "mi"), ("Post-récolte", 10, 11, "fin")], note="≈ Kc des fruits à noyau sans couverture."),
    C("agrumes", "Agrumes (citronnier, oranger, clémentinier)", "arbo", (0.65, 0.60, 0.65), (60, 90, 120, 95), 4.0, (1.1, 1.5), 0.50,
      [("Repos relatif", 12, 2, "ini"), ("Floraison", 3, 5, "ini"), ("Nouaison", 5, 6, "mi"), ("Grossissement des fruits", 7, 10, "mi"), ("Récolte", 11, 2, "fin")],
      note="Arbres couvrant environ 50 % du sol, sans enherbement (FAO-56).", irr={"ini": "Selon la pluie : les agrumes restent en feuilles l'hiver"}),
    C("avocatier", "Avocatier", "arbo", (0.60, 0.85, 0.75), (60, 90, 120, 95), 5.0, (0.5, 1.0), 0.70,
      [("Floraison", 3, 5, "ini"), ("Nouaison – croissance", 6, 9, "mi"), ("Récolte", 10, 3, "fin")]),
    C("grenadier", "Grenadier", "arbo", (0.40, 0.85, 0.65), (20, 50, 110, 40), 3.0, (1.0, 1.5), 0.50,
      [("Repos hivernal", 12, 3, "repos"), ("Débourrement – floraison", 4, 6, "ini"), ("Croissance des fruits", 7, 8, "mi"), ("Récolte", 9, 10, "fin")],
      note="≈ Kc des fruits à noyau sans couverture."),
    C("kaki", "Plaqueminier (kaki)", "arbo", (0.45, 0.90, 0.65), (20, 50, 110, 40), 4.0, (1.0, 1.5), 0.50,
      [("Repos hivernal", 12, 3, "repos"), ("Débourrement – floraison", 4, 5, "ini"), ("Croissance des fruits", 6, 8, "mi"), ("Récolte", 10, 11, "fin")],
      note="≈ Kc des fruits à noyau sans couverture."),
    C("pistachier", "Pistachier", "arbo", (0.40, 1.10, 0.45), (20, 60, 30, 40), 3.0, (1.0, 1.5), 0.40,
      [("Repos hivernal", 12, 3, "repos"), ("Floraison", 4, 4, "ini"), ("Croissance", 5, 6, "dev"), ("Remplissage des fruits", 7, 8, "mi"), ("Récolte", 9, 9, "fin")]),
    # ------------------------------------------------------------------ petits fruits
    C("framboisier", "Framboisier", "petits_fruits", (0.30, 1.05, 0.50), (20, 50, 75, 60), 1.5, (0.6, 1.2), 0.50,
      [("Repos hivernal", 12, 2, "repos"), ("Débourrement", 3, 4, "ini"), ("Croissance – floraison", 5, 5, "dev"), ("Récolte", 6, 7, "mi"),
       ("Récolte des remontants", 8, 10, "mi"), ("Post-récolte", 10, 11, "fin")], note="Kc des petits fruits (FAO-56, berries)."),
    C("myrtillier", "Myrtillier", "petits_fruits", (0.30, 1.05, 0.50), (20, 50, 75, 60), 1.5, (0.4, 0.8), 0.50,
      [("Repos hivernal", 12, 2, "repos"), ("Floraison", 4, 4, "ini"), ("Croissance des baies", 5, 6, "dev"), ("Récolte", 7, 8, "mi"), ("Post-récolte", 9, 10, "fin")],
      note="Kc des petits fruits (FAO-56).", irr={"mi": "Oui, goutte à goutte : racines superficielles en sol acide, aucun manque à la récolte"}),
    C("cassis", "Cassis, groseillier", "petits_fruits", (0.30, 1.05, 0.50), (20, 50, 75, 60), 1.5, (0.6, 1.2), 0.50,
      [("Repos hivernal", 12, 2, "repos"), ("Débourrement – floraison", 3, 4, "ini"), ("Croissance des baies", 5, 5, "dev"), ("Récolte", 6, 7, "mi"),
       ("Post-récolte", 8, 10, "fin")], note="Kc des petits fruits (FAO-56)."),
    C("mure", "Mûre (ronce sans épines)", "petits_fruits", (0.30, 1.05, 0.50), (20, 50, 75, 60), 1.5, (0.6, 1.2), 0.50,
      [("Repos hivernal", 12, 2, "repos"), ("Débourrement", 3, 4, "ini"), ("Floraison", 5, 6, "dev"), ("Récolte", 7, 9, "mi"), ("Post-récolte", 10, 11, "fin")],
      note="Kc des petits fruits (FAO-56)."),
    # ------------------------------------------------------------------ vigne
    C("vigne", "Vigne", "vigne", (0.30, 0.70, 0.45), (30, 60, 40, 80), 1.5, (1.0, 2.0), 0.45,
      [("Repos hivernal", 11, 2, "repos"), ("Débourrement", 3, 4, "ini"), ("Floraison", 5, 6, "dev"), ("Nouaison – véraison", 7, 8, "mi"),
       ("Maturation – vendanges", 9, 10, "fin")], note="Vigne de cuve (FAO-56, wine grapes) : contrainte hydrique modérée recherchée.",
      irr={"mi": "Oui en irrigation de précision : contrainte modérée entre nouaison et véraison, selon le potentiel hydrique de tige",
           "fin": "Rarement : l'eau en maturation dilue le raisin ; arrêt avant les vendanges"}),
    C("raisin_table", "Raisin de table", "vigne", (0.30, 0.85, 0.45), (20, 40, 120, 60), 2.0, (1.0, 2.0), 0.35,
      [("Repos hivernal", 11, 2, "repos"), ("Débourrement", 3, 4, "ini"), ("Floraison", 5, 5, "dev"), ("Grossissement des baies", 6, 7, "mi"),
       ("Véraison – maturation", 8, 8, "mi"), ("Récolte", 8, 10, "fin")], irr={"mi": "Oui : le calibre des baies se fait de la nouaison à la véraison"}),
    C("houblon", "Houblon", "vigne", (0.30, 1.05, 0.85), (25, 40, 80, 10), 5.0, (1.0, 1.2), 0.50,
      [("Repos hivernal", 11, 2, "repos"), ("Reprise – taille", 3, 4, "ini"), ("Croissance sur fil", 5, 6, "dev"), ("Floraison", 7, 7, "mi"),
       ("Récolte des cônes", 8, 9, "fin")], irr={"mi": "Oui : besoin maximal en juillet, à la floraison"}),
    # ------------------------------------------------------------------ plantes à parfum, aromatiques et médicinales
    C("lavande", "Lavande et lavandin", "ppam", (0.35, 0.75, 0.60), (30, 60, 60, 40), 0.8, (0.5, 1.0), 0.65,
      [("Repos hivernal", 11, 2, "repos"), ("Reprise de végétation", 3, 4, "ini"), ("Croissance des tiges", 5, 6, "dev"), ("Floraison", 6, 7, "mi"),
       ("Récolte (coupe)", 7, 8, "fin")], note="≈ Kc estimé (culture conduite en sec ; irrigation de complément sur jeunes plantations).",
      irr={"mi": "Rarement : seulement les jeunes plantations ou en sécheresse sévère"}),
    C("ppam", "Plantes aromatiques et médicinales (thym, sauge, mélisse, menthe)", "ppam", (0.60, 1.00, 0.90), (20, 40, 80, 30), 0.5, (0.4, 0.8), 0.40,
      [("Repos hivernal", 12, 2, "repos"), ("Reprise – plantation", 3, 4, "ini"), ("Croissance", 5, 5, "dev"), ("Coupes", 6, 9, "mi"), ("Dernière coupe", 10, 10, "fin")],
      note="≈ Kc de la menthe (1,15) et des petits légumes."),
    # ------------------------------------------------------------------ sous abri
    C("tomate_abri", "Tomate sous abri", "sous_abri", (0.6, 1.15, 0.80), (30, 40, 150, 30), 2.5, (0.5, 1.0), 0.40,
      [("Plantation", 2, 3, "ini"), ("Croissance – floraison", 3, 4, "dev"), ("Récoltes", 5, 10, "mi"), ("Fin de culture", 10, 11, "fin")],
      note="Sous abri, l'ETP intérieure vaut environ 60 à 80 % de l'ETP extérieure.", irr={"mi": "Oui, goutte à goutte piloté (drainage, conductivité) plusieurs fois par jour"}),
    C("concombre_abri", "Concombre sous abri", "sous_abri", (0.6, 1.00, 0.75), (20, 30, 60, 15), 2.0, (0.5, 0.8), 0.50,
      [("Plantation", 2, 3, "ini"), ("Récoltes (1er cycle)", 4, 6, "mi"), ("Replantation", 7, 7, "ini"), ("Récoltes (2e cycle)", 8, 10, "mi")]),
    C("fraise_hors_sol", "Fraise hors-sol", "sous_abri", (0.4, 0.85, 0.75), (20, 30, 120, 60), 0.3, (0.1, 0.2), 0.20,
      [("Plantation", 12, 1, "ini"), ("Floraison", 2, 3, "dev"), ("Récolte", 3, 6, "mi"), ("Remontantes (été – automne)", 7, 10, "fin")],
      irr={"mi": "Oui : ferti-irrigation pilotée, nombreux petits apports par jour (substrat)"}),
    C("salade_abri", "Salades sous abri", "sous_abri", (0.7, 1.00, 0.95), (15, 25, 15, 5), 0.3, (0.2, 0.4), 0.30,
      [("Plantations", 9, 2, "ini"), ("Récoltes", 11, 4, "mi")]),
    C("horticulture", "Horticulture, plantes en pot et à massifs", "pepiniere", (0.50, 1.00, 0.80), (20, 30, 120, 30), 0.5, (0.1, 0.3), 0.30,
      [("Rempotage – mise en culture", 1, 3, "ini"), ("Croissance", 3, 4, "dev"), ("Pleine production – ventes", 4, 9, "mi"), ("Fin de saison", 10, 11, "fin")],
      note="≈ Kc estimé ; le besoin dépend surtout du substrat et de l'abri.", irr={"mi": "Oui : arrosage quotidien (goutte à goutte, tablettes, aspersion)"}),
    C("pepiniere", "Pépinière (arbres et arbustes en conteneur)", "pepiniere", (0.60, 1.00, 0.80), (30, 40, 120, 40), 2.0, (0.2, 0.4), 0.30,
      [("Repos hivernal", 12, 2, "repos"), ("Débourrement – rempotage", 3, 4, "ini"), ("Croissance", 5, 5, "dev"), ("Pleine croissance", 6, 8, "mi"),
       ("Aoûtement", 9, 11, "fin")], note="≈ Kc estimé ; en conteneur, la réserve est de quelques jours seulement.",
      irr={"mi": "Oui, une à plusieurs fois par jour : le conteneur se vide en un jour de chaleur"}),
    # ------------------------------------------------------------------ espaces verts
    C("gazon", "Gazon (stades, golfs, espaces verts)", "espaces_verts", (0.90, 0.95, 0.95), (10, 20, 180, 40), 0.1, (0.5, 1.0), 0.40,
      [("Repos hivernal", 12, 2, "ini"), ("Reprise – premières tontes", 3, 4, "dev"), ("Saison (tontes, jeu)", 5, 9, "mi"), ("Automne – regarnissage", 10, 11, "fin")],
      note="Gazon de saison fraîche, bien entretenu (FAO-56).",
      irr={"mi": "Oui : arrosage automatique de nuit, 3 à 5 mm par jour en plein été ; respecter les arrêtés sécheresse"}),
    C("massifs", "Massifs, arbustes et haies d'ornement", "espaces_verts", (0.50, 0.70, 0.60), (20, 40, 150, 40), 2.0, (0.4, 1.0), 0.50,
      [("Repos hivernal", 12, 2, "repos"), ("Plantations – reprise", 3, 4, "ini"), ("Croissance", 5, 6, "dev"), ("Été", 7, 8, "mi"), ("Automne – plantations", 9, 11, "fin")],
      note="≈ Kc estimé pour les plantations d'ornement établies (paillées, goutte à goutte).",
      irr={"ini": "Oui pour les jeunes plantations (2 premières années)", "mi": "Oui, goutte à goutte : 1 à 2 apports par semaine pour les sujets établis"}),
    # ------------------------------------------------------------------ cultures tropicales (DOM)
    C("canne_sucre", "Canne à sucre", "tropicales", (0.40, 1.25, 0.75), (35, 60, 190, 120), 3.0, (1.2, 2.0), 0.65,
      [("Plantation – repousses", 9, 10, "ini"), ("Tallage", 11, 12, "dev"), ("Grande croissance", 1, 4, "mi"), ("Maturation", 5, 6, "fin"), ("Récolte (campagne sucrière)", 7, 12, "fin")],
      note="Calendrier de La Réunion.", irr={"fin": "Arrêter 4 à 6 semaines avant la coupe (richesse en sucre)"}),
    C("bananier", "Bananier", "tropicales", (0.50, 1.10, 1.00), (120, 90, 120, 60), 4.0, (0.5, 0.9), 0.35,
      [("Saison des pluies", 11, 4, "dev"), ("Saison sèche (pleine demande)", 5, 10, "mi")], note="Culture continue (Antilles, La Réunion).",
      irr={"mi": "Oui : besoin élevé et continu, enracinement superficiel", "dev": "Selon la pluie"}),
    C("ananas", "Ananas", "tropicales", (0.50, 0.30, 0.30), (60, 120, 600, 10), 0.6, (0.3, 0.6), 0.50,
      [("Plantation", 1, 3, "ini"), ("Croissance", 4, 9, "mi"), ("Floraison induite – récolte", 10, 12, "fin")],
      note="Plante à métabolisme CAM : Kc très faible (FAO-56)."),
]


def mois(debut, fin):
    return list(range(debut, fin + 1)) if debut <= fin else list(range(debut, 13)) + list(range(1, fin + 1))


def fenetres(stades):
    """Le projet : les deux mois qui suivent la fin du cycle ; l'achat : les deux mois qui précèdent le premier besoin d'eau."""
    fins = [s for s in stades if s[3] in ("fin", "mi")]
    besoin = next((s for s in stades if s[3] in ("dev", "mi")), stades[0])
    fin_cycle = fins[-1][2] if fins else stades[-1][2]
    projet = (fin_cycle % 12 + 1, (fin_cycle + 1) % 12 + 1)
    debut = besoin[1]
    achat = ((debut - 3) % 12 + 1, (debut - 2) % 12 + 1)
    if set(mois(*achat)) & set(mois(*projet)):  # cycle court : on resserre l'achat sur le mois d'avant
        achat = ((debut - 2) % 12 + 1, (debut - 2) % 12 + 1)
    return projet, achat


def champ(nom, valeur):
    return f'            <field name="{nom}">{escape(str(valeur))}</field>\n'


def generer():
    vus = set()
    lignes_cultures, lignes_detail = [], []
    rang = {}
    for c in CULTURES:
        assert c["code"] not in vus, c["code"]
        vus.add(c["code"])
        ini, mi, fin = c["kc"]
        cid = f"culture_{c['code']}"
        r = rang.setdefault(c["cat"], 0)
        rang[c["cat"]] += 1
        attributs = [("kc_ini", ini), ("kc_mi", mi), ("kc_fin", fin), ("duree_ini", c["durees"][0]), ("duree_dev", c["durees"][1]),
                     ("duree_mi", c["durees"][2]), ("duree_fin", c["durees"][3]), ("hauteur_max", c["h"]), ("racines_min", c["racines"][0]),
                     ("racines_max", c["racines"][1]), ("p_tarissement", c["p"]),
                     ("source_kc", "FAO-56 (Allen et al., 1998)" + (f" — {c['note']}" if c["note"] else ""))]
        if c["code"] in EXISTANTES:
            # ces fiches ont été créées « à ne pas mettre à jour » : on écrit leurs Kc par un appel, rejoué à chaque mise à jour
            valeurs = ", ".join(f"'{k}': {v!r}" for k, v in attributs)
            lignes_cultures.append(f'        <function model="cultiveau.culture" name="write" eval="[[ref(\'{cid}\')], {{{escape(valeurs, {chr(34): "&quot;"})}}}]"/>\n')
        else:
            bloc = f'        <record id="{cid}" model="cultiveau.culture">\n'
            bloc += champ("name", c["nom"]) + champ("categorie", c["cat"]) + champ("couleur", COULEURS[c["cat"]][r % len(COULEURS[c["cat"]])])
            bloc += champ("sequence", 100 + list(COULEURS).index(c["cat"]) * 100 + r)
            bloc += "".join(champ(k, v) for k, v in attributs) + "        </record>\n"
            lignes_detail.append(bloc)
        # la frise France
        for i, (nom, d, f, t) in enumerate(c["stades"], start=1):
            kmin, kmax = kc_du_stade(t, ini, mi, fin)
            ms = mois(d, f)
            etp_min, etp_max = min(ETP[m][0] for m in ms), max(ETP[m][1] for m in ms)
            lignes_detail.append(
                f'        <record id="stade_{c["code"]}_fr_{i}" model="cultiveau.culture.stade">\n'
                f'            <field name="culture_id" ref="{cid}"/>\n'
                + champ("name", nom) + champ("mois_debut", d) + champ("mois_fin", f) + champ("kc_min", kmin) + champ("kc_max", kmax)
                + champ("besoin_min", round(kmin * 100)) + champ("besoin_max", round(kmax * 100)) + champ("etp_min", etp_min) + champ("etp_max", etp_max)
                + champ("irrigation", c["irr"].get(t) or IRRIGATION[t]) + champ("sequence", i) + "        </record>\n")
        projet, achat = c["fenetres"] or fenetres(c["stades"])
        for genre, (d, f) in (("projet", projet), ("achat", achat)):
            lignes_detail.append(
                f'        <record id="fenetre_{c["code"]}_fr_{genre}" model="cultiveau.culture.fenetre">\n'
                f'            <field name="culture_id" ref="{cid}"/>\n' + champ("genre", genre) + champ("mois_debut", d) + champ("mois_fin", f)
                + "        </record>\n")
    entete = ('<?xml version="1.0" encoding="utf-8"?>\n<!-- Généré par scripts/generer_cultures.py : modifier le script, pas ce fichier. -->\n<odoo>\n'
              "    <!-- Les Kc des cultures déjà décrites pour le Gard : remis à jour à chaque mise à jour du module. -->\n"
              '    <data noupdate="0">\n')
    milieu = ("    </data>\n    <!-- Les nouvelles cultures et la frise France de toutes : créées une fois, ensuite modifiables dans l'ERP. -->\n"
              '    <data noupdate="1">\n')
    with open(SORTIE, "w") as f:
        f.write(entete + "".join(lignes_cultures) + milieu + "".join(lignes_detail) + "    </data>\n</odoo>\n")
    return len(CULTURES), sum(len(c["stades"]) for c in CULTURES)


if __name__ == "__main__":
    n, s = generer()
    print(f"{n} cultures, {s} stades -> {os.path.relpath(SORTIE)}")
