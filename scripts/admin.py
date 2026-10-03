# Crée (ou met à jour) un compte administrateur de l'ERP, depuis les variables ADMIN_EMAIL, ADMIN_MDP et ADMIN_NOM.
#   ADMIN_EMAIL=... ADMIN_MDP=... docker compose run --rm -T -e ADMIN_EMAIL -e ADMIN_MDP -e ADMIN_NOM odoo odoo shell -d cultiveau --no-http < scripts/admin.py
import os

email = (os.environ.get("ADMIN_EMAIL") or "").strip().lower()
mdp = os.environ.get("ADMIN_MDP") or ""
nom = (os.environ.get("ADMIN_NOM") or "").strip() or email.split("@")[0].replace(".", " ").title()
if not email or not mdp:
    raise SystemExit("ADMIN_EMAIL et ADMIN_MDP sont requis.")
Users = env["res.users"].with_context(no_reset_password=True)
groupes = [env.ref("base.group_system"), env.ref("base.group_erp_manager"), env.ref("base.group_partner_manager"),
           env.ref("cultiveau_base.group_equipe", raise_if_not_found=False)]
groupes = [g for g in groupes if g]
u = Users.search([("login", "=", email)], limit=1)
valeurs = {"login": email, "email": email, "name": nom, "lang": "fr_FR", "tz": "Europe/Paris", "password": mdp,
           "groups_id": [(4, g.id) for g in groupes]}
if u:
    u.write(valeurs)
    action = "mis à jour"
else:
    u = Users.create(valeurs)
    action = "créé"
env.cr.commit()
print(f"Compte administrateur {action} : {email} ({nom}), groupes : {', '.join(g.full_name for g in groupes)}.")
