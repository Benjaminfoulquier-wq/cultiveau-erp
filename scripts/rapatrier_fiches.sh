#!/bin/sh
# Rapatrie les documents de la bibliothèque technique depuis le Drive du réseau (dossiers partagés par lien)
# vers /srv/erp/data/fiches : un fichier par identifiant Drive, plus la première page en PNG pour les PDF.
# Relançable : ce qui est déjà là n'est pas retéléchargé. Ensuite : sh scripts/donnees.sh fiches
#   sh scripts/rapatrier_fiches.sh            # tout l'inventaire (donnees/bibliotheque.csv)
#   LIMITE=20 sh scripts/rapatrier_fiches.sh  # les 20 premiers, pour essayer
set -u
INVENTAIRE=${INVENTAIRE:-donnees/bibliotheque.csv}
DOSSIER=${DOSSIER:-/srv/erp/data/fiches}
PARALLELE=${PARALLELE:-6}
LIMITE=${LIMITE:-0}
mkdir -p "$DOSSIER"
if [ "${1:-}" != "--un" ]; then
libre=$(df -Pm "$DOSSIER" | awk 'NR==2{print $4}')
if [ "${libre:-0}" -lt 6000 ]; then echo "Pas assez de place sur le disque ($libre Mo libres, 6 000 nécessaires)." >&2; exit 1; fi
if ! command -v pdftoppm >/dev/null 2>&1 || ! command -v curl >/dev/null 2>&1; then
  apt-get update -qq >/dev/null && apt-get install -y -qq poppler-utils curl >/dev/null
fi

# id<TAB>extension pour les PDF et les images (les plans DWG et les tableurs restent sur le Drive).
awk -F';' 'NR>1 { ext=""; if ($8=="application/pdf") ext="pdf"; else if ($8=="image/jpeg") ext="jpg"; else if ($8=="image/png") ext="png";
                  if (ext!="" && $10!="") print $10 "\t" ext }' "$INVENTAIRE" | sort -u > "$DOSSIER/.liste"
if [ "$LIMITE" -gt 0 ]; then head -n "$LIMITE" "$DOSSIER/.liste" > "$DOSSIER/.liste.tmp" && mv "$DOSSIER/.liste.tmp" "$DOSSIER/.liste"; fi
total=$(wc -l < "$DOSSIER/.liste")
echo "Documents à rapatrier : $total (déjà présents : $(ls "$DOSSIER" | grep -c -E '\.(pdf|jpg|png)$' || true))"
fi

un() {  # un id, une extension : télécharge, vérifie, rend la première page
  id=$1; ext=$2; cible="$DOSSIER/$id.$ext"; tmp="$cible.part"
  if [ ! -s "$cible" ]; then
    ok=0
    for url in "https://drive.usercontent.google.com/download?id=$id&export=download&confirm=t" "https://drive.google.com/uc?export=download&id=$id&confirm=t"; do
      for essai in 1 2 3; do
        curl -sS -L --fail --max-time 600 --retry 2 -o "$tmp" "$url" 2>/dev/null || { sleep $((essai * 5)); continue; }
        entete=$(head -c 8 "$tmp" | tr -d '\0')
        case "$ext:$entete" in
          pdf:%PDF*|jpg:*JFIF*|jpg:*Exif*|png:*PNG*) ok=1; break 2 ;;
          jpg:*) [ "$(head -c 3 "$tmp" | od -An -tx1 | tr -d ' ')" = "ffd8ff" ] && { ok=1; break 2; } ;;
        esac
        sleep $((essai * 5))
      done
    done
    if [ "$ok" = 1 ]; then mv "$tmp" "$cible"; chmod 644 "$cible"; else rm -f "$tmp"; echo "ÉCHEC $id.$ext"; return 1; fi
  fi
  if [ "$ext" = "pdf" ] && [ ! -s "$DOSSIER/$id.png" ]; then
    pdftoppm -f 1 -l 1 -r 50 -scale-to 800 -png -singlefile "$cible" "$DOSSIER/$id" 2>/dev/null || echo "Pas de vignette pour $id"
    [ -f "$DOSSIER/$id.png" ] && chmod 644 "$DOSSIER/$id.png"
  fi
  return 0
}
# sh (dash) n'exporte pas les fonctions : on relance ce script lui-même pour chaque document.
if [ "${1:-}" = "--un" ]; then un "$2" "$3"; exit $?; fi
xargs -P "$PARALLELE" -n 2 -a "$DOSSIER/.liste" sh "$0" --un < /dev/null
echo "Rapatriement terminé : $(ls "$DOSSIER" | grep -c -E '\.(pdf|jpg)$' || true) fichiers, $(ls "$DOSSIER" | grep -c '\.png$' || true) vignettes, $(du -sh "$DOSSIER" | cut -f1) sur le disque."
