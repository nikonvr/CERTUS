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
#   scripts/ab_compare.sh <fichier[,fichier2,...]> <ref-git> <module> <n_paires> \
#       [options-du-banc]
#
# Le premier argument accepte UN fichier (usage historique, inchange) ou une
# LISTE de fichiers separes par des virgules. Les espaces autour des virgules
# sont toleres ; la liste doit alors etre entre guillemets.
#
# Exemple — un seul fichier, verifier le correctif de sur-souscription PGLOBAL
# sur DESIGN :
#   scripts/ab_compare.sh certus/physics/certus_optimizers.py 2572f46^ design 4 \
#       --auto-yes --time-cost
#
# Exemple — plusieurs fichiers, le commit 190a37d (compute_layer_profile) sur STRAT :
#   scripts/ab_compare.sh \
#       certus/core/certus_strat_robustness.py,certus/core/certus_strat_consensus.py \
#       "190a37d^" strat 4 --auto-yes
#
# 🔴 POURQUOI ALTERNER TOUS LES FICHIERS D'UN CHANGEMENT, ET PAS UN SEUL.
# Un changement qui touche plusieurs fichiers ne se bascule que d'un bloc. Sur
# 190a37d, ne faire basculer que certus_strat_robustness.py rendrait l'ancienne
# signature de _test_strategy_robustness_task — qui ne connait pas le mot-cle
# compute_layer_profile — face a un certus_strat_consensus.py reste en version
# HEAD, qui continue de le passer. Au mieux un TypeError bien visible ; au pire,
# et c'est le cas ici, l'exception est avalee par le `except` englobant : les
# candidats concernes sont silencieusement ecartes et le bras SANS parait
# spectaculairement plus rapide. On mesurerait un gain entierement faux.
# D'ou la verification prealable et la bascule groupee ci-dessous.
#
# <ref-git> est la version SANS le changement : typiquement `<commit>^` si le
# changement est deja commite, ou `HEAD` s'il est encore dans l'arbre de travail.
#
# Restauration : le contenu de l'arbre de travail de CHAQUE fichier est sauvegarde
# avant la premiere bascule et remis en place a la sortie — fin normale, erreur,
# Ctrl-C (INT) ou TERM. Une restauration partielle laisserait le depot dans un
# melange de deux versions, incoherent et silencieux : le trap traite donc tous
# les fichiers, et il est idempotent.
#
# Resultat attendu : compter les paires gagnantes, pas faire une moyenne. Une
# metrique stable aide — COST_US_PER_CALL plutot que RUN_S sur DESIGN, dont le
# temps total va naturellement de 43 a 93 s.
#
# 🔴 AB_WARMUP=1 — OBLIGATOIRE DES QUE LA LISTE CONTIENT UN FICHIER A NOYAUX @njit.
# Numba tient un cache sur disque dans certus/*/__pycache__/*.nbi, dont la cle est
# l'empreinte (mtime, taille) du fichier source. `switch_to` recopie par `cp -f`,
# donc CHAQUE bascule remet le mtime a maintenant et invalide le cache : le run
# qui suit paie la recompilation complete.
#
# Mesure du 2026-08-05 sur STRAT, machine au repos : 145,3 s a froid contre 44,1
# et 37,7 s a chaud. La compilation pese donc ~105 s, soit 72 % du RUN_S a froid.
#
# Et ce n'est pas qu'du bruit, c'est un BIAIS ORIENTE : le bras qui contient le
# plus de code a compiler paie la recompilation la plus longue, et l'A/B attribue
# cet ecart a son cout d'EXECUTION. Sur le balayage POEM, le faux positif tombe
# exactement dans le sens attendu — le pire cas possible.
#
# AB_WARMUP=1 insere un run jete apres chaque bascule. Il double le cout de la
# campagne et supprime le biais.
#
#   AB_WARMUP=1 bash scripts/ab_compare.sh "a.py,b.py" "<commit>^" strat 4 --auto-yes

set -u

FILES_ARG="${1:?fichier(s) a alterner — un chemin, ou plusieurs separes par des virgules}"
REF="${2:?reference git (ex: <commit>^)}"
MODULE="${3:?module}"
PAIRS="${4:-3}"
shift 4 || shift $#
OPTS=("$@")

cd "$(dirname "$0")/.." || exit 1

PY=.venv/Scripts/python.exe
[ -x "$PY" ] || PY=python

# --- decoupage du premier argument : "a.py,b.py" -> tableau FILES -------------
FILES=()
IFS=',' read -r -a _RAW_FILES <<< "$FILES_ARG"
for _raw in "${_RAW_FILES[@]}"; do
    _f="${_raw#"${_raw%%[![:space:]]*}"}"   # retire les espaces de tete
    _f="${_f%"${_f##*[![:space:]]}"}"       # retire les espaces de queue
    [ -n "$_f" ] && FILES+=("$_f")
done
[ "${#FILES[@]}" -gt 0 ] || { echo "aucun fichier a alterner"; exit 1; }

# --- sauvegarde / restauration : TOUS les fichiers, toujours -----------------
TMPD=$(mktemp -d) || { echo "mktemp -d a echoue"; exit 1; }
BACKUPS=()   # contenu de l'arbre de travail (bras AVEC)
REFCOPY=()   # contenu a la reference        (bras SANS)

restore() {
    local _st=$? _i
    for _i in "${!BACKUPS[@]}"; do
        [ -f "${BACKUPS[$_i]}" ] || continue
        cp -f -- "${BACKUPS[$_i]}" "${FILES[$_i]}" 2>/dev/null \
            || echo "ATTENTION : restauration de ${FILES[$_i]} IMPOSSIBLE" >&2
    done
    return $_st
}

cleanup() {
    local _st=$?
    restore
    rm -rf -- "$TMPD"
    return $_st
}

trap cleanup EXIT
trap 'echo; echo "interruption — restauration des ${#FILES[@]} fichier(s)"; cleanup; trap - EXIT; exit 130' INT
trap 'cleanup; trap - EXIT; exit 143' TERM

# --- verifications PREALABLES : tout ou rien --------------------------------
git rev-parse --verify --quiet "$REF" >/dev/null 2>&1 || {
    echo "reference git illisible : $REF"; exit 1
}

ERRORS=()
for _f in "${FILES[@]}"; do
    [ -f "$_f" ] || ERRORS+=("absent de l'arbre de travail : $_f")
    git cat-file -e "HEAD:$_f" 2>/dev/null || ERRORS+=("absent a HEAD : $_f")
    git cat-file -e "$REF:$_f" 2>/dev/null || ERRORS+=("absent a $REF : $_f")
done
if [ "${#ERRORS[@]}" -gt 0 ]; then
    echo "A/B non lance — un A/B partiel melangerait deux versions du code :" >&2
    for _e in "${ERRORS[@]}"; do echo "  - $_e" >&2; done
    exit 1
fi

# --- extraction unique des deux versions de chaque fichier ------------------
# La bascule se resume ensuite a des copies : elle est rapide, et un git show
# qui echoue en cours de route ne peut plus tronquer un fichier du depot.
for _i in "${!FILES[@]}"; do
    _f="${FILES[$_i]}"
    BACKUPS[$_i]="$TMPD/cur_$_i"
    REFCOPY[$_i]="$TMPD/ref_$_i"
    cp -- "$_f" "${BACKUPS[$_i]}" || { echo "sauvegarde de $_f impossible"; exit 1; }
    git show "$REF:$_f" > "${REFCOPY[$_i]}" || { echo "lecture de $REF:$_f impossible"; exit 1; }
done

switch_to() {   # $1 = nom du tableau source (BACKUPS ou REFCOPY)
    local _src _i
    for _i in "${!FILES[@]}"; do
        eval "_src=\${$1[$_i]}"
        cp -f -- "$_src" "${FILES[$_i]}" || {
            echo "bascule de ${FILES[$_i]} impossible" >&2; exit 1
        }
    done
}

echo "A/B alterne : ${#FILES[@]} fichier(s)   reference=$REF   module=$MODULE   paires=$PAIRS"
for _f in "${FILES[@]}"; do echo "  - $_f"; done
echo

warmup() {   # run jete apres une bascule, pour ne pas mesurer la compilation numba
    [ "${AB_WARMUP:-0}" = "1" ] || return 0
    printf '  (chauffe) '
    "$PY" -u scripts/bench_examples.py "$MODULE" "${OPTS[@]}" 2>&1 \
        | grep -E '^RUN_S' | tr '\n' ' '
    echo
}

for i in $(seq 1 "$PAIRS"); do
    switch_to REFCOPY
    warmup
    printf 'paire %s  SANS : ' "$i"
    "$PY" -u scripts/bench_examples.py "$MODULE" "${OPTS[@]}" 2>&1 \
        | grep -E '^(RUN_S|COST_US_PER_CALL|RESULT)' | tr '\n' ' '
    echo

    switch_to BACKUPS
    warmup
    printf 'paire %s  AVEC : ' "$i"
    "$PY" -u scripts/bench_examples.py "$MODULE" "${OPTS[@]}" 2>&1 \
        | grep -E '^(RUN_S|COST_US_PER_CALL|RESULT)' | tr '\n' ' '
    echo
done

echo
echo "TERMINE — compter les paires gagnantes, pas la moyenne."
