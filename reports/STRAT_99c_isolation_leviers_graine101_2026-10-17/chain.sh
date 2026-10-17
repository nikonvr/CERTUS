#!/bin/bash
# 99c, graine 101 : replique de l'isolation des leviers du Rate elargi (protocole fige avant la lecture des resultats de la graine 42).
# Bras C1 (budget 240 seul) puis C2 (budget 240 + six tours), un seul run a la fois.
# Amendement du 2026-10-17, avant tout lancement de cette chaine : un bras n'avorte plus quand un python etranger tourne ; il attend au plus
# 90 minutes deux releves consecutifs sans aucun python, puis demarre ; pendant le bras, un releve par minute des python etrangers a la sonde
# est ecrit dans foreign_python_<bras>.log (voir protocol.json, champ amendments).
cd "D:/drivfl/01_Recherche_Enseignement/02_Couches_Minces_Optique/couches minces 2026/CERTUS/certus0310" || exit 1
D=reports/STRAT_99c_isolation_leviers_graine101_2026-10-17
MARQUEUR=reports/STRAT_99c_isolation_leviers_2026-10-17/MESURES_TERMINEES.txt
FIGE=7f3edea879ab150eb9bee50b3b9f5d1675bb3869
export CERTUS_BENCH_TIMEOUT_S=36000 PYTHONUTF8=1 NUMBA_NUM_THREADS=15 OMP_NUM_THREADS=15 MKL_NUM_THREADS=15 OPENBLAS_NUM_THREADS=15

py_count() { powershell.exe -NoProfile -Command "(Get-CimInstance Win32_Process | Where-Object { \$_.Name -match '^(python|pythonw)(\.exe)?\$' } | Measure-Object).Count" | tr -d '\r'; }
foreign_py_count() { powershell.exe -NoProfile -Command "(Get-CimInstance Win32_Process | Where-Object { \$_.Name -match '^(python|pythonw)(\.exe)?\$' -and \$_.CommandLine -notmatch 'probe_blocs_vs_plantage' } | Measure-Object).Count" | tr -d '\r'; }
code_clean() { [ -z "$(git -c core.longpaths=true status --porcelain -- certus certus_physics scripts tools tests example | grep -v '^??')" ]; }
code_frozen() { git diff --quiet "$FIGE" HEAD -- certus certus_physics scripts tools tests example; }
now() { date -u +%Y-%m-%dT%H:%M:%SZ; }

# la porte des autres sessions : ce fichier dit « plus aucune de mes mesures ne tourne » (fin normale, abandon ou erreur)
trap 'echo "$(now) mesures terminees ou interrompues (chaine graine 101)" > "$MARQUEUR"' EXIT

wait_free() {  # attend au plus 90 min deux releves consecutifs sans aucun python ; rend 0 des que la machine est libre
  local clear=0 waited=0
  while [ "$waited" -lt 5400 ]; do
    if [ "$(py_count)" = "0" ]; then clear=$((clear+1)); else clear=0; fi
    [ "$clear" -ge 2 ] && return 0
    sleep 60; waited=$((waited+60))
  done
  return 1
}

sample_foreign() {  # $1 = fichier : un releve par minute du nombre de python etrangers a la sonde
  while true; do echo "$(now) foreign_python=$(foreign_py_count)" >> "$1"; sleep 60; done
}

run_arm() {  # $1 = nom du bras, $2 = surcharges de sonde, $3 = etiquette
  local name="$1" over="$2" tag="$3"
  echo "$(now) WAIT $name: attente d'une machine sans python (90 min au plus)" >> $D/chain.log
  wait_free || { echo "$(now) ABORT $name: la machine n'est pas devenue libre en 90 minutes" >> $D/chain.log; return 3; }
  code_clean || { echo "$(now) ABORT $name: du code suivi a change depuis le protocole" >> $D/chain.log; return 4; }
  code_frozen || { echo "$(now) ABORT $name: le code suivi differe du commit fige $FIGE" >> $D/chain.log; return 5; }
  echo "$(now) START $name HEAD=$(git rev-parse --short HEAD)" >> $D/chain.log
  sample_foreign "$D/foreign_python_$name.log" &
  local sampler=$!
  CERTUS_PROBE_OVERRIDES="$over" CERTUS_PROBE_TAG="$tag" python -X cpu_count=16 scripts/probe_blocs_vs_plantage.py 99c premium 0 0 2 0 101 > $D/run_$name.log 2>&1
  local rc=$?
  kill "$sampler" 2>/dev/null; wait "$sampler" 2>/dev/null
  echo "exit=$rc" >> $D/run_$name.log
  echo "$(now) END $name exit=$rc" >> $D/chain.log
  return $rc
}

run_arm C1_budget240_seul "elite_rate_max_candidates=240" rate_budget240_seul || exit $?
run_arm C2_budget240_six_tours "elite_rate_max_candidates=240,elite_rounds=6" rate_budget240_six_tours
exit $?
