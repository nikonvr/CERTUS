#!/usr/bin/env bash
# 2026-10-30, owner: the four contest leaders used two metals, Ni stays: Au or Ag? Both pairs side by side (owner: "en //"),
# same settings and seed, random starts only, after mini2. MINUTES first argument (default 45).
cd "$(dirname "$0")" || exit 1
minutes=${1:-45}
export MINI_PARALLEL=1 CISSOID_WORKERS=4
for pair in UN AN; do
  bash mini.sh "duel_$pair" "$minutes" 9 CISSOID_METALS=$pair CISSOID_ISLANDS=3 CISSOID_POP=12 CISSOID_DIELECTRICS=all \
    CISSOID_MAX_METALS=20 CISSOID_DEEP_EVERY=1 CISSOID_DEEP_CYCLES=30 CISSOID_K=12 CISSOID_RANDOM=mixed \
    CISSOID_GRID=log130c8 CISSOID_REMOVAL_SCREEN=6 CISSOID_RUIN=0.5 CISSOID_OVERSHOOT=65 &
done
wait
