#!/usr/bin/env bash
# TEST DU CRIBLAGE DE GRAINES A BUDGET MONTE-CARLO REDUIT -- propose par 👤 le 2026-08-22.
#
# ## LA QUESTION, ET POURQUOI ELLE N'EST PAS EVIDENTE
#
# 👤 : « implanter plein de seed en prod, sur un nombre modeste de tirages pour que cela aille
# assez vite, et une fois qu'on a identifie les bons seed, on elargit le nombre de tirage ».
#
# Le schema EXISTE DEJA en production, une strate plus bas : `certus_strat_workers.py:930-971`
# crible toutes les strategies a `n_screen_runs`, garde `k_keep_survivors`, puis confirme les
# survivantes a `robustness_num_runs`. Il marche au niveau des STRATEGIES.
#
# 🔴 CE QUI N'EST PAS ACQUIS, C'EST QU'IL MONTE D'UN ETAGE, DES STRATEGIES AUX GRAINES.
#   - au niveau STRATEGIE, le criblage estime une propriete FIXE d'un objet FIXE (le taux de
#     plantage de cette strategie-la). Moins de tirages = meme nombre, moins bien estime.
#   - au niveau GRAINE, il n'y a aucun objet fixe. La graine agit A TRAVERS le criblage -- §3
#     point 3 de REPRENDRE_ICI : « le point de divergence des graines EST le criblage ».
#     Changer le budget change QUELS PLANS SURVIVENT, donc quels PARENTS ELITE recoit, donc
#     une AUTRE RECHERCHE. Une graine n'est pas bonne dans l'absolu : le couple (graine,
#     budget) l'est.
#
# ⚠️ Et le regime degenere aggrave exactement cela. Journal de la graine 404, 2026-08-22 :
# « les strategies rendues portent un score de REPLI, et leur crash_rate est constant. Le
# classement qui suit -- donc le choix des PARENTS d'ELITE -- ne dispose d'aucun signal dans
# ses deux premieres cles. » Quand tout plante a 100 %, le tri se rabat sur une cle ou le bruit
# Monte-Carlo domine : couper le budget y brouille le plus la trajectoire.
#
# ## 🔑 POURQUOI CE TEST EST BON MARCHE ET CONCLUANT : ON A DEJA LE CORRIGE
#
# Six graines sont mesurees a PLEIN budget sur `r75x2` a 2 nm, plage complete, sans surcharge :
#
#     42 -> 0/1617      77 -> 547/2231 ✅      101 -> 0/1630
#    202 -> 0/1646     303 -> 0/1680          404 -> 372/2016 ✅
#
# On valide donc un criblage bon marche contre une VERITE TERRAIN qui existe deja.
#
# ## 🔒 LA REGLE DE DECISION, ECRITE AVANT LA MESURE
#
#   77 et 404 ressortent SEULES en tete   -> la qualite d'une graine TRAVERSE le budget.
#                                            Le balayage a deux etages est valide.
#   elles n'en ressortent pas             -> la qualite ne traverse pas. On abandonne le
#                                            balayage, l'union simple de §8.2quater reste
#                                            la reponse.
#   une des quatre NULLES ressort         -> FAUX POSITIF. Pire que l'echec ci-dessus : le
#                                            criblage couterait des runs pleins pour rien.
#
# ## CE QUI EST CHANGE, ET CE QUI NE L'EST PAS
#
# UNE SEULE VARIABLE : la profondeur Monte-Carlo, coupee d'un facteur 4.
#
#     n_screen_runs        50  -> 12
#     robustness_num_runs 300  -> 75
#     consensus_num_runs  300  -> 75
#
# 🔴 `dp_top_k` reste a 100. Il regle la LARGEUR DE RECHERCHE de la DP, pas un nombre de
# tirages : le toucher ferait deux variables et le test ne dirait plus rien. Meme raison pour
# la plage de blocs, qui reste COMPLETE (§2 : la restreindre VIDE le solveur).
#
# ⚠️ A 75 tirages, la granularite minimale au-dessus de zero vaut 1/75 = 1,33 %. Un taux de
# plantage lu ici ne se compare donc PAS chiffre a chiffre a un taux lu a 300. Ce qui se
# compare, c'est le VERDICT binaire deposable / pas deposable -- et la falaise (100 % ou ~1 %,
# rien entre les deux) le rend lisible meme a 75.
#
# ## USAGE
#
#     bash scripts/batch_mc_reduit.sh 404 42 202        # un slot
#     bash scripts/batch_mc_reduit.sh 77 101 303        # l'autre, en parallele
#
# Il SAUTE toute graine dont l'artefact etiquete existe deja avec `verdict = OK`, donc il se
# relance sans reflechir.

set -u

# 🔴 LE PLAFOND NE SE BAISSE PAS PARCE QUE LE BUDGET BAISSE. `bench_examples.py:171` fait
# rendre None a `wait_for` au-dela -- ce qui RESSEMBLE a un resultat. Quatre mesures de 91 min
# ont ete detruites ainsi le 2026-08-22, coupees a 98,9 %. Un plafond trop grand ne coute rien.
export CERTUS_BENCH_TIMEOUT_S=38400

export CERTUS_PROBE_OVERRIDES="n_screen_runs=12,robustness_num_runs=75,consensus_num_runs=75"
export CERTUS_PROBE_TAG=mcreduit4x

PY="${CERTUS_PY:-C:/envs/certus/Scripts/python.exe}"
J="reports/mc_reduit_2026-08-22"
mkdir -p "$J"

if [ "$#" -eq 0 ]; then
  echo "usage: bash scripts/batch_mc_reduit.sh <graine> [graine...]" >&2
  exit 2
fi

deja_fait() {   # $1 = graine  -> 0 si un artefact etiquete et OK existe
  "$PY" - "$1" <<'PYEOF'
import glob, json, sys
graine = int(sys.argv[1])
for f in glob.glob(f"reports/blocs_vs_plantage_r75x2_deep_s{graine:03d}_mcreduit4x*.json"):
    try:
        d = json.load(open(f, encoding="utf-8"))
    except (OSError, ValueError):
        continue
    # 🔴 `verdict != OK` NE COMPTE PAS comme fait : un artefact sans strategie est le
    # symptome d'un plafond atteint, pas une mesure.
    if d.get("verdict") == "OK" and (d.get("strategies") or []):
        print(f)
        sys.exit(0)
sys.exit(1)
PYEOF
}

echo "[mc4x] DEMARRAGE $(date '+%Y-%m-%d %H:%M:%S')"
echo "[mc4x] interpreteur : $PY"
echo "[mc4x] surcharges   : $CERTUS_PROBE_OVERRIDES  [$CERTUS_PROBE_TAG]"
echo "[mc4x] plafond      : ${CERTUS_BENCH_TIMEOUT_S} s"
echo "[mc4x] graines      : $*"
echo

for graine in "$@"; do
  if art=$(deja_fait "$graine"); then
    echo "[mc4x] ⏭  graine $graine DEJA FAITE -- $art"
    continue
  fi
  echo "=========================================================================="
  echo "[mc4x] graine $graine -- demarrage $(date '+%H:%M:%S')"
  echo "=========================================================================="
  t0=$(date +%s)
  # SYNCHRONE. 🔴 On n'attend JAMAIS l'apparition d'un artefact comme signal de fin : la sonde
  # l'ecrit AVANT sa synthese, et une chaine qui le guettait a lance la mesure suivante 10 s
  # trop tot le 2026-08-21 -- « RuntimeError: QThread has been deleted ».
  "$PY" scripts/probe_blocs_vs_plantage.py r75x2 deep 0 0 2.0 0 "$graine" \
      > "$J/journal_s${graine}_mc4x.log" 2>&1
  code=$?
  echo "[mc4x] graine $graine EXIT=$code en $(( ($(date +%s) - t0) / 60 )) min -- $(date '+%H:%M:%S')"
  # 🔴 Un EXIT non nul se DIT et n'arrete pas la campagne : les autres graines gardent leur
  # valeur, et la regle de decision ci-dessus se lit sur ce qui existe.
  [ $code -ne 0 ] && echo "[mc4x] 🔴 graine $graine a echoue -- cherche « WAIT_TIMEOUT= » dans son journal"
  echo
done

echo "[mc4x] TERMINE $(date '+%Y-%m-%d %H:%M:%S')"
