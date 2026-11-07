#!/usr/bin/env bash
# 2026-10-31: alternate forced growth (20 trials) and combined swaps (2-4 among the top 12), each from the current best;
# usage: bash alternate.sh START.csv ROUNDS; the best so far is always cissoid_record_best.csv
cd "$(dirname "$0")" || exit 1
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1 CISSOID_WORKERS=15 CISSOID_K=12 CISSOID_METALS=AN \
  CISSOID_DIELECTRICS=all CISSOID_MAX_METALS=20 CISSOID_REMOVAL_SCREEN=6 CISSOID_GRID=log130c8 CISSOID_SWAP_MAX=3
cp "$1" cissoid_record_best.csv
for r in $(seq 1 "$2"); do
  rm -f alt_force.csv alt_swap.csv
  python cissoid_force_grow.py cissoid_record_best.csv alt_force.csv 20 > "alt_force_$r.out" 2>&1
  [ -f alt_force.csv ] && cp alt_force.csv cissoid_record_best.csv
  python cissoid_multiswap.py cissoid_record_best.csv alt_swap.csv 12 > "alt_swap_$r.out" 2>&1
  [ -f alt_swap.csv ] && cp alt_swap.csv cissoid_record_best.csv
  echo "$(date '+%F %H:%M') alternate round $r: best $(python -c "import csv;print(next(csv.DictReader(open('cissoid_record_best.csv',encoding='utf-8')))['mf_oracle'][:8])")" >> campaign.log
done
