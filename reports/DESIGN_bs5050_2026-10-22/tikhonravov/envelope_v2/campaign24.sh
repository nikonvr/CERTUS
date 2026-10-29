#!/usr/bin/env bash
# Trubetskov 2020's evolution step (GRAD_GROW, 2026-10-29 18:50): one layer thickened to the next minimum of the
# one-parameter MF (AO 59 A75, Sec. 2), from the bare substrate with no starting design, as in that paper (Sec. 4A).
# One change against our step (stretch / outer layer): deep 1, 2, 4 without cleaning; the same with GRAD_CLEAN 2; deep 3.
cd "$(dirname "$0")" || exit 1
log() { echo "$(date '+%F %H:%M') $*" >> campaign.log; }
until grep -q "cleaning test done" campaign.log; do sleep 60; done
while tasklist //FI "IMAGENAME eq python.exe" | grep -q python; do sleep 20; done
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 SEARCH_TARGET=threeline GRAD_GROW=1
log "grow test (GRAD_GROW, their evolution step) from the bare substrate to 14500 nm, 240 min: deep 1/2/4, clean 0/2, deep 3"
for k in 1 2 4; do
  GRAD_DEEP=$k GRAD_CLEAN=0 python gradual.py 240 14500 > "gradual_grow_deep$k.out" 2>&1 &
  GRAD_DEEP=$k GRAD_CLEAN=2 python gradual.py 240 14500 > "gradual_grow_deep${k}_clean2.out" 2>&1 &
done
GRAD_DEEP=3 GRAD_CLEAN=0 python gradual.py 240 14500 > gradual_grow_deep3.out 2>&1 &
wait
log "grow test done"
