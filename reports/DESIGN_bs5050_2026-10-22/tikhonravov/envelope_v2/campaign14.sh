#!/usr/bin/env bash
# Cissoid OIC 2016 B1 rerun, after campaign8 ("night program done"): the 22:19 runs failed on a NaN in the polish.
cd "$(dirname "$0")" || exit 1
export OPENBLAS_NUM_THREADS=1
log() { echo "$(date '+%Y-%m-%d %H:%M') $1" >> campaign.log; }
until grep -q "night program done" campaign.log; do sleep 60; done
log "cissoid rerun (thickness bounds, metal <= 100 nm; non-finite guard): from the example design, 45 min"
python cissoid_opt.py 45 example > cissoid_opt_example.out 2>&1 || log "cissoid example FAILED"
log "cissoid rerun: from a single H layer, 45 min"
python cissoid_opt.py 45 H > cissoid_opt_H.out 2>&1 || log "cissoid H FAILED"
log "cissoid rerun done"
