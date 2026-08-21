#!/usr/bin/env bash
# Chaine de mesures autonome du 2026-08-21 apres-midi.
#
# Regle appliquee : UNE MESURE, UNE MACHINE. Chaque run attend l'artefact du precedent
# au lieu de se lancer en parallele -- le pipeline sature tous les coeurs en prange, et
# deux runs simultanes rendent des durees, voire des resultats, incomparables.
set -u
cd /c/certus
PY="C:/envs/certus/Scripts/python.exe"
J="reports/nuit_multiseed_20260821"

attendre() {   # $1 = artefact attendu
  echo "[chaine] attente de $1"
  until [ -f "$1" ]; do sleep 20; done
  echo "[chaine] $1 present -- $(date +%H:%M:%S)"
}

# 1. la couverture sur la plage COMPLETE tourne deja (tag couvfull)
attendre "reports/blocs_vs_plantage_r75x2_deep_s042_couvfull.json"

# 2. REPRISE DE LA CONFIG LIVREE A LA GRAINE 101.
#    C'est la mesure qui borne la maledictionpdu vainqueur : les 12 rampes ont ete choisies
#    sur des mesures a la graine 42, puis remesurees a la graine 42. Une graine qui n'a pas
#    servi a choisir est le seul controle possible. Aucune surcharge : tout vient du JSON.
echo "[chaine] === graine 101 sur la config livree ==="
CERTUS_BENCH_TIMEOUT_S=5400 "$PY" scripts/probe_blocs_vs_plantage.py \
    r75x2-2nm deep 0 0 2.0 0 101 > "$J/journal_accept101.log" 2>&1
echo "[chaine] graine 101 terminee, EXIT=$? -- $(date +%H:%M:%S)"

# 3. Et la graine 202, pour que le controle ne repose pas sur UNE graine -- c'est la lecon
#    de §24-46 : un verdict d'intervalle n'est pas determine par une graine.
echo "[chaine] === graine 202 sur la config livree ==="
CERTUS_BENCH_TIMEOUT_S=5400 "$PY" scripts/probe_blocs_vs_plantage.py \
    r75x2-2nm deep 0 0 2.0 0 202 > "$J/journal_accept202.log" 2>&1
echo "[chaine] graine 202 terminee, EXIT=$? -- $(date +%H:%M:%S)"
echo "[chaine] CHAINE COMPLETE"
