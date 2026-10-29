#!/usr/bin/env bash
# 2026-10-28 19:00 (user: "ok continue"), after the OpenBLAS benchmark. 7 workers, one BLAS thread each.
#   C: three-line, every polish at imposed TOT = 11000 nm (Trubetskov's drop: 0.058 % there; his 14000 nm designs have
#      ~138 nm of optical thickness per layer, i.e. ~80 layers at 11000 nm), N = 75..95, started from the 70 designs of
#      starts_tot11000.csv (TOT 10300-11900 nm, scaled to 11000), 120 min;
#   B: control without gradual evolution, random stacks N = 75..95 at TOT 9000-12000 nm, TOT free, 120 min;
#   then campaign8 (diag5050).
cd "$(dirname "$0")" || exit 1
log() { echo "$(date '+%F %H:%M') $*" >> campaign.log; }
while tasklist //FI "IMAGENAME eq python.exe" | grep -q python; do sleep 20; done
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 SEARCH_WORKERS=7 SEARCH_TARGET=threeline
log "3line arm C: fixed-N search at imposed TOT 11000 nm, N 75-95, from starts_tot11000.csv, 120 min, 7 workers"
SEARCH_TOT=11000 SEARCH_STARTS=none SEARCH_FOCUS=75-95 python search.py free 120 1 starts_tot11000.csv \
  > search_3line_armC.out 2>&1 || log "3line arm C FAILED"
log "3line arm B: envelope search N 70-100 from random stacks at TOT 9000-12000 nm, 120 min, 7 workers"
SEARCH_RANDOM=75-95:9000-12000:12 SEARCH_FOCUS=70-100 python search.py free 120 1 \
  > search_3line_armB.out 2>&1 || log "3line arm B FAILED"
log "3line arms done"
unset SEARCH_WORKERS SEARCH_TARGET
bash campaign8.sh
