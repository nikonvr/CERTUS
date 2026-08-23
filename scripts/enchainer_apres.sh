#!/usr/bin/env bash
# LANCER UNE MESURE DES QUE LA MACHINE SE LIBERE -- generique.
#
#     bash scripts/enchainer_apres.sh <etiquette> <composant> [args de l'orchestrateur...]
#
# ## 🔴 POURQUOI ATTENDRE, ET POURQUOI EN REGARDANT LES PROCESSUS
#
# 📏 Mesure du 2026-08-22 sur 16 threads : deux runs concurrents ne rendent que **+29 %** de
# debit, et le CPU plafonne a 74 % avec un seul -- le goulot est la bande passante memoire.
# Ajouter un troisieme travail ne ferait donc que ralentir les deux autres ET gonfler leurs
# durees, qui sont elles-memes des mesures.
#
# 🔴 On regarde les PROCESSUS, jamais l'apparition d'un artefact : la sonde l'ecrit AVANT sa
# synthese, et une chaine qui le guettait a lance la mesure suivante 10 s trop tot le
# 2026-08-21 (« RuntimeError: QThread has been deleted »). Temporisation de trois minutes : une
# campagne passe d'un composant au suivant en quelques secondes, jamais en trois minutes.

set -u
[ "$#" -ge 2 ] || { echo "usage: $0 <etiquette> <composant> [args...]" >&2; exit 2; }
ETIQ="$1"; COMP="$2"; shift 2
PY="${CERTUS_PY:-C:/envs/certus/Scripts/python.exe}"
J="reports/${ETIQ}"
mkdir -p "$J"
LOG="$J/journal_${COMP}.log"

echo "[$ETIQ] en attente que la machine se libere -- $(date '+%Y-%m-%d %H:%M:%S')"
vide=0
while [ "$vide" -lt 3 ]; do
  n=$(powershell.exe -NoProfile -Command \
      "(Get-CimInstance Win32_Process -Filter \"Name LIKE 'python%'\" | Measure-Object).Count" \
      2>/dev/null | tr -d '\r' | tail -1)
  n="${n:-0}"
  if [ "$n" -eq 0 ]; then vide=$((vide + 1)); else vide=0; fi
  sleep 60
done

echo "[$ETIQ] machine libre -- demarrage $COMP a $(date '+%H:%M:%S')"
t0=$(date +%s)
"$PY" scripts/orchestre_multigraine.py "$COMP" "$@" --evenements > "$LOG" 2>&1
code=$?
echo "[$ETIQ] $COMP EXIT=$code en $(( ($(date +%s) - t0) / 60 )) min -- $(date '+%H:%M:%S')"
grep -E "RESULTAT CITABLE|annonce en cours|MULTI-TEMOIN|MINIMUM TROUVE|Aucune realisation|NON ESSAYEES" \
    "$LOG" | sed 's/^/    /' || true
