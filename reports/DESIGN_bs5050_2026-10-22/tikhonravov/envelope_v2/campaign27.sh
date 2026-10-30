#!/usr/bin/env bash
# 2026-10-30, owner: "mettre le paquet pour trouver le minimum global a 50 couches", no time limit.
# Cissoid OIC 2016 B1 (single optic, no uniformity), memetic search under the contest rules (cissoid_memetic.py),
# one run at a time on 7 workers, population 40, 120 min each:
#   1. dielectrics F M H, at most 2 metal layers (owner's practice), seed 1
#   2. F M H, at most 6 metal layers (the contest table counts metal MATERIALS, 2 for the winner, not layers)
#   3. the six dielectrics, at most 6 metal layers
#   4. F M H, at most 2 metal layers, seed 2 (does a second seed find the same best?)
cd "$(dirname "$0")" || exit 1
log() { echo "$(date '+%F %H:%M') $*" >> campaign.log; }
until grep -q "cissoid grow done" campaign.log; do sleep 60; done
while tasklist //FI "IMAGENAME eq python.exe" | grep -q python; do sleep 20; done
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 CISSOID_WORKERS=7 CISSOID_POP=40
run() {  # tag dielectrics max_metals seed
  log "cissoid memetic $1 (dielectrics $2, metals <= $3, seed $4), 120 min"
  CISSOID_TAG=$1 CISSOID_DIELECTRICS=$2 CISSOID_MAX_METALS=$3 CISSOID_SEED=$4 python cissoid_memetic.py 120 \
    > "cissoid_memetic_$1.out" 2>&1 || log "cissoid memetic $1 FAILED"
  log "cissoid memetic $1 done: $(tail -n 1 "cissoid_memetic_$1.log")"
}
run fmh_m2_s1 FMH 2 1
run fmh_m6_s1 FMH 6 1
run all_m6_s1 all 6 1
run fmh_m2_s2 FMH 2 2
log "cissoid memetic campaign done"
