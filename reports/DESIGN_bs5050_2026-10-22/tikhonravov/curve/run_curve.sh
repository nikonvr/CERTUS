#!/bin/sh
# RMSE vs layer count on the problem of Tikhonravov et al. 1996 (n 1.45 / 2.35 constant, glass 1.52), no QWOT
# ceiling, DESIGN default setting of 2026-10-23, 8 threads. Resumable: an N already in curve.jsonl is skipped.
export NUMBA_NUM_THREADS=8
C=reports/DESIGN_bs5050_2026-10-22/tikhonravov/curve
for n in 10 14 18 22 26 30 34 12 16 20 24 28 32; do
  if grep -q "\"label\": \"tcurve$n\"" $C/curve.jsonl 2>/dev/null; then continue; fi
  python -u scripts/design_bench.py run --config $C/config_$n.json --label tcurve$n --max-s 10800 \
    --out $C/curve.jsonl --save-design $C/best_$n.json > $C/tcurve$n.log 2>&1
  echo "N=$n done $(date +%H:%M)"
done
