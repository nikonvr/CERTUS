#!/bin/bash
# A9 : le 99c en une seule campagne, trois bras par graine de recherche (O optique pur, R Rate, RP Rate + derniers raffinements), un run a la fois.
#
# CE SCRIPT NE LANCE RIEN SANS LE GO ECRIT DU PROPRIETAIRE : le fichier GO_OWNER.txt de ce dossier, une unite par ligne (S1, S2, S3, CONTROL_J),
# avec ses mots. Il n'a jamais ete lance au moment de sa redaction (voir protocole_A9.md, section 11).
#
# Usage    : bash chain_A9.sh S1                (puis, apres l'audit de S1 : bash chain_A9.sh S2 ; bash chain_A9.sh S3)
#            bash chain_A9.sh CONTROL_J         (controle facultatif : recherche conjointe 480 SANS raffinement final, graine S1)
#            bash chain_A9.sh --plan S1         (n'execute RIEN : affiche les trois commandes et passe les portes, sans GO ni creneau pris)
# Les valeurs ci-dessous sont celles de protocol.json ; la verification a sec les compare (verification_a_sec.json).
set -u
PLAN=0
if [ "${1:-}" = "--plan" ]; then PLAN=1; shift; fi
UNIT="${1:-}"
case "$UNIT" in
  S1) SEED=17810001 ;;
  S2) SEED=17810011 ;;
  S3) SEED=17810021 ;;
  CONTROL_J) SEED=17810001 ;;
  *) echo "unite inconnue : '$UNIT' (S1, S2, S3, CONTROL_J)"; exit 2 ;;
esac

ROOT="$(cd "$(dirname "$0")/../.." && pwd)" || exit 1
cd "$ROOT" || exit 1
D=reports/STRAT_99c_A9_protocole_2026-10-17
FIGE=6e54651535d662331e9e57d9c6b368e9ce9e1a72
CODE_DIRS="certus certus_physics scripts tools tests example CERTUS_STRAT.py pyproject.toml data"
CEIL=7200
# La base commune de TOUS les bras (protocole_A9.md, section 3) ; seuls les interrupteurs du bras changent.
COMMON="elite_rate_max_candidates=240,elite_rounds=6,elite_rate_balanced_moves=false"

export CERTUS_BENCH_TIMEOUT_S=$CEIL PYTHONUTF8=1 NUMBA_NUM_THREADS=15 OMP_NUM_THREADS=15 MKL_NUM_THREADS=15 OPENBLAS_NUM_THREADS=15
unset CERTUS_CONSENSUS_SEEDS CERTUS_RATE_SETS CERTUS_TAIL_CUTS CERTUS_PROBE_OVERRIDES CERTUS_PROBE_TAG CERTUS_DESIGN_JSON NUMBA_CACHE_DIR _CERTUS_NUMBA_CONFIGURED NUMBA_THREADING_LAYER
# Les preferences de l'operateur ne doivent pas entrer dans le calcul : un dossier de preferences vide, hors du depot suivi.
export CERTUS_CONFIG_DIR="$ROOT/scratch/a9_prefs"

now() { date -u +%Y-%m-%dT%H:%M:%SZ; }
py_count() { powershell.exe -NoProfile -Command "(Get-CimInstance Win32_Process | Where-Object { \$_.Name -match '^(python|pythonw)(\.exe)?\$' } | Measure-Object).Count" | tr -d '\r'; }
foreign_py_count() { powershell.exe -NoProfile -Command "(Get-CimInstance Win32_Process | Where-Object { \$_.Name -match '^(python|pythonw)(\.exe)?\$' -and \$_.CommandLine -notmatch 'probe_blocs_vs_plantage' } | Measure-Object).Count" | tr -d '\r'; }
foreign_py_list() { powershell.exe -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { \$_.Name -match '^(python|pythonw)(\.exe)?\$' -and \$_.CommandLine -notmatch 'probe_blocs_vs_plantage' } | ForEach-Object { \"pid=\$(\$_.ProcessId) \$(\$_.CommandLine)\" }" | tr -d '\r' | cut -c1-220; }

go_ok() { [ -f "$D/GO_OWNER.txt" ] && tr -d '\r' < "$D/GO_OWNER.txt" | grep -qxF "$UNIT"; }
code_clean() { [ -z "$(git -c core.longpaths=true status --porcelain -- $CODE_DIRS | grep -v '^??')" ]; }
code_frozen() { git diff --quiet "$FIGE" HEAD -- $CODE_DIRS; }
sources_ok() { sha256sum -c --quiet "$D/sources_sha256.txt" > "$D/runs/sha_check_last.txt" 2>&1; }
disk_ok() { [ "$(df -Pm . | awk 'NR==2{print $4}')" -ge 5000 ]; }
claim() { ( set -o noclobber; printf '{"slot":"%s","claimed_utc":"%s","head":"%s","pid":%s}\n' "$1" "$(now)" "$(git rev-parse HEAD)" "$$" > "$D/claims/$1.json" ) 2>/dev/null; }

wait_free() {  # attend au plus 10 min deux releves consecutifs sans aucun python ; 0 si la machine est libre, 1 sinon
  local clear=0 waited=0
  while [ "$waited" -lt 600 ]; do
    if [ "$(py_count)" = "0" ]; then clear=$((clear+1)); else clear=0; fi
    [ "$clear" -ge 2 ] && return 0
    sleep 60; waited=$((waited+60))
  done
  return 1
}
sample_foreign() {  # $1 = fichier : un releve par minute du nombre de python etrangers a la sonde
  while true; do echo "$(now) foreign_python=$(foreign_py_count)" >> "$1"; sleep 60; done
}

mkdir -p "$D/claims" "$D/runs" scratch/a9_prefs

run_arm() {  # $1 = bras, $2 = surcharges de sonde, $3 = etiquette
  local arm="$1" over="$2" tag="$3" slot="${UNIT}_$1"
  local cmd="python -X cpu_count=16 scripts/probe_blocs_vs_plantage.py 99c premium 0 0 2 0 $SEED"
  if [ "$PLAN" = "1" ]; then
    echo "PLAN $slot"
    echo "  CERTUS_PROBE_OVERRIDES='$over' CERTUS_PROBE_TAG='$tag' timeout --kill-after=120 $((CEIL+600)) $cmd"
    echo "  porte code propre      : $(code_clean && echo OUI || echo NON)"
    echo "  porte code fige ($FIGE) : $(code_frozen && echo OUI || echo NON)"
    echo "  porte empreintes       : $(sources_ok && echo OUI || echo NON)"
    echo "  porte disque libre     : $(disk_ok && echo OUI || echo NON)"
    echo "  porte creneau libre    : $([ -e "$D/claims/$slot.json" ] && echo NON || echo OUI)"
    echo "  porte GO ecrit         : $(go_ok && echo OUI || echo "NON (normal avant le GO du proprietaire)")"
    echo "  python vivants         : $(py_count)"
    return 0
  fi
  go_ok || { echo "$(now) REFUS $slot : pas de GO ecrit du proprietaire pour $UNIT dans $D/GO_OWNER.txt" >> "$D/chain.log"; return 9; }
  echo "$(now) WAIT $slot : attente d'une machine sans python (10 min au plus)" >> "$D/chain.log"
  if wait_free; then
    echo "$(now) FREE $slot : machine libre" >> "$D/chain.log"
  else
    echo "$(now) CONTENTION $slot : le bras demarre sous charge etrangere :" >> "$D/chain.log"
    foreign_py_list >> "$D/chain.log"
  fi
  code_clean   || { echo "$(now) ABORT $slot : du code suivi a change depuis le protocole" >> "$D/chain.log"; return 4; }
  code_frozen  || { echo "$(now) ABORT $slot : le code suivi differe du commit fige $FIGE" >> "$D/chain.log"; return 5; }
  sources_ok   || { echo "$(now) ABORT $slot : une empreinte de sources_sha256.txt differe (voir runs/sha_check_last.txt)" >> "$D/chain.log"; return 6; }
  disk_ok      || { echo "$(now) ABORT $slot : moins de 5 Go libres" >> "$D/chain.log"; return 7; }
  claim "$slot" || { echo "$(now) ABORT $slot : creneau deja pris, a inspecter, jamais a rejouer" >> "$D/chain.log"; return 8; }
  echo "$(now) START $slot HEAD=$(git rev-parse --short HEAD) seed=$SEED tag=$tag" >> "$D/chain.log"
  echo "$(now) CMD   $slot CERTUS_PROBE_OVERRIDES='$over' CERTUS_PROBE_TAG='$tag' $cmd" >> "$D/chain.log"
  sample_foreign "$D/runs/foreign_python_$slot.log" &
  local sampler=$!
  local t0; t0=$(date +%s)
  CERTUS_PROBE_OVERRIDES="$over" CERTUS_PROBE_TAG="$tag" timeout --kill-after=120 $((CEIL+600)) $cmd > "$D/runs/$slot.log" 2>&1
  local rc=$?
  local t1; t1=$(date +%s)
  kill "$sampler" 2>/dev/null; wait "$sampler" 2>/dev/null
  echo "exit=$rc" >> "$D/runs/$slot.log"
  local art verdict="absent" size=0 sha="" foreign_max=0
  art=$(ls -t reports/blocs_vs_plantage_99c_premium_s${SEED}_${tag}*.json 2>/dev/null | head -1)
  if [ -n "$art" ]; then
    size=$(stat -c %s "$art"); sha=$(sha256sum -b "$art" | cut -d' ' -f1)
    verdict=$(head -c 400 "$art" | grep -m1 -o '"verdict": "[A-Z_]*"' | cut -d'"' -f4)
  fi
  foreign_max=$(awk -F= '{ if ($2 + 0 > m) m = $2 + 0 } END { print m + 0 }' "$D/runs/foreign_python_$slot.log" 2>/dev/null)
  printf '{"slot":"%s","arm":"%s","seed":%s,"tag":"%s","overrides":"%s","duration_s":%s,"exit":%s,"verdict":"%s","artefact":"%s","artefact_bytes":%s,"artefact_sha256":"%s","head":"%s","foreign_python_max":%s,"ended_utc":"%s"}\n' \
    "$slot" "$arm" "$SEED" "$tag" "$over" "$((t1-t0))" "$rc" "$verdict" "$art" "$size" "$sha" "$(git rev-parse --short HEAD)" "$foreign_max" "$(now)" >> "$D/runs_index.jsonl"
  echo "$(now) END   $slot exit=$rc verdict=$verdict duree=$((t1-t0))s artefact=$art" >> "$D/chain.log"
  if [ "$rc" != "0" ] || [ "$verdict" != "OK" ]; then
    echo "$(now) STOP  $slot : un bras en echec arrete la chaine, sans reprise automatique (protocole_A9.md, section 7, regle R3)" >> "$D/chain.log"
    return 1
  fi
  return 0
}

if [ "$PLAN" = "0" ]; then
  ( set -o noclobber; echo "$UNIT pid=$$ $(now)" > "$D/.running" ) 2>/dev/null || { echo "verrou $D/.running present : une autre unite tourne ou a ete interrompue, a inspecter"; exit 3; }
  rm -f "$D/MESURES_TERMINEES.txt"
  trap 'rm -f "$D/.running"; echo "$(now) mesures terminees ou interrompues (A9, unite $UNIT)" > "$D/MESURES_TERMINEES.txt"' EXIT
fi

lc="$(echo "$UNIT" | tr 'A-Z' 'a-z')"
case "$UNIT" in
  CONTROL_J)
    run_arm J  "allow_rate=true,${COMMON},elite_rate_joint_candidates=480,rate_post_refinement=false" "a9_ratejoint_s1" ;;
  *)
    run_arm O  "allow_rate=false,${COMMON},elite_rate_joint_candidates=0,rate_post_refinement=false" "a9_opt_${lc}"      || exit $?
    run_arm R  "allow_rate=true,${COMMON},elite_rate_joint_candidates=0,rate_post_refinement=false"  "a9_rate_${lc}"     || exit $?
    run_arm RP "allow_rate=true,${COMMON},elite_rate_joint_candidates=480,rate_post_refinement=true" "a9_rateplus_${lc}" ;;
esac
exit $?
