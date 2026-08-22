#!/usr/bin/env bash
# BATCH DE LA NUIT DU 2026-08-21 au 22 -- quatre mesures, strictement sequentielles.
#
# ## 🔑 CE QU'IL TRANCHE, ET DANS QUEL ORDRE
#
# Les deux premieres repondent a LA question de fond, et elles passent en premier pour que le
# resultat existe meme si la nuit tourne court :
#
#     r75x2 NU, sans rampes, graines 101 puis 202
#
#   On n'a que DEUX graines mesurees nues sur ce composant a 2 nm : la 77 trouve 547
#   strategies deposables, la 42 en trouve ZERO sur 1617. Deux points ne permettent aucune
#   probabilite. La regle de decision est ecrite AVANT la mesure, en §8.2ter de
#   docs/REPRENDRE_ICI.md -- la lire la-bas, pas la reinventer ici.
#
# Les deux dernieres consolident le chiffre LIVRE :
#
#     r75x2-2nm (config livree), graines 101 puis 202
#
#   La 101 avait ete lue hier DANS UN JOURNAL parce que le run a ete arrete avant d'ecrire son
#   artefact -- SEEL 0,5707 au bloc 10. Un chiffre publie doit etre re-derivable depuis un
#   artefact (§7bis) : on le refait proprement, sur la plage complete.
#
# ## 🔴 LES TROIS LECONS DU 2026-08-21 QUI SONT CABLEES ICI
#
# 1. ON N'ATTEND JAMAIS UN ARTEFACT COMME SIGNAL DE FIN. La sonde ecrit son artefact AVANT sa
#    synthese, depuis le correctif du matin -- pour qu'un print ne puisse plus detruire une
#    mesure. Une chaine qui guettait ce fichier a donc lance la mesure suivante 10 s avant la
#    fin de la precedente, et le run mourant a rendu « RuntimeError: QThread has been
#    deleted ». Ici chaque sonde est appelee SYNCHRONEMENT : le shell attend son retour.
#
# 2. UNE MESURE, UNE MACHINE. Le pipeline sature tous les coeurs en prange. Rien en parallele,
#    ni tests, ni lint, ni recherche recursive.
#
# 3. UN AFFICHAGE NE DOIT PAS POUVOIR DETRUIRE UNE MESURE. La sonde consigne desormais avant
#    de raconter, et les 66 scripts qui impriment de l'Unicode protegent leur console.
#
# ## Sortie
#
# Un journal par mesure dans reports/nuit_2026-08-21/, plus un recapitulatif final lisible.
set -u
cd /c/certus
PY="C:/envs/certus/Scripts/python.exe"
J="reports/nuit_2026-08-21"
mkdir -p "$J"

# 🔴 LE PLAFOND, ET IL A COUTE UNE NUIT ENTIERE LE 2026-08-21.
#
# `bench_examples.py:171` : DEFAULT_TIMEOUT_MS = CERTUS_BENCH_TIMEOUT_S x 1000, defaut 1800 s.
# Au-dela, `wait_for` ABANDONNE et rend None -- ce qui RESSEMBLE a un resultat.
#
# 📏 La premiere version de ce script exportait 5400. Les quatre mesures ont alors dure
# EXACTEMENT 90 min chacune et rendu SURCHARGES_NON_APPLIQUEES ou ECHEC_RESULT_NONE, avec
# l'empreinte « WAIT_TIMEOUT=5400 s — aucune emission recue ». Elles avaient pourtant fait
# 13 a 16 nombres de blocs : le travail etait presque fini quand le plafond l'a coupe.
#
# 🔑 5400 EST UN PLANCHER, PAS UNE VALEUR. Les autres pilotes du depot l'ecrivent ainsi
# depuis toujours -- `max(5400, mn * 60 * 4)` dans batch_nuit_2026-08-19.py, _20.py et
# batch_diagnostic_elite.py : QUATRE FOIS la duree attendue. C'est CLAUDE.md §21 qui m'a
# egare en disant « mets 5400 et laisse finir », phrase ecrite pour une charge plus courte.
#
# Duree mesuree d'un run pleine plage sur r75x2 a 2 nm : 2 h 39 = 9540 s (2026-08-21).
# Donc 4 x 160 min = 38400 s.
export CERTUS_BENCH_TIMEOUT_S=38400

mesure() {   # $1 = composant · $2 = graine · $3 = etiquette lisible
  local comp="$1" graine="$2" nom="$3"
  local log="$J/journal_${nom}.log"
  echo "=========================================================================="
  echo "[nuit] $nom -- composant $comp, graine $graine -- demarrage $(date '+%H:%M:%S')"
  echo "=========================================================================="
  local t0=$(date +%s)
  # SYNCHRONE : le shell attend le retour du processus. Voir la lecon 1 du bandeau.
  "$PY" scripts/probe_blocs_vs_plantage.py "$comp" deep 0 0 2.0 0 "$graine" > "$log" 2>&1
  local code=$?
  local dt=$(( ($(date +%s) - t0) / 60 ))
  echo "[nuit] $nom termine EXIT=$code en ${dt} min -- $(date '+%H:%M:%S')"
  # 🔑 On lit tout de suite ce qui compte, pour que le recapitulatif existe meme si la suite
  # echoue. `Best strategy ready` porte le score de tete par nombre de blocs.
  grep -oE "\[Block [0-9]+\] Best strategy ready: RMSE=[0-9.]+" "$log" | tail -20 \
      | sed "s/^/    /" || true
  echo
}

echo "[nuit] BATCH DEMARRE $(date '+%Y-%m-%d %H:%M:%S')"
echo "[nuit] machine : $(nproc 2>/dev/null || echo '?') coeurs logiques"
echo

# --- LA QUESTION DE FOND, en premier -----------------------------------------
mesure r75x2      101 nu_s101
mesure r75x2      202 nu_s202

# --- LA CONSOLIDATION DU CHIFFRE LIVRE ---------------------------------------
mesure r75x2-2nm  101 livree_s101
mesure r75x2-2nm  202 livree_s202

echo "=========================================================================="
echo "[nuit] RECAPITULATIF -- $(date '+%H:%M:%S')"
echo "=========================================================================="
"$PY" scripts/lire_nuit_2026-08-21.py || true
echo "[nuit] BATCH COMPLET $(date '+%Y-%m-%d %H:%M:%S')"
