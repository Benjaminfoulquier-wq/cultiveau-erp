#!/bin/sh
# Charge des données dans la base de production, depuis /srv/erp/app (ou la racine du projet) :
#   sh scripts/donnees.sh demo        # Jean Martin, ses cultures, son persona, son installation, un dépannage, un devis, des opportunités
#   sh scripts/donnees.sh catalogue   # le catalogue 3D (24 000 articles, quelques minutes) ; relançable
#   sh scripts/donnees.sh bibliotheque  # la bibliothèque technique (2 300 documents du Drive) et le lien article ↔ fiche
#   sh scripts/donnees.sh fiches      # rapatrie les PDF du Drive (3 Go, une heure) et les joint aux fiches, première page en image
#   sh scripts/donnees.sh tout        # les quatre
set -eu
. ./.env 2>/dev/null || true
BASE=${ODOO_DB:-cultiveau}
QUOI=${1:-tout}
shell() { docker compose run --rm -T odoo odoo shell -d "$BASE" --no-http < "$1" 2>&1 | grep -v "^$" | grep -v "^\s*File \|Traceback\|^\s*\^" ; }
case "$QUOI" in
  demo) shell scripts/demo.py ;;
  catalogue) shell scripts/charger_catalogue.py ;;
  bibliotheque) shell scripts/charger_bibliotheque.py ;;
  fiches) sh scripts/rapatrier_fiches.sh; shell scripts/charger_fiches.py ;;
  tout) shell scripts/charger_catalogue.py; shell scripts/charger_bibliotheque.py; sh scripts/rapatrier_fiches.sh; shell scripts/charger_fiches.py; shell scripts/demo.py ;;
  *) echo "usage : sh scripts/donnees.sh demo|catalogue|bibliotheque|fiches|tout"; exit 1 ;;
esac
