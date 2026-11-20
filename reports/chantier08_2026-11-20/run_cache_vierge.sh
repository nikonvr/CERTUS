#!/usr/bin/env bash
# Chantier 8 (2026-11-20): the same 36c deep bench on a VIRGIN Numba cache (a new NUMBA_CACHE_DIR): the kernels are
# compiled inside the bench, as they were in the morning run of chantier 7 (key changed by a059cf47).
set -u
OUT=reports/chantier08_2026-11-20
HEAD=$(git rev-parse --short=8 HEAD)
CACHE="$TEMP/certus_numba_vierge_ch8_$(date +%H%M%S)"
mkdir -p "$CACHE"
echo "START D (virgin cache $CACHE) $(date +%T) python_before=$(ps -W | grep -ci python)"
NUMBA_CACHE_DIR="$CACHE" QT_QPA_PLATFORM=offscreen CERTUS_DESIGN_JSON=example/example_strat/JSON-strat-bandpass-3cav-deep.json \
    CERTUS_BENCH_TIMEOUT_S=21600 PYTHONIOENCODING=utf-8 \
    python scripts/bench_examples.py strat --auto-yes --out "$OUT/STRAT_bench_36c_runD_cache_vierge_${HEAD}.txt" \
    > "$OUT/STRAT_bench_36c_runD_cache_vierge_${HEAD}.raw.log" 2>&1
echo "END D exit=$? $(date +%T)"
