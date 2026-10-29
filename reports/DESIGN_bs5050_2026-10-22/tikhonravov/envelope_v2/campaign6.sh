#!/usr/bin/env bash
# Replaces campaign5 (2026-10-28, 09:45): after its deep search, the comparison with Trubetskov 2020 Fig. 5 up to
# 11000 nm (compare3line.py), then the robust AR and the 50/50 check.
cd "$(dirname "$0")" || exit 1
log() { echo "$(date '+%F %H:%M') $*" >> campaign.log; }
while tasklist //FI "IMAGENAME eq python.exe" | grep -q python; do sleep 20; done
CURVES="curve_foc27-36_free_s2.csv curve_free_s1.csv curve_abl_t0k1_free_s1.csv curve_abl_t0k6_free_s1.csv curve_abl_t1k1_free_s1.csv curve_v3_free_s1.csv"

log "three-line comparison with Trubetskov 2020 Fig. 5 up to 11000 nm"
python compare3line.py 11000 > compare3line.out 2>&1 || log "compare3line FAILED"

log "robust AR catalogues N = 5..14"
for n in 5 6 7 8 9 10 11 12 13 14; do
  SEARCH_TARGET=ar CAT_N=$n CAT_PREFIX=ar$n CAT_TOT=2,14 python catalog.py build 4 8 > ar${n}_build.out 2>&1 || log "AR catalogue N=$n FAILED"
done
log "robust AR selection, polish and Monte Carlo"
SEARCH_TARGET=ar python ar_robust.py 5,6,7,8,9,10,11,12,13,14 10 10000 > ar_robust.out 2>&1 || log "robust AR FAILED"

log "50/50 check on 6401 points"
python check6401.py $CURVES > check6401.out 2>&1 || log "check6401 FAILED"
log "campaign done"
