#!/usr/bin/env bash
# Campaign of 2026-10-27 night, one Python process at a time. Progress: campaign.log.
# Three-line filter (Trubetskov 2020 Fig. 5) from three kinds of starts, 100 min each, then a combined run from their
# fronts; then the robust AR (Tikhonravov 2012) and the 50/50 check on 6401 points.
cd "$(dirname "$0")" || exit 1
log() { echo "$(date '+%F %H:%M') $*" >> campaign.log; }
while tasklist //FI "IMAGENAME eq python.exe" | grep -q python; do sleep 20; done
CURVES="curve_foc27-36_free_s2.csv curve_free_s1.csv curve_abl_t0k1_free_s1.csv curve_abl_t0k6_free_s1.csv curve_abl_t1k1_free_s1.csv curve_v3_free_s1.csv"
export SEARCH_TARGET=threeline SEARCH_NMAX=90

log "3line A: random starts, focus N=45-85, 100 min"
SEARCH_FOCUS=45-85 SEARCH_STARTS=random python search.py free 100 1 > threeline_A.out 2>&1 || log "3line A FAILED"
log "3line B: bare substrate (one layer grown by the moves), 100 min"
SEARCH_STARTS=bare python search.py free 100 3 > threeline_B.out 2>&1 || log "3line B FAILED"
log "3line C: quarter-wave stacks with cavities, focus N=45-85, 100 min"
SEARCH_FOCUS=45-85 SEARCH_STARTS=qw python search.py free 100 4 > threeline_C.out 2>&1 || log "3line C FAILED"
log "3line D: combined from the fronts of A, B, C, focus N=45-85, 150 min"
F=""
for f in curve_3line_foc45-85_free_s1.csv front_3line_foc45-85_free_s1.csv curve_3line_bare_free_s3.csv \
         front_3line_bare_free_s3.csv curve_3line_qw_foc45-85_free_s4.csv front_3line_qw_foc45-85_free_s4.csv; do
  [ -f "$f" ] && F="$F $f"
done
SEARCH_FOCUS=45-85 SEARCH_STARTS=qw python search.py free 150 5 $F > threeline_D.out 2>&1 || log "3line D FAILED"
unset SEARCH_TARGET SEARCH_NMAX

log "robust AR catalogues N = 5..14"
for n in 5 6 7 8 9 10 11 12 13 14; do
  SEARCH_TARGET=ar CAT_N=$n CAT_PREFIX=ar$n CAT_TOT=2,14 python catalog.py build 4 8 > ar${n}_build.out 2>&1 || log "AR catalogue N=$n FAILED"
done
log "robust AR selection, polish and Monte Carlo"
SEARCH_TARGET=ar python ar_robust.py 5,6,7,8,9,10,11,12,13,14 10 10000 > ar_robust.out 2>&1 || log "robust AR FAILED"

log "50/50 check on 6401 points"
python check6401.py $CURVES > check6401.out 2>&1 || log "check6401 FAILED"
log "campaign done"
