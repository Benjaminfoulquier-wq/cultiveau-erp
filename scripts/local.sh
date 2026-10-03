#!/bin/sh
# Lancer l'ERP sur son ordinateur, en localhost, avec Docker Desktop (Mac, Windows via Git Bash ou WSL, Linux).
#   sh scripts/local.sh            # installe tout, puis ouvre http://localhost:8069
#   sh scripts/local.sh demo       # idem, avec un agriculteur, son installation, un dépannage et un devis de démonstration
#   sh scripts/local.sh stop       # arrête les conteneurs (les données restent dans ./data)
#   sh scripts/local.sh reset      # efface tout et repart de zéro
set -eu
cd "$(dirname "$0")/.."
BASE=${ODOO_DB:-cultiveau}

if [ "${1:-}" = "stop" ]; then docker compose down; exit 0; fi
if [ "${1:-}" = "reset" ]; then docker compose down -v; rm -rf data; echo "Données effacées."; exit 0; fi

command -v docker >/dev/null 2>&1 || { echo "Docker n'est pas installé : https://www.docker.com/products/docker-desktop/"; exit 1; }
if [ ! -f .env ]; then
  printf 'POSTGRES_PASSWORD=%s\nODOO_ADMIN_PASSWD=admin\nODOO_DB=%s\nDOMAINE=localhost\n' "$(date +%s | sha256sum 2>/dev/null | head -c 24 || echo cultiveau-local)" "$BASE" > .env
fi
mkdir -p data/odoo data/postgres
# Sur Linux, le conteneur Odoo écrit avec l'utilisateur 101.
chmod 777 data/odoo 2>/dev/null || true
cat > docker-compose.local.yml <<'EOF'
# Surcouche locale : le port 8069 ouvert sur l'ordinateur, pas de réseau Caddy.
services:
  odoo:
    ports: ["8069:8069", "8072:8072"]
    networks: [erp]
networks:
  web:
    external: false
EOF
COMPOSE="docker compose -f docker-compose.yml -f docker-compose.local.yml"
$COMPOSE up -d db
echo "Attente de PostgreSQL…"; sleep 8
if ! $COMPOSE run --rm odoo odoo shell -d "$BASE" --no-http -c /etc/odoo/odoo.conf </dev/null >/dev/null 2>&1; then
  echo "Création de la base « $BASE » et installation des modules (quelques minutes la première fois)…"
  $COMPOSE run --rm odoo odoo -d "$BASE" -c /etc/odoo/odoo.conf --without-demo=all --load-language=fr_FR \
    -i contacts,sale_management,account,l10n_fr,crm,stock,purchase,project,mass_mailing,calendar,cultiveau_base,cultiveau_frise,cultiveau_persona,cultiveau_catalogue,cultiveau_installation,cultiveau_ventes,cultiveau_interventions,cultiveau_connecteurs,cultiveau_marque \
    --stop-after-init
  $COMPOSE run --rm odoo odoo shell -d "$BASE" -c /etc/odoo/odoo.conf --no-http < scripts/reglages_initiaux.py
fi
if [ "${1:-}" = "demo" ]; then
  echo "Données de démonstration…"
  $COMPOSE run --rm odoo odoo shell -d "$BASE" -c /etc/odoo/odoo.conf --no-http < scripts/demo.py
fi
$COMPOSE up -d
echo
echo "L'ERP est là : http://localhost:8069  (identifiant admin, mot de passe admin)"
echo "Menu Cultiveau en haut à gauche. Arrêter : sh scripts/local.sh stop"
