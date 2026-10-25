# A13 — profil d'une évaluation de `strat_local_search` (Claude, 2026-10-23)

Code `ee6310e3` (`claude/2026-10-22`). `prof_stage.py.txt` : mise en place du scanner archivé (`r75x2`, deep), l'évaluateur de
l'étage (`native_evaluator` au corridor de recherche), le plan LOCAL_SEARCH du banc A10 `r75x2` graine 101, 20 évaluations de
300 tirages sur la même graine (comme l'étage), `NUMBA_NUM_THREADS=8`, `cProfile` et chronomètre autour des noyaux compilés.

| poste | ms par évaluation | part |
|---|---|---|
| `compute_batch_rmse` (spectres et RMSE des tirages) | 175,8 | 53 % |
| `simulate_stack_robustness_batch` (simulation du dépôt) | 140,4 | 43 % |
| `calculate_RT_batch_kernel` | 1,2 | < 1 % |
| préparation Python (tout le reste) | ≈ 12 | ≈ 3,5 % |
| total | 329 | |

Le bruit Sobol est déjà mis en cache par graine (`_get_cached_sobol_noise`) ; il ne coûte que si la graine change. Avec 2 300 à
3 900 évaluations par étage, 329 ms donnent 13 à 21 min, l'ordre de grandeur annoncé.

**Conclusion.** Un gain qui garde les bits hors des noyaux est borné à environ 3,5 % : non codé, la complexité ajoutée ne le
vaut pas. Les deux voies réelles demandent une décision de 👤 : (1) accélérer `compute_batch_rmse` ou la simulation dans le noyau,
à prouver au bit par `c1_diff` (risque : un ordre de sommation différent change les bits) ; (2) changer la recherche (présélection
à moins de tirages, puis contrôle à 300), à mesurer contre l'étage actuel avec une règle écrite d'avance. Non mesuré : la
répartition à 16 threads (machine partagée).
