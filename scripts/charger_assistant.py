# Côté ERP (shell Odoo) : les adhérents de l'assistant (numéro dédié, n° d'adhérent) reportés sur les sociétés, leurs
# clients importés chez chacun (moteur « Importer mes clients », sans doublon), et la messagerie sortante de l'ERP
# branchée sur notification@cultiveau.fr (le même compte que l'assistant). Relançable.
import csv
import io
import json
import os
import re
import unicodedata


chemin = os.environ.get("ASSISTANT_JSON", "/mnt/donnees/assistant.json")
if not os.path.exists(chemin):
    chemin = "donnees/assistant.json"


def cle(texte):
    s = unicodedata.normalize("NFKD", str(texte or "")).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(sas|sasu|sarl|eurl|ei|ets|sa|societe|etablissements)\b", " ", s)
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s).split())


Company = env["res.company"].sudo()
Partner = env["res.partner"].sudo()
Moteur = env["cultiveau.import.clients.moteur"].sudo()
societes = {cle(c.name): c for c in Company.search([])}
principale = Company.browse(1) if Company.browse(1).exists() else Company.search([], limit=1)
# Le groupe (holding, Cultiveau, Solution Magnus) n'a pas de clients agriculteurs : les contacts que l'assistant lui
# attribue sont la base de contacts du réseau, rangée sous Cultiveau avec une étiquette au nom de l'adhérent d'origine.
GROUPE = {"agrifusion", "agrifusion holding", "cultiveau", "solution magnus", "magnus formation"}


def etiquette(nom):
    Cat = env["res.partner.category"].sudo()
    return Cat.search([("name", "=ilike", nom)], limit=1) or Cat.create({"name": nom})

total = {"adherents": 0, "crees": 0, "clients_crees": 0, "clients_maj": 0, "clients_ignores": 0}
non_trouves = []
for a in json.load(open(chemin, encoding="utf-8")):
    k = cle(a["entreprise"])
    company = societes.get(k)
    if not company:
        company = next((c for kk, c in societes.items() if kk and (kk in k or k in kk) and len(min(k, kk)) >= 4), None)
    if not company:
        company = Company.create({"name": a["entreprise"], "cultiveau_adherent": True})
        societes[k] = company
        total["crees"] += 1
        non_trouves.append(a["entreprise"])
    company.write({"cultiveau_numero_dedie": a.get("numero_dedie") or False, "cultiveau_assistant_id": a["id"]})
    if a.get("zone") and not company.partner_id.comment:
        company.partner_id.comment = f"Zone d'intervention : {a['zone']}"
    total["adherents"] += 1
    cible = company
    if cle(a["entreprise"]) in GROUPE or cle(company.name) in GROUPE or not company.cultiveau_adherent:
        cible = principale
        deplaces = Partner.search([("company_id", "=", company.id), ("parent_id", "=", False), ("id", "!=", company.partner_id.id),
                                   ("cultiveau_type", "in", ["agriculteur", "autre", False])]) if company != principale else Partner
        if deplaces:
            deplaces.write({"company_id": principale.id, "category_id": [(4, etiquette(f"Contacts de l'assistant — {a['entreprise']}").id)]})
            print(f"{len(deplaces)} contacts déplacés de {company.name} vers {principale.name}.")
    if a.get("clients"):
        sortie = io.StringIO()
        w = csv.writer(sortie, delimiter=";")
        w.writerow(["Nom", "Exploitation", "Téléphone", "Autre téléphone", "E-mail", "Adresse", "Commune", "Matériel", "Produits", "Commercial", "Notes", "Civilité", "Type"])
        for c in a["clients"]:
            w.writerow([c.get(x) or "" for x in ("nom", "exploitation", "telephone", "telephone2", "email", "adresse", "commune", "materiel", "produits", "commercial", "notes", "civilite", "type")])
        avant = set(Partner.search([("company_id", "=", cible.id)]).ids) if cible != company else set()
        bilan = Moteur.with_company(cible).importer("assistant.csv", sortie.getvalue().encode("utf-8"), societe=cible)
        if cible != company:
            nouveaux = set(Partner.search([("company_id", "=", cible.id)]).ids) - avant
            Partner.browse(list(nouveaux)).write({"category_id": [(4, etiquette(f"Contacts de l'assistant — {a['entreprise']}").id)]})
        total["clients_crees"] += bilan["crees"]
        total["clients_maj"] += bilan["maj"]
        total["clients_ignores"] += bilan["ignores"]
    env.cr.commit()
# Les sociétés créées par un passage précédent pour des adhérents qui ne sont plus exportés (essais) : archivées si vides.
exportes = {a["id"] for a in json.load(open(chemin, encoding="utf-8"))}
archivees = []
for c in Company.search([("cultiveau_assistant_id", "!=", 0), ("cultiveau_assistant_id", "not in", list(exportes))]):
    if c.id == 1 or env["res.users"].sudo().search_count([("company_id", "=", c.id)]) or env["res.partner"].sudo().search_count([("company_id", "=", c.id), ("id", "!=", c.partner_id.id)]):
        continue
    c.write({"active": False, "cultiveau_assistant_id": 0})
    archivees.append(c.name)
if archivees:
    env.cr.commit()
    print(f"Sociétés d'essai archivées : {', '.join(archivees)}.")
print(f"Adhérents de l'assistant reliés : {total['adherents']} ({total['crees']} sociétés créées" + (f" : {', '.join(non_trouves)}" if non_trouves else "") + ").")
print(f"Clients de l'assistant : {total['clients_crees']} créés, {total['clients_maj']} mis à jour, {total['clients_ignores']} ignorés.")

mdp = os.environ.get("SMTP_MDP")
if mdp:
    Serveur = env["ir.mail_server"].sudo()
    hote, port, utilisateur = os.environ.get("SMTP_HOTE") or "smtp.hostinger.com", int(os.environ.get("SMTP_PORT") or 465), os.environ.get("SMTP_UTILISATEUR") or "notification@cultiveau.fr"
    vals = {"name": "Cultiveau (notification)", "smtp_host": hote, "smtp_port": port, "smtp_encryption": "ssl" if port == 465 else "starttls",
            "smtp_user": utilisateur, "smtp_pass": mdp, "from_filter": utilisateur.split("@")[-1], "sequence": 1}
    serveur = Serveur.search([("smtp_user", "=", utilisateur)], limit=1)
    serveur.write(vals) if serveur else Serveur.create(vals)
    # Le domaine d'alias : tout e-mail de l'ERP part de notification@cultiveau.fr, quel que soit l'auteur, pour toutes les sociétés.
    domaine_nom, local = utilisateur.split("@")[-1], utilisateur.split("@")[0]
    Domaine = env["mail.alias.domain"].sudo()
    domaine = Domaine.search([("name", "=", domaine_nom)], limit=1)
    vals_d = {"name": domaine_nom, "default_from": local, "bounce_alias": "bounce", "catchall_alias": "catchall"}
    domaine = domaine.write(vals_d) and domaine or (domaine or Domaine.create(vals_d))
    Company.with_context(active_test=False).search([]).write({"alias_domain_id": domaine.id})
    robot = env.ref("base.partner_root", raise_if_not_found=False)
    if robot and (not robot.email or robot.email.endswith("example.com")):
        robot.sudo().write({"email": utilisateur})
    en_echec = env["mail.mail"].sudo().search([("state", "=", "exception")])
    en_echec.write({"state": "outgoing", "failure_reason": False})  # repartiront avec le bon expéditeur
    env.cr.commit()
    print(f"Messagerie sortante : {utilisateur} via {hote}:{port} ; domaine d'alias {domaine_nom} sur {Company.search_count([])} sociétés ;"
          f" {len(en_echec)} e-mail(s) en échec remis en file.")
