#!/bin/sh
# Best RMSE vs layer count: one memetic run per N (pop 20, 100 children, first layer random, total <= 30 QWOT).
# Resumable: an N already in sweep.jsonl is skipped. One log per N in logs/.
R=reports/DESIGN_bs5050_2026-10-22
mkdir -p $R/sweep/logs
for n in 10 15 20 25 30 35 12 18 22 28 32 34 11 13 14 16 17 19 21 23 24 26 27 29 31 33; do
  if grep -q "\"label\": \"sweep$n\"" $R/sweep/sweep.jsonl 2>/dev/null; then continue; fi
  python -u scripts/design_probe.py memetic --layers $n --pop 20 --rounds 100 --seed $n --label sweep$n \
    --out $R/sweep/sweep.jsonl --qwot-max 30 --save $R/sweep/best_$n.json > $R/sweep/logs/sweep$n.log 2>&1
  echo "N=$n done $(date +%H:%M)"
done
