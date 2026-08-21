#!/usr/bin/env bash
# SUITE de chaine_2026-08-21_apresmidi.sh -- LA question la plus informative qui reste.
#
# 🔑 CE QU'ELLE TRANCHE. Sur r75x2 a 2 nm on n'a que DEUX graines mesurees : la 77 trouve
# 547 deposables nativement, la 42 en trouve ZERO sur 1617. Deux points ne permettent aucune
# probabilite. Deux graines de plus, SANS rampes, disent laquelle des deux est l'exception.
#
# 🔴 ET ELLE N'ATTEND PLUS UN ARTEFACT -- LECON PAYEE LE 2026-08-21 A 15h33.
#
# L'ancienne version attendait l'apparition du JSON de la mesure precedente. Or la sonde
# ecrit desormais son artefact AVANT sa synthese (correctif du meme jour, pour qu'un print
# ne puisse plus detruire une mesure). L'artefact apparait donc alors que le processus vit
# encore, et la chaine a lance le run suivant 10 s avant que `couvfull` ne finisse.
#
#   15:33:15  la chaine voit l'artefact et demarre la graine 101
#   15:33:22  couvfull : « Critical error in parallel worker for block 3 »
#   15:33:25  idem blocs 2 et 1 -- RuntimeError: QThread has been deleted
#
# ⚠️ La causalite n'est PAS etablie : correlation temporelle a 7 s, et un plantage Qt de
# fin de vie peut avoir d'autres causes. Mais le SIGNAL est faux quoi qu'il en soit, et
# « une mesure, une machine » interdit le recouvrement. On attend donc le marqueur de fin
# de la chaine precedente, qui n'est ecrit qu'apres le retour du processus.
set -u
cd /c/certus
PY="C:/envs/certus/Scripts/python.exe"
J="reports/nuit_multiseed_20260821"

echo "[soir] attente du marqueur de fin de la chaine de l'apres-midi"
until grep -q "CHAINE COMPLETE" "$J/journal_chaine.log" 2>/dev/null; do sleep 60; done
echo "[soir] chaine de l'apres-midi terminee -- $(date +%H:%M:%S)"

for g in 101 202; do
  echo "[soir] === r75x2 NU a la graine $g ==="
  CERTUS_BENCH_TIMEOUT_S=5400 "$PY" scripts/probe_blocs_vs_plantage.py \
      r75x2 deep 0 0 2.0 0 "$g" > "$J/journal_nu_s$g.log" 2>&1
  echo "[soir] graine $g terminee, EXIT=$? -- $(date +%H:%M:%S)"
done
echo "[soir] CHAINE DU SOIR COMPLETE"
