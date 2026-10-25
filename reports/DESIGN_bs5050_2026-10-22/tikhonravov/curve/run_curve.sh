#!/bin/sh
# RMSE vs layer count on the problem of Tikhonravov et al. 1996 (n 1.45 / 2.35 constant, glass 1.52), no QWOT
# ceiling, DESIGN default setting of 2026-10-23. Resumable: an N with a row in curve.jsonl that did not
# time out is skipped. Runs from 2026-10-24 18:00 (N >= 24) wait up to 12 h; earlier ones up to 3 h. A run that
# starts between 03:00 and 19:59 uses 16 threads (owner, 2026-10-24: the whole machine from 03:00), else 8.
C=reports/DESIGN_bs5050_2026-10-22/tikhonravov/curve
for n in 10 14 18 22 26 30 34 $(seq 1 33); do
  if grep "\"label\": \"tcurve$n\"" $C/curve.jsonl 2>/dev/null | grep -q '"timeout": false'; then continue; fi
  h=$(date +%H); if [ "$h" -ge 3 ] && [ "$h" -lt 20 ]; then export NUMBA_NUM_THREADS=16; else export NUMBA_NUM_THREADS=8; fi
  python -u scripts/design_bench.py run --config $C/config_$n.json --label tcurve$n --max-s 43200 \
    --out $C/curve.jsonl --save-design $C/best_$n.json > $C/tcurve$n.log 2>&1
  echo "N=$n done $(date +%H:%M) threads $NUMBA_NUM_THREADS"
done
