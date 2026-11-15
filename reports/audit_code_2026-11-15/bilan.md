# Audit du code CERTUS — bilan (2026-11-15)

Six lots de revue qualitative (`lot1` à `lot6`), métriques (`metriques.json`), double vérification de chaque défaut
critique ou majeur : relevé du lot, ma lecture, contre-vérificateur indépendant sans la conclusion
(`contre_verification.md`), preuve par la mesure quand c'était faisable (`preuves/`, chaque script se relance seul).
Liste détaillée et emplacements : `a_verifier.md`. Résultats STRAT touchés par le substrat : `recensement_sio2.md`.

**Verdicts.** CONFIRMÉ-M : reproduit par la mesure. CONFIRMÉ-L : deux ou trois lectures indépendantes concordantes,
non mesuré. Aucun défaut soumis n'a été RÉFUTÉ.

## 1. En une phrase

Le calcul optique central (TMM, conventions, oracle) est sain ; les résultats faux viennent des **raccords** : lecture
des fichiers et des substrats, passage de l'interface au calcul, comparaison de grandeurs qui ne se correspondent pas.

## 2. Notes sur 10, par lot

| critère | 1 physique | 2 core | 3 spline, workers | 4 utils, entrées | 5 UI a | 6 UI b | moyenne |
|---|---|---|---|---|---|---|---|
| Exactitude | 7 | 6 | 5 | 5 | 5 | 3 | **5,2** |
| Tests | 7 | 7 | 4 | 5 | 6 | 5 | **5,7** |
| Architecture | 5 | 5 | 4 | 5 | 5 | 4 | **4,7** |
| Lisibilité | 6 | 5 | 4 | 6 | 5 | 5 | **5,2** |
| Robustesse | 7 | 6 | 4 | 5 | 5 | 5 | **5,3** |
| Performance | 8 | 7 | 6 | — | 6 | 5 | **6,4** |
| Reproductibilité | 6 | 8 | 6 | 7 | — | — | **6,8** |

Couverture : physique, core, spline, utils lus en grande partie ; interface ≈ 18-19 % des lignes (flux UI → calcul,
sauvegarde, export, fermeture), le reste survolé.

## 3. Critiques — un résultat physique faux, sans message

| id | où | effet | verdict |
|---|---|---|---|
| C-L3 | SPLINE, `_njit_single_layer_mse_fused` (mode ratio) | R mesuré (ratio) comparé à R absolu : au film exact, RMS 1,8 point de R → ajustement R ou R+T vers un film faux | CONFIRMÉ-M |
| M-L5a ↑ | INDEX, `opt_strat` → objectif | `k_sub` du fichier entier lu avec l'indice des points masqués : λ min relevé de 150 nm → T modélisé faux jusqu'à 0,50 | CONFIRMÉ-M |
| M-L6g ↑ | RE, `_parse_re_index` | cellule n « 2,30 » (virgule) → n = 1,50 sans message | CONFIRMÉ-M |
| C-L6b | METAL, balayage d'épaisseur | coût sur R seul, seuil issu de la moyenne R/T/Rback → plage d'épaisseurs acceptables fausse | CONFIRMÉ-L (3) |
| C-L6a | évaluation de spectre | après un changement de réglage, l'ancienne courbe, l'ancien RMSE et l'ancien QWOT sont réaffichés et mis dans `last_result` | CONFIRMÉ-L (2) |
| M-L6a ↑ | RE, évaluation affichée | une colonne BK coche la face arrière pour **toutes** les colonnes, noBK comprises (le REWorker, lui, respecte chaque colonne) | CONFIRMÉ-L (2) |
| M-L6b ↑ | RE, `_compute_re_rmse` | après optimisation, RMSE du titre et de l'export calculé sur les épaisseurs **chargées** | CONFIRMÉ-L (2) |
| M-L6e ↑ | METAL, configuration | substrat non sauvé (revient à saphir), fenêtre λ écrasée au chargement de la cible | CONFIRMÉ-L (2) |

↑ : majeur au lot, relevé en critique par la contre-vérification ou la mesure.

## 4. Majeurs

Résultat faux dans un cas plausible :

| id | effet | verdict |
|---|---|---|
| C-L4 ↓ | STRAT : substrat « SiO2 » à n = 1,48625 au lieu de 1,45991 (550 nm), **juge de paix compris**, depuis au moins le 2026-05-27. 👤 : effet réel, pas catastrophique (STRAT robustes à l'indice du substrat) ; à chiffrer avant/après | CONFIRMÉ-M |
| M-L1 | INDEX : ε1 Tauc-Lorentz plafonnée à 1 dans le coût, pas dans le gradient (86/161 points) | CONFIRMÉ-M |
| M-L2 | STRAT : une graine rejetée disparaît du consensus (0,00705, devant une stratégie stable à 0,0081) | CONFIRMÉ-M |
| M-L3a | SPLINE : maillage des nœuds décodé non croissant | CONFIRMÉ-M |
| M-L4a, b, c | RE : `R45p` lu à 0° s ; « sans arrière » accentué → avec face arrière ; % lu en fraction (×100) | CONFIRMÉ-M |
| M-L5g | INDEX : épaisseur FFT divisée par l'indice du substrat ; SiO2/Si → bornes qui excluent la vraie épaisseur | CONFIRMÉ-M |
| M-L3c | SPLINE : points de secours (RMSE de graine ou 5 × pire) dans la courbe RMSE(d) | CONFIRMÉ-L (2), effet sur le corridor non mesuré |
| M-L5d | DESIGN : décocher « Oblique » change une cible R à 45° en cible T normale | CONFIRMÉ-L (3) |
| M-L6d | STRAT : tolérance d'épaisseur non sauvée → phase B photométrique au rechargement | CONFIRMÉ-L (2) |
| M-L6f | STRAT : export « N/A » pour H/L, substrat, couches ; « unseeded » ; SEEL absent | CONFIRMÉ-L (2) |

Perte de données, réglage ignoré, plantage :

| id | effet | verdict |
|---|---|---|
| M-L3b | fil générique : `KeyError`, `IndexError`, `TypeError`, `AttributeError` → aucun signal, Run SPLINE grisé | CONFIRMÉ-M |
| M-L5b | INDEX, FIELD, DESIGN : réglages sauvés non relus, ou non sauvés | CONFIRMÉ-L (2) |
| M-L5c | DESIGN : export Excel en échec (`if ep:` sur un tableau) après une optimisation | CONFIRMÉ-L (2) + mécanisme |
| M-L5e | lisseur : classeur source réécrit en place, non atomique, formes perdues | CONFIRMÉ-L (2) |
| M-L5f, M-L6c | MC de DESIGN et arrêt de RE : bouton actif, QThread lâché en marche, gel jusqu'à 5 min | CONFIRMÉ-L (2), plantage déduit |
| M-L4d | export d'un graphe zoomé : seulement la partie visible | CONFIRMÉ-L (2) |

Mineurs : 40 au total, dans les lots, non contre-vérifiés.

## 5. Ce qui est bien fait

Source TMM unique sous cliquet et oracle indépendant ; convention n − ik tenue ; tirages C2 fonctions pures de la
graine ; décisions datées et mesurées dans les docstrings ; garde-fous de publication et de licence ; accessibilité
(noms dérivés, contraste WCAG).

## 6. Corrections — ordre décidé avec 👤

Après ce bilan, un commit par défaut, test rouge sur le code d'avant, oracle avant/après, `c1_diff` pour le noyau.

1. Critiques mesurés : C-L3, M-L5a, M-L6g ; puis C-L6b, C-L6a, M-L6a, M-L6b, M-L6e.
2. Majeurs physiques : C-L4 (Sellmeier partout, juge de paix remesuré, invalidations dans `docs/ETAT_acquis.md`),
   M-L1, M-L2 (graine rejetée → stratégie rejetée), M-L3a, M-L4a-c, M-L5g (n initial du film), M-L3c, M-L5d, M-L6d, M-L6f.
3. Majeurs d'interface : M-L3b, M-L5b, M-L5c, M-L5e, M-L5f, M-L6c, M-L4d.

## 7. Limites

Interface lue à ≈ 18-19 % ; défauts CONFIRMÉ-L non exécutés ; mineurs non contre-vérifiés ; aucun défaut cherché dans
`studies/` ni les scripts.
