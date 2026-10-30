#!/usr/bin/env bash
# 2026-10-30, replaces runs 2-4 of campaign27: run 1 (one population of 40) sat in one basin from generation 440
# (best = median = worst = 0.1009). Owner: "Oui relance" (islands and restarts, several hours).
# Cissoid OIC 2016 B1, cissoid_islands.py: 6 islands x 16, restarts on stall (60 island generations) or collapse,
# ring migration every 25, needle-removal cycles every 10; one run at a time on 7 workers:
#   1. dielectrics F M H, metals Ag Au Ni, at most 6 metal layers, 360 min
#   2. F M H, Ag Au Ni, at most 2 metal layers (the run-1 setting), seed 2, 240 min
cd "$(dirname "$0")" || exit 1
log() { echo "$(date '+%F %H:%M') $*" >> campaign.log; }
while tasklist //FI "IMAGENAME eq python.exe" | grep -q python; do sleep 20; done
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 CISSOID_WORKERS=7 CISSOID_ISLANDS=6 CISSOID_POP=16
run() {  # tag dielectrics max_metals seed minutes
  log "cissoid islands $1 (dielectrics $2, metals <= $3, seed $4), $5 min"
  CISSOID_TAG=$1 CISSOID_DIELECTRICS=$2 CISSOID_MAX_METALS=$3 CISSOID_SEED=$4 python cissoid_islands.py "$5" \
    > "cissoid_islands_$1.out" 2>&1 || log "cissoid islands $1 FAILED"
  log "cissoid islands $1 done: $(tail -n 1 "cissoid_islands_$1.log")"
}
run fmh_m6_s1 FMH 6 1 360
run fmh_m2_s2 FMH 2 2 240
log "cissoid islands campaign done"
