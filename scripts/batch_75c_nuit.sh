#!/usr/bin/env bash
# LA SERIE 75 COUCHES EN ENTIER, AVEC LE CODE DE PRODUCTION ABOUTI -- nuit du 2026-08-22.
#
# 👤 : « lance le batch complet de tous les 75c integralement avec le code de production.
# Toutes les 30mn verifie la coherence des resultats et si probleme, corrige. »
#
# ## CE QUI REND CETTE CAMPAGNE DIFFERENTE DE CELLE DE LA SOIREE
#
# Le code a change entre les deux (`6f600b3`), et pas a la marge :
#
#   rate_by_swing               False -> True    le Rate se place ou il est NECESSAIRE
#   rate_max_variants_per_strategy  3 -> 40      contradiction A reparee
#   rate_variant_top_n            (neuf) 50      profond sur peu, au lieu de plat sur tous
#   rate_layers                 EXPORTE          on saura enfin dans quelles couches
#
# 🔴 LES ARTEFACTS DE LA SOIREE ONT DONC ETE ARCHIVES dans `reports/avant_leviers_2026-08-22/`.
# Les laisser en place aurait fait une campagne a DEUX versions de code : l'orchestrateur saute
# ce qui porte deja un artefact, il aurait donc melange des mesures anciennes et neuves sans
# que rien ne le dise. Table rase, une seule version.
#
# ## L'ORDRE, PAR VALEUR D'INFORMATION
#
#   1. r75x2      la reference : 3 graines sur 7 trouvaient AVANT. Le nouveau placement du
#                 Rate change-t-il cela ?
#   2. r75x0.5    celui qui ne trouve RIEN. C'est lui qui exercera l'ESCALADE MULTI-TEMOIN,
#                 le chemin neuf qui n'a jamais tourne en vrai.
#   3. r75x1.5    0,4255 nm avant. Le Rate par besoin fait-il mieux ?
#   4. r75x1.75   0,4749 nm avant, et le seul jamais mesure en `deep` avant hier
#   5. 75c        il passe largement (852 deposables). L'union fait-elle mieux ?
#   6. r75x2-2nm  la config livree, avec ses rampes
#
# ## LE BUDGET, ET IL EST CALCULE POUR DOUZE HEURES
#
# 1 h de recherche par composant -> 2 graines a ~50 min, puis la notation finale (~1 h). Six
# composants a ~2 h font ~12 h. ⚠️ Avec deux graines seulement, un composant qui ne trouve rien
# a 67 % de chances d'etre un vrai negatif si p vaut 3/7 -- c'est assume, et c'est ce qui laisse
# le temps a l'escalade multi-temoin de tourner sur ceux qui echouent.
#
# 🔒 REPRENABLE : tout artefact `verdict = OK` deja present est saute. Une relance apres coupure
# ne refait rien.

set -u
PY="${CERTUS_PY:-C:/envs/certus/Scripts/python.exe}"
J="reports/nuit75_2026-08-22"
mkdir -p "$J"

BUDGET="${CERTUS_BUDGET:-1h}"
# 🔑 L'escalade s'arrete au MINIMUM de temoins qui rend faisable : chaque coupure GELE de
# l'erreur dans la piece, on n'en prend pas une de plus que necessaire.
MAXTEMOINS="${CERTUS_MAXTEMOINS:-4}"
COMPOSANTS="r75x2 r75x0.5 r75x1.5 r75x1.75 75c r75x2-2nm"

echo "=========================================================================="
echo "[nuit75] DEMARRAGE $(date '+%Y-%m-%d %H:%M:%S')"
echo "[nuit75] code       : $(git rev-parse --short HEAD)"
echo "[nuit75] composants : $COMPOSANTS"
echo "[nuit75] budget     : $BUDGET par composant · objectif meilleur · escalade jusqu'a $MAXTEMOINS temoins"
echo "[nuit75] constant   : deep · fente 2,0 nm · plage COMPLETE · notation sur 42 disjointe"
echo "=========================================================================="
echo

for comp in $COMPOSANTS; do
  echo "=========================================================================="
  echo "[nuit75] $comp -- demarrage $(date '+%H:%M:%S')"
  echo "=========================================================================="
  t0=$(date +%s)
  "$PY" scripts/orchestre_multigraine.py "$comp" \
      --budget "$BUDGET" \
      --objectif meilleur \
      --mode deep \
      --resolution 2.0 \
      --graine-notation 42 \
      --multitemoin "$MAXTEMOINS" \
      --evenements \
      > "$J/journal_${comp}.log" 2>&1
  code=$?
  echo "[nuit75] $comp EXIT=$code en $(( ($(date +%s) - t0) / 60 )) min -- $(date '+%H:%M:%S')"
  # 🔴 Un echec se DIT et n'arrete pas la campagne : un composant qui ne trouve rien EST un
  # resultat, et les suivants gardent leur valeur.
  grep -E "RESULTAT CITABLE|MULTI-TEMOIN|MINIMUM TROUVE|Aucune realisation|NON ESSAYEES|🔴" \
      "$J/journal_${comp}.log" | tail -6 | sed 's/^/    /' || true
  echo
done

echo "=========================================================================="
echo "[nuit75] TERMINE $(date '+%Y-%m-%d %H:%M:%S')"
"$PY" scripts/coherence_campagne.py "$J" || true
echo "=========================================================================="
