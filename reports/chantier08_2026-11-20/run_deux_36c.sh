#!/usr/bin/env bash
# Chantier 8 (2026-11-20): the same 36c deep bench twice, seed 42, on a free machine, in series.
set -u
OUT=reports/chantier08_2026-11-20
HEAD=$(git rev-parse --short=8 HEAD)
for run in A B; do
    echo "START $run $(date +%T) python_before=$(ps -W | grep -ci python)"
    QT_QPA_PLATFORM=offscreen CERTUS_DESIGN_JSON=example/example_strat/JSON-strat-bandpass-3cav-deep.json \
        CERTUS_BENCH_TIMEOUT_S=21600 PYTHONIOENCODING=utf-8 \
        python scripts/bench_examples.py strat --auto-yes --out "$OUT/STRAT_bench_36c_run${run}_${HEAD}.txt" \
        > "$OUT/STRAT_bench_36c_run${run}_${HEAD}.raw.log" 2>&1
    echo "END $run exit=$? $(date +%T)"
done
