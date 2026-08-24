#!/usr/bin/env bash
# REJOUER LA PAIRE DE RUNS PARALLELES, MACHINE PROPRE -- et mesurer enfin la DISPERSION.
#
#     bash scripts/mesure_paire_propre.sh <etiquette> [graine1] [graine2]
#
# ## 🔑 CE QU'ELLE REND, ET POURQUOI ELLE VAUT MIEUX QU'UNE MESURE DE PLUS
#
# Le 2026-08-23, le DOCP (2133 -> 3600 MHz) a rendu **+4,9 % / +5,0 %** de DUREE sur les runs
# complets, deux graines. Verdict : aucun gain. ⚠️ Mais `n = 1` DANS CHAQUE CONFIGURATION, et
# la dispersion de run a run sur cette machine n'a JAMAIS ete mesuree. Tant qu'elle manque,
# « +5 % » n'est pas distinguable du bruit ordinaire et ne decide rien.
#
# 🔑 Rejouer la MEME paire, dans la MEME configuration materielle, sur machine propre, donne
# precisement ce chiffre :
#
#     ecart a la paire d'hier ~ 0,5 %  ->  la machine est stable, le +5 % du DOCP est REEL
#     ecart a la paire d'hier ~ 5 %    ->  le +5 % etait du bruit, le DOCP est NEUTRE
#
# 📌 On ne peut plus remesurer le 2133 MHz sans redemonter la machine. La reference d'hier
# (`reports/orchestre_r75x2_20260823_124146/`) est donc definitive, et c'est une raison de plus
# pour qualifier le bruit du cote qu'on peut encore rejouer.
#
# ## 🔴 « MACHINE PROPRE » SE CONSTATE, ET PAS AVEC N'IMPORTE QUEL INSTRUMENT
#
# ⚠️ `Get-Process | Select CPU` rend le CPU **CUMULE DEPUIS LE DEMARRAGE** du processus. Lu
# comme une charge instantanee il fait croire a une machine chargee : le 2026-08-24 il montrait
# « GoogleDriveFS 2328 s » sur une machine parfaitement au repos. Le seul releve qui repond est
# un DELTA sur un intervalle. On refuse donc de demarrer si un delta depasse le seuil.

set -u
PY="${CERTUS_PY:-C:/envs/certus/Scripts/python.exe}"
ETIQ="${1:-docp_propre_2026-08-24}"
G1="${2:-404}"
G2="${3:-505}"
J="reports/${ETIQ}"
REF="reports/docp_2026-08-23"

for g in "$G1" "$G2"; do
  if [ -e "$J/journal_s${g}.log" ]; then
    echo "🔴 $J/journal_s${g}.log existe deja -- refus d'ecraser un journal." >&2
    exit 3
  fi
done
mkdir -p "$J"

sondes() {
  powershell.exe -NoProfile -Command \
    "(Get-CimInstance Win32_Process -Filter \"Name LIKE 'python%'\" | Where-Object { \$_.CommandLine -like '*probe_blocs_vs_plantage*' } | Measure-Object).Count" \
    2>/dev/null | tr -d '\r' | tail -1
}
autres() {
  powershell.exe -NoProfile -Command \
    "(Get-CimInstance Win32_Process -Filter \"Name LIKE 'python%'\" | Where-Object { \$_.CommandLine -notlike '*probe_blocs_vs_plantage*' } | Measure-Object).Count" \
    2>/dev/null | tr -d '\r' | tail -1
}
cpu() {
  powershell.exe -NoProfile -Command \
    "(Get-CimInstance Win32_PerfFormattedData_PerfOS_Processor -Filter \"Name='_Total'\").PercentProcessorTime" \
    2>/dev/null | tr -d '\r' | tail -1
}

# 🔴 LE CONTROLE DE PROPRETE, PAR DELTA -- voir l'en-tete. Seuil a 2 s de CPU cumule sur 10 s,
# soit ~20 % d'un coeur : au-dessus, quelque chose travaille vraiment.
echo "[$ETIQ] controle de proprete -- delta CPU par processus sur 10 s"
sale=$(powershell.exe -NoProfile -Command \
  "\$a=@{}; Get-Process | ForEach-Object { \$a[\$_.Id]=\$_.CPU }; Start-Sleep -Seconds 10; (Get-Process | ForEach-Object { \$d=\$_.CPU - \$a[\$_.Id]; if (\$d -gt 2.0) { \$_.Name } } | Measure-Object).Count" \
  2>/dev/null | tr -d '\r' | tail -1)
sale="${sale:-0}"
if [ "$sale" -ne 0 ]; then
  echo "🔴 $sale processus consomment vraiment du CPU -- la machine n'est PAS propre." >&2
  echo "   Une mesure de duree lancee ici ne vaudrait rien. ARRET." >&2
  exit 4
fi
n0=$(sondes); [ "${n0:-0}" -eq 0 ] || { echo "🔴 une sonde tourne deja -- ARRET." >&2; exit 5; }
echo "[$ETIQ] 🟢 machine propre"

echo "[$ETIQ] demarrage des DEUX runs en parallele, graines $G1 et $G2, a $(date '+%H:%M:%S')"
t0=$(date +%s)
for g in "$G1" "$G2"; do
  CERTUS_BENCH_TIMEOUT_S=38400 "$PY" scripts/probe_blocs_vs_plantage.py \
      r75x2 deep 0 0 2 0 "$g" > "$J/journal_s${g}.log" 2>&1 &
done

max_autres=0
n_avec_autres=0
n_releves=0
somme_cpu=0
n_cpu=0
while [ "$(jobs -rp | wc -l)" -gt 0 ]; do
  a=$(autres); a="${a:-0}"
  [ "$a" -gt "$max_autres" ] && max_autres="$a"
  [ "$a" -gt 0 ] && n_avec_autres=$((n_avec_autres + 1))
  n_releves=$((n_releves + 1))
  c=$(cpu); c="${c:-}"
  case "$c" in ''|*[!0-9]*) ;; *) somme_cpu=$((somme_cpu + c)); n_cpu=$((n_cpu + 1));; esac
  # 🔴 L'INTERVALLE ETAIT DE 120 s ET IL A DONNE UN FEU VERT FAUX. Le 2026-08-24, la mesure a
  # ete polluee par des analyses lancees a la main sur la machine, le bloc 8 a saute de +20 %
  # sur LES DEUX graines a la meme minute -- et ce compteur a rendu `max_autres_python=0`.
  # Des commandes de quelques secondes passent entre deux releves espaces de deux minutes.
  #
  # ⚠️ ET 20 s NE FERME PAS LE TROU, IL LE RETRECIT. Un instrument qui echantillonne ne verra
  # jamais ce qui vit moins que son pas. LE VRAI DETECTEUR EST AILLEURS, et il est gratuit :
  # une contamination exterieure frappe les DEUX graines a la MEME minute, alors que le bruit
  # propre au calcul, lui, ne se synchronise pas. C'est la simultanee dans le tableau des
  # durees qui a trahi la pollution, pas ce compteur. Le compteur aide ; il ne conclut pas.
  #
  # 📏 Cout de l'echantillonnage a 20 s : ~0,5 % du CPU, dix fois sous l'effet mesure.
  sleep 20
done
wait
mn=$(( ($(date +%s) - t0) / 60 ))
cpu_moy=$(( n_cpu > 0 ? somme_cpu / n_cpu : -1 ))
echo "[$ETIQ] les deux runs sont finis en ${mn} min -- $(date '+%H:%M:%S')"

# 🔴 L'HEURE DE DEMARRAGE DE WINDOWS EST LE CHAMP QUI MANQUAIT. Le 2026-08-24, la machine
# avait redemarre a 19:38 la veille : le premier run partait sur des caches de fichiers
# FROIDS, son bloc 75 a pris 1:07 contre 0:22, et il a fallu DEDUIRE la chauffe d'une courbe
# decroissante au lieu de la lire. Un run qui suit de peu un demarrage n'est pas comparable a
# un run etabli, et cela doit se voir sans reflexion.
boot=$(powershell.exe -NoProfile -Command \
  "(Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToString('yyyy-MM-dd HH:mm:ss')" \
  2>/dev/null | tr -d '\r' | tail -1)
{
  echo "mode=PAIRE_PARALLELE"
  echo "graines=$G1,$G2"
  echo "duree_min=$mn"
  echo "demarrage_windows=$boot   # un run peu apres un boot part sur des caches FROIDS"
  echo "cpu_moyen_pct=$cpu_moy   # moyenne des releves pendant les deux runs"
  echo "max_autres_python=$max_autres   # PLANCHER : voir le commentaire du releve"
  echo "releves_avec_autres=$n_avec_autres/$n_releves   # combien de releves ont vu un intrus"
  echo "machine_propre_au_depart=oui   # controle par delta CPU sur 10 s"
} > "$J/CONTEXTE.txt"
cat "$J/CONTEXTE.txt"

for g in "$G1" "$G2"; do
  if grep -q "WAIT_TIMEOUT" "$J/journal_s${g}.log"; then
    echo "🔴 « WAIT_TIMEOUT » graine $g -- mesure COUPEE, elle ne vaut rien." >&2
  fi
done

echo
echo "################ DISPERSION : aujourd'hui contre hier, MEME configuration 3600 MHz"
for g in "$G1" "$G2"; do
  echo "======== graine $g"
  "$PY" scripts/lire_solo_vs_parallele.py \
      "$J/journal_s${g}.log" "$REF/journal_s${g}.log" "auj. propre" "hier 3600" 2>&1 \
    | sed -n '/^B\./,/^  cumul/p'
done
