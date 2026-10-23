#!/bin/sh
# DESIGN on example/example_design/JSON-design-example.json as it is (max_layers 34, max_total_qwot 30, 5 nm rule),
# default setting of 2026-10-23 (memetic, compliant champion, restarts), 8 threads.
export NUMBA_NUM_THREADS=8
R=reports/DESIGN_bs5050_2026-10-22/final_runs
python -u scripts/design_bench.py run --label example_asis --max-s 10800 --out $R/runs.jsonl \
  --save-design $R/best_example_asis.json > $R/example_asis.log 2>&1
