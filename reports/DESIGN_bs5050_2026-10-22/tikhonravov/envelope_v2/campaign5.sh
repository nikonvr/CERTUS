#!/usr/bin/env bash
# Replaces the tail of campaign4 (2026-10-28, 03:10, user request "more time"): once the deep search of campaign4 ends,
# it is continued from its last design for 300 more minutes up to TOT 13000 nm, then the rest of campaign4.
cd "$(dirname "$0")" || exit 1
log() { echo "$(date '+%F %H:%M') $*" >> campaign.log; }
while tasklist //FI "IMAGENAME eq python.exe" | grep -q python; do sleep 20; done
CURVES="curve_foc27-36_free_s2.csv curve_free_s1.csv curve_abl_t0k1_free_s1.csv curve_abl_t0k6_free_s1.csv curve_abl_t1k1_free_s1.csv curve_v3_free_s1.csv"

log "3line gradual deep search K=4 continued from gradual_deep4.csv, 300 min max"
GRAD_DEEP=4 GRAD_RESUME=gradual_deep4.csv python gradual.py 300 13000 > gradual_deep4_cont.out 2>&1 || log "gradual deep continuation FAILED"

log "robust AR catalogues N = 5..14"
for n in 5 6 7 8 9 10 11 12 13 14; do
  SEARCH_TARGET=ar CAT_N=$n CAT_PREFIX=ar$n CAT_TOT=2,14 python catalog.py build 4 8 > ar${n}_build.out 2>&1 || log "AR catalogue N=$n FAILED"
done
log "robust AR selection, polish and Monte Carlo"
SEARCH_TARGET=ar python ar_robust.py 5,6,7,8,9,10,11,12,13,14 10 10000 > ar_robust.out 2>&1 || log "robust AR FAILED"

log "50/50 check on 6401 points"
python check6401.py $CURVES > check6401.out 2>&1 || log "check6401 FAILED"
log "campaign done"
