#!/bin/bash
# Archive des artefacts JSON volumineux hors du depot : gzip sans perte, relecture verifiee (SHA256 du contenu decompresse = SHA256 du brut),
# une ligne de manifeste par fichier, et seulement ensuite retrait du brut. Un fichier dont la relecture differe est CONSERVE.
# usage : archive_artefacts.sh <racine_archive> <fichier_brut> [...]     (chemins relatifs a la racine du depot, sous reports/)
set -u
REPO="D:/drivfl/01_Recherche_Enseignement/02_Couches_Minces_Optique/couches minces 2026/CERTUS/certus0310"
ROOT="$1"; shift
cd "$REPO" || exit 1
mkdir -p "$ROOT/reports" || exit 1
MAN="$ROOT/manifest.jsonl"
ok=0; ko=0
for f in "$@"; do
  [ -f "$f" ] || { echo "ABSENT $f"; ko=$((ko+1)); continue; }
  dest="$ROOT/$f.gz"
  mkdir -p "$(dirname "$dest")"
  raw_sha=$(sha256sum "$f" | cut -d' ' -f1); raw_size=$(wc -c < "$f")
  gzip -c "$f" > "$dest" || { echo "GZIP ECHEC $f"; rm -f "$dest"; ko=$((ko+1)); continue; }
  back_sha=$(gzip -dc "$dest" | sha256sum | cut -d' ' -f1)
  if [ "$raw_sha" = "$back_sha" ]; then
    gz_sha=$(sha256sum "$dest" | cut -d' ' -f1); gz_size=$(wc -c < "$dest")
    printf '{"path":"%s","raw_bytes":%s,"raw_sha256":"%s","gz_bytes":%s,"gz_sha256":"%s","archived_utc":"%s"}\n' \
      "$f" "$raw_size" "$raw_sha" "$gz_size" "$gz_sha" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$MAN"
    rm -- "$f" && { echo "OK $f ($raw_size -> $gz_size octets)"; ok=$((ok+1)); }
  else
    echo "VERIFICATION ECHOUEE $f : brut conserve"; rm -f "$dest"; ko=$((ko+1))
  fi
done
echo "archives=$ok echecs=$ko manifeste=$MAN"
[ "$ko" = "0" ]
