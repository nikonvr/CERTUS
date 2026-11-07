#!/usr/bin/env bash
# Sec. 7.3 redone with the corrected method (owner, 2026-11-03 03:50: publish TRACK_STEPS=localmax TRACK_MULTISTART=dense
# TRACK_PEAK=top). The searches on the grid (arm A) do not use the detector and stay; redone: arm B (the search with the
# poles charged, 60 min, the two targets side by side with 4 Numba threads each, as A and B were), the judging of the four
# fronts (semi_threshold.py) and the cure of the best design of each N of A (cure_archive.py, 15 rounds, 6 workers).
# The night's files (old detector) are kept with the suffix _2026-11-02_olddetector.
set -u
cd "$(dirname "$0")"
log() { echo "$(date '+%Y-%m-%d %H:%M') sec73_corrected.sh: $*" >> campaign.log; }
export SEARCH_NO_LSUB=1 TRACK_DETECT=complex TRACK_STEPS=localmax TRACK_MULTISTART=dense TRACK_PEAK=top
log "start: arm B of mshape and highpass, seed 9, 60 min, side by side"
for t in mshape highpass; do
  SEARCH_TARGET=$t SEARCH_POLES=3 NUMBA_NUM_THREADS=4 python search.py free 60 9 > poles3_nolsub_${t}_search_s9.out 2>&1 &
done
wait
log "searches done: mshape B $(grep 'end after' poles3_nolsub_mshape_search_s9.out), highpass B $(grep 'end after' poles3_nolsub_highpass_search_s9.out)"
mkdir -p _sec73
for t in mshape highpass; do
  SEARCH_TARGET=$t THRESH_SEED=9 NUMBA_NUM_THREADS=4 python semi_threshold.py _sec73 > nolsub_${t}_threshold_s9.out 2>&1 &
  SEARCH_TARGET=$t SEARCH_POLES=3 THRESH_SEED=9 NUMBA_NUM_THREADS=4 python semi_threshold.py _sec73 > poles3_nolsub_${t}_threshold_s9.out 2>&1 &
  wait
done
log "fronts judged"
for t in mshape highpass; do
  SEARCH_TARGET=$t NUMBA_NUM_THREADS=1 CURE_SEED=9 python cure_archive.py 15 6 > nolsub_${t}_cure_archive_s9.out 2>&1
  log "arm A of $t cured: $(tail -1 nolsub_${t}_cure_archive_s9.out)"
done
