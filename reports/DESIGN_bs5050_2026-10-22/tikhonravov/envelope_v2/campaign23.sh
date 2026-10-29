#!/usr/bin/env bash
# Thin-layer cleaning in gradual evolution (2026-10-29 15:20, GRAD_CLEAN): the seed test showed needles inflating the
# designs (124-155 layers against 101 for Trubetskov 2020, layers of 0.5 nm). One change (cleaning), 7 trajectories:
# the N89 seed in deep 2 with thresholds 2/5/10 nm and deep 3 at 5 nm, the N79 seed at 5 nm, our own race starts at 5 nm.
cd "$(dirname "$0")" || exit 1
log() { echo "$(date '+%F %H:%M') $*" >> campaign.log; }
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 SEARCH_TARGET=threeline GRAD_DTOT=100
log "cleaning test (GRAD_CLEAN): seed N89 deep2 clean 2/5/10, deep3 clean 5; seed N79 deep2 clean 5; ours (12100, 11600 nm) deep2 clean 5; 150 min"
run() { GRAD_DEEP=$1 GRAD_CLEAN=$2 GRAD_RESUME=$3 GRAD_TAG=$4 python gradual.py 150 "$5" > "gradual_deep$1_clean$2$4.out" 2>&1 & }
run 2 2 seed_up14k_N90.csv _seed89 14200
run 2 5 seed_up14k_N90.csv _seed89 14200
run 2 10 seed_up14k_N90.csv _seed89 14200
run 3 5 seed_up14k_N90.csv _seed89 14200
run 2 5 seed_up14k_N80.csv _seed79 14200
run 2 5 gradual_classic.csv _own12100 14500
run 2 5 gradual_deep4_cont.csv _own11600 14500
wait
log "cleaning test done"
