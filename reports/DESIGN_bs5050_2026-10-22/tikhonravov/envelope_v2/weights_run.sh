#!/usr/bin/env bash
# Weight variants of 2026-10-31 in parallel, 3 workers each: phase A (4 rounds, walk, weighted) then phase B (4 rounds,
# normal, keep-best), all from the same start; usage: bash weights_run.sh START.csv
cd "$(dirname "$0")" || exit 1
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1 CISSOID_WORKERS=3 CISSOID_K=12 CISSOID_METALS=AN \
  CISSOID_DIELECTRICS=all CISSOID_MAX_METALS=20 CISSOID_REMOVAL_SCREEN=6 CISSOID_GRID=log130c8 CISSOID_OVERSHOOT=55,60
run() {  # tag weight
  CISSOID_WEIGHT="$2" WEIGHTED_WALK=1 python cissoid_weighted.py "$START" "w_$1_A.csv" 4 "$1_A" > "w_$1.out" 2>&1 &&
    python cissoid_weighted.py "w_$1_A.csv" "w_$1_B.csv" 4 "$1_B" >> "w_$1.out" 2>&1
}
START=$1
run ctrl "" & run x3 "495-505:3,645-655:3" & run x30 "495-505:30,645-655:30" & run z500 "495-505:30" & run z650 "645-655:30" &
wait
