#!/usr/bin/env bash
# COUPER UNE CAMPAGNE DES QU'UN COMPOSANT DONNE A FINI -- sans surveiller a la seconde.
#
#     bash scripts/couper_apres_composant.sh r75x1.75 batch_75c_nuit.sh
#
# 👤, 2026-08-23 : couper le batch apres `r75x1.75`, parce que les deux composants suivants
# (`75c` et `r75x2-2nm`) ont DEJA ete mesures cette nuit par l'autre campagne. Les refaire
# couterait ~2 h de machine pour un second exemplaire de chiffres qu'on possede -- au lieu de
# quoi la comparaison `r75x2` 404+505 demarre deux heures plus tot.
#
# ## 🔴 POURQUOI TUER LE BASH, ET PAS SEULEMENT LA TACHE
#
# 📏 Mesure du 2026-08-22 a 23h45 : `TaskStop` sur la tache de l'orchestrateur N'A PAS tue le
# script bash. Il a continue toute la nuit en parallele de la campagne relancee -- deux
# campagnes concurrentes, des durees gonflees de 50 a 72 min par run, et du travail fait deux
# fois. On vise donc le PROCESSUS, par son nom de script.
#
# ## CE QU'IL NE FAIT PAS
#
# Il ne coupe rien tant que le composant tourne encore : on attend la DISPARITION de son
# orchestrateur, jamais l'apparition d'un artefact -- la sonde ecrit celui-ci AVANT sa
# synthese. Une temporisation de deux minutes evite de confondre une fin avec un intervalle.

set -u
[ "$#" -ge 2 ] || { echo "usage: $0 <composant> <nom_du_script>" >&2; exit 2; }
COMP="$1"; SCRIPT="$2"
LOG="reports/COUPURE_${COMP}.log"
mkdir -p reports

_compte() {  # combien d'orchestrateurs travaillent sur ce composant ?
  powershell.exe -NoProfile -Command \
    "(Get-CimInstance Win32_Process -Filter \"Name LIKE 'python%'\" | Where-Object { \$_.CommandLine -like '*orchestre_multigraine.py $COMP *' } | Measure-Object).Count" \
    2>/dev/null | tr -d '\r' | tail -1
}

echo "[coupure] guette la fin de $COMP -- $(date '+%Y-%m-%d %H:%M:%S')" | tee -a "$LOG"

# 1. attendre qu'il DEMARRE (il peut ne pas encore avoir ete lance)
for _ in $(seq 1 120); do
  [ "$(_compte)" -gt 0 ] 2>/dev/null && break
  sleep 30
done
echo "[coupure] $COMP en cours a $(date '+%H:%M:%S')" | tee -a "$LOG"

# 2. attendre qu'il FINISSE -- deux releves consecutives a zero
vide=0
while [ "$vide" -lt 2 ]; do
  n="$(_compte)"; n="${n:-0}"
  if [ "$n" -eq 0 ]; then vide=$((vide + 1)); else vide=0; fi
  sleep 60
done
echo "[coupure] $COMP TERMINE a $(date '+%H:%M:%S') -- arret de $SCRIPT" | tee -a "$LOG"

# 3. couper le script, pas seulement la tache
powershell.exe -NoProfile -Command \
  "Get-CimInstance Win32_Process -Filter \"Name='bash.exe'\" | Where-Object { \$_.CommandLine -like '*$SCRIPT*' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force -ErrorAction SilentlyContinue }" \
  2>/dev/null
sleep 5
reste=$(powershell.exe -NoProfile -Command \
  "(Get-CimInstance Win32_Process -Filter \"Name='bash.exe'\" | Where-Object { \$_.CommandLine -like '*$SCRIPT*' } | Measure-Object).Count" \
  2>/dev/null | tr -d '\r' | tail -1)
echo "[coupure] $SCRIPT restant(s) : ${reste:-?} -- $(date '+%H:%M:%S')" | tee -a "$LOG"
