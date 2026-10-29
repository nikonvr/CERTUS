#!/usr/bin/env bash
# Replaces the tail of campaign9 (2026-10-28, 17:15, user request "Fig. 5 with the new data"): once arm A ends, the
# Fig. 5 comparison with arm A up to 12000 nm, then arm B, then campaign8 (diag5050). The running arm A is kept.
cd "$(dirname "$0")" || exit 1
log() { echo "$(date '+%F %H:%M') $*" >> campaign.log; }
while tasklist //FI "IMAGENAME eq python.exe" | grep -q python; do sleep 20; done
log "three-line comparison with Trubetskov 2020 Fig. 5, arm A included, up to 12000 nm"
python compare3line.py 12000 > compare3line.out 2>&1 || log "compare3line FAILED"
log "3line arm B: envelope search N 70-100 from random stacks at TOT 9000-12000 nm, 180 min max"
SEARCH_TARGET=threeline SEARCH_RANDOM=75-95:9000-12000:12 SEARCH_FOCUS=70-100 python search.py free 180 1 \
  > search_3line_armB.out 2>&1 || log "3line arm B FAILED"
log "3line arms done"
bash campaign8.sh
