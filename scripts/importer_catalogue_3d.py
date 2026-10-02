#!/usr/bin/env python3
"""Importe le catalogue 3D (27 000 références) dans l'ERP par lots, en XML-RPC.

    python3 scripts/importer_catalogue_3d.py https://erp.cultiveau.fr cultiveau admin 'mot-de-passe' ../cultiveau-3d/reseau-3d/catalogue.json

Chaque lot de 1 500 produits est un appel validé (commit) : on peut interrompre et relancer, un
produit déjà présent est mis à jour. Le compte doit faire partie de l'équipe Cultiveau.
"""
import json
import sys
import time
import xmlrpc.client

if len(sys.argv) != 6:
    print(__doc__)
    sys.exit(1)
url, base, login, mdp, fichier = sys.argv[1:]
donnees = json.load(open(fichier, encoding="utf-8"))
dicts, fiches, produits = donnees["dicts"], donnees.get("fiches", {}), donnees["produits"]

commun = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = commun.authenticate(base, login, mdp, {})
if not uid:
    sys.exit("Connexion refusée.")
modeles = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", allow_none=True)
LOT = 1500
total = {"crees": 0, "maj": 0}
debut = time.time()
for i in range(0, len(produits), LOT):
    bilan = modeles.execute_kw(base, uid, mdp, "product.template", "cultiveau_importer_3d", [dicts, fiches, produits[i:i + LOT]])
    total["crees"] += bilan["crees"]
    total["maj"] += bilan["maj"]
    print(f"{min(i + LOT, len(produits))}/{len(produits)} produits — créés {total['crees']}, mis à jour {total['maj']} ({time.time() - debut:.0f} s)")
print("Terminé.")
