# Reprise — session du 2026-08-03

Écrit pour l'agent (ou l'humain) qui prend la suite, y compris sous un autre
compte ou sur une autre machine. **Tout chiffre marqué « mesuré » l'a été ici** ;
tout le reste est signalé comme hypothèse.

À lire avec `docs/REPRISE_PERF.md`, que ce document **corrige sur plusieurs
points** — voir §5. Ne pars pas des chiffres du §2 de ce document-là sans avoir
lu le §2 de celui-ci.

---

## 1. Ce qui a changé dans l'environnement

Trois variables ont bougé **en même temps**. Aucune comparaison avant/après ne
peut enjamber cette session.

| | Avant | Maintenant |
|---|---|---|
| Emplacement | `G:\Mon Drive\...\CERTUS\0108` (Google Drive) | **`C:\dev\CERTUS\0108`** (disque local) |
| Machine | 16 cœurs | **i5-8250U, 4 cœurs / 8 threads, 15 W, 8 Go** |
| numba / llvmlite | 0.65.1 / 0.47.0 | **0.66.0 / 0.48.0** |
| scipy | 1.17.1 | **1.18.0** |
| Python | 3.14.6 | 3.14.6 (inchangé, c'est la dernière stable) |
| uv | 0.10.6 et 0.11.14 | **0.12.1** |

### Pourquoi le projet a déménagé

Le venv ne peut **pas** vivre dans Google Drive File Stream. Mesuré :

- `uv pip install` a échoué sur `os error 433` — le volume `G:` a disparu en
  cours d'écriture, emportant l'interpréteur.
- uv signale `Failed to hardlink files; falling back to full copy` : le cache uv
  est sur `C:`, la cible était sur `G:`. Chaque fichier était recopié en entier.
- Débit d'écriture mesuré : **24,4 Mo/min vers Drive contre 99,7 Mo/min en
  local**, sur un arbre de milliers de petits fichiers.
- L'ancien `.venv` était de toute façon mort : son interpréteur de base
  `C:\Python314` n'existe plus (trampoline cassé).

Drive reste la sauvegarde : instantané `G:\Mon Drive\couches minces 2026\CERTUS\0308`,
6 894 fichiers, dépôt git valide, **sans `.venv`** — ne jamais l'y recopier.

### Reconstruire l'environnement

```bat
cd /d C:\dev\CERTUS\0108
uv sync --extra dev --extra freeze
```

`uv sync` et **pas** `uv pip install -r requirements.lock` : ce dernier
n'installe pas le projet lui-même, et le check n°1 du §0 de `REPRISE_PERF.md`
échoue alors silencieusement.

---

## 2. Facteur machine — mesuré, partiellement

Le seul chiffre **propre** est celui de l'oracle, mesuré machine au repos :

| | Réf. doc (16 cœurs) | Ici | Facteur |
|---|---|---|---|
| `pytest tests/oracle/ -q --no-cov`, cache chaud | 8 s | **11,71 s** | **×1,46** |
| idem, cache numba froid | — | 104,60 s | — |

⚠️ **Ne généralise pas ce ×1,46.** L'oracle est court et essentiellement
mono-thread. Il ne dit rien de DESIGN (873 % de CPU) ni de STRAT (691 %), qui
exploitent réellement 16 cœurs sur la machine d'origine.

### Bancs rapides : chiffres POLLUÉS, à refaire

Mesurés pendant qu'un robocopy vers Drive et des agents de lecture tournaient.
**Inexploitables**, conservés seulement pour l'ordre de grandeur.

| Module | Réf. doc | `RUN_S` ici (chaud) | Rapport |
|---|---|---|---|
| FIELD | 0,06 s | 0,216 | ×3,6 |
| INDEX_SPLINE | 1,6 s | 12,188 | ×7,6 |
| INDEX | 6,5 s | 81,521 | ×12,5 |

La contamination est **prouvée par la série elle-même** : sur INDEX_SPLINE,
`RUN_S` descend de 17,898 à 12,188 s pendant que le wall-clock monte de 26,65 à
33,74 s. Le calcul accélère et le processus ralentit : c'est une interférence
externe, pas du bruit.

**À refaire machine au repos**, un seul processus à la fois.

### Le JIT est plus cher qu'avant

Mesuré sur l'oracle : compilation à froid **60,6 s → 104,6 s** (+73 %) entre
numba 0.65.1 et 0.66.0. Conséquence directe : la piste **§4.2** de
`REPRISE_PERF.md` (noyaux non couverts par `warmup_physics()`) a **gagné** en
rentabilité, elle n'en a pas perdu.

Hypothèse **non vérifiée** à tester en priorité : si les ratios ×7 à ×12
ci-dessus survivent à une mesure propre, ils sont trop grands pour un simple
écart 4 cœurs contre 16 sur du mono-thread. Suspect n°1 : un `cache=True`
devenu inopérant sur les décorateurs numba après la montée de version, qui
ferait recompiler à chaque run.

---

## 3. 🔴 Le banc INDEX n'a aucun ancrage de correction

`scripts/bench_examples.py` sort `RESULT`, défini dans sa docstring comme la
grandeur physique permettant de vérifier qu'une optimisation n'a pas changé le
résultat. **Sur INDEX, `RESULT` vaut `None`.**

Ce n'est pas un échec de run : le code de sortie est 0, aucune trace, et
`RUN_S` vaut bien 81 s — le worker a tourné et rendu quelque chose.

La chaîne fautive, dans `scripts/bench_examples.py:455`:

```python
worker = getattr(app, "worker", None) or getattr(app, "_worker", None)
res = wait_for(worker) if worker else None
val = getattr(res, "rmse_final", None) if res is not None else None
if val is None and isinstance(res, dict):
    val = res.get("rmse")
```

Les signaux `finished` des workers d'INDEX portent bien une charge utile —
`certus/workers/certus_index_workers.py:358` et `:757` émettent `pyqtSignal(object)`,
`:1178` émet `pyqtSignal(list)`. Donc `res` n'est pas nul, mais il n'a **ni
l'attribut `rmse_final`, ni la forme d'un dict**. Le cas `list` est le candidat
le plus probable.

**À faire :** identifier lequel des trois workers `app.run_optimization()`
emploie réellement, puis extraire la grandeur comme le font les autres runners
(`run_design` lit `getattr(app, "_workflow_best_rmse", None)`).

**Tant que ce n'est pas corrigé, toute optimisation des noyaux d'INDEX — donc
toute la piste §4.2 — se ferait sans filet.** C'est exactement la classe de
problème que `tests/oracle/test_silent_wrong_results.py` existe pour attraper.

---

## 4. Ambiguïté à trancher dans REPRISE_PERF.md

Le §2 donne INDEX à **6,5 s**. Le §6 titre « INDEX (6,5 s, avec `--auto-yes`) »,
mais explique dans le même paragraphe que le « No » par défaut fait sauter la
phase IR et fait tomber le run **de 12,8 s à 6,5 s**.

Les deux lectures sont incompatibles : soit 6,5 s est la mesure `--auto-yes`,
soit c'est celle sans. **Le facteur machine d'INDEX en dépend du simple au
double.** À trancher avant de reconstruire le tableau du §2.

---

## 5. Corrections à REPRISE_PERF.md

1. **§4.3, « le dépôt vit dans un dossier Google Drive » — obsolète.** Le dépôt
   est sur disque local. L'hypothèse Drive pour expliquer les 18,6 % de
   `_path_stat` d'INDEX et les 23 % d'INDEX_SPLINE doit être **re-testée**, pas
   supposée. Si les pourcentages s'effondrent, la piste est close sans écrire une
   ligne ; s'ils tiennent, les imports tardifs sont bien en cause.
2. **§0, « warning: ignoring broken ref refs/heads/desktop.ini » — disparu.** La
   ref cassée n'a pas survécu au rapatriement. Le commit orphelin `01047a1b`
   reste, lui : `fatal: bad tree object` continue de s'afficher à chaque commit,
   qui réussit quand même.
3. **§3, tous les gains mesurés (`33af845` −61 %, `2572f46` −29 %, `f6f9102`
   −11 %) datent de numba 0.65.1 et de 16 cœurs.** Ils ne sont pas invalidés,
   mais ils ne sont plus reproductibles ici en l'état.
4. ~~**`2572f46` est suspect sur cette machine.**~~ ❌ **J'avais tort — voir §10.4.**
   La lecture du code montre que son réglage (`certus/physics/certus_optimizers.py:892`)
   est **adaptatif**, pas en dur, et reste pertinent sur 4 cœurs. La
   sur-souscription réelle est ailleurs, et elle est bien plus large que ce
   commit.

---

## 6. Verrous de dépendances — piège à connaître

`pyproject.toml` épingle `pydantic>=2.14.0a1`, une **préversion**. Conséquence :

- `uv pip compile` bascule en mode préversions pour **tout le graphe** et tire
  `numba 0.67.0rc1`, `llvmlite 0.49.0rc1`, `numpy 2.5.1` — jamais testés.
- Or `.github/workflows/release-windows.yml:31` fait
  `pip install -r requirements.lock` : une release aurait été construite dessus.

**`requirements.lock` est désormais généré par `uv export`**, pas par
`uv pip compile` :

```bat
uv export --extra dev --extra freeze --no-emit-project -o requirements.lock
```

Il reflète ainsi exactement `uv.lock`, c'est-à-dire ce qui est installé et ce que
l'oracle a validé. **N'utilise plus la commande inscrite dans l'ancien en-tête du
fichier.**

Effet de bord favorable : `uv export` produit les hashes. Le fichier en compte
441, là où il n'en avait **aucun** — ce qui faisait échouer l'étape
« Verify lockfile hashes » de `release-windows.yml` pour la totalité des paquets.
Ce job était rouge, il ne devrait plus l'être.

---

## 7. État git et auto-push

- Branche `refactor-corridors-mixins`, alignée sur `origin`.
- `fdb3a74` — verse 67 fichiers de travail non commité (moteur rust, audit, rapports).
- `726403d` — remontée des dépendances et réparation des hashes.
- 🔴 **`.git/hooks/post-commit` est RÉARMÉ.** Chaque commit pousse
  automatiquement vers le dépôt **public** `nikonvr/CERTUS`, en arrière-plan.
  Le log est dans `logs/git_auto_push.log`.
- Le hook lance le push avec `&` : **un échec est silencieux**. Il a d'ailleurs
  échoué une fois ici (`could not read Username`, pas de terminal interactif).
  Vérifier `git status -sb` et le log, ne pas se fier au message du hook.
- `.env` est bien ignoré (`.gitignore:26`) et non suivi.

---

## 8. Ce qui reste à faire, par ordre

1. **Refaire les bancs rapides machine au repos** — FIELD, INDEX_SPLINE, INDEX,
   deux passes, rien d'autre en vol. C'est ce qui tranche l'hypothèse
   « régression numba 0.66 » et la question `_path_stat` du §4.3, pour quelques
   minutes de calcul.
2. **Corriger l'extraction de `RESULT` du banc INDEX** (§3 ci-dessus).
3. **Trancher l'ambiguïté 6,5 s / 12,8 s** (§4).
4. **Vérifier les réglages de threads pour 4 cœurs** — le gain le moins cher s'ils
   sont en dur.
5. Puis seulement les bancs lourds : RE, METAL_SINGLE, METAL_BILAYER, et enfin
   STRAT et DESIGN, dont la dispersion naturelle impose plusieurs runs chacun.
   Sur cette machine c'est une campagne de fond, pas une mesure interactive.

🔴 **Rappel non négociable** : une seule session de calcul à la fois. Deux
processus numba concurrents se bloquent mutuellement (verrou du cache, §0 de
`REPRISE_PERF.md`), et sur 4 cœurs toute charge parallèle fausse la mesure.

---

## 9. Analyse statique du §4.4 — la prémisse du document est fausse

Issu d'une analyse parallèle dont **16 agents sur 17 ont été tués par une limite
de quota**. Un seul a abouti, sur le §4.4, et ses dix vérificateurs sont morts
avec les autres.

⚠️ **Statut : NON VÉRIFIÉ**, sauf les trois lignes contrôlées à la main et
marquées ✅ ci-dessous. Tout le reste est à recouper avant d'agir.

### 9.1 Le gisement n'est pas là où le document le dit

Le §4.4 de `REPRISE_PERF.md` désigne la liste réfléchie numba
(`extrema_d = []`, `certus/physics/certus_strat_math.py`) comme le problème.
La lecture du code dit autre chose : cette liste ne représente que **2 des 6
allocations NRT** par appel et ne contient en pratique que **0 à 2 éléments**.
Le coût réel de la fonction, ce sont les **56 à 88 évaluations** de
`_calc_T_added_layer`, chacune avec `cos`/`sin` sur argument complexe.

Le vrai gisement est ailleurs, et il est bien plus gros. Le bloc de profil
théorique de `certus/core/certus_strat_robustness.py:624-658` est **calculé puis
jeté** par deux des trois familles d'appelants :

- rescoring consensus (`robustness.py:951`) ne lit que `robustness_score` ;
- successive halving ELITE (`certus_strat_consensus.py:570`) ne lit que
  `results_per_noise[].rmse_p95`.

✅ Vérifié à la main : `final_score` est calculé en `:622`, **avant** le bloc, qui
démarre en `:624` par `extrema_dist_info = []` et boucle
`for i_layer in range(num_layers)`.

Or c'est exactement là que vivent **les deux lignes les plus chères** du profil
post-`33af845` du document : `certus_strat_objectives.py:489`
(`compute_T_front_profile`, 107,2 %) et `:497` (`calculate_extrema_distances`,
106,7 %). Volume estimé : **~500 tâches × 48 couches ≈ 25 000 appels inutiles**
par run, sur chacune des deux fonctions.

**Action proposée** — ajouter `compute_layer_profile: bool = True` à
`_test_strategy_robustness_task` (`robustness.py:448`), englober les lignes
624-658 dans `if compute_layer_profile:`, et passer `False` aux **deux seuls**
sites qui jettent le résultat : `robustness.py:951` et `consensus.py:570`.
Surtout **pas** en `consensus.py:621` (évaluation complète, dont
`full_res['strategy']` est réutilisé en `:648`) ni dans
`_execute_robustness_tasks`. Le défaut `True` préserve tout appelant non modifié.

### 9.2 ✅ Sur-souscription de threads confirmée — à corriger AVANT toute mesure

Vérifié à la main dans `certus/core/certus_strat_robustness.py` :

- `:314` → `max_workers = max(1, multiprocessing.cpu_count() // 2)`
- `:466` → `numba.set_num_threads(2)` en tête de **chaque** tâche

Sur l'i5-8250U, `cpu_count()` renvoie 8 (SMT), donc `max_workers = 4`, soit
**4 × 2 = 8 threads numba pour 4 cœurs physiques à 15 W**. Le réglage `2` a été
choisi sur une machine 16 cœurs.

🔴 **C'est un prérequis, pas une optimisation.** Une sur-souscription ×2 sur un
15 W se paie en throttling thermique, ce qui **bruite toutes les mesures A/B**.
Le corriger après avoir lancé les campagnes invaliderait les campagnes.
Piste : baser `max_workers` sur les cœurs **physiques** plutôt que sur
`cpu_count()`. Vérifier aussi `get_safe_worker_count()` (`:944`), autre chemin.

### 9.3 Le `.tolist()` du §4.4 exige un commit préalable défensif

Retirer les `.tolist()` (`robustness.py:595` et `:614`) casserait **quatre**
tests de véracité, dont **deux silencieusement** — `if thicknesses_all:` sur un
ndarray 2D lève `ValueError`, avalée par le `except` englobant :

| Site | Effet |
|---|---|
| `certus/ui/certus_strat_thickness_ui.py:402` | 🔇 silencieux — stats par couche vides |
| `certus/ui/certus_strat_table_ui.py:164` | 🔇 silencieux — colonne en erreur tronquée |
| `certus/core/certus_strat_robustness.py:1081` | échec franc |
| `certus/utils/certus_strat_service.py:1220` | échec franc |

C'est le mode de défaillance de `bc2042a` (§3 du document : 278 évaluations
fausses sur 48 000, sans erreur visible). **Faire d'abord un commit séparé et
neutre** remplaçant les 4 tests par `is None or len(...) == 0`, puis seulement
basculer le producteur. Gain CPU estimé faible (~1-3 %), mais ~4× en mémoire —
ce qui compte sur 8 Go.

### 9.4 Deux pièges signalés

- **Docstring fausse**, `certus_strat_math.py:121` : elle annonce 200 nm de
  portée, le code balaie ±16 nm de **chemin optique**, soit ±16/|n| nm physiques
  (±6,96 nm pour Nb₂O₅, ±10,96 nm pour SiO₂). Erreur d'un facteur 12 à 29.
- **Ne pas réduire `scan_ot`** (`certus_strat_math.py:129`, valeur 16.0) en
  croyant faire une optimisation iso-résultat. Le terme `balance` de
  `_compute_local_extrema_symmetry_score`
  (`certus/utils/certus_strat_context.py:264-265`) utilise les distances brutes,
  pas saturées : tronquer le scan **change le classement des stratégies**.

---

## 10. Analyse statique — 5 pistes restantes

Seconde vague de fan-out. Les 5 analyses ont abouti ; **les 4 vérificateurs et la
synthèse ont été tués par le quota**. Statut par défaut : **NON VÉRIFIÉ**, sauf
✅ = contrôlé à la main dans cette session.

### 10.1 ✅ Le cache numba n'a JAMAIS été dans `%TEMP%` — le §4.3 dit le contraire

`REPRISE_PERF.md` §4.3 affirme, en gras et avec un ⚠️, que `configure_numba_env`
place déjà le cache dans `%TEMP%\CERTUS_Numba_Cache`, hors du dossier synchronisé,
et conclut « ne repars pas sur cette piste ».

**C'est faux, et l'instruction de ne pas creuser était donc infondée.**

`configure_numba_env` ne pose `NUMBA_CACHE_DIR` qu'en `certus/core/certus_core.py:359-361`,
mais la branche de `:334` (`if "numba" in sys.modules ...`) **retourne en `:352`
avant d'y arriver**. Or `scripts/bench_examples.py:443` fait `import certus_physics`
— qui importe numba — **avant** la ligne `:444` qui importe `CERTUS_INDEX`, seul
endroit appelant `_configure_numba_env()`. La branche est donc toujours prise.
`tests/conftest.py` ne pose rien non plus.

Aggravant, lu dans numba 0.66 installé : le locator de cache est figé **à la
décoration**, pas à la compilation (`numba/core/caching.py:414-420`). Poser la
variable après le premier import `@njit` est sans effet de toute façon.

✅ **Vérifié à la main :**

| Contrôle | Résultat |
|---|---|
| `%TEMP%\CERTUS_Numba_Cache` | **n'existe pas** |
| `.nbi` dans les `__pycache__` du dépôt | **58 fichiers** |

Le cache JIT vit donc **à côté des sources** — c'est-à-dire, avant le
rapatriement, **dans le dossier Google Drive**. Les 18,6 % / 23 % de `_path_stat`
du §4.3 étaient très probablement ce cache lu à travers Drive.

⚠️ **Conséquence de mesure** : le banc et l'application n'utilisent pas le même
répertoire de cache. Un « cache chaud » mesuré par `bench_examples.py` ne dit
rien du cache de `python CERTUS_INDEX.py`, qui n'a jamais été peuplé ici.

### 10.2 §4.3 — la mesure elle-même est l'artefact

`scripts/bench_examples.py:687` : **la fenêtre d'échantillonnage englobe l'import
de l'application**. Les 18,6 % et 23 % de `_path_stat` ne sont donc **pas du temps
de calcul** — c'est le chargement des modules, compté dans le profil.

La piste « remonter les imports tardifs » ne peut pas rapporter ce que le §4.3
espère. Ce qui reste, plus modeste mais réel :

- `certus/spline/spline_workers.py:789` — **4 à 5 imports par évaluation
  L-BFGS-B**, tous redondants avec le bloc d'en-tête. Supprimables sans risque.
- `certus/core/certus_index_solvers.py:240` — le seul import tardif d'INDEX
  capable de produire un vrai `_path_stat` pendant le run.
- `certus/workers/certus_index_workers.py` — les 11 imports tardifs sont **NON
  déplaçables**, cycle d'import prouvé. Ne pas y toucher.

### 10.3 §4.5 RÉSOLU — `use_cache=True` n'est PAS sûr, et on sait pourquoi

La question ouverte du document trouve sa réponse, et **ce ne sont pas les
1,78e-15 de réassociation flottante**. C'est une **perte d'information dans la clé
de cache**.

`SplineBasisCache.get` arrondit les positions de nœuds à **6 décimales** pour
construire sa clé (`certus/physics/certus_optical_models.py:419`). Les longueurs
d'onde de METAL sont en **nanomètres** (`CERTUS_METAL_SINGLE.py:1256` :
`knot_l = np.array([400.0, 800.0])`). Le quantum de la clé vaut donc **1e-6 nm**,
soit **100× le pas de différence finie de L-BFGS-B (1e-8)**.

**La perturbation du gradient est exactement annulée par l'arrondi de la clé.**
L'optimiseur calcule des dérivées sur un objectif devenu localement constant.

Trois corollaires, tous ancrés :

- `certus_optical_models.py:453` — la matrice stockée n'est pas reconstruite à
  partir de la clé : l'objectif devient **dépendant de l'historique du cache**,
  donc non reproductible d'un run à l'autre.
- `tests/oracle/test_spline_basis_cache.py:46` — le garde-fou censé attraper
  exactement ce bug **ne peut pas le voir** : il déplace les nœuds de 1e-4, soit
  100× le quantum de la clé.
- `scripts/bench_examples.py:307` — **le 55,9 s → 24,7 s ne mesure pas ce que le
  §4.5 propose** : `--force-cache` patche globalement, y compris des sites que le
  plan ne prévoit pas de basculer. Le gain annoncé n'est pas celui de l'action.

Même pathologie ailleurs, en pire : `certus/utils/certus_re_math.py:396` arrondit
les nœuds à 0,1 nm et la grille à 1 nm — quantum **100 000× plus grossier**.

**Conclusion : ne pas basculer `use_cache=True` en l'état.** Les sites où les
positions de nœuds sont figées sont immunisés ; ceux où elles varient ne le sont
pas.

### 10.4 La sur-souscription est systémique, pas locale

> **AUCUN endroit du dépôt ne connaît la notion de cœur physique.** Pas de
> `psutil`, pas de `cpu_count(logical=False)`. 100 % des décisions de
> parallélisme dérivent de `os.cpu_count()` / `multiprocessing.cpu_count()`, qui
> vaut **8** ici. Le facteur 2 du SMT est donc **systématique**.

| Fichier:ligne | Constat |
|---|---|
| `certus/core/certus_core.py:226` | `get_safe_worker_count()` rend **7 workers** pour 4 cœurs physiques ; `_RESERVED_CORES_FOR_WORKERS` a son adaptativité **inversée** |
| `certus/core/certus_core.py:379` | `NUMBA_NUM_THREADS` = logiques − 1 = **7 threads OMP par noyau** |
| `certus/core/certus_strat_consensus.py:525` | **Trois autres sites** du type de `:314`, et pires : 7 workers × 2 threads numba |
| `certus/core/certus_index_solvers.py:511` | Le garde-fou anti-sur-souscription de PGlobal est posé **sur le mauvais thread** — `set_num_threads` avant création du pool, le masque n'atteint aucun worker : **inerte** |
| `certus/core/certus_re_solvers.py:174` | RE : **deux pools imbriqués à 8 threads chacun**, aucun bridage numba sur tout le chemin |
| `certus/workers/certus_field_workers.py:308` | Deux pools non bornés, et un noyau défini en double |
| `certus/physics/certus_optimizers.py:892` | ✅ `2572f46` est **adaptatif** et reste pertinent — **corrige le §5.4 ci-dessus, où j'avais tort** |

### 10.5 ✅ Le bloc colorimétrie de `warmup_physics` est mort depuis des années

`certus/core/_certus_physics_impl.py` : `:1419` construit `wls` sur **50 points**,
`:1490` construit `R_test` sur **10 points**, et `:1492` fait
`np.interp(CIE_LAMBDA, wls, R_test)` → `ValueError`, avalée par le
`except RuntimeError, ValueError:` de `:1502`. Tout ce qui suit dans le bloc n'est
jamais compilé.

✅ **Vérifié par artefact disque** — les `.nbi` présents sont exactement ceux des
appels situés **avant** la ligne 1492 (`_lab_f`, `_lab_f_inv`,
`_gamma_correct_scalar`), et il n'existe **aucun** `.nbi` pour
`_xyz_from_spectrum_kernel` ni `delta_e_2000`. La coupure sur disque tombe
précisément au point de rupture.

Correctif : `R_test = np.full(len(wls), 0.5, dtype=np.float64)`. Gain nul sur
INDEX (la colorimétrie n'est pas sur le chemin chaud) — l'intérêt est
méthodologique : **un bloc de warmup peut mourir sans le moindre bruit**, et la
présence du `.nbi` est un contrôle qui ne coûte aucun calcul.

### 10.6 §4.2 — l'hypothèse prioritaire est infirmée, la vraie cause est ailleurs

Un balayage AST des **111 fonctions `@njit`/`@jit`** du paquet `certus` montre
qu'**elles portent toutes `cache=True`**, sans exception. Aucun cache n'a été
perdu avec numba 0.66 : mon hypothèse était fausse.

La vraie cause du JIT pendant le run est ✅ `certus/core/certus_index_solvers.py:255` :
`X = np.empty((n, self.dim), dtype=np.float32)`. Les échantillons partent en
**float32** vers `TLUObjective.__call__` (`certus_index_objectives.py:1755`, les
54 % du profil), tandis que la phase locale scipy repasse en **float64**. numba
compile donc **deux signatures** du chemin chaud, et `warmup_physics` — qui ne
passe que des float Python — n'en couvre qu'une. Une **troisième** variante
`readonly` existe, produite par l'idiome `np.frombuffer(clé_en_octets)` des caches
lru (`certus_optical_models.py:534-536`, `spline_objective.py:33`).

Corroboré par `pickletools` sur les `.nbi` : 2 à 3 `.nbc` par fonction
(`epsilon2_TLU_array`, `epsilon1_TL_analytic`, `calculate_RT_single_layer_backside_array`).

> **Ce ne sont pas des noyaux oubliés, ce sont des SIGNATURES oubliées sur des
> noyaux déjà réchauffés.**

⚠️ Passer `:255` en float64 change le pas d'échantillonnage, donc la trajectoire
de l'optimiseur. **À ne tenter qu'après réparation de l'extraction `RESULT` du
banc INDEX (§3)** — sinon c'est un changement numérique sans filet.

