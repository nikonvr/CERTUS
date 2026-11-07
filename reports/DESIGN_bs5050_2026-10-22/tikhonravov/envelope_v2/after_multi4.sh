#!/usr/bin/env bash
# 2026-10-31: after mini multi4, take the best of its final design and the 0.01375 record, then exhaustive pairs and
# neighbour inversions, then the reduction to the quintet (L, B, T -> F, M, H)
cd "$(dirname "$0")" || exit 1
until grep -q "mini multi4 done" campaign.log; do sleep 20; done
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1 CISSOID_WORKERS=15 CISSOID_K=12 CISSOID_METALS=AN \
  CISSOID_DIELECTRICS=all CISSOID_MAX_METALS=20 CISSOID_GRID=log130c8
python - <<'PY'
import csv
a = sorted(csv.DictReader(open("cissoid_islands_multi4.csv", encoding="utf-8")), key=lambda r: float(r["mf_oracle"] or 9))[0]
b = next(csv.DictReader(open("cissoid_record_0p01375.csv", encoding="utf-8")))
r = a if float(a["mf_oracle"]) < float(b["mf_oracle"]) else b
w = csv.DictWriter(open("cissoid_record_best.csv", "w", newline="", encoding="utf-8"), fieldnames=list(r))
w.writeheader(); w.writerow(r)
print("start", r["mf_oracle"])
PY
python cissoid_exhaustive.py cissoid_record_best.csv cissoid_record_exhaustive.csv > cissoid_exhaustive.out 2>&1
S=cissoid_record_best.csv; [ -f cissoid_record_exhaustive.csv ] && S=cissoid_record_exhaustive.csv
python cissoid_reduce.py "$S" cissoid_reduce_quintet.csv LBT FMH > cissoid_reduce.out 2>&1
echo "$(date '+%F %H:%M') after_multi4: exhaustive -> $(tail -1 cissoid_exhaustive.out); reduce to quintet: $(grep -c '^step' cissoid_reduce.out) steps, see cissoid_reduce.out" >> campaign.log
