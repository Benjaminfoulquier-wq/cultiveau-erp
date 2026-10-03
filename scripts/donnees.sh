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
# Le journal passe par un fichier : un chargement interrompu (mémoire, erreur) fait échouer l'étape au lieu de passer inaperçu.
shell() {
  docker compose run --rm -T -e "LIMITE=${LIMITE:-0}" odoo odoo shell -d "$BASE" --no-http < "$1" > /tmp/erp-donnees.log 2>&1
  code=$?
  grep -v "^$" /tmp/erp-donnees.log | grep -v "^\s*File \|^\s*\^"
  [ "$code" -eq 0 ] || { echo "Chargement interrompu ($1, code $code)." >&2; return "$code"; }
}
# Les PDF sont joints par passages de 100 (un processus par passage : la mémoire ne s'accumule pas).
fiches() {
  sh scripts/rapatrier_fiches.sh
  free -m 2>/dev/null | head -2
  reste=1
  while [ "$reste" -gt 0 ]; do
    LIMITE=100 shell scripts/charger_fiches.py || return $?
    reste=$(grep -o "Reste : [0-9]*" /tmp/erp-donnees.log | grep -o "[0-9]*$" || echo 0)
  done
}
case "$QUOI" in
  demo) shell scripts/demo.py ;;
  catalogue) shell scripts/charger_catalogue.py ;;
  bibliotheque) shell scripts/charger_bibliotheque.py ;;
  fiches) fiches ;;
  tout) shell scripts/charger_catalogue.py; shell scripts/charger_bibliotheque.py; fiches; shell scripts/demo.py ;;
  *) echo "usage : sh scripts/donnees.sh demo|catalogue|bibliotheque|fiches|tout"; exit 1 ;;
esac
