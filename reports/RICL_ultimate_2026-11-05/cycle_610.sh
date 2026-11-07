cd "D:/drivfl/01_Recherche_Enseignement/02_Couches_Minces_Optique/couches minces 2026/CERTUS/certus0310/reports/RICL_ultimate_2026-11-05"
export OPENBLAS_NUM_THREADS=1
PY="C:/Users/Fabien/AppData/Local/Programs/Python/Python315/python.exe"
N=$1; SEED=$2
$PY - "$SEED" <<'PYEOF'
import csv, sys
r=sorted(csv.DictReader(open("CL_FHANB610_clean.csv",encoding="utf-8")),key=lambda x: float(x["mf_oracle"]))[0]
with open(sys.argv[1],"w",newline="",encoding="utf-8") as h:
    w=csv.writer(h); w.writerow(["mf","layers","physical_nm","mats","d_nm"])
    w.writerow([r["mf_oracle"],r["layers"],r["physical_nm"],r["mats"],r["d_nm"]])
PYEOF
$PY cissoid_ultimate.py --mode run --axis phys --floor 0.1 --nmax 50 --pop 40 --tag $N --minutes 40 --workers 6 --seeds $SEED --only-seeds --window 6800:10500 --rng 97 > $N.out 2>&1
$PY clean_multi.py --designs ${N}_best.csv --axis phys --floor 3 --nmax 50 --tag CL_$N --minutes 10 --workers 4 > CL_$N.out 2>&1
$PY -c "
import csv
r=sorted(csv.DictReader(open('CL_${N}_clean.csv',encoding='utf-8')),key=lambda x: float(x['mf_oracle']))[0]
print('CYCLE_RESULT', '$N', round(float(r['mf_oracle']),5), 'physical', round(float(r['physical_nm']),1), 'thinnest', round(float(r['thinnest_nm']),2), 'N', r['layers'])
" >> cycle_610.result
