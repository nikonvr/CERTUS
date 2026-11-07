#!/usr/bin/env bash
# OIC 2016 B1 (cissoid), 2026-11-01 afternoon: repeat cissoid_xmoves.py (block crossovers with the elite pool, which
# grows each round, and interference-order hops) on the record; each gain through take_record.py; after a round
# without a record, one beam (BEAM, N3) on the record, then one more round; stops after two misses in a row.
cd "$(dirname "$0")" || exit 1
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1 CISSOID_WORKERS=15 CISSOID_GRID=full \
  CISSOID_METALS=AN CISSOID_DIELECTRICS=all CISSOID_MAX_METALS=20 CISSOID_REMOVAL_SCREEN=6 CISSOID_K=12 CISSOID_SWAP_MAX=3
miss=0
for k in 2 3 4 5 6 7 8 9 10 11 12; do
  out=cissoid_xmoves_$k
  python -u cissoid_xmoves.py $out.csv > $out.out 2>&1
  if [ -f $out.csv ] && python take_record.py $out.csv "xmoves round $k" | grep -q TAKEN; then
    miss=0
  else
    miss=$((miss + 1))
    echo "$(date '+%Y-%m-%d %H:%M') xmoves round $k: no record ($(tail -n 1 $out.out))" >> campaign.log
    [ $miss -ge 2 ] && break
    FLAIR_START=BEAM,N3 FLAIR_ITERS=0 FLAIR_DATA="D:/certus_hors_drive/cissoid_flair" \
      python -u flair_campaign.py cissoid_record_best.csv 1 > xloop_beam_$k.out 2>&1
  fi
done
echo "xloop done"
