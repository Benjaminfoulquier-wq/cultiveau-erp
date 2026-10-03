# Joint aux documents de la bibliothèque les fichiers rapatriés du Drive (scripts/rapatrier_fiches.sh, montés dans
# /mnt/fiches) et leur première page en image, qui illustre aussi les articles reliés sans photo.
# À lancer dans un shell Odoo (voir scripts/donnees.sh fiches). Relançable : un document déjà joint est laissé.
# LIMITE borne le nombre de documents traités par passage (la mémoire du processus grossit avec les gros PDF ;
# donnees.sh relance jusqu'à « Reste : 0 ») ; au-delà de TAILLE_MAX octets le PDF reste sur le Drive, seule la
# première page est gardée.
import gc
import os

LIMITE = int(os.environ.get("LIMITE") or 0)
TAILLE_MAX = int(os.environ.get("TAILLE_MAX") or 40 * 1024 * 1024)

dossier = os.environ.get("FICHES", "/mnt/fiches")
if not os.path.isdir(dossier):
    dossier = "data/fiches"
Fiche = env["cultiveau.fiche"]
fiches = Fiche.with_context(active_test=False).search([("drive_id", "!=", False), ("fichier_nom", "=", False)], order="taille, id")
disponibles = {f for f in os.listdir(dossier) if not f.startswith(".")} if os.path.isdir(dossier) else set()
# Un seul fichier par document, le PDF d'abord : son <id>.png n'est que la vignette de la première page.
a_faire = [(fiche.id, nom) for fiche in fiches for nom in [next((fiche.drive_id + ext for ext in (".pdf", ".jpg", ".png") if fiche.drive_id + ext in disponibles), None)] if nom]
print(f"Documents sans fichier joint : {len(fiches)}, dont {len(a_faire)} rapatriés" + (f" ; {LIMITE} par passage." if LIMITE else "."), flush=True)
joints = illustres = sans_vignette = logos = 0
for fiche_id, nom_fichier in a_faire[:LIMITE or None]:
    fiche = Fiche.browse(fiche_id)
    chemin = os.path.join(dossier, nom_fichier)
    if chemin.endswith(".pdf") and os.path.getsize(chemin) > TAILLE_MAX:
        contenu = None  # trop gros pour la base : le document reste sur le Drive, la première page est gardée
    else:
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
    # Le cache de l'ORM garderait sinon chaque fichier en mémoire : 2 000 PDF, et le processus serait tué.
    contenu = vignette = None
    env.invalidate_all()
    gc.collect()
    # Une image nommée « logo » dans le dossier d'un fournisseur devient le logo de sa fiche partenaire.
    if not chemin.endswith(".pdf") and "logo" in nom.lower() and fiche.fournisseur_id and not fiche.fournisseur_id.image_1920:
        fiche.fournisseur_id.image_1920 = fiche.vignette
        logos += 1
    if joints % 25 == 0:
        env.cr.commit()
        print(f"  {joints} documents joints…", flush=True)
    elif joints % 5 == 0:
        env.cr.commit()
env.cr.commit()
print(f"Reste : {max(len(a_faire) - joints, 0)} documents à joindre.")
print(f"Fichiers joints : {joints} ({sans_vignette} sans vignette) ; articles illustrés par la première page de leur fiche : {illustres} ; logos de fournisseurs : {logos}.")
print(f"Bibliothèque : {Fiche.search_count([('fichier_nom', '!=', False)])} documents traités, {Fiche.search_count([('fichier', '!=', False)])} avec fichier joint, sur {Fiche.search_count([])}.")
