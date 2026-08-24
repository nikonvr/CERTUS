#!/usr/bin/env bash
# L'HYSTERESIS EXPLIQUE-T-ELLE L'ANOMALIE DU §1ter ? -- un seul run, et il tranche dans les
# deux sens.
#
#     bash scripts/enchainer_hysteresis.sh [etiquette] [graine]
#
# ## 🔴 L'ANOMALIE, ET LE CANDIDAT QUE LE CODE CONFIRME
#
# 📏 Le taux de plantage DECROIT quand le bruit CROIT. Mesure sur la graine 404
# (`reports/blocs_vs_plantage_r75x2_deep_s404.json`, murs a 100 % ecartes) :
#
#     DECROISSANT  1577   ·   croissant  402      ->  rapport 3,92
#
# 🔑 Le mecanisme candidat n'est pas une supposition, il est DANS LE CODE.
# `certus_strat_robustness.py:2489-2495` :
#
#     tp_hysteresis = tp_hysteresis_factor * A * noise_val
#
# Le seuil du detecteur de points tournants **suit le niveau de bruit**. Quand le bruit croit,
# le detecteur devient donc plus CONSERVATEUR, fabrique moins de faux points tournants, et
# `TP_MISCOUNT` -- 79 % des plantages mesures -- recule. Cela produirait exactement le sens
# observe. ⚠️ Le mecanisme EXISTE ; ce qui n'est pas su, c'est s'il suffit a rendre compte de
# l'ampleur.
#
# ## 🔑 POURQUOI UN SEUL POINT, ET POURQUOI CELUI-LA
#
# §8.2 action 6 disait « balayer `tp_hysteresis_factor` a bruit fixe ». Un balayage a trois
# points coute ~1 h 50. L'extreme `= 0` coute 36 min et repond dans les deux sens, parce que le
# garde `if tp_hysteresis_factor > 0.0` (`:2489`) coupe alors TOUTE la dependance au bruit :
#
#     rapport ~ 1,0   ->  l'hysteresis EXPLIQUE l'anomalie ; le §1ter est clos
#     rapport ~ 3,9   ->  elle n'y est pour RIEN ; chercher ailleurs, et le §1ter reste ouvert
#     rapport entre   ->  elle explique une PART, et la il faut le balayage complet
#
# ⚠️ **UN RISQUE ASSUME, ET LE SIGNE QUI LE TRAHIT** : sans hysteresis du tout, le detecteur
# fabrique des faux points tournants a tous les niveaux et les taux peuvent SATURER a 100 %.
# La sonde compterait alors des « murs » et n'aurait plus rien a classer. Le journal le dit --
# la ligne « murs a 100 % ecartes » explose et les deux compteurs tombent a zero. Ce n'est pas
# une panne, c'est un resultat : il voudrait dire que l'hysteresis ne fait pas que biaiser le
# detecteur, elle le rend utilisable. Dans ce cas seulement, refaire a `= 0,5` puis `= 1,0`.
#
# ## 🔴 LA GRAINE EST 404 ET ELLE NE SE CHANGE PAS SANS CHANGER LE CONTROLE
#
# Le temoin est `reports/blocs_vs_plantage_r75x2_deep_s404.json`, deja sur le disque, produit
# par exactement cette ligne de commande a l'hysteresis PAR DEFAUT (1,66). Changer la graine
# obligerait a produire un second temoin -- une heure de plus pour rien.

set -u
PY="${CERTUS_PY:-C:/envs/certus/Scripts/python.exe}"
ETIQ="${1:-hysteresis_2026-08-24}"
G="${2:-404}"
# 🔴 LE FACTEUR EST UN ARGUMENT, ET IL ENTRE DANS L'ETIQUETTE. La premiere version le codait
# en dur et le document invitait a « remplacer 0 par 0.5 avant de relancer » : une edition
# manuelle avant chaque mesure, donc une occasion de se tromper a chaque fois -- et deux runs
# a facteurs differents auraient rendu deux artefacts au MEME nom.
FACTEUR="${3:-0}"
J="reports/${ETIQ}"
TEMOIN="reports/blocs_vs_plantage_r75x2_deep_s${G}.json"
TAG="hyst$(echo "$FACTEUR" | tr -d '.')"
LOG="$J/journal_s${G}.log"

[ -e "$LOG" ] && { echo "🔴 $LOG existe deja -- refus d'ecraser." >&2; exit 3; }
[ -e "$TEMOIN" ] || { echo "🔴 temoin absent : $TEMOIN -- rien a quoi comparer." >&2; exit 3; }
mkdir -p "$J"

sondes() {
  powershell.exe -NoProfile -Command \
    "(Get-CimInstance Win32_Process -Filter \"Name LIKE 'python%'\" | Where-Object { \$_.CommandLine -like '*probe_blocs_vs_plantage*' } | Measure-Object).Count" \
    2>/dev/null | tr -d '\r' | tail -1
}

echo "[$ETIQ] en attente que les sondes CERTUS se terminent -- $(date '+%Y-%m-%d %H:%M:%S')"
vide=0
while [ "$vide" -lt 3 ]; do
  n=$(sondes); n="${n:-0}"
  if [ "$n" -eq 0 ]; then
    vide=$((vide + 1)); echo "[$ETIQ] $(date '+%H:%M:%S')  aucune sonde -- ${vide}/3"
  else
    vide=0
  fi
  sleep 60
done

echo "[$ETIQ] demarrage, tp_hysteresis_factor=${FACTEUR} (etiquette ${TAG}), graine ${G}, a $(date '+%H:%M:%S')"
t0=$(date +%s)
CERTUS_BENCH_TIMEOUT_S=38400 \
CERTUS_PROBE_OVERRIDES="tp_hysteresis_factor=${FACTEUR}" \
CERTUS_PROBE_TAG="$TAG" \
  "$PY" scripts/probe_blocs_vs_plantage.py r75x2 deep 0 0 2 0 "$G" > "$LOG" 2>&1
code=$?
echo "[$ETIQ] EXIT=$code en $(( ($(date +%s) - t0) / 60 )) min -- $(date '+%H:%M:%S')"

grep -q "WAIT_TIMEOUT" "$LOG" && {
  echo "🔴 « WAIT_TIMEOUT » -- mesure COUPEE, elle ne vaut rien." >&2; exit 4; }

# 🔴 L'ARTEFACT PORTE L'ETIQUETTE DANS SON NOM, et c'est la raison d'etre de l'etiquette :
# sans elle il ecraserait le temoin auquel on veut justement le comparer.
# ⚠️ La sonde imprime un chemin WINDOWS (`reports\blocs_vs_plantage_...`). Sous Git Bash,
# `[ -e ]` ne resout pas les antislashs : sans cette conversion le test echoue toujours et la
# comparaison finale ne se fait jamais -- en silence, apres 36 minutes de calcul.
NEUF=$(grep -a "consigne dans" "$LOG" | tail -1 | sed 's/.*consigne dans //' \
       | tr -d '\r' | tr '\134' '/')   # \134 = antislash, en octal : `tr '\\'` avertit
echo "[$ETIQ] artefact neuf : ${NEUF:-INTROUVABLE}"

echo
echo "################ TEMOIN -- hysteresis PAR DEFAUT (1,66)"
"$PY" scripts/probe_plantage_vs_sigma.py "$TEMOIN" 2>&1 | sed -n '/murs a 100/,/rapport DECROISSANT/p'
echo
echo "################ ESSAI -- tp_hysteresis_factor = ${FACTEUR}"
[ -n "$NEUF" ] && [ -e "$NEUF" ] \
  && "$PY" scripts/probe_plantage_vs_sigma.py "$NEUF" 2>&1 | sed -n '/murs a 100/,/rapport DECROISSANT/p' \
  || echo "⚠️ artefact neuf illisible -- lance la sonde a la main sur le fichier cite plus haut."
