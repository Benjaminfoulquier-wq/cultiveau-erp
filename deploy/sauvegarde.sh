#!/bin/sh
# Sauvegarde nocturne : la base (pg_dump) et les fichiers d'Odoo (filestore), 30 jours conservés.
set -eu
cd /srv/erp/app
. /srv/erp/.env
DEST=/srv/sauvegardes/erp
JOUR=$(date +%Y-%m-%d)
mkdir -p "$DEST"
docker compose exec -T db pg_dump -U odoo -Fc "$ODOO_DB" > "$DEST/$ODOO_DB-$JOUR.dump"
tar -czf "$DEST/filestore-$JOUR.tar.gz" -C /srv/erp/data/odoo filestore 2>/dev/null || true
find "$DEST" -type f -mtime +30 -delete
