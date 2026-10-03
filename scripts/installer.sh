#!/bin/sh
# Crée la base de production et y installe l'ERP de l'irrigation : les modules Odoo utiles au
# réseau (ventes, factures, comptabilité française, CRM, stocks, achats, projet, e-mailing, contacts)
# et les modules Cultiveau. À lancer une fois, depuis /srv/erp/app (ou en local depuis la racine).
#   sh scripts/installer.sh            # base $ODOO_DB (défaut : cultiveau)
set -eu
. ./.env 2>/dev/null || true
BASE=${ODOO_DB:-cultiveau}
NATIFS=contacts,sale_management,account,l10n_fr,crm,stock,purchase,project,mass_mailing,calendar
CULTIVEAU=cultiveau_base,cultiveau_frise,cultiveau_persona,cultiveau_catalogue,cultiveau_installation,cultiveau_ventes,cultiveau_interventions,cultiveau_connecteurs,cultiveau_marque

docker compose up -d db
sleep 5
# Les droits du dossier de fichiers d Odoo sont posés depuis l intérieur du conteneur : c est le seul point de vue
# qui vaut quelle que soit la façon dont le serveur mappe les utilisateurs des conteneurs.
docker compose run --rm --user root --entrypoint sh odoo -c 'mkdir -p /var/lib/odoo/filestore /var/lib/odoo/sessions && chown -R odoo:odoo /var/lib/odoo && ls -ld /var/lib/odoo /var/lib/odoo/filestore'
# Une base laissée à moitié créée par un essai raté (module base absent) est repartie de zéro ; une base installée est gardée.
existe=$(docker compose exec -T db psql -U odoo -d postgres -tAc "select 1 from pg_database where datname='$BASE'" 2>/dev/null || true)
if [ "$existe" = "1" ]; then
  base=$(docker compose exec -T db psql -U odoo -d "$BASE" -tAc "select state from ir_module_module where name='base'" 2>/dev/null || true)
  dernier=$(docker compose exec -T db psql -U odoo -d "$BASE" -tAc "select state from ir_module_module where name='cultiveau_connecteurs'" 2>/dev/null || true)
  if [ "$dernier" = "installed" ]; then
    echo "La base « $BASE » est déjà installée (modules Cultiveau compris) : rien à créer. Pour mettre à jour : sh deploy/deployer.sh"
    exit 0
  fi
  if [ "$base" = "installed" ]; then
    echo "Base « $BASE » : Odoo est posé, les modules manquants vont être installés."
  else
    echo "Base « $BASE » incomplète (essai précédent interrompu) : on la recrée."
    docker compose stop odoo >/dev/null 2>&1 || true
    docker compose exec -T db psql -U odoo -d postgres -c "drop database \"$BASE\"" >/dev/null
  fi
fi
docker compose stop odoo >/dev/null 2>&1 || true
docker compose run --rm odoo odoo -d "$BASE" -i "$NATIFS,$CULTIVEAU" --without-demo=all --load-language=fr_FR --stop-after-init
# Langue, pays et réglages par défaut : français, France, euro.
docker compose run --rm odoo odoo shell -d "$BASE" --no-http <<'EOF'
env["res.lang"]._activate_lang("fr_FR")
env.ref("base.user_admin").write({"lang": "fr_FR", "tz": "Europe/Paris"})
env.ref("base.main_company").write({"country_id": env.ref("base.fr").id, "currency_id": env.ref("base.EUR").id})
env["ir.config_parameter"].sudo().set_param("cultiveau.url_assistant", "https://assistant.cultiveau.fr")
env["ir.config_parameter"].sudo().set_param("cultiveau.url_dte", "https://dte.cultiveau.fr")
env["ir.config_parameter"].sudo().set_param("cultiveau.url_disc", "https://disc.cultiveau.fr")
env["ir.config_parameter"].sudo().set_param("cultiveau.url_academie", "https://formations.lesjourneesdecultiveau.fr")
env.cr.commit()
print("Réglages posés. Clé de l'API des outils : à saisir dans Cultiveau → Réglages (et dans la page Clés de l'assistant).")
EOF
docker compose up -d
echo "Base « $BASE » prête. Première connexion : admin / admin — changer le mot de passe tout de suite."
