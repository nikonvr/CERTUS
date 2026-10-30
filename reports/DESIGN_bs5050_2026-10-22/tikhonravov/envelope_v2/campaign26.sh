#!/usr/bin/env bash
# Morning of 2026-10-30: finish the cleaning of the cissoid designs to <= 50 layers of >= 3 nm (cissoid_clean50.py).
cd "$(dirname "$0")" || exit 1
log() { echo "$(date '+%F %H:%M') $*" >> campaign.log; }
until grep -q "cissoid grow done" campaign.log; do sleep 60; done
while tasklist //FI "IMAGENAME eq python.exe" | grep -q python; do sleep 20; done
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
log "cissoid clean to <= 50 layers, unfinished rows of cissoid_grow_H.csv, 75 min"
CISSOID_WORKERS=7 python cissoid_clean50.py 75 cissoid_grow_H.csv > cissoid_clean50_H.out 2>&1 || log "cissoid clean50 FAILED"
log "cissoid clean50 done"
