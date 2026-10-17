#!/bin/bash
# 99c, graine 42 : isolation des leviers du Rate elargi. Bras C1 (budget 240 seul) puis C2 (budget 240 + six tours), un seul run a la fois.
cd "D:/drivfl/01_Recherche_Enseignement/02_Couches_Minces_Optique/couches minces 2026/CERTUS/certus0310" || exit 1
D=reports/STRAT_99c_isolation_leviers_2026-10-17
export CERTUS_BENCH_TIMEOUT_S=36000 PYTHONUTF8=1 NUMBA_NUM_THREADS=15 OMP_NUM_THREADS=15 MKL_NUM_THREADS=15 OPENBLAS_NUM_THREADS=15

py_count() { powershell.exe -NoProfile -Command "(Get-CimInstance Win32_Process | Where-Object { \$_.Name -match '^(python|pythonw)(\.exe)?\$' } | Measure-Object).Count" | tr -d '\r'; }
code_clean() { [ -z "$(git -c core.longpaths=true status --porcelain -- certus scripts tools tests example | grep -v '^??')" ]; }
now() { date -u +%Y-%m-%dT%H:%M:%SZ; }

run_arm() {  # $1 = nom du bras, $2 = surcharges de sonde, $3 = etiquette
  local name="$1" over="$2" tag="$3"
  [ "$(py_count)" = "0" ] || { echo "$(now) ABORT $name: un processus python tourne deja" >> $D/chain.log; return 3; }
  code_clean || { echo "$(now) ABORT $name: du code suivi a change depuis le protocole" >> $D/chain.log; return 4; }
  echo "$(now) START $name HEAD=$(git rev-parse --short HEAD)" >> $D/chain.log
  CERTUS_PROBE_OVERRIDES="$over" CERTUS_PROBE_TAG="$tag" python -X cpu_count=16 scripts/probe_blocs_vs_plantage.py 99c premium 0 0 2 0 42 > $D/run_$name.log 2>&1
  local rc=$?
  echo "exit=$rc" >> $D/run_$name.log
  echo "$(now) END $name exit=$rc" >> $D/chain.log
  return $rc
}

run_arm C1_budget240_seul "elite_rate_max_candidates=240" rate_budget240_seul || exit $?
run_arm C2_budget240_six_tours "elite_rate_max_candidates=240,elite_rounds=6" rate_budget240_six_tours
exit $?
