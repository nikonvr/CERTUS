#!/usr/bin/env bash
# 2026-10-31 (owner: keep digging around the record, all on the 301 points): after otswaps, loop over
# forced grow (20 trials) -> exhaustive pairs on every layer -> reduction path L,B,T -> F,M,H keeping its best step,
# each from the current best; stops after a full round without gain
cd "$(dirname "$0")" || exit 1
until grep -q "otswaps done" campaign.log; do sleep 30; done
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 NUMBA_NUM_THREADS=1 CISSOID_WORKERS=15 CISSOID_K=12 CISSOID_METALS=AN \
  CISSOID_DIELECTRICS=all CISSOID_MAX_METALS=20 CISSOID_REMOVAL_SCREEN=6 CISSOID_GRID=full CISSOID_SWAP_MAX=3
best() { python -c "import csv;print(next(csv.DictReader(open('cissoid_record_best.csv',encoding='utf-8')))['mf_oracle'])"; }
take() {  # take $1 if better than the current best (single-row csv, or the best row of a reduction csv)
  [ -f "$1" ] || return
  python - "$1" <<'PY'
import csv, sys
rows = list(csv.DictReader(open(sys.argv[1], encoding="utf-8")))
r = min(rows, key=lambda x: float(x["mf_oracle"]))
b = next(csv.DictReader(open("cissoid_record_best.csv", encoding="utf-8")))
if float(r["mf_oracle"]) < float(b["mf_oracle"]) * (1 - 1e-4):
    keep = {k: r[k] for k in ("layers", "mf_oracle", "mats", "d_nm") if k in r}
    keep["mf_kernel"] = keep["mf_full"] = r.get("mf_full") or r["mf_oracle"]
    w = csv.DictWriter(open("cissoid_record_best.csv", "w", newline="", encoding="utf-8"), fieldnames=list(keep))
    w.writeheader(); w.writerow(keep)
    print("taken", r["mf_oracle"])
PY
}
take cissoid_record_otswaps.csv
for r in 1 2 3 4 5; do
  b0=$(best)
  rm -f dig_force.csv dig_pairs.csv
  python cissoid_force_grow.py cissoid_record_best.csv dig_force.csv 20 > "dig_force_$r.out" 2>&1; take dig_force.csv
  python cissoid_exhaustive.py cissoid_record_best.csv dig_pairs.csv > "dig_pairs_$r.out" 2>&1; take dig_pairs.csv
  python cissoid_reduce.py cissoid_record_best.csv dig_reduce.csv LBT FMH > "dig_reduce_$r.out" 2>&1; take dig_reduce.csv
  echo "$(date '+%F %H:%M') dig round $r: $b0 -> $(best)" >> campaign.log
  [ "$(best)" = "$b0" ] && break
done
