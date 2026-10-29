#!/usr/bin/env bash
# Day program of 2026-10-29, queued at 08:30, after campaign20 (race to 14500 nm). Waits for campaign20's last log
# line, not for "no python" (both scripts would otherwise start at the same moment).
# 1. Seeds of the 2020 deep design (AUDIT point 7): reduce, redeploy by needles at the seed TOT, judge.
# 2. Hot mirror N=40: trf locals (the 0.865 tie), wide starts and jumps, to test "only two designs" (2012).
cd "$(dirname "$0")" || exit 1
log() { echo "$(date '+%F %H:%M') $*" >> campaign.log; }
until grep -q "3line race to 2020 done" campaign.log; do sleep 60; done
while tasklist //FI "IMAGENAME eq python.exe" | grep -q python; do sleep 20; done
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1

log "seeds of the 2020 deep design (101 layers, 0.0128): reduction with beam 3 down to 20 layers, 90 min"
SEARCH_TARGET=threeline python seed.py reduce fig4_2020_designs.csv:1 deep2020 90 > seed_deep2020_reduce.out 2>&1 \
  || log "seed reduce FAILED"
log "seeds: redeployment by needles at the seed TOT, 7 seeds in parallel, 120 min"
for n in 80 70 60 50 40 30 20; do
  [ -f "seed_deep2020_N$n.csv" ] || continue
  SEARCH_TARGET=threeline GRAD_DEEP=1 GRAD_DTOT=100 GRAD_TAG="_seed_deep2020_N$n" GRAD_RESUME="seed_deep2020_N$n.csv" \
    python gradual.py 120 0 > gradual_seed_deep2020_N$n.out 2>&1 &
done
wait
SEARCH_TARGET=threeline python seed.py judge fig4_2020_designs.csv:1 deep2020 > seed_deep2020_judge.out 2>&1 \
  || log "seed judge FAILED"
log "seeds done"

log "hot mirror N=40, trf locals, mix starts, sigma 3/10/20/40 %, K 20, M0 700, M1 300, 4 runs, 90 min (theirs 0.865, 2 designs only)"
SEARCH_TARGET=hotmirror CONSTRAINED_STARTS=mix CONSTRAINED_SIGMAS=0.03,0.1,0.2,0.4 CONSTRAINED_K=20 \
  CONSTRAINED_M0=700 CONSTRAINED_M1=300 python constrained.py 40 226 4 90 > constrained_hotmirror_mix.out 2>&1 \
  || log "hot mirror mix FAILED"
log "day program done"
