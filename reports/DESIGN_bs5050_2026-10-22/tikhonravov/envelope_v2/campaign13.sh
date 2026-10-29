#!/usr/bin/env bash
# 2026-10-28 19:50 (user: "7 diversified gradual-evolution trajectories in parallel, one per core, up to 11500 nm"):
# the three-line filter from the bare substrate, 7 trajectories that differ by deep-search width K, TOT step and first
# material; one BLAS thread each; 150 min max; then the 50/50 diagnostics (campaign8).
cd "$(dirname "$0")" || exit 1
log() { echo "$(date '+%F %H:%M') $*" >> campaign.log; }
while tasklist //FI "IMAGENAME eq python.exe" | grep -q python; do sleep 20; done
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 SEARCH_TARGET=threeline
log "3line beam: 7 gradual trajectories in parallel (K, DTOT, first layer varied), up to 11500 nm, 150 min max"
i=0
# (first try at 19:47 varied the first material too: a first L layer becomes H at the first needle, so trajectories
#  3 and 4 were identical; restarted at 19:50 with the TOT step varied instead)
for cfg in "1 70" "1 130" "2 100" "2 60" "3 80" "3 120" "2 150"; do
  set -- $cfg; i=$((i + 1))
  GRAD_DEEP=$1 GRAD_DTOT=$2 GRAD_TAG="_beam$i" python gradual.py 150 11500 > gradual_beam$i.out 2>&1 &
done
wait
log "3line beam done"
unset SEARCH_TARGET
echo "$(date '+%F %H:%M') 3line arms done (beam replaces arm B for now)" >> campaign.log
bash campaign8.sh
