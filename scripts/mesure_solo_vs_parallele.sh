#!/usr/bin/env bash
# MESURER CE QUE COUTE LE PARALLELISME -- lance UN run SEUL des que la machine se libere.
#
#     bash scripts/mesure_solo_vs_parallele.sh
#
# ## 🔑 CE QU'ELLE DECIDE, ET POURQUOI ELLE EXISTE
#
# Le 2026-08-23, monter la bande passante memoire de +69 % (2133 -> 3600 MHz) n'a rien rendu :
# la conclusion « le goulot est la bande passante memoire » est REFUTEE (§0000 de
# docs/REPRENDRE_ICI.md). Reste la question ouverte : la machine passe-t-elle a l'echelle ?
# 👤 demande ou mettre son argent -- RAM, coeurs, ou rien. Cette mesure est la seule qui
# repond, et elle est GRATUITE.
#
# ## 🔴 LA MEME GRAINE ET LES MEMES ARGUMENTS, COPIES A L'IDENTIQUE
#
# `r75x2 deep 0 0 2 0 404` est la ligne de commande exacte du run en vol du 2026-08-23 a 17:33.
# A graine et code identiques le travail est le MEME au bit -- verifie sur six blocs. La seule
# variable devient « seul » contre « a deux ». Changer la graine casserait la comparaison, et
# `lire_solo_vs_parallele.py` REFUSE de comparer des durees s'il voit les RMSE diverger.
#
# ## 🔴 ON ATTEND EN REGARDANT LES SONDES, PAS TOUS LES `python`
#
# `enchainer_apres.sh` compte TOUS les processus `python%`. Le 2026-08-23 a 18:06 un travail
# etranger de hachage tournait sous `C:\Python314\python.exe` : cette attente-la n'aurait
# jamais rendu la main. On filtre donc sur la LIGNE DE COMMANDE.
#
# 🔴 Et jamais sur l'apparition d'un artefact : la sonde l'ecrit AVANT sa synthese, et une
# chaine qui le guettait a lance la mesure suivante 10 s trop tot le 2026-08-21
# (« RuntimeError: QThread has been deleted »). D'ou la temporisation de trois minutes.
#
# ## ⚠️ LE PLAFOND EST GENEREUX, ET C'EST SANS EFFET SUR LA MESURE
#
# `CERTUS_BENCH_TIMEOUT_S` n'est qu'un `QTimer` a un coup dans `bench_examples.wait_for`
# (`bench_examples.py:205-216`) : tant qu'il ne tombe pas, il ne change RIEN a la duree. Le
# defaut de 1800 s couperait ce run a 30 min. Regle du §0.3 : `max(5400, 4 x duree attendue)`.

set -u
PY="${CERTUS_PY:-C:/envs/certus/Scripts/python.exe}"
ETIQ="${1:-solo_2026-08-23}"
GRAINE="${2:-404}"
J="reports/${ETIQ}"
mkdir -p "$J"
LOG="$J/journal_s${GRAINE}.log"
REF="reports/docp_2026-08-23/journal_s${GRAINE}.log"

if [ -e "$LOG" ]; then
  echo "🔴 $LOG existe deja -- refus d'ecraser un journal." >&2
  echo "   Donne une autre etiquette : bash $0 <etiquette> [graine]" >&2
  exit 3
fi

sondes() {
  powershell.exe -NoProfile -Command \
    "(Get-CimInstance Win32_Process -Filter \"Name LIKE 'python%'\" | Where-Object { \$_.CommandLine -like '*probe_blocs_vs_plantage*' } | Measure-Object).Count" \
    2>/dev/null | tr -d '\r' | tail -1
}

# Les python qui ne sont PAS des sondes CERTUS : ils ne bloquent pas l'attente, mais ils
# volent du CPU et doivent apparaitre dans le contexte de la mesure.
autres() {
  powershell.exe -NoProfile -Command \
    "(Get-CimInstance Win32_Process -Filter \"Name LIKE 'python%'\" | Where-Object { \$_.CommandLine -notlike '*probe_blocs_vs_plantage*' } | Measure-Object).Count" \
    2>/dev/null | tr -d '\r' | tail -1
}

echo "[$ETIQ] en attente que les sondes CERTUS se terminent -- $(date '+%Y-%m-%d %H:%M:%S')"
vide=0
while [ "$vide" -lt 3 ]; do
  n=$(sondes); n="${n:-0}"
  if [ "$n" -eq 0 ]; then
    vide=$((vide + 1))
    echo "[$ETIQ] $(date '+%H:%M:%S')  aucune sonde -- ${vide}/3 minutes de calme"
  else
    [ "$vide" -ne 0 ] && echo "[$ETIQ] $(date '+%H:%M:%S')  une sonde est repartue, compteur remis a zero"
    vide=0
  fi
  sleep 60
done

echo "[$ETIQ] machine libre -- demarrage du run SEUL, graine ${GRAINE}, a $(date '+%H:%M:%S')"
t0=$(date +%s)
CERTUS_BENCH_TIMEOUT_S=38400 "$PY" scripts/probe_blocs_vs_plantage.py \
    r75x2 deep 0 0 2 0 "$GRAINE" > "$LOG" 2>&1 &
pid=$!

# 🔴 « SEUL » DOIT ETRE CONSTATE, PAS SUPPOSE. Un journal ne porte aucune trace de ce qui
# tournait A COTE de lui : donne deux journaux PARALLELES au lecteur et il rend « la machine
# passe a l'echelle, 2,12x » sans broncher -- essaye le 2026-08-23, c'est ce qui a fait
# ajouter ce releve. On echantillonne donc la concurrence PENDANT le run et on la consigne.
#
# 📏 Une sonde = DEUX processus python (mesure du 2026-08-23 : 4 processus pour 2 runs).
# Donc `sondes > 2` veut dire qu'un second run a chevauche celui-ci.
max_sondes=0
max_autres=0
while kill -0 "$pid" 2>/dev/null; do
  s=$(sondes); s="${s:-0}"
  a=$(autres); a="${a:-0}"
  [ "$s" -gt "$max_sondes" ] && max_sondes="$s"
  [ "$a" -gt "$max_autres" ] && max_autres="$a"
  sleep 60
done
wait "$pid"; code=$?
mn=$(( ($(date +%s) - t0) / 60 ))
echo "[$ETIQ] EXIT=$code en ${mn} min -- $(date '+%H:%M:%S')"

{
  echo "mode=SEUL"
  echo "graine=$GRAINE"
  echo "debut=$(date -d "@$t0" '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo "$t0")"
  echo "duree_min=$mn"
  echo "exit=$code"
  echo "max_processus_sonde=$max_sondes   # une sonde = 2 processus ; > 2 = un run a chevauche"
  echo "max_autres_python=$max_autres     # travaux etrangers vus pendant la mesure"
} > "$J/CONTEXTE.txt"
echo "[$ETIQ] contexte consigne dans $J/CONTEXTE.txt (sondes max=$max_sondes, autres=$max_autres)"

# 🔴 Le plafond qui tombe RESSEMBLE a un resultat : `wait_for` rend `None` en silence. On le
# cherche explicitement plutot que d'esperer le voir passer.
if grep -q "WAIT_TIMEOUT" "$LOG"; then
  echo "🔴 « WAIT_TIMEOUT » dans le journal -- la mesure a ete COUPEE, elle ne vaut rien." >&2
  exit 4
fi

echo
if [ -e "$REF" ]; then
  "$PY" scripts/lire_solo_vs_parallele.py "$LOG" "$REF"
else
  echo "⚠️ reference introuvable ($REF) -- comparaison non faite."
  echo "   a la main : $PY scripts/lire_solo_vs_parallele.py $LOG <journal a deux runs>"
fi
