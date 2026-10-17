#!/bin/bash
# 99c, graine 101 : bras A (defauts de production) puis bras B (Rate elargi + raffinement final), un seul run a la fois.
cd "D:/drivfl/01_Recherche_Enseignement/02_Couches_Minces_Optique/couches minces 2026/CERTUS/certus0310" || exit 1
D=reports/STRAT_99c_paire_graine101_2026-10-16
export CERTUS_BENCH_TIMEOUT_S=36000 PYTHONUTF8=1 NUMBA_NUM_THREADS=15 OMP_NUM_THREADS=15 MKL_NUM_THREADS=15 OPENBLAS_NUM_THREADS=15

py_count() { powershell.exe -NoProfile -Command "(Get-CimInstance Win32_Process | Where-Object { \$_.Name -match '^(python|pythonw)(\.exe)?\$' } | Measure-Object).Count" | tr -d '\r'; }
code_clean() { [ -z "$(git -c core.longpaths=true status --porcelain -- certus scripts tools tests example | grep -v '^??')" ]; }
now() { date -u +%Y-%m-%dT%H:%M:%SZ; }

run_arm() {  # $1 = nom du bras, $2 = surcharges de sonde ("" = aucune), $3 = etiquette
  local name="$1" over="$2" tag="$3"
  [ "$(py_count)" = "0" ] || { echo "$(now) ABORT $name: un processus python tourne deja" >> $D/chain.log; return 3; }
  code_clean || { echo "$(now) ABORT $name: du code suivi a change depuis le protocole" >> $D/chain.log; return 4; }
  echo "$(now) START $name" >> $D/chain.log
  if [ -n "$over" ]; then
    CERTUS_PROBE_OVERRIDES="$over" CERTUS_PROBE_TAG="$tag" python -X cpu_count=16 scripts/probe_blocs_vs_plantage.py 99c premium 0 0 2 0 101 > $D/run_$name.log 2>&1
  else
    python -X cpu_count=16 scripts/probe_blocs_vs_plantage.py 99c premium 0 0 2 0 101 > $D/run_$name.log 2>&1
  fi
  local rc=$?
  echo "exit=$rc" >> $D/run_$name.log
  echo "$(now) END $name exit=$rc" >> $D/chain.log
  return $rc
}

run_arm A_defauts "" "" || exit $?
run_arm B_elargi_raffinement "elite_rate_max_candidates=240,elite_rounds=6,elite_rate_joint_candidates=480,rate_post_refinement=true" rate_elargi_refinement_240_6_480
exit $?
