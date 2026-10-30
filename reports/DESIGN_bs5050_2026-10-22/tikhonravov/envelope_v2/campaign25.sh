#!/usr/bin/env bash
# Night of 2026-10-29/30, after the night checks:
# 1. three-line filter, Trubetskov's evolution step with free-TOT refinements (GRAD_GROW=1 GRAD_FREE=1), one change
#    against campaign24 (imposed TOT): deep 1/2/3/4, and deep 1/2/4 with GRAD_CLEAN 2; 180 min, to 14500 nm;
# 2. cissoid OIC 2016 B1, the owner's strategy (dielectrics first, then at most 1-2 metal layers, then the cleaner),
#    gradual evolution from a single H layer, 180 min, 7 workers.
cd "$(dirname "$0")" || exit 1
log() { echo "$(date '+%F %H:%M') $*" >> campaign.log; }
until grep -q "night checks done" campaign.log; do sleep 60; done
while tasklist //FI "IMAGENAME eq python.exe" | grep -q python; do sleep 20; done
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
log "free-TOT grow test (GRAD_GROW=1 GRAD_FREE=1) from the bare substrate to 14500 nm, 180 min: deep 1/2/3/4, clean 2 with deep 1/2/4"
for k in 1 2 3 4; do
  SEARCH_TARGET=threeline GRAD_GROW=1 GRAD_FREE=1 GRAD_DEEP=$k python gradual.py 180 14500 > "gradual_growfree_deep$k.out" 2>&1 &
done
for k in 1 2 4; do
  SEARCH_TARGET=threeline GRAD_GROW=1 GRAD_FREE=1 GRAD_CLEAN=2 GRAD_DEEP=$k python gradual.py 180 14500 \
    > "gradual_growfree_deep${k}_clean2.out" 2>&1 &
done
wait
log "free-TOT grow test done"
log "cissoid B1, dielectrics first then <= 2 metal layers, gradual evolution from H, 180 min (theirs 0.0238 deep 2020, 0.0139 contest)"
CISSOID_WORKERS=7 CISSOID_DEEP=7 python cissoid_grow.py 180 H > cissoid_grow_H.out 2>&1 || log "cissoid grow FAILED"
log "cissoid grow done"
