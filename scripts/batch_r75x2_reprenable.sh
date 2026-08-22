#!/usr/bin/env bash
# BATCH REPRENABLE de la campagne r75x2 -- concu pour survivre a un changement de MACHINE.
#
# ## 🔑 CE QU'IL FAUT SAVOIR AVANT DE LE LANCER
#
# Il SAUTE toute mesure dont l'artefact existe deja et porte `verdict = OK`. On peut donc le
# relancer autant de fois qu'on veut : il reprend ou la campagne s'est arretee, sur n'importe
# quelle machine, sans refaire 91 minutes pour rien.
#
#     C:\envs\certus\Scripts\python.exe -m ...   -> non, c'est du bash :
#     bash scripts/batch_r75x2_reprenable.sh
#
# ## 🔴 LE PLAFOND SE CALCULE, IL NE SE COPIE PAS
#
# `bench_examples.py:171` : DEFAULT_TIMEOUT_MS = CERTUS_BENCH_TIMEOUT_S x 1000, defaut 1800 s.
# Au-dela, `wait_for` ABANDONNE et rend None -- ce qui RESSEMBLE a un resultat.
#
# 📏 Le 2026-08-22, un plafond a 5400 s a detruit QUATRE mesures. Duree reelle d'un run pleine
# plage sur r75x2 a 2 nm : **91 min** sur i5-8250U 8 threads. Le plafond etait a 90 : elles ont
# ete coupees a 98,9 % d'avancement.
#
# 🔑 La regle du depot est `max(5400, 4 x duree_attendue)`. Le facteur 4 absorbe une graine
# defavorable, qui peut doubler le nombre de survivants au criblage.
#
# ⚠️ SUR UNE MACHINE PLUS PUISSANTE, LA DUREE ATTENDUE BAISSE -- mais on NE BAISSE PAS le
# plafond pour autant. Un plafond trop grand ne coute rien ; un plafond trop petit detruit la
# mesure a la derniere minute. On garde donc 38400 s (4 x 160 min) tant que personne n'a
# MESURE la duree sur la machine courante.
export CERTUS_BENCH_TIMEOUT_S=38400

set -u
PY="${CERTUS_PY:-C:/envs/certus/Scripts/python.exe}"
J="reports/nuit_2026-08-21"
mkdir -p "$J"

# Les quatre mesures de la campagne, dans l'ordre de VALEUR D'INFORMATION decroissante.
#   nu_*     : r75x2 SANS rampes  -> la question de fond (42 malchanceuse, ou 77 chanceuse ?)
#   livree_* : config livree       -> consolidation du chiffre 0,5676
MESURES="r75x2:101:nu_s101 r75x2:202:nu_s202 r75x2-2nm:101:livree_s101 r75x2-2nm:202:livree_s202"

deja_fait() {   # $1 = composant · $2 = graine  -> 0 si un artefact OK existe
  "$PY" - "$1" "$2" <<'PYEOF'
import glob, json, sys
comp, graine = sys.argv[1], int(sys.argv[2])
for f in glob.glob(f"reports/blocs_vs_plantage_{comp}_deep_s{graine:03d}*.json"):
    try:
        d = json.load(open(f, encoding="utf-8"))
    except (OSError, ValueError):
        continue
    # 🔴 `verdict != OK` NE COMPTE PAS comme fait : les quatre mesures perdues du 2026-08-22
    # avaient toutes un artefact, et il ne portait aucune strategie.
    if d.get("verdict") == "OK" and (d.get("strategies") or []):
        print(f)
        sys.exit(0)
sys.exit(1)
PYEOF
}

echo "[batch] DEMARRAGE $(date '+%Y-%m-%d %H:%M:%S')"
echo "[batch] interpreteur : $PY"
echo "[batch] plafond      : ${CERTUS_BENCH_TIMEOUT_S} s"
echo

for m in $MESURES; do
  comp="${m%%:*}"; reste="${m#*:}"; graine="${reste%%:*}"; nom="${reste#*:}"
  if art=$(deja_fait "$comp" "$graine"); then
    echo "[batch] ⏭  $nom DEJA FAIT -- $art"
    continue
  fi
  echo "=========================================================================="
  echo "[batch] $nom -- composant $comp, graine $graine -- demarrage $(date '+%H:%M:%S')"
  echo "=========================================================================="
  t0=$(date +%s)
  # SYNCHRONE. 🔴 On n'attend JAMAIS l'apparition d'un artefact comme signal de fin : la sonde
  # l'ecrit AVANT sa synthese, et une chaine qui le guettait a lance la mesure suivante 10 s
  # trop tot le 2026-08-21 -- « RuntimeError: QThread has been deleted ».
  "$PY" scripts/probe_blocs_vs_plantage.py "$comp" deep 0 0 2.0 0 "$graine" > "$J/journal_${nom}.log" 2>&1
  code=$?
  echo "[batch] $nom EXIT=$code en $(( ($(date +%s) - t0) / 60 )) min -- $(date '+%H:%M:%S')"
  grep -oE "\[Block [0-9]+\] Best strategy ready: RMSE=[0-9.]+" "$J/journal_${nom}.log" \
      | tail -20 | sed "s/^/    /" || true
  # 🔴 Un EXIT non nul se DIT et n'arrete pas la campagne : les mesures suivantes gardent leur
  # valeur, et `lire_nuit` refusera de conclure sur ce qui manque.
  [ $code -ne 0 ] && echo "[batch] 🔴 $nom a echoue -- cherche « WAIT_TIMEOUT= » dans son journal"
  echo
done

echo "=========================================================================="
echo "[batch] RECAPITULATIF -- $(date '+%H:%M:%S')"
echo "=========================================================================="
"$PY" scripts/lire_nuit_2026-08-21.py || true
echo "[batch] TERMINE $(date '+%Y-%m-%d %H:%M:%S')"
