#!/usr/bin/env bash
# Night program of 2026-10-28 → 29 (user: beat Trubetskov on every problem; programme in PROGRAMME_NUIT_2026-10-28.md).
# Called by campaign13 once the 7 three-line trajectories end; one step at a time, each on 7 processes with one BLAS
# thread. Order: cissoid (new, exact target), the two constrained problems of 2012, the three-line trajectories
# continued, quarter-wave starts at 11000 nm, EF1-EF10 robustness, 50/50 diagnostics.
cd "$(dirname "$0")" || exit 1
log() { echo "$(date '+%F %H:%M') $*" >> campaign.log; }
until grep -q "3line beam done" campaign.log; do sleep 20; done
while tasklist //FI "IMAGENAME eq python.exe" | grep -q python; do sleep 20; done
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1

log "cissoid OIC 2016 B1 (exact target): needles over 9 materials then cleaner, from the example design, 45 min"
python cissoid_opt.py 45 example > cissoid_opt_example.out 2>&1 || log "cissoid example FAILED"
log "cissoid OIC 2016 B1: from a single H layer, 45 min"
python cissoid_opt.py 45 H > cissoid_opt_H.out 2>&1 || log "cissoid H FAILED"

log "constrained three-line N=51, OT 100-350 nm (theirs 0.464-0.599), 90 min"
SEARCH_TARGET=threeline python constrained.py 51 175 6 90 > constrained_threeline.out 2>&1 || log "constrained three-line FAILED"
log "constrained hot mirror N=40, OT 100-350 nm (theirs 0.865 / 0.913), 90 min"
SEARCH_TARGET=hotmirror python constrained.py 40 226 6 90 > constrained_hotmirror.out 2>&1 || log "constrained hot mirror FAILED"

log "3line beam continued: the 7 trajectories resumed from their partial csv, up to 11500 nm, 120 min max"
i=0
for cfg in "1 70 classic" "1 130 classic" "2 100 deep2" "2 60 deep2" "3 80 deep3" "3 120 deep3" "2 150 deep2"; do
  set -- $cfg; i=$((i + 1))
  SEARCH_TARGET=threeline GRAD_DEEP=$1 GRAD_DTOT=$2 GRAD_TAG="_beam$i" GRAD_RESUME="gradual_$3_beam${i}_partial.csv" \
    python gradual.py 120 11500 > gradual_beam${i}_cont.out 2>&1 &
done
wait
log "3line beam continuation done"

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
