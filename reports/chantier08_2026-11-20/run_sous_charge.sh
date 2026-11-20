#!/usr/bin/env bash
# Chantier 8 (2026-11-20): the same 36c deep bench under a deliberate CPU load (12 busy processes that stop themselves
# after 25 min), to test whether the load alone makes the run diverge from the free-machine runs A and B.
set -u
OUT=reports/chantier08_2026-11-20
HEAD=$(git rev-parse --short=8 HEAD)
for i in $(seq 1 12); do
    python -c "import time
t = time.time()
while time.time() - t < 1500:
    pass" &
done
sleep 5
echo "START C (load) $(date +%T) python_before=$(ps -W | grep -ci python)"
QT_QPA_PLATFORM=offscreen CERTUS_DESIGN_JSON=example/example_strat/JSON-strat-bandpass-3cav-deep.json \
    CERTUS_BENCH_TIMEOUT_S=21600 PYTHONIOENCODING=utf-8 \
    python scripts/bench_examples.py strat --auto-yes --out "$OUT/STRAT_bench_36c_runC_charge_${HEAD}.txt" \
    > "$OUT/STRAT_bench_36c_runC_charge_${HEAD}.raw.log" 2>&1
echo "END C exit=$? $(date +%T)"
kill $(jobs -p) 2>/dev/null
wait 2>/dev/null
echo "BURNERS_STOPPED $(date +%T) python_after=$(ps -W | grep -ci python)"
