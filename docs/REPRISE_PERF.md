# Reprise — performance CERTUS

Écrit le 2026-08-02, pour l'agent (ou l'humain) qui prend la suite, éventuellement
sur une autre machine. **Tout chiffre de ce document a été mesuré**, jamais estimé.

À lire après `CLAUDE.md`. Ce document **corrige** `docs/PLAN_OPTIMISATION.md` sur
plusieurs points : voir §5.

---

## 0. Démarrage rapide — les cinq minutes qui font gagner des heures

### Vérifier l'environnement (30 s)

```bat
:: 1. Le venv charge-t-il bien LE code d'ici ? (un .pth a déjà pointé ailleurs)
.venv\Scripts\python.exe -c "import certus.physics.certus_opt_tmm as m; print(m.__file__)"

:: 2. Le hook d'auto-push vers le dépôt PUBLIC est-il neutralisé ?
dir .git\hooks\post-commit*        :: doit afficher post-commit.disabled

:: 3. L'oracle passe-t-il ? (8 s, 552 tests)
.venv\Scripts\python.exe -m pytest tests\oracle\ -q --no-cov
```

### Combien de temps coûte quoi

| Action | Durée |
|---|---|
| `pytest tests/oracle/ -q --no-cov` | **8 s** — à lancer après chaque modif de calcul |
| Suite complète `pytest tests/ -q --no-cov` | ~6 min |
| Banc FIELD / INDEX_SPLINE | 1–2 s |
| Banc INDEX | 7 s |
| Banc RE | 30 s |
| Banc METAL_SINGLE / BILAYER | 55–70 s |
| Banc DESIGN | 45–90 s (très dispersé) |
| Banc STRAT | 50–65 s |
| Une campagne A/B de 4 paires sur DESIGN | ~10 min → **tâche de fond** |

Le timeout de l'outil Bash est plafonné à **10 minutes** : toute campagne de
mesure doit partir en tâche de fond.

### Les deux commandes du quotidien

```bat
:: mesurer un module sur son vrai exemple
.venv\Scripts\python.exe scripts\bench_examples.py strat --auto-yes --sample

:: prouver un gain, en alternant les deux versions
bash scripts\ab_compare.sh certus\physics\certus_optimizers.py 2572f46^ design 4 --auto-yes --time-cost
```

### Ce qui est déjà rouge — ne pas partir à la chasse

**La suite a des fuites d'état entre tests.** Plusieurs fichiers passent
isolément et échouent dans une sélection large. Vérifié le 2026-08-02 :

| Test | En sélection large | Isolé | Statut |
|---|---|---|---|
| `test_certus_re.py::TestREAppSkeletonLoaders::test_re_app_skeletons_methods` | ❌ | ✅ | ✅ **corrigé** |
| `tests/unit/test_certus_ui.py` (4 échecs) | ❌ | ✅ 80 passed | ✅ **corrigé** |

✅ **Ces deux lignes sont résolues et le correctif est commité** — cause racine
trouvée le 2026-08-02 : `tests/ui/test_ui_module_imports.py` remplaçait des
objets-modules dans `sys.modules` sans les restaurer, ce qui faisait atterrir les
`monkeypatch.setattr("<module>.<nom>", …)` suivants sur une copie orpheline.
Détails et reste à faire dans **`docs/REPRISE_TESTS_ISOLATION.md`**.

Avant d'accuser ton changement : relancer le test **seul**. S'il passe, c'est une
fuite d'état pré-existante, pas toi. (Vérifié aussi en remettant le code d'origine.)

🔴 **Ne pas lancer deux sessions pytest en parallèle sur ce dépôt.** Deux
processus pytest simultanés se bloquent mutuellement — observé le 2026-08-02, les
deux à +0,08 s de CPU en 20 s de temps réel. Cause probable : le verrou de fichier
du cache numba (`configure_numba_env`, cf. `certus_strat_objectives.py:164`).

### Bruits de fond à ignorer

Ces messages apparaissent à chaque fois et n'indiquent aucun problème :

- Chaque `git commit` affiche `fatal: bad tree object …` et
  `failed to perform geometric repack`. C'est le commit orphelin `01047a1b`
  (arbre manquant) décrit dans `CLAUDE.md §5.4`. **Le commit réussit quand même** —
  vérifier avec `git log --oneline -1`, ne pas recommencer.
- `warning: ignoring broken ref refs/heads/desktop.ini` : idem, sans effet.

### Réflexe avant de croire à un gain

L'utilisateur a une règle explicite : **ne jamais annoncer un gain sans l'avoir
mesuré avant/après.** Trois pièges l'ont mise à l'épreuve aujourd'hui :

- mesurer à entrée **figée** (un `lru_cache` qui touche à chaque appel masque tout) ;
- mesurer **en séquence** alors que la machine dérive de ±25 % ;
- mesurer un module dont **le résultat varie naturellement** d'un facteur 2.

---

## 1. Comment mesurer — la seule méthode qui tienne

```bash
.venv\Scripts\python.exe scripts\bench_examples.py <module> --auto-yes [--sample]
```

`scripts/bench_examples.py` pilote les **vrais exemples de `example/`** en
headless, sans mock. Il documente en tête les quatre pièges qui rendent un banc
CERTUS faux ou bloqué — lis-les avant d'y toucher.

**N'utilise pas `tests/headless/` comme banc.** `test_design.py` remplace
`run_optim` par une fonction qui renvoie `0.001` sans calculer, et `test_strat.py`
remplace `_execute_full_pipeline` par un mock. Les 9,3 s de STRAT annoncées dans
`PLAN_OPTIMISATION.md §1` sont du chargement d'interface.

### Trois règles apprises à la dure

1. **Alterner les deux versions, ne pas les mesurer en séquence.** La machine
   dérive : sur cette session, le même code est passé de 743 à 990 µs/évaluation
   en deux heures (thermique, synchronisation Google Drive, autre session). Un
   A/B en séquence attribue la dérive au changement. Faire
   `sans / avec / sans / avec…` et compter les paires gagnantes.
2. **Ne pas conclure d'un run isolé sur DESIGN ni STRAT.** Dispersion naturelle
   mesurée : DESIGN 43 → 93 s et RMSE 0,0023 → 0,0051 ; STRAT 47 → 64 s. Quand le
   temps total est trop bruité, mesurer une grandeur stable — pour DESIGN, le
   **coût par évaluation** de `cost_numba_fast` (`--time-cost`, ~850 000 appels
   par run) donne un signal exploitable.
3. **`pytest tests/oracle/ -q --no-cov` après toute modification de calcul.**
   552 tests, 8 s. Et un test qui ne tombe pas sur le code d'avant correctif ne
   prouve rien : le vérifier en remettant l'ancienne version.

---

## 2. Référence actuelle, exemples réels

Mesuré sur cette machine (16 cœurs), calcul pur hors chargement, après les
correctifs de la §3.

| Module | Exemple | Temps | Point chaud dominant |
|---|---|---|---|
| STRAT | `JSON-strat-example.json` | 47–64 s | `compute_batch_rmse`, `simulate_stack_robustness_batch` |
| DESIGN | `JSON-design-example.json` | 43–93 s | `cost_numba_fast` (873 % — pool de ~10 threads) |
| METAL_BILAYER | `JSON-metal-bilayer-example.json` | 67 s | — |
| METAL_SINGLE | `JSON-metal-example.json` | 52–68 s | `get_nk_from_spline`, 66 975 appels |
| RE | `reverse_sample.xlsx` | 29–30 s | `_global_evaluate_oblique_physics` 61 % |
| INDEX | `H400-RTNBrel-sapphire.xlsx` | 6,5 s | `certus_index_objectives.py:1755:__call__` 54 % |
| INDEX_SPLINE | `TSIO2-1700-1.xlsx` | 1,6 s | `spline_objective.py:517` 25 %, `_fast_nk` 20 % |
| FIELD | `test_hr_mirror.json` | 0,06 s | rien à gagner |

Les pourcentages dépassent 100 % : DESIGN et STRAT tournent sur un pool de threads.

---

## 3. Ce qui est fait (commits sur `refactor-corridors-mixins`)

| Commit | Objet | Gain **mesuré** |
|---|---|---|
| `a9983c4` | Éviction LRU du cache de base spline | **0 s** aujourd'hui — voir §5 |
| `33af845` | STRAT : dispatch njit supprimé, cache de matrices factorisé | **−61 %** (137,7 · 126,7 → 56,9 · 47,1 s) |
| `2572f46` | PGLOBAL : sur-souscription de threads numba | **−29 %** par évaluation, 4 paires alternées sur 4 |
| `f6f9102` | RE : indexation par `slice` au lieu de copies de blocs | **−11 %** (33,3 → 29,5 s médian) |
| `bc2042a` | DESIGN : course sur le tampon d'épaisseurs | correction, pas performance |

`bc2042a` mérite d'être lu : `app._ep_buffer` était **un seul tableau partagé**
entre les ~14 threads du pool PGLOBAL. Dès qu'une couche est figée, deux threads
s'écrasaient mutuellement et le coût était calculé sur un mélange de deux
empilements. Mesuré : **278 évaluations fausses sur 48 000**, sans aucune erreur
visible. Garde-fou : `tests/oracle/test_design_objective_thread_safety.py`.

---

## 4. Ce qui reste à faire

### 4.1 Tirage informé par la physique dans PGLOBAL — le plus prometteur

**Choisi par l'utilisateur, non commencé.**

PGLOBAL échantillonne uniformément `[0, 1,2 × QWOT]^N` avec Sobol brouillé
(`qmc.Sobol(scramble=True)`, `certus_optimizers.py:646` — le réglage est correct,
ne le change pas pour rien). Mais pour des couches minces, les bonnes solutions se
concentrent près des multiples de QWOT ; un remplissage uniforme, aussi bien
équilibré soit-il, dépense l'essentiel de ses points loin de là.

Piste : tirer par couche un multiple dans {0 ; 0,5 ; 1} × QWOT (au-delà de 1,2
QWOT on sort des bornes), plus une gigue, en gardant une fraction de points Sobol
purs pour l'exploration. Point d'entrée : `PGlobalOptimizer._generate_samples`
(`certus/physics/certus_optimizers.py:694`).

**Protocole obligatoire** : comparer **à budget d'évaluations fixé**, sur
plusieurs graines, et regarder le meilleur RMSE atteint — pas le temps.
Changer d'échantillonneur ne peut **pas** accélérer quoi que ce soit :
l'échantillonnage pèse 1,5 % du profil. Le gain visé est la qualité d'optimum à
coût égal. Vu la dispersion de DESIGN (RMSE 0,0023 → 0,0051), il faut au moins
5 graines par variante.

### 4.2 INDEX — compilation numba pendant le calcul

~15 % du run d'INDEX part en JIT **pendant** l'optimisation, malgré
`warmup_physics()` : `llvmlite/binding/ffi.py:210` 11 %, `numba compiler_lock`
2,9 %, `numba/core/caching.py:_load_index` 1 %. Trouver quels noyaux ne sont pas
couverts par le warmup, et les y ajouter.

### 4.3 Imports tardifs sur disque lent

`<frozen importlib._bootstrap_external>:145:_path_stat` pèse 18,6 % du thread
principal d'INDEX et 23 % d'INDEX_SPLINE. Le dépôt vit dans un dossier **Google
Drive** (`D:\drivefl\…`) : chaque `stat` peut être coûteux.

⚠️ **Le cache numba n'est PAS en cause, c'est vérifié** : `configure_numba_env`
(`certus/core/certus_core.py:323`) le place déjà dans
`%TEMP%\CERTUS_Numba_Cache`, donc hors du dossier synchronisé. Ne repars pas sur
cette piste.

Il reste donc une seule piste : remonter en tête de module les imports faits
tardivement, pendant le calcul. Le profil `--sample` les montre sous
`_path_stat` et `get_data` du thread principal.

### 4.4 STRAT — ce qui reste après `33af845`

Le profil à la ligne est désormais dominé par de vrais noyaux compilés :
`compute_batch_rmse` (146 %), `compute_T_front_profile` (107 %),
`calculate_extrema_distances` (107 %), `simulate_stack_robustness_batch` (44 %).

Une piste concrète reste : `calculate_extrema_distances`
(`certus/physics/certus_strat_math.py:106`) accumule ses extrema dans une **liste
réfléchie numba** (`extrema_d = []`), notoirement lente. La remplacer par un
tableau préalloué. Résultats à vérifier identiques.

Autre piste, plus lourde : `_test_strategy_robustness_task` stocke
`rmse_all` et `thicknesses_all` en listes Python (`.tolist()` sur des tableaux
`num_runs × num_layers`), par niveau de bruit et par stratégie.

### 4.5 METAL — étape 2 de `PLAN_OPTIMISATION.md §2.4`

Toujours ouverte, et c'est le **seul** endroit où le §2 de ce plan s'applique.
Basculer `use_cache=True` site par site (`gradient_metal.py` ×2,
`CERTUS_METAL_BILAYER.py` ×2, `CERTUS_METAL_SINGLE.py` ×3).

Mesuré en forçant globalement `use_cache=True` sur METAL_SINGLE :
**55,9 s → 24,7 s**. Mais **attention** : le RMSE final change (0,006100 →
0,006124–0,006190). À comprendre avant de basculer — la mesure d'équivalence
numérique du plan (1,78e-15) ne suffit visiblement pas à garantir la même
trajectoire d'optimiseur.

Le banc sait le faire : `--force-cache --trace-nk --instrument`.

### 4.6 Dette non liée à la performance

- ~~`tests/unit/test_certus_re.py::TestREAppSkeletonLoaders::test_re_app_skeletons_methods`
  échoue dans la sélection `-k "re_ or reverse or objectives"` et passe isolément.~~
  ✅ **Résolu et commité le 2026-08-02** — cf. `docs/REPRISE_TESTS_ISOLATION.md`.
- `_is_busy` est lu dans `certus_design_ui.py:339` et **jamais écrit** nulle part.
- `git gc` échoue toujours sur le commit orphelin `01047a1b` (arbre manquant) —
  chaque commit affiche `fatal: bad tree object`. Sans effet sur les commits.

---

## 5. Corrections à `docs/PLAN_OPTIMISATION.md`

Ce plan reste utile pour METAL, mais trois de ses affirmations sont démenties par
la mesure. Ne perds pas de temps à les refaire.

1. **§2.5 « le cache se saborde lui-même », « le −53 % est un plancher » — faux.**
   Le vidage total ne coûtait que **15 reconstructions sur 5 522** : la localité
   temporelle est si serrée que jeter le cache ne fait presque pas mal. L'éviction
   LRU (`a9983c4`) rapporte **+0,124 s**, soit 0,4 % d'un run — et **0 s** en
   production, puisque `SplineBasisCache` n'est appelé que **18 fois** par run de
   METAL_SINGLE (99,97 % des appelants passent `use_cache=False`).
2. **§5, ordre de travail : les étapes 1 et 2 ne concernent QUE METAL.** Mesuré :
   INDEX, INDEX_SPLINE, RE et FIELD font **zéro appel** à `SplineBasisCache` et
   **zéro appel** à `get_nk_from_spline`. Pour les modules du quotidien, il fallait
   commencer par l'étape 3 (profiler les autres modules).
3. **§1, tableau des durées : STRAT et DESIGN y sont sous-évalués**, parce que les
   tests headless correspondants mockent le calcul. Vrais chiffres au §2 ci-dessus.

---

## 6. Diagnostics bruts du 2026-08-02

Conservés pour ne pas avoir à re-profiler. Échantillonnage de piles à 5 ms, tous
threads, exemples réels, dialogues répondus automatiquement. Les pourcentages
dépassent 100 % quand plusieurs threads travaillent en parallèle.

### STRAT — avant `33af845` (137 s)

```
691,4 %  _compute_theoretical_layer_profile   <- ~200 dispatches njit par couche
226,2 %  threading.wait
104,4 %  _test_strategy_robustness_task
 36,5 %  calculate_RT_vectorized_real_HL
 32,7 %  _compute_dT_dd_per_layer
```

### STRAT — après (lignes les plus chères)

```
146,5 %  certus_strat_robustness.py:596   compute_batch_rmse
107,2 %  certus_strat_objectives.py:489   compute_T_front_profile
106,7 %  certus_strat_objectives.py:497   calculate_extrema_distances
 67,7 %  certus_strat_objectives.py:376   precompute_matrix_cache_kernel
 44,5 %  certus_strat_robustness.py:567   simulate_stack_robustness_batch
```

### DESIGN

```
872,9 %  certus_design_core.py:264        cost_numba_fast
 85,4 %  gradient_oblique.py:1136
  1,5 %  certus_optimizers.py:438         <- toute la machinerie PGLOBAL
```

**PGLOBAL lui-même ne pèse que 1,5 %.** Il n'y a rien à gratter dans son code :
les gains restants sont dans la fonction objectif, ou dans le *nombre*
d'évaluations (donc l'échantillonnage, §4.1).

### RE — avant `f6f9102` (lignes)

```
32,1 %  certus_re_objectives.py:599   yR_all[idx], dR_all[idx, :]  <- copies
17,7 %  certus_re_objectives.py:600   idem pour T
15,5 %  certus_re_objectives.py:434   grad_raw += np.dot(coeff, dy_vals)
12,2 %  certus_re_objectives.py:424   np.sum / np.dot sur les poids
10,8 %  gradient_oblique.py:869
```

### INDEX (6,5 s, avec `--auto-yes`)

```
[WORK] 54,5 %  certus_index_objectives.py:1755:__call__
[MAIN] 18,6 %  <frozen importlib._bootstrap_external>:145:_path_stat
[WORK] 11,0 %  llvmlite/binding/ffi.py:210      <- JIT PENDANT le run
[MAIN]  7,5 %  <frozen importlib._bootstrap_external>:947:get_data
[WORK]  4,2 %  certus_index_objectives.py:1535:gradient
[WORK]  2,9 %  numba/core/compiler_lock.py:11
```

Sans `--auto-yes`, le même run affiche 26 % dans `_ask_keep_raw_or_smoothed` et
28 % dans `_on_tlu_constrained_finished` : ce sont des **QMessageBox modales**, pas
du calcul. Et le « No » par défaut fait sauter la phase IR : le chargement tombe
de 5,7 s à 0,6 s et le run de 12,8 s à 6,5 s — on mesurait la moitié du pipeline.

### INDEX_SPLINE (1,6 s)

```
25,2 %  spline_objective.py:517   spline_objective_mse_on_masked_grid
23,0 %  <frozen importlib._bootstrap_external>:145:_path_stat
19,7 %  spline_objective.py:973   _fast_nk
 8,5 %  llvmlite/binding/ffi.py:210
```

### Cache de base spline — pourquoi le §2 du plan ne s'applique qu'à METAL

METAL_SINGLE, code de production :

```
CACHE_CALLS=18        CACHE_CLEARS=0
NK_CALLS=66975        NK_DISTINCT_KNOTS=18402   NK_REPEAT=72,5 %
NK_USE_CACHE_FALSE=66957   (99,97 %)
```

Le même run avec `--force-cache` :

```
CACHE_CALLS=55611     CACHE_DISTINCT=5457   CACHE_HITS=50104   HITRATE=90,1 %
```

Rejeu déterministe de la séquence réelle contre les deux politiques d'éviction :

```
vidage total (>500)   4,524 s   5522 constructions
éviction LRU (512)    4,400 s   5507 constructions
```

INDEX, INDEX_SPLINE, RE, FIELD : `CACHE_CALLS=0` et `NK_CALLS=0`.

### Pièges d'outillage (Windows)

- Code de sortie **127** = `ERROR_PROC_NOT_FOUND`. Deux causes rencontrées :
  QApplication ramassée par le GC, et numpy/scipy importés avant Qt.
- `os._exit()` **ne vide pas** les tampons de `stdout` : un `print` avant lui est
  perdu quand la sortie est redirigée. Flusher explicitement.
- Depuis bash (MSYS), passer les chemins de script en **forme Windows**
  (`C:/…`) à `python.exe` ; la forme `/c/…` échoue avec un code 127 trompeur.
- Le timeout de l'outil Bash est plafonné à 10 min : lancer les campagnes de
  mesure en tâche de fond.

---

## 7. Rappels d'environnement

- Venv : `.venv\Scripts\python.exe`. Vérifier ce qui est réellement importé :
  `python -c "import certus.physics.certus_opt_tmm as m; print(m.__file__)"`.
- 🔴 `.git/hooks/post-commit` pousse chaque commit vers le dépôt **public**
  `nikonvr/CERTUS`. Actuellement renommé `post-commit.disabled`. `--no-verify` ne
  le neutralise pas. **Vérifier son état avant tout commit.**
- `numba.set_num_threads` est **thread-local** (vérifié à l'exécution) : on peut
  brider un pool sans toucher au reste du processus.
