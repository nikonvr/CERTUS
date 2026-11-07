#!/usr/bin/env bash
# OIC 2016 B1 (cissoid), 2026-11-01: repeat the slot trade (cissoid_slot_trade.py: a needle paid by the cheapest
# freeings, then a swap descent) on the current record until a round gains nothing; each gain goes through
# take_record.py (oracle, N <= 50, d >= 3 nm). Then one beam (flair_campaign BEAM) on the last record.
cd "$(dirname "$0")" || exit 1
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1 CISSOID_WORKERS=15 CISSOID_GRID=full \
  CISSOID_METALS=AN CISSOID_DIELECTRICS=all CISSOID_MAX_METALS=20 CISSOID_REMOVAL_SCREEN=6 CISSOID_K=12 CISSOID_SWAP_MAX=3
for k in 1 2 3 4 5 6 7 8 9 10; do
  out=cissoid_slot_trade_${SLOT_TAG:-}$k
  python -u cissoid_slot_trade.py cissoid_record_best.csv $out.csv > $out.out 2>&1
  if grep -q "^GAIN" $out.out; then
    python take_record.py $out.csv "slot loop round $k"
  else
    echo "$(date '+%Y-%m-%d %H:%M') slot loop round $k: no gain ($(tail -n 1 $out.out))" >> campaign.log
    break
  fi
done
FLAIR_START=BEAM,N3 FLAIR_ITERS=0 FLAIR_DATA="D:/certus_hors_drive/cissoid_flair" \
  python -u flair_campaign.py cissoid_record_best.csv 1 > slot_loop_beam.out 2>&1
echo "slot loop done"
