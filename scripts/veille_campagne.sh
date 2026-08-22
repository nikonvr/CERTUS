#!/usr/bin/env bash
# VEILLE DE CAMPAGNE -- un battement de coeur toutes les 5 minutes, ecrit sur disque.
#
# 👤 : « fais des verifs a 30mn d'intervalle pour voir si ca plante ».
#
# 🔑 POURQUOI UN FICHIER ET PAS SEULEMENT DES REGARDS. Une campagne de huit heures peut mourir
# a 3 h du matin. Un controle qui ne tourne que quand quelqu'un le lance ne verra qu'un
# resultat manquant, sans jamais dire NI QUAND ni DANS QUEL ETAT. Ce fichier-ci donne l'heure
# du deces et ce que la machine faisait juste avant.
#
# Il n'interrompt rien et n'ecrit que dans son propre journal : le voir tourner ne change
# aucune mesure.
#
#     bash scripts/veille_campagne.sh reports/serie75_2026-08-22 &
#     tail -20 reports/serie75_2026-08-22/VEILLE.log

set -u
DOSSIER="${1:-reports/serie75_2026-08-22}"
PERIODE="${2:-300}"
LOG="$DOSSIER/VEILLE.log"
mkdir -p "$DOSSIER"

echo "[veille] demarrage $(date '+%Y-%m-%d %H:%M:%S') · periode ${PERIODE}s · dossier $DOSSIER" >> "$LOG"

vide=0
while true; do
  n=$(powershell.exe -NoProfile -Command \
      "(Get-CimInstance Win32_Process -Filter \"Name LIKE 'python%'\" | Measure-Object).Count" \
      2>/dev/null | tr -d '\r' | tail -1)
  n="${n:-0}"

  # le composant en cours : le journal le plus recemment ecrit
  courant=$(ls -t "$DOSSIER"/journal_*.log 2>/dev/null | head -1)
  comp="(aucun)"; bloc="--"
  if [ -n "$courant" ]; then
    comp=$(basename "$courant" .log | sed 's/^journal_//')
    dernier=$(ls -t reports/orchestre_${comp}_*/journal_s*.log 2>/dev/null | head -1)
    [ -n "$dernier" ] && bloc=$(grep -oE '\[Block [0-9]+\]' "$dernier" 2>/dev/null | tail -1)
  fi

  # 🔴 ZERO PROCESSUS DEUX FOIS DE SUITE = la campagne est morte ou terminee. On le DIT au
  # lieu de laisser un journal qui s'arrete sans explication -- un silence se lit « tout va
  # bien » aussi facilement que « tout est mort ».
  if [ "$n" -eq 0 ]; then
    vide=$((vide + 1))
  else
    vide=0
  fi

  etat="ok"
  [ "$vide" -ge 2 ] && etat="🔴 AUCUN PROCESSUS -- campagne terminee ou MORTE"

  echo "[$(date '+%H:%M:%S')] python=$n · composant=$comp · $bloc · $etat" >> "$LOG"

  if [ "$vide" -ge 2 ]; then
    echo "[veille] arret $(date '+%Y-%m-%d %H:%M:%S') -- plus rien ne tourne" >> "$LOG"
    exit 0
  fi
  sleep "$PERIODE"
done
