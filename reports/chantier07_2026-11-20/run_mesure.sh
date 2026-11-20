#!/usr/bin/env bash
# Chantier 7 (2026-11-20): the local-search check on 6 fresh seeds against 2, graine 42, in series on a free machine.
# 1. 36c deep livre, 2 seeds (control: the code of now must give the 2026-11-20 benchmark, RESULT 0.032898)
# 2. 36c deep livre, 6 seeds
# 3. 35c deep, 6 seeds
# Run from the root of the worktree: bash reports/chantier07_2026-11-20/run_mesure.sh
set -u
OUT=reports/chantier07_2026-11-20
HEAD=$(git rev-parse --short=8 HEAD)
run() {
    local tag=$1 json=$2
    echo "START $tag $(date +%T)"
    QT_QPA_PLATFORM=offscreen CERTUS_DESIGN_JSON="$json" CERTUS_BENCH_TIMEOUT_S=21600 PYTHONIOENCODING=utf-8 \
        python scripts/bench_examples.py strat --auto-yes --out "$OUT/STRAT_bench_${tag}_${HEAD}.txt" \
        > "$OUT/STRAT_bench_${tag}_${HEAD}.raw.log" 2>&1
    echo "END $tag exit=$? $(date +%T)"
}
run 36c_deep_livre_2graines example/example_strat/JSON-strat-bandpass-3cav-deep.json
run 36c_deep_livre_6graines "$OUT/config_36c_deep_livre_6graines.json"
run 35c_deep_6graines "$OUT/config_35c_deep_6graines.json"
echo "MESURE_FINIE $(date +%T)"
