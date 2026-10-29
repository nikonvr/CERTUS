#!/usr/bin/env bash
# Night program reordered at 2026-10-29 02:10, replacing campaign15 after its constrained_clean step.
# Reason: the ten 2012 designs of Fig. 3 reproduce Table 1 with our MF, so the 0.875 of constrained.py is a search
# failure; trf crawls from random starts and L-BFGS-B does far better (campaign.log). One step at a time, 7 processes.
cd "$(dirname "$0")" || exit 1
log() { echo "$(date '+%F %H:%M') $*" >> campaign.log; }
while tasklist //FI "IMAGENAME eq python.exe" | grep -q python; do sleep 20; done
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1

log "constrained three-line N=51, L-BFGS-B locals, H first, M0 700, M1 300, 4 runs, 75 min (theirs 0.464)"
SEARCH_TARGET=threeline CONSTRAINED_LOCAL=lbfgsb CONSTRAINED_FIRST=H CONSTRAINED_M0=700 CONSTRAINED_M1=300 \
  python constrained.py 51 175 4 75 > constrained_threeline_lbfgsb.out 2>&1 || log "constrained three-line lbfgsb FAILED"
log "constrained hot mirror N=40, L-BFGS-B locals, H first, M0 700, M1 300, 4 runs, 60 min (theirs 0.865)"
SEARCH_TARGET=hotmirror CONSTRAINED_LOCAL=lbfgsb CONSTRAINED_FIRST=H CONSTRAINED_M0=700 CONSTRAINED_M1=300 \
  python constrained.py 40 226 4 60 > constrained_hotmirror_lbfgsb.out 2>&1 || log "constrained hot mirror lbfgsb FAILED"

log "cissoid rerun (thickness bounds, metal <= 100 nm; non-finite guard): from the example design, 45 min"
python cissoid_opt.py 45 example > cissoid_opt_example.out 2>&1 || log "cissoid example FAILED"
log "cissoid rerun: from a single H layer, 45 min"
python cissoid_opt.py 45 H > cissoid_opt_H.out 2>&1 || log "cissoid H FAILED"

log "3line arm D: quarter-wave starts at imposed TOT 11000 nm, N 75-95, 90 min, 7 workers"
SEARCH_TARGET=threeline SEARCH_STARTS=qw SEARCH_QW=75-95:12 SEARCH_TOT=11000 SEARCH_FOCUS=75-95 SEARCH_WORKERS=7 \
  python search.py free 90 1 > search_3line_armD.out 2>&1 || log "3line arm D FAILED"

log "EF1-EF10 robustness analysis, sigma OT 1 and 2 nm, 1000 draws"
python ef2012.py analyse 1,2 1000 > ef2012_analyse.out 2>&1 || log "EF analyse FAILED"

log "diag5050 H2: re-polish of the gradual 50/50 designs"
SEARCH_TARGET=bs5050 python diag5050.py repolish > diag5050_repolish.out 2>&1 || log "diag5050 repolish FAILED"
log "diag5050 H3: gradual evolution resumed from the envelope N=37 design, 60 min max"
SEARCH_TARGET=bs5050 python diag5050.py seed > diag5050_seed.out 2>&1 || log "diag5050 seed FAILED"
SEARCH_TARGET=bs5050 GRAD_DEEP=4 GRAD_WORKERS=4 GRAD_DTOT=50 GRAD_RESUME=diag5050_seed37.csv python gradual.py 60 4600 \
  > gradual_bs5050_deep4_cont.out 2>&1 || log "diag5050 resume FAILED"
log "diag5050 H1: both methods on both axes"
python diag5050.py axes > diag5050_axes.out 2>&1 || log "diag5050 axes FAILED"
log "night program done"
