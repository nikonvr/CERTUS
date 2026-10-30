#!/usr/bin/env bash
# Mini campaign of the cissoid (2026-10-30, the owner: "des mini campagnes de 45 mn, puis analyse si on est dans une
# voie de garage ou qq chose de prometteur", "ne rien prévoir à l'avance, mais s'adapter à la réalité des résultats").
# usage: bash mini.sh TAG MINUTES SEED [CISSOID_VAR=VALUE ...]; the settings are written to campaign.log.
cd "$(dirname "$0")" || exit 1
tag=$1 minutes=$2 seed=$3
shift 3
log() { echo "$(date '+%F %H:%M') $*" >> campaign.log; }
[ -n "$MINI_PARALLEL" ] || while tasklist //FI "IMAGENAME eq python.exe" | grep -q python; do sleep 20; done
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1 CISSOID_WORKERS=${CISSOID_WORKERS:-7}
for kv in "$@"; do export "${kv?}"; done
log "mini $tag ($minutes min, seed $seed): $*"
CISSOID_TAG=$tag CISSOID_SEED=$seed python cissoid_islands.py "$minutes" > "cissoid_islands_$tag.out" 2>&1 || log "mini $tag FAILED"
log "mini $tag done: $(tail -n 1 "cissoid_islands_$tag.log")"
