#!/usr/bin/env bash
# 2026-10-28 (user request "ok go"): gradual evolution with needles from the bare substrate on the 50/50 splitter,
# deep search K=4, TOT step 50 nm up to 4600 nm, 240 min max; starts once the validation is over.
cd "$(dirname "$0")" || exit 1
log() { echo "$(date '+%F %H:%M') $*" >> campaign.log; }
# the validation runs several python commands in turn: wait for its end marker, not for a moment without python
until grep -q "post done" campaign.log; do sleep 20; done
while tasklist //FI "IMAGENAME eq python.exe" | grep -q python; do sleep 20; done
log "50/50 gradual deep search K=4, DTOT 50 nm, TOT <= 4600 nm, 240 min max"
SEARCH_TARGET=bs5050 GRAD_DEEP=4 GRAD_DTOT=50 python gradual.py 240 4600 > gradual_bs5050_deep4.out 2>&1 || log "50/50 gradual FAILED"
log "50/50 gradual done"
