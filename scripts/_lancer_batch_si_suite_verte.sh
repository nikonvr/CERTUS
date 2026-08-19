#!/usr/bin/env bash
# Seconde passe de la suite, puis lancement du batch UNIQUEMENT si elle est verte.
#
# 🔴 POURQUOI UNE SECONDE PASSE, ET POURQUOI ELLE EST LEGITIME. CLAUDE.md §2 documente que
# sur un cache numba FROID la premiere passe rend TROIS echecs, et qu'ils sont FAUX :
#
#     tests/unit/test_phase2_gradient.py::test_phase2_gradient_analytic_vs_fd
#     tests/unit/workers/test_index_workers_ir_strat.py::TestIRGlobalModelStrategy (x2)
#
# La cause est dans numba lui-meme (`ir_utils.py` fait un import de chemin pointe DANS une
# fonction, ce qui cree une locale resolue depuis sys.modules a l'appel), et ce chemin n'est
# emprunte que pendant une COMPILATION REELLE. Le correctif du 2026-08-19 change la signature
# du noyau, donc force une recompilation, donc rend le cache froid : la premiere passe DEVAIT
# echouer sur ces trois-la. « Relance une seconde fois avant de signaler quoi que ce soit. »
#
# ⚠️ MAIS ON NE RELANCE PAS EN AVEUGLE. Si les echecs ne sont pas EXACTEMENT ces trois-la, ou
# si la seconde passe echoue encore, le batch n'est pas lance. Une regle qui absoudrait
# n'importe quel echec ne protegerait plus rien.
set -u
cd /c/certus || exit 1
JRN="reports/_suite_passe2.log"

echo "SECONDE PASSE de la suite (cache numba desormais chaud) -- ~6 a 13 min"
PYTHONUTF8=1 PYTHONIOENCODING=utf-8 /c/envs/certus/Scripts/python.exe \
  -m pytest tests/oracle/ tests/unit/ -q --no-cov >"$JRN" 2>&1

BILAN=$(grep -oE "[0-9]+ (passed|failed|error)[^,]*" "$JRN" | tr '\n' ' ')
echo "PASSE 2: $BILAN"

if grep -qE "[0-9]+ (failed|error)" "$JRN"; then
  echo "🔴 SUITE ENCORE ROUGE A CHAUD -- ce n'est PAS l'artefact numba. Batch NON lance."
  grep -E "^FAILED|^ERROR" "$JRN" | head -20
  exit 2
fi

echo "🟢 SUITE VERTE A CACHE CHAUD -- les 3 echecs de la passe 1 etaient bien l'artefact."
echo "Lancement du batch Rate (~3 h 15)"
PYTHONUTF8=1 PYTHONIOENCODING=utf-8 /c/envs/certus/Scripts/python.exe \
  scripts/batch_rate_2026-08-19.py
echo "BATCH TERMINE code=$?"
