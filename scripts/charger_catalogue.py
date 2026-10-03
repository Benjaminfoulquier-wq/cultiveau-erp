# Charge le catalogue 3D (donnees/catalogue-3d.json.gz) dans l'ERP, par lots validés : relançable, un article déjà
# présent est mis à jour. À lancer dans un shell Odoo (voir scripts/donnees.sh).
import gzip
import json
import os
import time

chemin = os.environ.get("CATALOGUE", "/mnt/donnees/catalogue-3d.json.gz")
if not os.path.exists(chemin):
    chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "donnees", "catalogue-3d.json.gz") if "__file__" in globals() else "donnees/catalogue-3d.json.gz"
with gzip.open(chemin, "rt", encoding="utf-8") as f:
    donnees = json.load(f)
dicts, fiches, produits = donnees["dicts"], donnees.get("fiches", {}), donnees["produits"]
limite = int(os.environ.get("LIMITE") or 0)
if limite:
    produits = produits[:limite]
Produit = env["product.template"]
LOT = 1500
total = {"crees": 0, "maj": 0}
debut = time.time()
for i in range(0, len(produits), LOT):
    bilan = Produit.cultiveau_importer_3d(dicts, fiches, produits[i:i + LOT])
    total["crees"] += bilan.get("crees", 0)
    total["maj"] += bilan.get("maj", 0)
    env.cr.commit()
    print(f"{min(i + LOT, len(produits))}/{len(produits)} produits : créés {total['crees']}, mis à jour {total['maj']} ({time.time() - debut:.0f} s)", flush=True)
print(f"Catalogue chargé : {total['crees']} articles créés, {total['maj']} mis à jour, {Produit.search_count([])} articles au total.")
