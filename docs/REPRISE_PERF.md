# Reprise — performance CERTUS

Écrit le 2026-08-02, pour l'agent (ou l'humain) qui prend la suite, éventuellement
sur une autre machine. **Tout chiffre de ce document a été mesuré**, jamais estimé.

À lire après `CLAUDE.md`. Ce document corrigeait un plan d'optimisation antérieur sur
plusieurs points : voir §5.

---

> 🔴 **AVERTISSEMENT — révision du 2026-08-04**
>
> Ce document reste utile, mais **plusieurs de ses conclusions ont été démenties
> par la mesure** depuis. Lis d'abord
> les journaux de session (supprimés le 2026-08-06, cf. `git log`).
>
> Ce qui a changé sous les pieds du plan : le dépôt a quitté Google Drive pour un
> disque local, la machine de travail a **4 cœurs et non 16**, et numba est passé
> de 0.65.1 à **0.66.0**. Aucune comparaison avant/après ne peut enjamber cette
> rupture.
>
> Les corrections sont signalées en ligne, section par section. Les cinq
> principales :
>
> | Section | Statut |
> |---|---|
> | §0, interdiction du parallélisme | ❌ **démentie** — voir ci-dessous |
> | §2, ligne INDEX à 6,5 s | ❌ **fausse d'un facteur 2**, la vraie référence est 12,8 s |
> | §4.3, « le cache numba n'est pas en cause, c'est vérifié » | ❌ **faux** — il n'a jamais été dans `%TEMP%` |
> | §4.4, la liste réfléchie numba | ⚠️ **mauvaise cible** — le vrai gisement était ailleurs |
> | §4.5, `use_cache=True` | ✅ **résolu** — le basculement n'est PAS sûr |

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

Mesurer un module sur son vrai exemple — depuis `cmd` :

```bat
.venv\Scripts\python.exe scripts\bench_examples.py strat --auto-yes --sample
```

Prouver un gain en alternant les deux versions — **depuis Git Bash**, avec des
barres obliques et le `^` entre guillemets :

```bash
bash scripts/ab_compare.sh certus/physics/certus_optimizers.py "2572f46^" design 4 --auto-yes --time-cost
```

⚠️ Ces deux détails ne sont pas cosmétiques. Sous bash, `scripts\ab_compare.sh`
devient `scriptsab_compare.sh` — l'antislash est un caractère d'échappement, et la
commande échoue. Sous `cmd`, c'est le `^` de `2572f46^` qui disparaît, car c'est
le caractère d'échappement de `cmd` : on ne compare alors plus au bon commit.

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

~~🔴 Ne pas lancer deux sessions pytest en parallèle sur ce dépôt.~~
❌ **DÉMENTI PAR LA MESURE le 2026-08-04.** À cache numba **chaud**, deux sessions
pytest simultanées ne se bloquent pas du tout :

| | Wall | pytest |
|---|---|---|
| 1 passe seule | 17,7 s | 11,32 s |
| 2 passes simultanées | 21,1 et 20,9 s | 12,12 et 12,11 s |

552 tests au vert dans les deux cas, **+7 %** seulement sur le temps pytest, et
22,3 s au total contre ~35,4 s en séquentiel — **37 % de gain**.

La cause invoquée par la version précédente de ce paragraphe (« le verrou de
fichier du cache numba, `configure_numba_env` ») ne peut pas être la bonne :
`configure_numba_env` **ne pose jamais** `NUMBA_CACHE_DIR`, cf.
un journal de session supprimé (§10.1). L'observation du 2026-08-02 était
probablement faite à cache **froid**, où deux processus tentent d'*écrire* les
mêmes `.nbi` ; à chaud ils ne font que les *lire*. Hypothèse non vérifiée.

⚠️ **Mais garde la distinction, elle est essentielle :**

- **Paralléliser des VALIDATIONS** — oracle, tests unitaires, lint, pendant qu'un
  banc tourne : ✅ sûr et rentable.
- **Paralléliser des MESURES** — deux bancs, ou un banc pendant autre chose :
  ❌ jamais. Mesuré le 2026-08-03 : INDEX affichait `RUN_S` **81,5 s** pendant
  qu'une copie vers Drive et des lectures tournaient, contre **12,4 s** machine au
  repos. Sur 4 cœurs, la charge concurrente n'ajoute pas du bruit, elle invente un
  résultat.

L'oracle ci-dessus est une charge légère. Deux bancs lourds (DESIGN tourne à 873 %
de CPU) se disputeraient bien davantage les 4 cœurs physiques.

### Bruits de fond à ignorer

Ces messages apparaissent à chaque fois et n'indiquent aucun problème :

- Chaque `git commit` affiche `fatal: bad tree object …` et
  `failed to perform geometric repack`. C'est le commit orphelin `01047a1b`
  (arbre manquant) décrit dans `CLAUDE.md §5.4`. **Le commit réussit quand même** —
  vérifier avec `git log --oneline -1`, ne pas recommencer.
- ~~`warning: ignoring broken ref refs/heads/desktop.ini` : idem, sans effet.~~
  ✅ **Disparu** : la ref cassée n'a pas survécu au rapatriement du dépôt hors de
  Google Drive (2026-08-03). Le commit orphelin `01047a1b`, lui, est toujours là.

### Réflexe avant de croire à un gain

L'utilisateur a une règle explicite : **ne jamais annoncer un gain sans l'avoir
mesuré avant/après.** Trois pièges l'ont mise à l'épreuve aujourd'hui :

- mesurer à entrée **figée** (un `lru_cache` qui touche à chaque appel masque tout) ;
- mesurer **en séquence** alors que la machine dérive de ±25 % ;
- mesurer un module dont **le résultat varie naturellement** d'un facteur 2.

---

## 1. Comment mesurer — la seule méthode qui tienne

```bat
.venv\Scripts\python.exe scripts\bench_examples.py <module> --auto-yes [--sample]
```

`scripts/bench_examples.py` pilote les **vrais exemples de `example/`** en
headless, sans mock. Il documente en tête les quatre pièges qui rendent un banc
CERTUS faux ou bloqué — lis-les avant d'y toucher.

**N'utilise pas `tests/headless/` comme banc.** `test_design.py` remplace
`run_optim` par une fonction qui renvoie `0.001` sans calculer, et `test_strat.py`
remplace `_execute_full_pipeline` par un mock. Les 9,3 s de STRAT annoncées dans
l'ancien plan d'optimisation (§1) sont du chargement d'interface.

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
| INDEX | `H400-RTNBrel-sapphire.xlsx` | ❌ ~~6,5 s~~ → **12,8 s** | `certus_index_objectives.py:1755:__call__` 54 % |
| INDEX_SPLINE | `TSIO2-1700-1.xlsx` | 1,6 s | `spline_objective.py:517` 25 %, `_fast_nk` 20 % |
| FIELD | `test_hr_mirror.json` | 0,06 s | rien à gagner |

Les pourcentages dépassent 100 % : DESIGN et STRAT tournent sur un pool de threads.

> ❌ **La ligne INDEX était fausse d'un facteur 2.** Elle mesurait le run SANS
> `--auto-yes`, c'est-à-dire avec la réponse « No » par défaut, qui fait sauter la
> phase IR — exactement ce que le §6 dénonce plus bas (« on mesurait la moitié du
> pipeline »). Mesuré le 2026-08-04 avec `--auto-yes` sur la machine 4 cœurs :
> **12,425 s**, contre 12,8 s ici. **La référence correcte est 12,8 s.**
>
> ⚠️ **INDEX est aussi DISPERSIF**, ce que ce tableau ne dit pas : deux passes
> consécutives donnent RMSE 0,002568 puis 0,002781 (**8 %**) et `RUN_S` 11,1 puis
> 8,1 s (**27 %**). La règle 2 du §1 ne vise que DESIGN et STRAT ; **elle vaut
> aussi pour INDEX**. Personne ne pouvait le savoir : le banc rendait `RESULT=None`
> sur ce module, faute d'extraction correcte (corrigé, cf. §3 du document de
> reprise).
>
> **Facteurs mesurés sur la machine 4 cœurs** (`RUN_S`, cache chaud, machine au
> repos) : FIELD ×2,0 · INDEX **×0,97, la parité** · INDEX_SPLINE **×5,9**.
> La parité d'INDEX s'explique : le cache `.nbi` de la machine 16 cœurs vivait
> dans Google Drive, son avantage CPU était mangé par les I/O.

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

> ⚠️ **Piste plus rentable qu'avant** : mesuré le 2026-08-03, la compilation à
> froid de l'oracle est passée de **60,6 s à 104,6 s** (+73 %) entre numba 0.65.1
> et 0.66.0.
>
> ❌ **Ce ne sont pas des noyaux oubliés, ce sont des SIGNATURES oubliées.** Un
> balayage AST des **111 fonctions `@njit`** du paquet montre qu'elles portent
> **toutes** `cache=True`. La vraie cause est
> `certus/core/certus_index_solvers.py:255`, qui alloue les échantillons en
> **float32** alors que la phase locale scipy repasse en float64 : numba compile
> **deux signatures** du chemin chaud, et `warmup_physics` — qui ne passe que des
> float Python — n'en couvre qu'une. Une **troisième** variante `readonly` existe,
> produite par l'idiome `np.frombuffer(clé_en_octets)` des caches lru.
>
> ✅ **Un bloc entier du warmup était mort depuis des années** :
> `certus/core/_certus_physics_impl.py:1492` faisait
> `np.interp(CIE_LAMBDA, wls, R_test)` avec `wls` à 50 points et `R_test` à 10 —
> `ValueError` avalée par le `except` englobant, donc `_xyz_from_spectrum_kernel`
> et `delta_e_2000` n'ont jamais été compilés par le warmup. Diagnostiqué par
> **l'absence de leur `.nbi` sur disque**, corrigé, confirmé par leur apparition.
> Retiens la méthode : **la présence du `.nbi` est un contrôle qui ne coûte aucun
> calcul.**
>
> ⚠️ Passer `:255` en float64 change le pas d'échantillonnage, donc la trajectoire
> de l'optimiseur. À ne tenter **qu'après** avoir exposé une graine dans le banc :
> INDEX est dispersif à 8 %, un A/B sur deux runs isolés donnerait un verdict au
> hasard.

### 4.3 Imports tardifs sur disque lent

`<frozen importlib._bootstrap_external>:145:_path_stat` pèse 18,6 % du thread
principal d'INDEX et 23 % d'INDEX_SPLINE. Le dépôt vit dans un dossier **Google
Drive** (`D:\drivefl\…`) : chaque `stat` peut être coûteux.

~~⚠️ Le cache numba n'est PAS en cause, c'est vérifié : `configure_numba_env` le
place déjà dans `%TEMP%\CERTUS_Numba_Cache`. Ne repars pas sur cette piste.~~

❌ **FAUX, et cette interdiction était donc infondée.** Vérifié le 2026-08-04 :

| Contrôle | Résultat |
|---|---|
| `%TEMP%\CERTUS_Numba_Cache` | **n'existe pas** |
| `.nbi` dans les `__pycache__` du dépôt | **78 fichiers** |

`configure_numba_env` ne pose `NUMBA_CACHE_DIR` qu'en `certus_core.py:359-361`,
mais la branche de `:334` **retourne en `:352` avant d'y arriver** — et
`bench_examples.py:443` importe `certus_physics`, donc numba, **avant** que
`CERTUS_INDEX` n'appelle `_configure_numba_env()`. La branche est toujours prise.
Aggravant : dans numba 0.66, le locator de cache est figé **à la décoration**
(`numba/core/caching.py:414-420`), donc poser la variable trop tard est sans effet.

**Le cache JIT vit à côté des sources** — c'est-à-dire, à l'époque de ce document,
**dans le dossier Google Drive**. Les 18,6 % et 23 % de `_path_stat` ci-dessus,
c'était très probablement lui.

❌ **Et la mesure elle-même était un artefact.** `scripts/bench_examples.py:687`
place la fenêtre d'échantillonnage **autour de l'import de l'application** : ces
pourcentages ne sont pas du temps de calcul, mais du chargement de modules.
Re-profilé le 2026-08-04 sur disque local, INDEX_SPLINE donne `_path_stat` à
**9,0 %** (contre 23,0 %) et 42 % dans `_call_with_frames_removed`, c'est-à-dire
l'import lui-même.

✅ **Ce qui restait de réel a été fait** : 8 imports tardifs supprimés de
`certus/spline/spline_workers.py`, dont un exécuté à **chaque évaluation
L-BFGS-B**. Aucun cycle (vérifié), et 6 des 8 noms étaient déjà en tête de module.
Les 11 imports tardifs de `certus/workers/certus_index_workers.py` sont, eux,
**NON déplaçables** : cycle d'import prouvé. Ne pas y toucher.

### 4.4 STRAT — ce qui reste après `33af845`

Le profil à la ligne est désormais dominé par de vrais noyaux compilés :
`compute_batch_rmse` (146 %), `compute_T_front_profile` (107 %),
`calculate_extrema_distances` (107 %), `simulate_stack_robustness_batch` (44 %).

~~Une piste concrète reste : `calculate_extrema_distances` accumule ses extrema
dans une liste réfléchie numba, notoirement lente. La remplacer par un tableau
préalloué.~~

⚠️ **MAUVAISE CIBLE.** La lecture du code montre que cette liste ne représente que
**2 des 6 allocations NRT** de la fonction et ne contient en pratique que **0 à 2
éléments** — la fenêtre couvre ±16 nm de chemin optique quand les extrema de T(d)
sont espacés de λ/2, soit ~275 nm à 550 nm. Le coût réel, ce sont les **56 à 88
évaluations** de `_calc_T_added_layer`, chacune avec `cos`/`sin` sur argument
complexe. Le plafond de gain de cette piste est donc bas.

✅ **Le vrai gisement était ailleurs, et il est traité.** Le bloc de profil
théorique de `certus/core/certus_strat_robustness.py:624-658` — là où vivent
précisément les deux lignes les plus chères ci-dessus, `compute_T_front_profile`
à 107,2 % et `calculate_extrema_distances` à 106,7 % — est calculé **puis jeté**
par deux appelants sur trois :

- le rescoring consensus ne lit que `robustness_score` ;
- le halving ELITE ne lit que `rmse_p95` et réempile la stratégie **d'entrée**.

Seules la passe principale et l'évaluation ELITE complète l'exploitent, cette
dernière via `full_res["strategy"]`. Un paramètre `compute_layer_profile: bool =
True` a été ajouté et les deux sites qui jettent le résultat passent `False`.
**Gain non mesuré** : le mécanisme est vérifié, le volume ne l'est pas.

⚠️ **Piste `.tolist()` : ne pas l'attaquer directement.** `_test_strategy_robustness_task`
stocke bien `rmse_all` et `thicknesses_all` en listes Python, mais passer en numpy
casserait **quatre** tests de véracité, dont **deux silencieusement** —
`if thicknesses_all:` sur un ndarray 2D lève `ValueError`, avalée par le `except`
englobant (`certus/ui/certus_strat_thickness_ui.py:402` et
`certus/ui/certus_strat_table_ui.py:164`). C'est le mode de défaillance de
`bc2042a`. Il faut un **commit préalable et séparé** remplaçant les 4 tests par
`is None or len(...) == 0`.

🔴 **Et un prérequis à toute mesure STRAT** : `certus_strat_robustness.py:314` fait
`max_workers = cpu_count() // 2` et `:466` fait `numba.set_num_threads(2)`, soit
**8 threads numba pour 4 cœurs physiques** sur la machine actuelle. Plus
largement, **aucun endroit du dépôt ne connaît la notion de cœur physique** : tout
dérive de `cpu_count()`. Six sites recensés au §10.4 du document de reprise. Sur un
15 W, cette sur-souscription se paie en throttling thermique, qui bruite toutes
les comparaisons A/B.

### 4.5 METAL — le cache d'indices, et pourquoi le gain ÉTAIT l'erreur

Toujours ouverte, et c'est le **seul** endroit où le §2 de ce plan s'applique.
Basculer `use_cache=True` site par site (`gradient_metal.py` ×2,
`CERTUS_METAL_BILAYER.py` ×2, `CERTUS_METAL_SINGLE.py` ×3).

Mesuré en forçant globalement `use_cache=True` sur METAL_SINGLE :
**55,9 s → 24,7 s**. Mais **attention** : le RMSE final change (0,006100 →
0,006124–0,006190).

🔴 **PISTE CLOSE le 2026-08-04, MESURE À L'APPUI. LE GAIN EST L'ERREUR.**

Trois runs `metal_single --force-cache --instrument`, machine au repos :

| | `RUN_S` | `RESULT` | `HITRATE` |
|---|---|---|---|
| Sans cache | 154,6 s | `0,006100345590625494` | — |
| Cache, **clé arrondie** (code actuel) | **75,2 s** | `0,00613372429822523` ❌ | **88,1 %** |
| Cache, **clé exacte** (essai) | **150,3 s** | `0,006100345473793503` ✅ | **18,8 %** |

Le ×2,06 se reproduit. Mais avec une clé **exacte**, le résultat redevient juste et
**le gain disparaît entièrement** — ×1,03. Les 88 % de succès étaient à ~70 points
des géométries réellement distinctes, écrasées par l'arrondi à 1e-6 nm : ce sont
précisément les perturbations de différence finie de L-BFGS-B. Construction des
matrices : 19,1 s pour 5 499 distinctes contre 69,3 s pour 10 737.

⚠️ **Piège supplémentaire, invisible dans la mesure d'origine** : avec le cache, le
nombre d'appels à `get_nk_from_spline` passe de **68 503 à 51 149**. L'optimiseur ne
fait pas le même travail plus vite, **il fait 25 % de travail en moins** parce que sa
trajectoire diverge. Le « ×2 » n'est donc même pas une accélération pure.

**Ne pas relancer cette piste.** L'arrondi de `certus_optical_models.py:419` est
délibéré et documenté sur place.

---

Analyse de la cause, conservée pour mémoire :

Ce ne sont pas les 1,78e-15 de réassociation flottante. C'est une **perte
d'information dans la clé de cache**. `SplineBasisCache.get` arrondit les
positions de nœuds à **6 décimales** pour construire sa clé
(`certus/physics/certus_optical_models.py:419`). Les longueurs d'onde de METAL
sont en **nanomètres** (`CERTUS_METAL_SINGLE.py:1256`), donc le quantum de la clé
vaut **1e-6 nm**, soit **100× le pas de différence finie de L-BFGS-B (1e-8)**.

> **La perturbation du gradient est exactement annulée par l'arrondi de la clé.**
> L'optimiseur dérive un objectif devenu localement constant.

Trois corollaires :

- `certus_optical_models.py:453` — la matrice stockée n'est pas reconstruite à
  partir de la clé : l'objectif devient **dépendant de l'historique du cache**,
  donc non reproductible d'un run à l'autre.
- `tests/oracle/test_spline_basis_cache.py:46` — le garde-fou censé attraper ce
  bug **ne peut pas le voir** : il déplace les nœuds de 1e-4, soit 100× le quantum.
- `scripts/bench_examples.py:307` — **le 55,9 s → 24,7 s ne mesure pas l'action
  proposée** : `--force-cache` patche globalement, y compris des sites que le plan
  ne prévoit pas de basculer.

Même pathologie, 100 000× plus grossière, dans `certus/utils/certus_re_math.py:396`
(nœuds arrondis à 0,1 nm, grille à 1 nm).

Les sites où les positions de nœuds sont **figées** sont immunisés ; ceux où elles
varient ne le sont pas. ⚠️ Constats issus d'une analyse dont les vérificateurs ont
été interrompus : **à recouper ligne à ligne avant d'agir.**

Le banc sait le faire : `--force-cache --trace-nk --instrument`.

### 4.6 Dette non liée à la performance

- ~~`tests/unit/test_certus_re.py::TestREAppSkeletonLoaders::test_re_app_skeletons_methods`
  échoue dans la sélection `-k "re_ or reverse or objectives"` et passe isolément.~~
  ✅ **Résolu et commité le 2026-08-02** — cf. `docs/REPRISE_TESTS_ISOLATION.md`.
- `_is_busy` est lu dans `certus_design_ui.py:339` et **jamais écrit** nulle part.
- `git gc` échoue toujours sur le commit orphelin `01047a1b` (arbre manquant) —
  chaque commit affiche `fatal: bad tree object`. Sans effet sur les commits.

---

## 5. Trois affirmations réfutées par la mesure

*Elles venaient d'un plan d'optimisation antérieur, supprimé le 2026-08-06. Elles sont conservées
ici parce que ce sont des CONCLUSIONS, et qu'elles évitent de refaire le chemin.*

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

### INDEX (❌ ~~6,5 s, avec `--auto-yes`~~ → **12,8 s avec `--auto-yes`**)

> Ce titre se contredisait avec son propre paragraphe ci-dessous, qui dit que le
> « No » par défaut fait tomber le run **de 12,8 s à 6,5 s**. Tranché par la mesure
> du 2026-08-04 : `--auto-yes` donne **12,425 s** sur la machine 4 cœurs. C'est le
> corps du texte qui avait raison — **6,5 s est la mesure SANS `--auto-yes`**,
> c'est-à-dire le demi-pipeline. Le tableau du §2 reprenait le mauvais chiffre.

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
