#!/bin/sh
# Branche l'assistant téléphonique (/srv/assistant, même serveur) sur l'ERP, dans les deux sens. Relançable.
#   sh scripts/connecter_assistant.sh        (depuis /srv/erp/app)
# 1. la clé d'API de l'ERP (créée au besoin) est posée dans l'assistant : connecteur « ERP Cultiveau » et flèche pour
#    chaque adhérent ; 2. les adhérents (numéro dédié) et leurs clients sont exportés de l'assistant et importés dans
#    l'ERP ; 3. la messagerie sortante de l'ERP utilise le compte notification@cultiveau.fr de l'assistant.
set -eu
. ./.env 2>/dev/null || true
BASE=${ODOO_DB:-cultiveau}
ASSISTANT=${ASSISTANT:-/srv/assistant}
ERP_URL=${ERP_URL:-https://erp.cultiveau.fr}
docker ps --format '{{.Names}}' | grep -qx assistant || { echo "Le conteneur « assistant » ne tourne pas sur ce serveur." >&2; exit 1; }
CLE=$(docker compose run --rm -T odoo odoo shell -d "$BASE" --no-http < scripts/cle_api.py 2>/dev/null | grep '^CLE=' | cut -d= -f2-)
[ -n "$CLE" ] || { echo "La clé d'API de l'ERP n'a pas pu être lue." >&2; exit 1; }
docker exec -i -e CLE="$CLE" -e ERP_URL="$ERP_URL" assistant python manage.py shell < scripts/assistant_connecteur.py
docker cp assistant:/data/export-erp.json donnees/assistant.json
docker exec assistant rm -f /data/export-erp.json
lire() { grep "^$1=" "$ASSISTANT/secrets/.env" 2>/dev/null | head -1 | cut -d= -f2- | sed 's/^"//; s/"$//'; }
docker compose run --rm -T -e "SMTP_MDP=$(lire SMTP_MDP)" -e "SMTP_HOTE=$(lire SMTP_HOTE)" -e "SMTP_PORT=$(lire SMTP_PORT)" -e "SMTP_UTILISATEUR=$(lire SMTP_UTILISATEUR)" \
  odoo odoo shell -d "$BASE" --no-http < scripts/charger_assistant.py 2>&1 | grep -v "^$" | grep -v "^\s*File \|^\s*\^"
rm -f donnees/assistant.json
echo "Assistant et ERP connectés."
