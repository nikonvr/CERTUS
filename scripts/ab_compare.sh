#!/bin/bash
# A/B ALTERNE entre le code courant et une version de reference.
#
# Pourquoi alterner : la machine derive. Sur la session du 2026-08-02, le MEME
# code est passe de 743 a 990 us/evaluation en deux heures (thermique,
# synchronisation Google Drive, autre session pytest en parallele). Un A/B mesure
# en sequence — 3 runs avant, puis 3 runs apres — attribue cette derive au
# changement. En alternant, on compte des PAIRES : si les N paires vont dans le
# meme sens, le gain est reel quelle que soit la derive.
#
# Usage :
#   scripts/ab_compare.sh <fichier> <ref-git> <module> <n_paires> [options-du-banc]
#
# Exemple — verifier le correctif de sur-souscription PGLOBAL sur DESIGN :
#   scripts/ab_compare.sh certus/physics/certus_optimizers.py 2572f46^ design 4 \
#       --auto-yes --time-cost
#
# <ref-git> est la version SANS le changement : typiquement `<commit>^` si le
# changement est deja commite, ou `HEAD` s'il est encore dans l'arbre de travail.
#
# Resultat attendu : compter les paires gagnantes, pas faire une moyenne. Une
# metrique stable aide — COST_US_PER_CALL plutot que RUN_S sur DESIGN, dont le
# temps total va naturellement de 43 a 93 s.

set -u

FILE="${1:?fichier a alterner}"
REF="${2:?reference git (ex: <commit>^)}"
MODULE="${3:?module}"
PAIRS="${4:-3}"
shift 4 || shift $#
OPTS=("$@")

cd "$(dirname "$0")/.." || exit 1

PY=.venv/Scripts/python.exe
[ -x "$PY" ] || PY=python

SAVED=$(mktemp)
git show "HEAD:$FILE" > "$SAVED" 2>/dev/null || {
    echo "impossible de lire $FILE a HEAD"; exit 1
}

restore() {
    git checkout -q HEAD -- "$FILE" 2>/dev/null
    rm -f "$SAVED"
}
trap restore EXIT INT TERM

echo "A/B alterne : $FILE   reference=$REF   module=$MODULE   paires=$PAIRS"
echo

for i in $(seq 1 "$PAIRS"); do
    git show "$REF:$FILE" > "$FILE" || { echo "reference $REF illisible"; exit 1; }
    printf 'paire %s  SANS : ' "$i"
    "$PY" -u scripts/bench_examples.py "$MODULE" "${OPTS[@]}" 2>&1 \
        | grep -E '^(RUN_S|COST_US_PER_CALL|RESULT)' | tr '\n' ' '
    echo

    git checkout -q HEAD -- "$FILE"
    printf 'paire %s  AVEC : ' "$i"
    "$PY" -u scripts/bench_examples.py "$MODULE" "${OPTS[@]}" 2>&1 \
        | grep -E '^(RUN_S|COST_US_PER_CALL|RESULT)' | tr '\n' ' '
    echo
done

echo
echo "TERMINE — compter les paires gagnantes, pas la moyenne."
