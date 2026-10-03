# Joint aux documents de la bibliothèque les fichiers rapatriés du Drive (scripts/rapatrier_fiches.sh, montés dans
# /mnt/fiches) et leur première page en image, qui illustre aussi les articles reliés sans photo.
# À lancer dans un shell Odoo (voir scripts/donnees.sh fiches). Relançable : un document déjà joint est laissé.
import os

dossier = os.environ.get("FICHES", "/mnt/fiches")
if not os.path.isdir(dossier):
    dossier = "data/fiches"
Fiche = env["cultiveau.fiche"]
fiches = Fiche.with_context(active_test=False).search([("drive_id", "!=", False), ("fichier", "=", False)])
print(f"Documents sans fichier joint : {len(fiches)} ; fichiers rapatriés : {len([f for f in os.listdir(dossier) if not f.endswith('.png') and not f.startswith('.')]) if os.path.isdir(dossier) else 0}.", flush=True)
joints = illustres = sans_vignette = 0
for n, fiche in enumerate(fiches, 1):
    chemin = next((os.path.join(dossier, fiche.drive_id + ext) for ext in (".pdf", ".jpg", ".png") if os.path.isfile(os.path.join(dossier, fiche.drive_id + ext))), None)
    if not chemin:
        continue
    with open(chemin, "rb") as f:
        contenu = f.read()
    vignette = None
    if chemin.endswith(".pdf"):
        png = os.path.join(dossier, fiche.drive_id + ".png")
        if os.path.isfile(png):
            with open(png, "rb") as f:
                vignette = f.read()
        else:
            sans_vignette += 1
    else:
        vignette = contenu
    nom = fiche.name or fiche.drive_id
    if not nom.lower().endswith(os.path.splitext(chemin)[1]):
        nom += os.path.splitext(chemin)[1]
    illustres += fiche.cultiveau_joindre(contenu, nom[:255], vignette)
    joints += 1
    if joints % 25 == 0:
        env.cr.commit()
        print(f"  {joints} documents joints…", flush=True)
env.cr.commit()
print(f"Fichiers joints : {joints} ({sans_vignette} sans vignette) ; articles illustrés par la première page de leur fiche : {illustres}.")
print(f"Bibliothèque : {Fiche.search_count([('fichier', '!=', False)])} documents avec fichier sur {Fiche.search_count([])}.")
