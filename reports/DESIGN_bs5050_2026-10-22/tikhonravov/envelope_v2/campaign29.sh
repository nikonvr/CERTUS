#!/usr/bin/env bash
# 2026-10-30, replaces campaign28 (stopped after 35 min, best 0.08521 with 7 metal layers, oracle). Owner: full autonomy.
# Facts behind the settings (campaign.log): numba threads per worker 1 instead of 8 gives 1.5x the generations; the
# contest caps layers (50), not metal layers, and the record jumped at needle-removal cycles with 7-8 metal layers;
# 70 % of MF^2 sits within 5 nm of the three corners (450, 550, 650 nm).
# cissoid_islands.py: 6 islands x 16, dielectrics F M H, metals Ag Au Ni, at most 12 metal layers, deep rounds every
# 5 island generations (up to 8 cycles), island 0 seeded with the campaign28 record; 480 min.
cd "$(dirname "$0")" || exit 1
log() { echo "$(date '+%F %H:%M') $*" >> campaign.log; }
while tasklist //FI "IMAGENAME eq python.exe" | grep -q python; do sleep 20; done
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1 CISSOID_WORKERS=7 CISSOID_ISLANDS=6 CISSOID_POP=16
export CISSOID_DEEP_EVERY=5 CISSOID_DEEP_CYCLES=8 CISSOID_MAX_METALS=12 CISSOID_SEEDS=cissoid_islands_fmh_m6_s1.csv:0
log "cissoid islands m12_s3 (FMH, metals <= 12, deep every 5 x 8, seeded with the 0.08521 record), 480 min"
CISSOID_TAG=m12_s3 CISSOID_SEED=3 python cissoid_islands.py 480 > cissoid_islands_m12_s3.out 2>&1 \
  || log "cissoid islands m12_s3 FAILED"
log "cissoid islands m12_s3 done: $(tail -n 1 cissoid_islands_m12_s3.log)"
