#!/usr/bin/env bash
# 2026-10-31 (owner): start from the winner, change the target to the x2 grid, do the usual moves (swaps, needles,
# overshoot, migrations) for 45 min, and only at the end go back to the 301 points (the campaign's final polish)
cd "$(dirname "$0")" || exit 1
until grep -q "drop L alone:" campaign.log; do sleep 20; done
S=cissoid_record_best.csv; [ -f cissoid_record_exhaustive.csv ] && S=cissoid_record_exhaustive.csv
MINI_PARALLEL=1 CISSOID_WORKERS=15 bash mini.sh over2 45 33 CISSOID_METALS=AN CISSOID_DIELECTRICS=all \
  CISSOID_SEEDS=$S:0,cissoid_record_force2.csv:0,cissoid_record_0p01448.csv:0,cissoid_record_0p01493.csv:0 \
  CISSOID_ISLANDS=4 CISSOID_POP=12 CISSOID_MAX_METALS=20 CISSOID_DEEP_EVERY=1 CISSOID_DEEP_CYCLES=30 CISSOID_K=12 \
  CISSOID_RANDOM=mixed CISSOID_GRID=over2 CISSOID_REMOVAL_SCREEN=6 CISSOID_RUIN=0.5 CISSOID_OVERSHOOT=55,60 \
  CISSOID_SEED_SPREAD=1 CISSOID_MIGRATE=10 CISSOID_STALL=40 CISSOID_SWAP=1 CISSOID_SWAP_MAX=3
