#!/usr/bin/env bash
# Campaign of 2026-10-27 evening, one Python process at a time. Progress: campaign.log.
# 1 three-line filter (Trubetskov 2020 Fig. 5), 3 h; 2 EF1-EF10 (Amotchkina 2012); 3 robust AR (Tikhonravov 2012);
# 4 50/50 check on 6401 points; 5 three-line filter again, 3 h, from the front of step 1.
cd "$(dirname "$0")" || exit 1
log() { echo "$(date '+%F %H:%M') $*" >> campaign.log; }
while tasklist //FI "IMAGENAME eq python.exe" | grep -q python; do sleep 20; done
CURVES="curve_foc27-36_free_s2.csv curve_free_s1.csv curve_abl_t0k1_free_s1.csv curve_abl_t0k6_free_s1.csv curve_abl_t1k1_free_s1.csv curve_v3_free_s1.csv"

log "step 1: three-line search, focus N=45-85, 240 min, seed 1"
SEARCH_TARGET=threeline SEARCH_FOCUS=45-85 SEARCH_NMAX=90 python search.py free 240 1 > threeline_run.out 2>&1 || log "step 1 FAILED"

log "step 2: EF1-EF10 check"
python ef2012.py check > ef2012_check.out 2>&1 || log "step 2 check FAILED"
if grep -q " OK" ef2012_flip.txt 2>/dev/null; then
  F=""; grep -q "^flip" ef2012_flip.txt && F="flip"
  log "step 2: EF analyse (order: ${F:-noflip})"
  python ef2012.py analyse 0.5,1.0 1000 $F > ef2012_analyse.out 2>&1 || log "step 2 analyse FAILED"
  python ef2012.py polish EF7 1.0 1000 $F > ef2012_polish_ef7.out 2>&1 || log "step 2 polish EF7 FAILED"
  python ef2012.py polish EF10 1.0 1000 $F > ef2012_polish_ef10.out 2>&1 || log "step 2 polish EF10 FAILED"
else
  log "step 2: EF reproduction does not match Table 3, EF analysis skipped"
fi

log "step 3: robust AR catalogues N = 5..14"
for n in 5 6 7 8 9 10 11 12 13 14; do
  SEARCH_TARGET=ar CAT_N=$n CAT_PREFIX=ar$n CAT_TOT=2,14 python catalog.py build 4 8 > ar${n}_build.out 2>&1 || log "step 3 catalogue N=$n FAILED"
done
log "step 3: robust AR selection, polish and Monte Carlo"
SEARCH_TARGET=ar python ar_robust.py 5,6,7,8,9,10,11,12,13,14 10 10000 > ar_robust.out 2>&1 || log "step 3 FAILED"

log "step 4: 50/50 check on 6401 points"
python check6401.py $CURVES > check6401.out 2>&1 || log "step 4 FAILED"

log "step 5: three-line search, 180 min, seed 2, from step 1"
SEARCH_TARGET=threeline SEARCH_FOCUS=45-85 SEARCH_NMAX=90 python search.py free 180 2 curve_3line_foc45-85_free_s1.csv front_3line_foc45-85_free_s1.csv > threeline_run2.out 2>&1 || log "step 5 FAILED"
log "campaign done"
