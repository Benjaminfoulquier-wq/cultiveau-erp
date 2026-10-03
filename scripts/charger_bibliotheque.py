# Charge la bibliothèque technique (donnees/bibliotheque.csv, l'inventaire du Drive) et relie les articles à leur fiche.
# À lancer dans un shell Odoo (voir scripts/donnees.sh). Relançable.
import os
import re

chemin = os.environ.get("BIBLIOTHEQUE", "/mnt/donnees/bibliotheque.csv")
if not os.path.exists(chemin):
    chemin = "donnees/bibliotheque.csv"
contenu = open(chemin, encoding="utf-8").read()
Fiche = env["cultiveau.fiche"]
bilan = Fiche.cultiveau_importer_inventaire(contenu)
env.cr.commit()
print(f"Bibliothèque : {bilan['crees']} documents créés, {bilan['maj']} mis à jour, {bilan['ignores']} ignorés.", flush=True)
# Les articles qui ont un lien Drive mais pas encore de fiche reliée.
fiches = {f.drive_id: f.id for f in Fiche.with_context(active_test=False).search([("drive_id", "!=", False)])}
Produit = env["product.template"]
cache = {}
relies = 0
produits = Produit.with_context(active_test=False).search([("cultiveau_fiche_url", "!=", False), ("cultiveau_fiche_id", "=", False)])
par_fiche = {}
for p in produits:
    m = re.search(r"/d/([A-Za-z0-9_-]+)", p.cultiveau_fiche_url or "")
    if not m:
        continue
    drive_id = m.group(1)
    if drive_id not in fiches:
        fiches[drive_id] = Fiche.cultiveau_trouver_ou_creer(drive_id, p.cultiveau_fiche_notes or drive_id, p.cultiveau_fiche_notes, cache).id
    par_fiche.setdefault(fiches[drive_id], []).append(p.id)
for fiche_id, ids in par_fiche.items():
    Produit.browse(ids).write({"cultiveau_fiche_id": fiche_id})
    relies += len(ids)
env.cr.commit()
print(f"Articles reliés à leur fiche : {relies} ({Produit.search_count([('cultiveau_fiche_id', '!=', False)])} au total).")
