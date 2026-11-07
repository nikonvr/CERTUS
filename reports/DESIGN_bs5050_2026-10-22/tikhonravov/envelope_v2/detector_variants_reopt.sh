#!/usr/bin/env bash
# Which charge to publish? (2026-11-03) One trajectory per variant cannot rank them (detector_redo_*.sh: 0.018-0.032 %
# resolved for the deep design). The re-optimization test of Sec. 7.2 (optimizer_test_trub101.py: six starts perturbed by
# 3 %, 40 bursts, 'nominal' and 'pole' arms) for the four variants: old or fixed detector (TRACK_STEPS/TRACK_MULTISTART),
# charge at 1/Re(sigma_p) or at the top of the peak (TRACK_PEAK=top). 6 workers of 1 Numba thread each, same for all.
set -u
cd "$(dirname "$0")"
log() { echo "$(date '+%Y-%m-%d %H:%M') detector_variants_reopt.sh: $*" >> campaign.log; }
export SEARCH_TARGET=threeline TRACK_DETECT=complex NUMBA_NUM_THREADS=1
for variant in today today_top localmax localmax_top; do
  (
    case $variant in *localmax*) export TRACK_STEPS=localmax TRACK_MULTISTART=dense ;; esac
    case $variant in *_top) export TRACK_PEAK=top ;; esac
    OPTTEST_OUT=optimizer_test_trub101_$variant.csv python optimizer_test_trub101.py 0.03 6 40 6 \
      > optimizer_test_trub101_$variant.out 2>&1
  )
  log "$variant done: $(grep -c pole optimizer_test_trub101_$variant.out) pole runs"
done
