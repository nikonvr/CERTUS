#!/usr/bin/env bash
# CAMPAGNE AUTONOME SUR LA SERIE D'ECHELLE DU RANDOM75 -- lancee le 2026-08-22 au soir.
#
# 👤 : « lance sur le code de production les differents designs a 75c de facon autonome ».
#
# ## 🔑 LA QUESTION QUE CETTE CAMPAGNE POSE, ET POURQUOI ELLE EST NEUVE
#
# La serie d'echelle est la SEULE EXPERIENCE CONTROLEE du projet : 75 couches, meme structure,
# memes materiaux, meme substrat, meme grille -- seule l'epaisseur optique varie. Son tableau
# de reference, mesure a UNE SEULE GRAINE (42), dit :
#
#     x0,5    ECHOUE      0 deposable / 375    crash 48 %
#     x1      passe     241 deposables / 662   crash  0 %   SEEL 0,272
#     x1,5    limite      1 deposable  / 704
#     x2      ECHOUE      0 deposable / 404    crash 100 %
#
# 🔴 OR LE 2026-08-22 A MONTRE QU'UN « 0 DEPOSABLE » PEUT ETRE UN ACCIDENT DE GRAINE, PAS UNE
# PROPRIETE DU COMPOSANT. Sur `r75x2`, les graines 42, 101, 202 et 303 rendent zero -- et les
# graines 404 et 505 rendent 372 et 311 deposables, SEEL 0,5599 et 0,6112 nm. Le « ECHOUE » de
# la ligne x2 etait donc FAUX : il decrivait une realisation, pas un empilement.
#
# 🔑 **Si c'est vrai de x2, ce peut l'etre de x1,5 et de x0,5.** Et alors tout le tableau
# ci-dessus -- qui sert de jeu de CALIBRATION a un futur predicteur -- serait a refaire. C'est
# la question la plus informative qui reste ouverte sur ce composant.
#
# ## L'ORDRE, ET IL EST CHOISI PAR VALEUR D'INFORMATION DECROISSANTE
#
# 👤 s'absente : si la campagne est interrompue, ce qui aura tourne doit etre le plus utile.
#
#   1. r75x1.75  LE TROU DE LA SERIE -- jamais mesure en `deep`. Aucune valeur de reference
#                n'existe, donc tout ce qu'il rendra sera neuf.
#   2. r75x1.5   « limite » a 1 deposable, et cet unique point vient d'un run `elargi`. Le
#                multiseed dit s'il est vraiment a la frontiere ou si la 42 etait malchanceuse.
#   3. r75x0.5   « echoue » -- mais a 48 % de plantage, PAS a 100 %. Un mode d'echec DIFFERENT
#                de celui de x2, donc une reponse au multiseed potentiellement differente.
#   4. 75c       il passe deja largement (852 deposables, SEEL 0,2598 a la graine 42, `deep`,
#                2 nm). La question n'est pas la faisabilite mais si l'union fait mieux.
#
# 📌 `r75x2` n'y est PAS : sa serie de graines et son union sont mesurees du jour meme
# (SEEL 0,5642 nm sur l'union 404+505, notee sur la graine 42 disjointe).
#
# ## CE QUI EST TENU CONSTANT, ET POURQUOI
#
#   mode deep · fente 2,0 nm · plage de blocs COMPLETE · aucune surcharge
#
# 🔴 La fente de 2,0 nm est celle des artefacts `deep` existants (`75c_deep_s042.json`), donc
# la comparaison reste apples-to-apples. ⚠️ Restreindre la plage de blocs VIDE le solveur
# (§2 de REPRENDRE_ICI) : elle reste complete, meme si c'est plus long.
#
# La notation finale se fait sur la graine 42, DISJOINTE de l'echelle de generation
# (101, 202, ...). C'est la garde anti-malediction du vainqueur, dont le cout est mesure a
# +0,55 % et le canal a +12,9 %.
#
# ## BUDGET
#
# 2 h par composant, `--objectif meilleur` (on n'arrete pas au premier succes : les trois
# graines qui trouvent sur r75x2 s'etalent de 0,5599 a 0,6112, soit 9,2 %). A ~44 min par run
# et 2 slots, cela laisse ~4 graines par composant -- de quoi atteindre ~89 % de chance de
# trouver si le composant se comporte comme r75x2 (p = 3/7).
#
# Total : ~8 h. Reprenable : tout artefact `verdict = OK` deja present est saute.

set -u

PY="${CERTUS_PY:-C:/envs/certus/Scripts/python.exe}"
J="reports/serie75_2026-08-22"
mkdir -p "$J"

BUDGET="${CERTUS_BUDGET:-2h}"
COMPOSANTS="r75x1.75 r75x1.5 r75x0.5 75c"

echo "=========================================================================="
echo "[serie75] DEMARRAGE $(date '+%Y-%m-%d %H:%M:%S')"
echo "[serie75] composants : $COMPOSANTS"
echo "[serie75] budget     : $BUDGET par composant · objectif meilleur"
echo "[serie75] constant   : deep · fente 2,0 nm · plage COMPLETE · notation sur 42 disjointe"
echo "=========================================================================="
echo

for comp in $COMPOSANTS; do
  echo "=========================================================================="
  echo "[serie75] $comp -- demarrage $(date '+%H:%M:%S')"
  echo "=========================================================================="
  t0=$(date +%s)
  "$PY" scripts/orchestre_multigraine.py "$comp" \
      --budget "$BUDGET" \
      --objectif meilleur \
      --mode deep \
      --resolution 2.0 \
      --graine-notation 42 \
      --evenements \
      > "$J/journal_${comp}.log" 2>&1
  code=$?
  echo "[serie75] $comp EXIT=$code en $(( ($(date +%s) - t0) / 60 )) min -- $(date '+%H:%M:%S')"
  # 🔴 Un echec se DIT et n'arrete pas la campagne : les composants suivants gardent leur
  # valeur, et un composant qui ne trouve rien est lui-meme un resultat.
  grep -E "RESULTAT CITABLE|Aucune realisation|NON ESSAYEES|🔴" "$J/journal_${comp}.log" \
      | tail -5 | sed 's/^/    /' || true
  echo
done

echo "=========================================================================="
echo "[serie75] TERMINE $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================================================="
