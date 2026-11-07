#!/usr/bin/env bash
# The charge at the top of the peak (TRACK_PEAK=top), 2026-11-03: the fixed detector stalled the deep design's charge from
# round 11 (threeline_track_height_trub101_localmax.out) because the Jacobian at 1/Re(sigma_p) was wrong by 18-66 %
# (stall_jacobian_probe.py). One change at a time: TRACK_PEAK=top with the old detector ("today_top") and with the fixed
# one ("localmax_top"), same 8 threads and 40 rounds as detector_redo_table1.sh; height mode only (the window, quad, is
# unaffected by the option).
set -u
cd "$(dirname "$0")"
log() { echo "$(date '+%Y-%m-%d %H:%M') detector_redo_top.sh: $*" >> campaign.log; }
export SEARCH_TARGET=threeline TRACK_DETECT=complex TRACK_ROUNDS=40 NUMBA_NUM_THREADS=8 TRACK_PEAK=top
for variant in today_top localmax_top; do
  if [ "$variant" = localmax_top ]; then export TRACK_STEPS=localmax TRACK_MULTISTART=dense; fi
  python threeline_track.py height fig4_2020_designs.csv 1 threeline_track_height_trub101_$variant.csv > threeline_track_height_trub101_$variant.out 2>&1
  python threeline_track.py height fig4_2020_classical_nolsub.csv 0 threeline_track_height_classical103_$variant.csv > threeline_track_height_classical103_$variant.out 2>&1
  log "$variant: deep $(tail -1 threeline_track_height_trub101_$variant.out | cut -c1-150) | classical $(tail -1 threeline_track_height_classical103_$variant.out | cut -c1-150)"
done
