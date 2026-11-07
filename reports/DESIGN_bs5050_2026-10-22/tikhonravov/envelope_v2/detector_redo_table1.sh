#!/usr/bin/env bash
# Table 1 of the method paper redone with the fixed detector (owner, 2026-11-03 03:00: "Oui, refais-les"). The runs of
# 2026-11-01 no longer reproduce bit for bit (other numeric environment: rows 1+ differ from 1e-6 nm on), so each row is
# run twice today, same environment, 8 Numba threads: "today" = the old detector (defaults), "localmax" = the fixed one
# (TRACK_STEPS=localmax TRACK_MULTISTART=dense). Rows: the deep design charged (height) and with a window (quad), the
# classical N103 charged (height), 40 rounds each as before.
set -u
cd "$(dirname "$0")"
log() { echo "$(date '+%Y-%m-%d %H:%M') detector_redo_table1.sh: $*" >> campaign.log; }
export SEARCH_TARGET=threeline TRACK_DETECT=complex TRACK_ROUNDS=40 NUMBA_NUM_THREADS=8
for variant in today localmax; do
  if [ "$variant" = localmax ]; then export TRACK_STEPS=localmax TRACK_MULTISTART=dense; fi
  python threeline_track.py height fig4_2020_designs.csv 1 threeline_track_height_trub101_$variant.csv > threeline_track_height_trub101_$variant.out 2>&1
  python threeline_track.py quad fig4_2020_designs.csv 1 threeline_track_quad_trub101_$variant.csv > threeline_track_quad_trub101_$variant.out 2>&1
  python threeline_track.py height fig4_2020_classical_nolsub.csv 0 threeline_track_height_classical103_$variant.csv > threeline_track_height_classical103_$variant.out 2>&1
  log "$variant: deep height $(tail -1 threeline_track_height_trub101_$variant.out | cut -c1-150) | quad $(tail -1 threeline_track_quad_trub101_$variant.out | cut -c1-150) | classical $(tail -1 threeline_track_height_classical103_$variant.out | cut -c1-150)"
done
