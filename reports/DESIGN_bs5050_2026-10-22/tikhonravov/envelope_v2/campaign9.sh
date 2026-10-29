#!/usr/bin/env bash
# 2026-10-28 (user request: finding the good basins at 80-90 layers on the three-line filter is essential), run right
# after the 50/50 gradual run, before the diag5050 tests (campaign8). Envelope search (fixed N, elites, needles, thick
# insertions) on N = 70..100, two arms, 180 min each:
#   A: started from the gradual-evolution designs only (gradual evolution finds the basin, fixed N exploits it);
#   B: control without gradual evolution, 60 random stacks at N = 75..95 and TOT 9000-12000 nm (Trubetskov's range).
cd "$(dirname "$0")" || exit 1
log() { echo "$(date '+%F %H:%M') $*" >> campaign.log; }
until grep -q "50/50 gradual done" campaign.log; do sleep 20; done
while tasklist //FI "IMAGENAME eq python.exe" | grep -q python; do sleep 20; done
log "3line arm A: envelope search N 70-100 from the gradual designs, 180 min max"
SEARCH_TARGET=threeline SEARCH_STARTS=none SEARCH_FOCUS=70-100 python search.py free 180 1 \
  gradual_classic.csv gradual_deep4.csv gradual_deep4_cont.csv > search_3line_armA.out 2>&1 || log "3line arm A FAILED"
log "3line arm B: envelope search N 70-100 from random stacks at TOT 9000-12000 nm, 180 min max"
SEARCH_TARGET=threeline SEARCH_RANDOM=75-95:9000-12000:12 SEARCH_FOCUS=70-100 python search.py free 180 1 \
  > search_3line_armB.out 2>&1 || log "3line arm B FAILED"
log "3line arms done"
