#!/usr/bin/env bash
# Replaces campaign10 (2026-10-28, 17:20, user rule "use nearly all cores"): once arm A ends, the Fig. 5 comparison,
# a 2-minute check that SEARCH_WORKERS=7 gives the same search as serial (and how much faster), then arm B on
# 7 workers, then campaign8 (diag5050). The running arm A is kept.
cd "$(dirname "$0")" || exit 1
log() { echo "$(date '+%F %H:%M') $*" >> campaign.log; }
while tasklist //FI "IMAGENAME eq python.exe" | grep -q python; do sleep 20; done
log "three-line comparison with Trubetskov 2020 Fig. 5, arm A included, up to 12000 nm"
python compare3line.py 12000 > compare3line.out 2>&1 || log "compare3line FAILED"
log "search.py parallel check: serial vs 7 workers, 2 min each, seed 99"
for w in 1 7; do
  SEARCH_WORKERS=$w SEARCH_TARGET=threeline SEARCH_RANDOM=75-95:9000-12000:2 SEARCH_FOCUS=70-100 \
    python search.py free 2 99 > parallel_check_w$w.out 2>&1 || log "parallel check w=$w FAILED"
done
log "3line arm B: envelope search N 70-100 from random stacks at TOT 9000-12000 nm, 180 min max, 7 workers"
SEARCH_WORKERS=7 SEARCH_TARGET=threeline SEARCH_RANDOM=75-95:9000-12000:12 SEARCH_FOCUS=70-100 \
  python search.py free 180 1 > search_3line_armB.out 2>&1 || log "3line arm B FAILED"
log "3line arms done"
bash campaign8.sh
