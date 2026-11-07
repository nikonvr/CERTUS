#!/usr/bin/env bash
# Sec. 7.3 of the method paper (OE_resonances), redone without the substrate-side L layer (owner, 2026-11-02 21:40:
# "Relance-la"). The budget of the night's runs (1-2 Nov) was not recorded, so the protocol is fixed here: target $1
# (mshape, the default and the run of 21:40; highpass, the long-wave pass, run at 23:10), SEARCH_NO_LSUB=1, both arms from
# the same seed (the same starts), 60 minutes each, side by side with 4 Numba threads each. A: search on the grid, then
# the cure of the best design of each N (cure_archive.py, 15 rounds, 6 workers). B: the search with the poles charged
# after every move (SEARCH_POLES=3). Both fronts judged by semi_threshold.py (resolved MF on 0.001 nm, resonances from
# the complex plane).
# usage: bash sec73.sh [mshape|highpass]
set -u
cd "$(dirname "$0")"
T="${1:-mshape}"
log() { echo "$(date '+%Y-%m-%d %H:%M') sec73.sh $T: $*" >> campaign.log; }
export SEARCH_TARGET=$T SEARCH_NO_LSUB=1 TRACK_DETECT=complex NUMBA_NUM_THREADS=4
log "start: arms A (grid) and B (SEARCH_POLES=3), seed 9, 60 min each, side by side"
python search.py free 60 9 > nolsub_${T}_search_s9.out 2>&1 &
SEARCH_POLES=3 python search.py free 60 9 > poles3_nolsub_${T}_search_s9.out 2>&1 &
wait
log "searches done: A $(grep 'end after' nolsub_${T}_search_s9.out), B $(grep 'end after' poles3_nolsub_${T}_search_s9.out)"
mkdir -p _sec73
THRESH_SEED=9 python semi_threshold.py _sec73 > nolsub_${T}_threshold_s9.out 2>&1 &
SEARCH_POLES=3 THRESH_SEED=9 python semi_threshold.py _sec73 > poles3_nolsub_${T}_threshold_s9.out 2>&1 &
wait
log "fronts judged: nolsub_${T}_threshold_s9.csv, poles3_nolsub_${T}_threshold_s9.csv"
NUMBA_NUM_THREADS=1 CURE_SEED=9 python cure_archive.py 15 6 > nolsub_${T}_cure_archive_s9.out 2>&1
log "arm A cured: $(tail -1 nolsub_${T}_cure_archive_s9.out) (nolsub_${T}_cure_archive_s9.csv)"
