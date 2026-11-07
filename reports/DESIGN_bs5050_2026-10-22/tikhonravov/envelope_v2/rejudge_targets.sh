#!/usr/bin/env bash
# The designs of Secs. 3 and 5 of the method paper judged again with the corrected detection (2026-11-03, owner: the
# corrected method everywhere): semi_threshold.py on the searches of seeds 5, 6 (three targets) and 7, 8 (half circle,
# n_H = 2.1, now also detected with n_H = 2.1). The MFs do not depend on the detector, only the columns poles/highest.
# Old files kept with the suffix _2026-11-02_olddetector.
set -u
cd "$(dirname "$0")"
S=_2026-11-02_olddetector
log() { echo "$(date '+%Y-%m-%d %H:%M') rejudge_targets.sh: $*" >> campaign.log; }
export SEARCH_NO_LSUB=1 TRACK_DETECT=complex TRACK_STEPS=localmax TRACK_MULTISTART=dense TRACK_PEAK=top NUMBA_NUM_THREADS=8
mkdir -p _sec73
for tt in semicircle:semi mshape:mshape highpass:highpass; do
  t=${tt%%:*}; tag=${tt##*:}
  for s in 5 6; do
    for f in nolsub_${tag}_threshold_s$s.csv nolsub_${tag}_threshold_s$s.out; do [ -f "$f" ] && cp -n "$f" "${f%.*}$S.${f##*.}"; done
    SEARCH_TARGET=$t THRESH_SEED=$s python semi_threshold.py _sec73 > nolsub_${tag}_threshold_s$s.out 2>&1
  done
done
for s in 7 8; do
  for f in nolsub_semi_threshold_s$s.csv nolsub_nh21_threshold_s$s.out; do [ -f "$f" ] && cp -n "$f" "${f%.*}$S.${f##*.}"; done
  SEARCH_TARGET=semicircle SEARCH_NH=2.1 THRESH_SEED=$s python semi_threshold.py _sec73 > nolsub_nh21_threshold_s$s.out 2>&1
done
log "done"
