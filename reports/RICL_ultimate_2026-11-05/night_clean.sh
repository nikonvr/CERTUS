cd "D:/drivfl/01_Recherche_Enseignement/02_Couches_Minces_Optique/couches minces 2026/CERTUS/certus0310/reports/RICL_ultimate_2026-11-05"
export OPENBLAS_NUM_THREADS=1
PY="C:/Users/Fabien/AppData/Local/Programs/Python/Python315/python.exe"
echo "$(date '+%H:%M') night clean start" >> night_clean.log
$PY clean.py --designs S_tl_free_curve.csv --tag CL_curve --minutes 240 --floor 5 --nmax 160 --top 1300 >> night_clean.log 2>&1
echo "$(date '+%H:%M') CL_curve done" >> night_clean.log
$PY clean.py --designs R_tl_free_elites.csv S_tl_free_curve.csv DG_free8_designs.csv --tag CL_tl101 --minutes 120 --tot 14171 --tot-window 800 --floor 5 --nmax 101 --top 400 >> night_clean.log 2>&1
echo "$(date '+%H:%M') CL_tl101 done" >> night_clean.log
