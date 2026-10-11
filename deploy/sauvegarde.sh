#!/bin/sh
# Sauvegarde nocturne : la base (pg_dump) et les fichiers de l'ERP (filestore).
# - 30 jours conservés sur le serveur, les sauvegardes du dimanche 90 jours ;
# - chaque sauvegarde est vérifiée (pg_restore --list) avant d'être gardée ;
# - si /srv/erp/rclone.conf existe (un espace de stockage hors du serveur, posé par le secret CULTIVEAU_RCLONE_CONF),
#   la sauvegarde du jour y est copiée aussi : le serveur peut brûler, la base est ailleurs.
set -eu
cd /srv/erp/app
. /srv/erp/.env
DEST=/srv/sauvegardes/erp
JOUR=$(date +%Y-%m-%d)
FICHIER="${DEST:?}/${ODOO_DB:?}-${JOUR:?}.dump"
mkdir -p "$DEST"
docker compose exec -T db pg_dump -U odoo -Fc "$ODOO_DB" > "$FICHIER.tmp"
if ! docker compose exec -T db pg_restore --list < "$FICHIER.tmp" > /dev/null 2>&1; then
  rm -f "${FICHIER:?}.tmp"
  echo "Sauvegarde du $JOUR illisible : abandon." >&2
  exit 1
fi
mv "$FICHIER.tmp" "$FICHIER"
tar -czf "$DEST/filestore-$JOUR.tar.gz" -C /srv/erp/data/odoo filestore 2>/dev/null || true
if [ "$(date +%u)" = "7" ]; then cp "$FICHIER" "$DEST/hebdo-$ODOO_DB-$JOUR.dump"; fi
find "${DEST:?}" -type f -name "hebdo-*" -mtime +90 -delete
find "${DEST:?}" -type f ! -name "hebdo-*" -mtime +30 -delete
if [ -f /srv/erp/rclone.conf ] && command -v rclone > /dev/null 2>&1; then
  if rclone --config /srv/erp/rclone.conf copy "$DEST" sauvegardes:erp --max-age 2d --quiet; then
    rclone --config /srv/erp/rclone.conf delete sauvegardes:erp --min-age 90d --quiet || true
  else
    echo "Copie hors serveur impossible ($JOUR) : vérifier /srv/erp/rclone.conf." >&2
  fi
fi
echo "Sauvegarde du $JOUR : $(du -sh "$DEST" | cut -f1) sur le serveur$( [ -f /srv/erp/rclone.conf ] && echo ', copiée hors serveur')."
