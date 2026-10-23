#!/bin/sh
# DESIGN in the window, record settings, one run per start layer count N (10..35). Resumable.
R=reports/DESIGN_bs5050_2026-10-22
W=$R/window_sweep
for n in 10 14 18 22 26 30 32 34 35 12 16 20 24 28 33 31 29 27 25 23 21 19 17 15 13 11; do
  if grep -q "\"label\": \"wsweep$n\"" $W/window_sweep.jsonl 2>/dev/null; then continue; fi
  python -u scripts/design_bench.py run --config $W/config_$n.json --kw memetic_children=1000 \
    --kw memetic_population=30 --kw memetic_qwot_max=30 --set _pareto_champion_respects_5nm=true \
    --label wsweep$n --out $W/window_sweep.jsonl --save-design $W/best_$n.json > $W/wsweep$n.log 2>&1
  echo "N=$n done $(date +%H:%M)"
done
