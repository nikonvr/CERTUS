#!/usr/bin/env bash
# 2026-10-31 (owner: can L or B go?): after after_multi4.sh, drop L alone, then B alone, from the same start
cd "$(dirname "$0")" || exit 1
until grep -q "after_multi4:" campaign.log; do sleep 20; done
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1 CISSOID_WORKERS=15
S=cissoid_record_best.csv; [ -f cissoid_record_exhaustive.csv ] && S=cissoid_record_exhaustive.csv
python cissoid_reduce.py "$S" cissoid_reduce_noL.csv L FBMTH > cissoid_reduce_noL.out 2>&1
python cissoid_reduce.py "$S" cissoid_reduce_noB.csv B FLMTH > cissoid_reduce_noB.out 2>&1
echo "$(date '+%F %H:%M') drop L alone: $(grep '^step' cissoid_reduce_noL.out | tail -1); drop B alone: $(grep '^step' cissoid_reduce_noB.out | tail -1)" >> campaign.log
