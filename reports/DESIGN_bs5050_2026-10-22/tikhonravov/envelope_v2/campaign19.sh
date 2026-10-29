#!/usr/bin/env bash
# Queued at 2026-10-29 06:20, after campaign18 ends. The best 51-layer three-line design (run 0 of the mix campaign,
# MF 0.6062) still gained at every third series: resume it with wider jumps (sigma 3/10/20/40 %), up to 40 series.
cd "$(dirname "$0")" || exit 1
log() { echo "$(date '+%F %H:%M') $*" >> campaign.log; }
while tasklist //FI "IMAGENAME eq python.exe" | grep -q python; do sleep 20; done
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1

log "constrained three-line N=51 resumed from the 0.6062 design, sigma 3/10/20/40 %, K 40, M1 300, 150 min (theirs 0.464)"
SEARCH_TARGET=threeline CONSTRAINED_RESUME=constrained_threeline_N51_lbfgsb_mix.csv CONSTRAINED_SIGMAS=0.03,0.1,0.2,0.4 \
  CONSTRAINED_K=40 CONSTRAINED_LOCAL=lbfgsb CONSTRAINED_STARTS=mix CONSTRAINED_M1=300 \
  python constrained.py 51 175 1 150 > constrained_threeline_resume.out 2>&1 || log "constrained resume FAILED"
log "constrained resume done"
