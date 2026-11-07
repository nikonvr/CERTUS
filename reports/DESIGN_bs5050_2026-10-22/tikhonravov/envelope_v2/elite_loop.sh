#!/usr/bin/env bash
# OIC 2016 B1 (cissoid), 2026-11-01: slot screens from the record and the 3 best other designs of the elite pool
# (cissoid_slot_screen.py, ELITES:3), each gain through take_record.py, then BEAM and N3 on a new record; stops after
# two rounds without a record.
cd "$(dirname "$0")" || exit 1
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1 CISSOID_WORKERS=15 CISSOID_GRID=full \
  CISSOID_METALS=AN CISSOID_DIELECTRICS=all CISSOID_MAX_METALS=20 CISSOID_REMOVAL_SCREEN=6 CISSOID_K=12 CISSOID_SWAP_MAX=3
miss=0
for k in 1 2 3 4 5 6; do
  out=cissoid_slot_screen_e$k
  python -u cissoid_slot_screen.py $out.csv cissoid_record_best.csv "ELITES:3@$(( k == 1 ? 5 : 0 ))" > $out.out 2>&1
  if [ -f $out.csv ] && python take_record.py $out.csv "elite loop round $k" | grep -q TAKEN; then
    miss=0
    FLAIR_START=BEAM,N3 FLAIR_ITERS=0 FLAIR_DATA="D:/certus_hors_drive/cissoid_flair" \
      python -u flair_campaign.py cissoid_record_best.csv 1 > elite_loop_beam_$k.out 2>&1
  else
    miss=$((miss + 1))
    echo "$(date '+%Y-%m-%d %H:%M') elite loop round $k: no record ($(tail -n 1 $out.out))" >> campaign.log
    [ $miss -ge 2 ] && break
  fi
done
echo "elite loop done"
