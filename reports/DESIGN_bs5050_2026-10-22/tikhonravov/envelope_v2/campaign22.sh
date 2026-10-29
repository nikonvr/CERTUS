#!/usr/bin/env bash
# Seeds of the 2020 deep design, redone (2026-10-29 12:05): campaign21 redeployed every seed at its own (reduced) TOT,
# so none could return to 14171 nm. Here the seeds N60-N90 grow back to TOT 14200 by gradual evolution.
# 7 trajectories: the 4 seeds classical (new layer on the air side), N70-N90 also deep (DEEP 2, both sides).
cd "$(dirname "$0")" || exit 1
log() { echo "$(date '+%F %H:%M') $*" >> campaign.log; }
until grep -q "day program done" campaign.log; do sleep 60; done
while tasklist //FI "IMAGENAME eq python.exe" | grep -q python; do sleep 20; done
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 SEARCH_TARGET=threeline GRAD_DTOT=100

log "seeds up to 14200 nm: seeds N60-N90 of the 2020 deep design, gradual evolution 150 min, 4 classical + 3 deep"
for n in 60 70 80 90; do
  cp "seed_deep2020_N$n.csv" "seed_up14k_N$n.csv"
  GRAD_DEEP=1 GRAD_TAG="_seed_up14k_N$n" GRAD_RESUME="seed_up14k_N$n.csv" \
    python gradual.py 150 14200 > gradual_seed_up14k_N$n.out 2>&1 &
done
for n in 70 80 90; do
  GRAD_DEEP=2 GRAD_TAG="_seed_up14k_N$n" GRAD_RESUME="seed_up14k_N$n.csv" \
    python gradual.py 150 14200 > gradual_seed_up14k_deep_N$n.out 2>&1 &
done
wait
python seed.py judge fig4_2020_designs.csv:1 up14k > seed_up14k_judge.out 2>&1 || log "seed up14k judge FAILED"
log "seeds up to 14200 nm done"
