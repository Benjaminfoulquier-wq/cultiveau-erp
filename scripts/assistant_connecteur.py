# Côté assistant téléphonique (shell Django, dans le conteneur « assistant ») : pour chaque adhérent, le connecteur
# « ERP Cultiveau » avec la clé d'API de l'ERP, la flèche « tout appel → fiche » s'il n'en a aucune, puis l'export des
# adhérents (numéro dédié, équipe) et de leurs clients vers /data/export-erp.json, que l'ERP importe ensuite.
import json
import os

from standard import secrets
from standard.models import Adherent, Connecteur, Fleche

cle = os.environ["CLE"]
url = os.environ.get("ERP_URL", "https://erp.cultiveau.fr")
sortie, fleches = [], 0
for a in Adherent.objects.all():
    c = a.connecteurs.filter(type="odoo").first()
    if not c:
        c = Connecteur.objects.create(adherent=a, type="odoo", nom="ERP Cultiveau", adresse=url, envoyer_sms_client=False, actif=True)
    else:
        c.adresse = c.adresse or url
        c.actif = True
        c.save()
    secrets.ecrire(c.cle_env, cle)
    if not a.fleches.filter(action="fiche", actif=True).exists():
        Fleche.objects.create(adherent=a, evenement="tout", action="fiche", connecteur=c)
        fleches += 1
    clients = []
    for cl in a.clients.all():
        parc = "; ".join(" ".join(x for x in (e.famille, e.marque, e.modele, f"({e.site})" if e.site else "", e.pose_le) if x) for e in cl.equipements.filter(actif=True))
        clients.append({"nom": cl.nom, "exploitation": cl.exploitation, "telephone": cl.telephone, "telephone2": cl.telephone2, "email": cl.email,
                        "adresse": cl.adresse, "commune": cl.commune, "materiel": "; ".join(x for x in (cl.materiel, parc) if x), "produits": cl.produits,
                        "commercial": cl.commercial.nom if cl.commercial else "", "notes": cl.notes, "civilite": cl.civilite, "type": cl.genre})
    personnes = [{"nom": p.nom, "role": p.role, "email": p.email, "telephone": p.telephone} for p in a.personnes.filter(actif=True)]
    sortie.append({"id": a.pk, "entreprise": a.entreprise, "prenom_dirigeant": a.prenom_dirigeant, "numero_dedie": a.numero_dedie,
                   "numero_habituel": a.numero_habituel, "zone": a.zone, "clients": clients, "personnes": personnes})
with open("/data/export-erp.json", "w", encoding="utf-8") as f:
    json.dump(sortie, f, ensure_ascii=False)
print(f"Assistant : {len(sortie)} adhérents, {sum(len(x['clients']) for x in sortie)} clients ; connecteur ERP posé partout, {fleches} flèche(s) ajoutée(s).")
