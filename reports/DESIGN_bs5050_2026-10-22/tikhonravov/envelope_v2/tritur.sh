#!/usr/bin/env bash
# 2026-10-30, owner: both the six-dielectric record and its F H M reduction "méritent d'être triturés". Two runs side by
# side after the duel, each design with partners on its own islands. MINUTES first argument (default 45).
cd "$(dirname "$0")" || exit 1
minutes=${1:-45}
until grep -q "mini duel_UN done\|mini duel_UN FAILED" campaign.log && grep -q "mini duel_AN done\|mini duel_AN FAILED" campaign.log; do sleep 10; done
export MINI_PARALLEL=1 CISSOID_WORKERS=4
common="CISSOID_ISLANDS=4 CISSOID_POP=12 CISSOID_MAX_METALS=20 CISSOID_DEEP_EVERY=1 CISSOID_DEEP_CYCLES=30 CISSOID_K=12 CISSOID_RANDOM=mixed CISSOID_GRID=log130c8 CISSOID_REMOVAL_SCREEN=6 CISSOID_RUIN=0.5 CISSOID_OVERSHOOT=55,60 CISSOID_SEED_SPREAD=1 CISSOID_MIGRATE=10 CISSOID_STALL=40"
# shellcheck disable=SC2086
bash mini.sh tri_6D "$minutes" 10 $common CISSOID_DIELECTRICS=all CISSOID_SEEDS=cissoid_islands_mini2.csv:0,cissoid_islands_duel_AN.csv:0,cissoid_islands_mini1.csv:1,cissoid_islands_m12_s3.csv:0 &
# shellcheck disable=SC2086
bash mini.sh tri_FHM "$minutes" 11 $common CISSOID_DIELECTRICS=FHM CISSOID_SEEDS=cissoid_three_diel.csv:0,cissoid_islands_m12_s3.csv:0,cissoid_islands_m12_s3.csv:2,cissoid_islands_m12_s3.csv:3 &
wait
