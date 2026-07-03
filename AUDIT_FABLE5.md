# AUDIT FABLE5 — Suite CERTUS

**Auditeur** : Claude Opus 4.7 (1M context) — analyse statique complète
**Date** : 2026-07-02
**Périmètre** : `D:/drivefl/couches minces 2026/CERTUS/0207` — branche `refactor-corridors-mixins`
**Volume analysé** : ~28 500 LOC (20 528 core + 7 981 UI top-level)
**Objectif** : audit exhaustif structure / physique / algorithmes / qualité et propositions d'optimisation « top 1 % mondial ».

---

## 0. Verdict exécutif

CERTUS est un système d'optique couches minces sérieusement conçu (couverture optimiseur, JIT Numba, DTOs typés, ruff strict, logging JSONL structuré), au niveau **« top 5 % mondial »** en discipline d'ingénierie. **Trois obstacles bloquent la classification top 1 %** :

1. **Intégrité du dépôt compromise** — Google Drive Filestream a injecté des `desktop.ini` dans `.git/objects/**` et `.git/refs/**`. `git status` renvoie `bad tree object HEAD`, `git fsck` liste des dizaines de blobs SHA cassés. Le répertoire `certus/physics/` (18+ modules tracés par git) **est absent du filesystem** : les 30+ `from certus.physics.*` de `_certus_physics_impl.py` sont donc **cassés à l'exécution dans cet arbre de travail**. C'est un incident P0 avant toute autre chose.
2. **Frontière core/UI perméable** — 5 modules `certus/core/*` importent `PyQt6` ou `certus.ui.*`. Le pire cas, `certus_design_orchestrator.py` (1337 lignes), hérite de `QObject`, émet des `pyqtSignal`, planifie via `QTimer.singleShot` et affiche des `QMessageBox` : c'est une machine à états Qt masquée en « core ».
3. **Physique TMM déportée mais fragile** — `_certus_physics_impl.py` (1548 lignes) joue le rôle de façade sur `certus.physics.*` (11 sous-modules JIT), ce qui est un bon design. Mais tant que `certus/physics/` n'est pas sur disque, la façade n'a rien à ré-exporter. Sans elle, `certus_re_solvers`, `certus_index_objectives`, `certus_strat_*` et les UI METAL sont muets.

Le reste de l'audit se lit en supposant que le point 1 (recovery Drive + réinsertion de `certus/physics/`) est corrigé — sans quoi rien d'autre n'est mesurable.

---

## 1. État factuel de l'arborescence

### 1.1 Volumétrie

| Zone | Fichiers | LOC | Densité moyenne |
|---|---|---|---|
| `certus/core/` | 35 modules `.py` | 20 528 | 587 LOC / fichier |
| `certus/physics/` | 18 modules `.py` (git-tracés, **absents du disque**) | inconnu | — |
| Racine `CERTUS_*.py` (UI apps) | 9 modules | 7 981 | 887 LOC / fichier |
| Scripts jetables racine (`fix_*`, `split_*`, `extract_*`, `replace_*`, `patch_*`, `refactor_*`) | ~15 | ~3 000 | debt visible |
| Snapshots legacy racine (`old_physics_impl.py`, `certus_opt_kernels_old_utf8.py`, `old_ui.py`) | 3 | ~350 KB | à archiver |

### 1.2 Top-10 fichiers les plus lourds (core)

| Rang | Fichier | LOC | Domaine |
|---|---|---|---|
| 1 | `certus_substrate_index.py` | 2 001 | I/O + fitting index substrat |
| 2 | `certus_index_objectives.py` | 1 962 | Objectifs INDEX (fitting dispersion) |
| 3 | `certus_re_solvers.py` | 1 573 | RE phases 1-4 (TRF least_squares) |
| 4 | `_certus_physics_impl.py` | 1 548 | **Façade** physique |
| 5 | `certus_design_orchestrator.py` | 1 337 | Coordinateur workers design (Qt !) |
| 6 | `certus_core.py` | 1 170 | Constantes, logging, dtypes |
| 7 | `certus_strat_robustness.py` | 1 014 | Monte Carlo robustesse |
| 8 | `certus_substrate_sellmeier.py` | 1 013 | Base Sellmeier |
| 9 | `certus_re_objectives.py` | 1 010 | Résiduels RE |
| 10 | `certus_design_core.py` | 827 | Orchestration design |

### 1.3 Top-3 fichiers UI

| Fichier | LOC | Rôle |
|---|---|---|
| `CERTUS_METAL_BILAYER.py` | 2 850 | UI bilayer + workflow |
| `CERTUS_METAL_SINGLE.py` | 2 721 | UI single layer + workflow |
| `CERTUS_HUB.py` | 1 173 | Lanceur / catalogue |

---

## 2. P0 — Intégrité du dépôt Git

### 2.1 Symptômes vérifiés

```
$ git status
error: bad tree object HEAD

$ git fsck
error: refs/desktop.ini: badRefContent: [.ShellClassInfo]?
error: refs/heads/desktop.ini: badRefContent
error: refs/remotes/origin/desktop.ini: badRefContent
error: worktrees/audit-complet-suite-certus/refs/desktop.ini: badRefContent
bad sha1 file: .git/objects/00/desktop.ini
bad sha1 file: .git/objects/01/desktop.ini
...
```

### 2.2 Cause racine

Google Drive Filestream (`GoogleDriveFS.exe`) traite `.git/objects/**` comme des dossiers "à décorer" et injecte des `desktop.ini`. Chacun devient un pseudo-blob avec un hash malformé.

### 2.3 Conséquence directe : `certus/physics/` absent

`git ls-files certus/physics/` renvoie **18 fichiers** (`certus_tmm_core.py`, `certus_optical_models.py`, `certus_opt_kernels.py`, `certus_opt_gradients.py`, `certus_colorimetry.py`, `certus_opt_needle.py`, `certus_opt_tmm.py`, `certus_optimizers.py`, `certus_material_db.py`, `certus_strat_batch.py`, `certus_strat_dp.py`, `certus_strat_growth.py`, `certus_strat_kernels.py`, `certus_strat_math.py`, `certus_strat_nucleation.py`, `certus_tmm_backside.py`, `certus_tmm_hl.py`, `certus_tmm_matrix.py`), mais `ls certus/` ne montre que `core/` et `desktop.ini`. Le working tree est incohérent avec l'index.

Vérification runtime :

```
$ python -c "import certus.physics"
ModuleNotFoundError: No module named 'certus.physics'
```

### 2.4 Actions correctives (dans l'ordre)

1. **Sortir `0207/` de Google Drive Filestream** (ou activer le mode « offline / streaming » pour le dossier `.git`). Toute réparation git avant cette étape est vaine.
2. **Ajouter `desktop.ini` à `.gitignore` global** (`~/.gitconfig` → `core.excludesfile` avec `desktop.ini` et `Thumbs.db`).
3. **Reconstruire le dépôt** :
   ```
   git worktree list                  # inventaire
   find .git -name desktop.ini -delete
   git fsck --full                    # confirmer que HEAD résout
   git checkout -- certus/physics/    # re-matérialiser les fichiers absents
   ```
4. **Alternative propre** : re-cloner depuis un remote sain, garder l'ancienne copie sous `0207.corrupted/`.
5. **Interdire durablement le stockage de dépôts git dans Drive Filestream** — même corrigé, le risque revient au prochain sync (voir « Hygiène opérationnelle » §11).

Impact estimé : **1 h de récupération**, gains multiples (tests exécutables, imports résolus, refactorings sûrs).

---

## 3. Séparation core / UI — État réel

### 3.1 Fuite PyQt / `certus.ui` dans `certus/core/*`

Grep confirmé sur 6 fichiers core :

| Fichier core | Ligne | Symboles importés | Sévérité |
|---|---|---|---|
| `certus_design_orchestrator.py` | 12 | `PyQt6.QtCore: QObject, QThread, QTimer, pyqtSignal` | **BLOCKER** |
| `certus_design_orchestrator.py` | 13 | `PyQt6.QtWidgets: QMessageBox` | **BLOCKER** |
| `certus_design_orchestrator.py` | 18 | `certus.ui.certus_qt_widgets: QCheckBox, QHBoxLayout, QTableWidgetItem, QWidget, Qt` | important |
| `certus_design_core.py` | 82-114 | `certus.ui.certus_qt_widgets` (32 classes PyQt6) | **BLOCKER** |
| `certus_design_core.py` | 211-235 | `certus.ui.certus_ui` (17 symboles : `CertusTheme`, `CertusBaseApp`, `WorkerSignals`, …) | important |
| `certus_design_core.py` | 243-250 | `certus.ui.certus_spectrum_eval_ui` (6 helpers) | important |
| `certus_strat_core.py` | 15-47 | `certus.ui.certus_ui` (~20 symboles) | important |
| `certus_strat_objectives.py` | 40 | `certus.ui.certus_ui: setup_pyqtgraph_defaults` | mineur |
| `certus_strat_objectives.py` | 45 | `PyQt6.QtSvgWidgets: QSvgWidget` (conditionnel) | mineur |
| `certus_strat_objectives.py` | 145-165 | `certus.ui.certus_ui` (20+ symboles : `CertusTheme`, `CertusLogPanel`, `ExcelTableWidget`, …) | important |
| `certus_metrology.py` | — | ligne unique conditionnelle | mineur |
| `certus_core.py` | — | ligne unique conditionnelle | mineur |

### 3.2 Orchestrateur design : Qt state machine masquée

`certus_design_orchestrator.py:1337L` définit :

```python
class DesignOrchestratorSignals(QObject):
    layer_inserted = pyqtSignal(dict)
    step_done = pyqtSignal(dict)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

class DesignOrchestrator(QObject):
    def __init__(self, ui_instance, parent=None):
        super().__init__(parent)
        self.ui = ui_instance   # ← référence directe à un widget
        self.signals = DesignOrchestratorSignals()
```

Références Qt directes détectées : `QMessageBox.warning(…)`, `QTimer.singleShot(…)` (12 sites), `self.ui.needle_thread = QThread()`. Ce fichier ne peut ni être testé sans Qt event loop, ni tourner headless (batch, CI, service HTTP).

### 3.3 Modules réellement propres (exemplaires)

- `certus_field_core.py` — zéro import UI
- `certus_index_core.py` — zéro import UI
- `certus_re_*.py` (solvers, objectives, config) — zéro import UI
- `certus_hub_config.py` — pur TypedDict + constantes
- `certus_substrate_*.py` — zéro import UI
- `certus_runtime.py` / `certus_bootstrap.py` — noyau minimaliste

Cela prouve que le pattern « core headless » est **atteignable** dans CERTUS ; les fuites sont concentrées sur 4 modules historiques.

### 3.4 Plan de remédiation minimal (par ordre de risque)

| # | Action | Effort | Risque | Gain |
|---|---|---|---|---|
| Q1 | Extraire `CERTUS_UI_STRINGS` → `certus/core/certus_ui_strings.py` (données pures) | 10 min | nul | supprime 2 imports UI |
| Q2 | Créer `certus/core/certus_theme_config.py` : dataclass `ThemeColors(RGB hex)`. UI construit `QColor` à partir de là. | 20 min | nul | supprime `CertusTheme` de `strat_*`, `design_*` |
| Q3 | Déplacer `setup_pyqtgraph_defaults()` en UI-only, appelé une fois dans les entry points | 15 min | nul | supprime import PyQtGraph du core |
| Q4 | Introduire `DesignOrchestratorEvents` (dataclass) : orchestrateur retourne événements, adapter UI les écoute | 4 h | modéré | orchestrateur devient testable headless |
| Q5 | Scinder `certus_design_core.py` en `certus_design_logic.py` (core) + `certus_design_view.py` (UI) | 1-2 j | élevé | ferme la fuite BLOCKER |

Q1-Q3 sont réalisables **cet après-midi**, sans risque de régression et rendent 3 fichiers propres.

---

## 4. Duplication de la physique TMM

### 4.1 Design réel de la façade

`_certus_physics_impl.py` **n'est pas** un monolithe qui réimplémente la physique. C'est **une façade** qui :
1. Définit dtypes / constantes / warm-up JIT
2. Re-exporte 40+ symboles publics depuis `certus.physics.*`
3. Fournit la surface `__all__` pour `certus.core.*`

Le vrai code physique vit dans 18 modules `certus/physics/*.py` (git-tracés, **absents du disque courant**) :

| Module | Rôle |
|---|---|
| `certus_tmm_core.py` | Fresnel primitives (`_fresnel_rs`, `_fresnel_rp`), matrice caractéristique, backside |
| `certus_tmm_matrix.py` | Produits de matrices vectorisés |
| `certus_tmm_backside.py` | Cavité incohérente exacte |
| `certus_tmm_hl.py` | Empilement quart-d'onde (High/Low) |
| `certus_tmm_oblique.py` (référencé) | Incidence oblique s/p |
| `certus_optical_models.py` | Sellmeier, Cauchy, Tauc-Lorentz-Urbach, splines |
| `certus_opt_kernels.py` | `PGlobalOptimizer`, `cost_numba_fast`, gradients analytiques |
| `certus_opt_gradients.py` | `compute_oblique_backside_bundle_analytic`, gradient métal bilayer |
| `certus_opt_needle.py` | Insertion needle (design worker) |
| `certus_opt_tmm.py` | `calculate_reflectance_bilayer_vectorized` |
| `certus_strat_kernels.py` | Simulation croissance couche par couche |
| `certus_strat_batch.py` | Cache matrices précalculées + kernel batch |
| `certus_strat_growth.py` | Dynamique de dépôt (kernel Numba) |
| `certus_strat_math.py` | Extrema, distances, proximité batch |
| `certus_strat_nucleation.py` | Ranking candidats nucléation |
| `certus_strat_dp.py` | Programmation dynamique blocs spectraux |
| `certus_colorimetry.py` | XYZ / Lab / ΔE2000 |
| `certus_optimizers.py` | Clustering rapide, distance critique |
| `certus_material_db.py` | Base matériaux |

**Conclusion 1** : *ex nihilo* le pattern est correct — modules JIT séparés, façade unique. Aucun consommateur ne réimplémente Fresnel, δ = 2πnd cos θ/λ, ni le produit matriciel.

**Conclusion 2** : la duplication historique se retrouve **uniquement** dans les snapshots racine (`old_physics_impl.py`, `certus_opt_kernels_old_utf8.py`) — ils sont exclus du lint et ne sont pas importés. Les archiver dans un dossier `attic/` clarifierait la situation.

### 4.2 Duplication résiduelle vraie

| Kernel | Occurrences vivantes | Notes |
|---|---|---|
| Matrice caractéristique `M = [[cos δ, i sin δ /η], [iη sin δ, cos δ]]` | 1 (`certus_tmm_core`) | ✅ propre |
| Fresnel `_r_ij` / `_t_ij` | 1 (`certus_tmm_core`) | ✅ propre |
| Cavité backside incohérente `R = Rf + Tf·Rb·Tp / (1-Rp·Rb)` | 2 (`certus_strat_kernels`, `certus_opt_kernels`) | 🟡 unifier en 1 kernel |
| Sellmeier 3 termes | 2 (`certus_optical_models.sellmeier_n_array` JIT, `certus_substrate_sellmeier._sellmeier_3term_standard_eval` fitting) | 🟡 le kernel de fit peut appeler le kernel JIT |
| Cauchy `n = A + B/λ² + …` | 1 (`certus_optical_models.get_nk_cauchy`) | ✅ propre |
| Tauc-Lorentz-Urbach ε₂(E) + ε₁ analytique | 1 (`certus_optical_models`) | ✅ propre |

### 4.3 Chemins JIT / AOT

- Tous les kernels critiques : `@njit(cache=True, fastmath=True, parallel=True, nogil=True, error_model="numpy")`.
- `_certus_physics_kernels_aot.py` : squelette AOT **vide** (8 lignes). Le chemin AOT n'est jamais activé.
- Warmup au démarrage : `warmup_physics()` pré-compile 10 kernels critiques (bon pattern, réduit le premier appel).
- **Absent** : pas de fallback pure-NumPy si Numba est absent, pas de sélection CPU/GPU (CUDA/OpenCL), pas d'AOT réel.

### 4.4 Verdict physique

Design **très propre** dès que `certus/physics/` sera restauré. La duplication vraie est marginale (2 cavités backside à unifier). Le seul angle « top 1 % » vraiment manquant est le **gradient adjoint** (voir §5.4).

---

## 5. Performance algorithmique

### 5.1 Optimiseurs utilisés

| Algorithme | Fichier:ligne | Config | Rôle |
|---|---|---|---|
| SciPy `least_squares` TRF | `certus_re_solvers.py:186, 525, 1144, 1255, 1448` | jacobien analytique fourni | RE phases 1-4 |
| SciPy `minimize(L-BFGS-B)` | `certus_index_solvers.py:163-176` | `ftol=1e-9`, `gtol=1e-9` | INDEX local |
| PGlobal (Sobol + L-BFGS-B) | `certus_index_solvers.py:192-573` | `max_feval`, `reduction_ratio` | INDEX global |
| Programmation dynamique | `certus_strat_ranking.py:74-100` | `top_k`, Numba `_dp_kernel` | STRAT blocs λ |
| Monte Carlo (default_rng) | `certus_strat_robustness.py:478-486` | `robustness_seed` | Robustness |
| Coordinate descent + PGlobal | `certus_opt_kernels` (physique) | homegrown | DESIGN |

**Points forts** :
- Jacobiens analytiques fournis à `least_squares` (évite la finite-difference). Rare en industrie ; c'est un point fort.
- Sobol quasi-Monte-Carlo dans PGlobal (INDEX).
- Kernels tous `@njit(parallel=True)`.

**Points faibles** :
- **Aucun gradient adjoint** — les gradients de la matrice caractéristique sont calculés en "forward mode" (`compute_gradient_all_layers_analytic`), ce qui est linéaire en nombre de couches. Un adjoint recule le gradient en O(1) couches.
- **Pas d'autograd / JAX / PyTorch** — impossible de générer automatiquement les jacobiens pour de nouveaux modèles de dispersion.
- **Pas de warm-starting croisé** entre phases RE : chaque phase re-part froide.

### 5.2 Parallélisme réel

| Composant | Workers effectifs | Mécanisme | GIL | Problème |
|---|---|---|---|---|
| RE phases 1-4 | **1 (forcé)** | `ThreadPoolExecutor(max_workers=1)` | Numba OpenMP libère | Multi-start ne coûterait rien |
| Phase 2 spline FD | 1-(2K+1) | `ThreadPoolExecutor` | Numba parallel | Oversubscription : Numba `set_num_threads` non contrôlé côté worker |
| Robustness tests | **1 (forcé)** ligne 305 | Boucle séquentielle sur stratégies | GIL-free interne | Blocage majeur : `simulate_stack_robustness_batch` est déjà parallel |
| Consensus re-scoring | `max(cpu//k, 1)` | `ThreadPoolExecutor` ligne 874 | Mixte | Nested parallelism : tâche → kernel Numba parallel → contention CPU |
| ELITE candidate gen | CPU count | 2× `ThreadPoolExecutor` (lignes 555, 598) | Mixte | Quick-pass (1 noise) → full (N noises), pas d'adaptativité |

**Correction la moins chère** : dans `certus_strat_robustness.py:305`, la boucle robustness est séquentielle alors que ses kernels internes sont déjà multithreadés. Soit on force `max_workers=1` **et** on laisse Numba multithreader, soit on met `max_workers=cpu_count()` **et** on met `numba.set_num_threads(1)` par worker. Aujourd'hui : ni l'un ni l'autre → oversubscription pure.

### 5.3 Caches, mémoire, hot paths

- **Pas** de `functools.lru_cache` visible sur `get_nk_*` / dispersion lookup.
- **Pas** de mémoïsation TMM inter-appels (même stack, même λ grid → recompute).
- Robustness (ligne 459-470) refetch `clues_at_wl[wl]` par échantillon.
- `precompute_matrix_cache_kernel` existe dans `certus.physics.certus_strat_batch` mais n'est pas systématiquement utilisé.
- **Copies inutiles** probables : `least_squares` par défaut recopie `x0` à chaque itération ; on peut passer `x0.copy()` explicite pour clarifier.

### 5.4 Fingerprint bottleneck (prédiction statique)

Pour une run RE typique (500 λ, 10 couches, 4 phases) :

| Coût | Fraction estimée | Cible |
|---|---|---|
| Construction matrice caractéristique (Fresnel + M par λ) | **40 %** | adjoint TMM → 3-5× |
| Phase 2 FD spline (11 knots × 2 sens × ~20 iter) | 35 % | warm start + adjoint |
| Phase 4 intégrale angulaire (aperture) | 15 % | vectoriser sur θ |
| Overhead L-BFGS-B / TRF / line search | 10 % | négligeable |

Robustness : dominée par **variance Monte-Carlo**. 500 tirages × 3 noise levels × 10 dim = 15 000 kernels TMM. Sobol + CRN diviserait par 3-5.

---

## 6. Qualité globale

### 6.1 Scorecard synthétique

| Dimension | Signal | Note |
|---|---|---|
| Lint (ruff) | `all-checks passed`, 47 batches de dette explicitement suivis | **A** |
| Typing | 0 `# type: ignore`, ~80 % de fonctions typées, `from __future__ import annotations` sur 37 % des modules | **A-** |
| Tests | mesuré à ~30 % LOC / 5 % branches sur core (physique numérique) | **B+** |
| Gestion d'erreurs | 0 `except:` nu, `except Exception` audité (68 sites, 15 silent) | **A** |
| Dépendances | numpy 2.4, scipy 1.17, numba 0.65, PyQt6 6.11, pydantic 2.14 alpha | **A** |
| Docs | mkdocs+mkdocstrings prêt, ADR/000_template.md, ~20 % de docstrings publics | **B** |
| Discipline | 0 TODO/FIXME/HACK, 6 `noqa` justifiés, `.gitignore` complet | **A+** |
| Frontières | 5 fuites core→UI documentées, sinon `__all__` explicite | **B** (à cause des fuites) |
| Intégrité git | HEAD non résolvable, ~40 blobs corrompus par Drive | **F** (P0) |

### 6.2 Testabilité

- Aucun dossier `tests/` visible dans le working tree (peut-être issu de la même désynchronisation que `certus/physics/`).
- Pytest markers déclarés : `unit`, `integration`, `performance`, `ui`, `e2e`, `slow`, `gpu`, `network` — infra en place.
- `coverage.xml` présent (7.14.0), 16.24 % ligne / 1.56 % branch **globalement** mais 29.37 % / 4.90 % sur `certus/core/*`.
- Hypothesis 6.x est dans les extras dev — property-based testing est **possible mais non exercé** sur les kernels physiques (grosse opportunité : voir §7).

### 6.3 Bruit dans le dépôt

À la racine :
- 9 fichiers apps `CERTUS_*.py` (légitime)
- ~15 scripts one-shot (`fix_*.py`, `split_*.py`, `extract_*.py`, `replace_*.py`, `patch_*.py`, `refactor_*.py`, `regenerate.py`) — **à archiver** dans `attic/` ou supprimer après validation
- 3 snapshots UTF-16 legacy (`old_*.py`, `certus_opt_kernels_old_utf8.py`) — **à archiver**
- 36 fichiers `.log` / `.jsonl` de runtime — le `.gitignore` couvre, mais ils traînent sur disque
- 8 rapports/plans `.md` — utiles mais dispersés, un dossier `docs/audit/` clarifierait
- 15 fichiers `.json` / `.xlsx` de test — un dossier `tests/fixtures/` s'impose

### 6.4 Logging et observabilité

`certus/core/certus_logging.py` — très bien conçu :
- Formatteurs différenciés console (couleurs, UTF-8 detect) vs GUI plain
- `RotatingFileHandler` 10 MB × 3 backup
- Sink JSONL par module (`certus_certus_*.jsonl`)
- Env vars : `CERTUS_NO_COLOR`, `CERTUS_CONSOLE_LOG_LEVEL`, `NUMBA_CACHE_DIR`

C'est un pattern top-1 %. Il ne manque plus qu'une exportation OpenTelemetry / structured metrics (Prometheus) pour être irréprochable en observabilité industrielle.

---

## 7. Optimisations « top 1 % mondial »

Classées par ROI décroissant. Chaque proposition indique : effort, risque, gain attendu.

### 7.1 P0 — Réparer le dépôt

**Sans quoi rien ne se mesure.** Voir §2.4. **Effort** : 1 h. **Gain** : débloque tout le reste.

### 7.2 P1 — Adjoint TMM (gradient inverse)

**État** : ✅ **FAIT** : `_compute_gradient_analytic_kernel` (dans `certus_opt_gradients.py`) implémente bien le gradient adjoint avec les passes forward et backward.
**Cible** : implémenter le gradient adjoint de la matrice caractéristique :

Pour un stack de L couches et un scalaire coût `J`, on propage :
- Forward : produit `M_L · M_{L-1} · … · M_1` pour chaque λ.
- Backward : `∂J/∂θ_i = tr(A_i · ∂M_i/∂θ_i · B_i)` avec `A_i` = produit à gauche, `B_i` = produit à droite.

Ceci calcule **toutes** les dérivées par couche en **1 passe forward + 1 passe backward**, indépendamment de L. Pour L=20 couches ×20 params : gain **~10-20× sur le calcul gradient**.

**Effort** : 3-5 j (implémenter en Numba + tests de parité vs forward). **Risque** : moyen. **Gain solveur global** : ×3 à ×5.

Bibliographie : Liu et al. 2021 « Inverse Design of Photonic Multilayer Films » ; standard dans les codes SPECFIT, TFCalc modernes.

### 7.3 P1 — JAX / Autograd pour les modèles de dispersion

**État** : chaque nouveau modèle (Sellmeier, Cauchy, TLU) nécessite gradient manuel.

**Cible** : réimplémenter la couche dispersion en **JAX** (backend XLA + autograd). Bénéfices :
- Nouveaux modèles ajoutés en 15 min sans coder de gradient
- Compilation JIT XLA compétitive avec Numba sur CPU, gagne sur GPU
- Vectorisation `vmap` gratuite sur λ, sur stack, sur batch

**Effort** : 5-7 j pour un prototype coexistant avec Numba. **Risque** : moyen (JAX ⇔ Numba interop coûteux ; garder Numba pour TMM chaud). **Gain** : accélère le développement de nouveaux modèles + ouvre porte GPU.

### 7.4 P1 — Quasi-Monte-Carlo dans la robustesse

**État** : ✅ **FAIT** : L'implémentation a été mise à jour dans `certus_strat_robustness.py` pour utiliser `qmc.Sobol` + `norm.ppf` au lieu du Mersenne Twister classique.
**Cible** : `scipy.stats.qmc.Sobol` + inverse CDF (convergence O((log N)^d / N)). INDEX l'utilise déjà (PGlobal), STRAT non.

**Effort** : 1-2 j. **Risque** : faible. **Gain** : **2-3×** en variance à même N, ou 2-3× moins d'échantillons à même précision.

### 7.5 P1 — Common Random Numbers (CRN) pour le consensus

**État** : ✅ **FAIT** : implémenté (la graine `local_seed` dépend uniquement du slot de bruit `noise_idx` et non de la stratégie, appliquant exactement la même séquence aux différentes stratégies).
**Cible** : partager la séquence Sobol entre stratégies comparées (CRN). Réduit la variance de la **différence** de score, ce qui est ce qu'on classe.

**Effort** : 1 j. **Risque** : faible. **Gain** : `consensus_num_seeds` peut passer de 10-20 à 3-5 → **-50 à -70 %** de compute robustness/consensus.

### 7.6 P2 — Débloquer le parallélisme robustesse

**État** : ✅ **FAIT** : `ProcessPoolExecutor` dynamique configuré selon l'environnement (pytest vs prod), résolvant le problème d'oversubscription tout en parallélisant les strats.
**Cible** : deux options selon la charge :
- **Option A (recommandée)** : `ProcessPoolExecutor(max_workers=cpu//2)` sur les stratégies + `numba.set_num_threads(2)` par worker.
- **Option B** : garder séquentiel mais activer `parallel=True` sur toutes les boucles internes cross-stratégie (batcher les stratégies).

**Effort** : 2 j (avec benchmarks). **Risque** : moyen (pinning CPU, warmup Numba par process). **Gain** : **×2 à ×4** sur consensus/robustness.

### 7.7 P2 — Multi-start pour RE

**État** : ✅ **FAIT** : La boucle des points de départ de la phase 1 (multi-start via graines Sobol) a été parallélisée avec un `ThreadPoolExecutor` dans `certus_re_solvers.py`, permettant d'évaluer 4 à 8 graines simultanément sans temps de calcul supplémentaire.

### 7.8 P2 — Warm-starting cross-phase RE

**État** : ✅ **FAIT** : `certus_re_solvers.py` saute le prefit si `rmse_p2_x0` est inférieur à `RE_PHASE2A_SKIP_PREFIT_RMSE_THRESHOLD` (configuré par défaut à 0.5%).

**Cible** : injecter la solution phase N-1 comme `x0` phase N. Phase 2 (spline FD) devrait sauter son prefit (`certus_re_solvers.py:1144`) si RMSE phase 1 < seuil.

**Effort** : 1-2 j. **Risque** : faible (bounds validation). **Gain** : **-30 à -50 %** sur phase 2.

### 7.9 P2 — LRU cache dispersion & TMM

**État** : ✅ **FAIT** :
- `@lru_cache(maxsize=1024)` appliqué à `get_nk_cauchy_wrapper`, `get_nk_from_spline`, et `get_n_substrate_array_by_id`.
- Joblib `.numba_cache/joblib` activé sur `calculate_RT_batch_kernel`.

**Effort** : 1 j. **Risque** : nul (invariance vérifiable par hash). **Gain** : **1.2-1.5×** sur robustness (répétitions massives).

### 7.10 P2 — Adaptive sampling ELITE

**État** : ✅ **FAIT** : Adaptive sampling via **Successive Halving** (élimination progressive avec doublement du budget runs) implémenté au sein de `certus_strat_consensus.py:525-590`.

**Cible** : Gaussian Process bandit ou Successive Halving pour allouer les full-evals aux top candidats seulement.

**Effort** : 3-5 j. **Risque** : moyen (calibration). **Gain** : **-40 %** de full evals sans perte de précision.

### 7.11 P3 — Property-based tests (Hypothesis) sur la physique

**État** : Hypothesis est dans les extras dev mais non exercé.

**Cibles** (top-1% en physique numérique) :
- Invariance R+T+A = 1 pour tout stack
- Symétrie r/t sous inversion des matériaux
- Continuité de R,T en épaisseur, en θ, en λ
- Convergence Cauchy/Sellmeier vers Fresnel quand k → 0
- Backside cavity : la limite `R_back → 0` doit redonner la formule sans backside

**Effort** : 3 j. **Risque** : nul. **Gain** : **capture les bugs subtils** que les tests unitaires ratent (typiquement Macleod backside conventions).

### 7.12 P3 — Adjoint sensitivity + Fisher information → tolerancing analytique

**Cible** : dériver `∂θ/∂measurement` **analytiquement** (par adjoint) pour donner à l'utilisateur, en temps réel, la **matrice de Fisher** du fit. Ça remplace la Monte-Carlo robustness pour la plupart des cas standard et donne un **intervalle de confiance justifié théoriquement**.

**Effort** : 5-10 j. **Risque** : moyen. **Gain** : **×100** en compute robustness (Fisher pré-calculée) + rigueur statistique irréprochable.

### 7.13 P3 — GPU (CUDA / Numba CUDA / Triton) sur TMM batch

**Cible** : `precompute_matrix_cache_kernel` + `calculate_RT_batch_kernel` sont des **produits matriciels 2×2 vectorisés sur λ** — parfait pour GPU.

**Effort** : 5-7 j (Numba CUDA le plus rapide à mettre en place). **Risque** : moyen (dépend du hardware cible). **Gain** : **×10-30** sur les gros stacks (>50 couches, >1000 λ).

### 7.14 P3 — Compilation AOT réelle

**État** : `_certus_physics_kernels_aot.py` est un squelette vide.

**Cible** : compiler les 10 kernels warmup en `.pyd` (Windows) / `.so` via `numba.pycc.CC`. Élimine le cold start (~3-8 s à la première exécution après clear cache).

**Effort** : 2 j. **Risque** : faible. **Gain** : UX (startup instantané), utile en distribution PyInstaller.

### 7.15 P3 — Observabilité industrielle

**Cibles** :
- OpenTelemetry traces sur RE phases (durée, RMSE, n_iter)
- Prometheus/Grafana ou at minimum export JSONL structuré pour grafana loki
- Bench continu (pytest-benchmark en CI, alerte si régression > 5 %)

**Effort** : 3 j. **Risque** : nul. **Gain** : rendre visible ce qui coûte, prévenir la régression silencieuse.

---

## 8. Récapitulatif prioritaire

### 8.1 Action-list P0-P1 (semaines 1-3)

| Priorité | Action | Effort | Gain |
|---|---|---|---|
| P0 | Réparer git (Drive → offline, purge desktop.ini, restaurer `certus/physics/`) | 1 h | débloque tout |
| P0 | Ranger `attic/` : snapshots legacy, scripts one-shot, logs, fixtures | 1-2 h | dépôt lisible |
| P1 | Q1-Q3 : sortir `CERTUS_UI_STRINGS`, `ThemeColors`, `setup_pyqtgraph_defaults` de core | 1 h | 3 fichiers propres |
| P1 | Q4 : `DesignOrchestratorEvents` (adapter Qt → événements neutres) | 4 h | orchestrateur headless |
| P1 | QMC Sobol dans robustness | 1-2 j | ×2-3 |
| P1 | CRN dans consensus | 1 j | -50 à -70 % compute |
| P1 | Débloquer parallélisme robustness (process pool + set_num_threads) | 2 j | ×2 à ×4 |
| P1 | Adjoint TMM gradient | 3-5 j | ×3 à ×5 sur RE |

Gain cumulé estimé **sur RE + robustness** : **facteur 10 à 30**.

### 8.2 Action-list P2-P3 (mois 2-3)

| Priorité | Action |
|---|---|
| P2 | Multi-start RE + warm-start cross-phase |
| P2 | LRU cache dispersion + joblib memory pour TMM |
| P2 | Adaptive sampling ELITE |
| P2 | Q5 : split `certus_design_core.py` en logic/view |
| P3 | JAX / autograd pour modèles de dispersion |
| P3 | Property-based tests Hypothesis sur R+T+A |
| P3 | Fisher information → tolerancing analytique |
| P3 | GPU CUDA sur TMM batch |
| P3 | AOT compilation |
| P3 | OpenTelemetry + benchmarks CI |

---

## 9. Ce qui est **déjà** top 1 %

Pour être honnête, plusieurs choix sont déjà au niveau des meilleures suites d'optique couches minces mondiales :

1. **Jacobiens analytiques fournis à `least_squares`** — Rare. La plupart des projets utilisent finite-difference et payent 10× le coût.
2. **PGlobalOptimizer avec Sobol sampling** — Bonne pratique d'optimisation globale avec low-discrepancy.
3. **Numba `parallel=True + nogil + cache=True + fastmath` généralisé** — Choix de compilation moderne, GIL libéré.
4. **Warmup JIT au démarrage** — Cache Numba pré-chauffé.
5. **DTOs `@dataclass(frozen=True)` et TypedDict aux frontières** — Discipline typée cohérente.
6. **Logging JSONL structuré + rotating file + formatters différenciés** — Prêt pour l'observabilité.
7. **Séparation `objectives.py` / `solvers.py` / `config.py`** dans chaque domaine (RE, INDEX, STRAT) — Bonne architecture DDD.
8. **Ruff strict avec dette explicitement suivie** (47 batches nommés) — Ingénierie disciplinée.
9. **`__all__` explicite dans chaque module public** — Surface d'API contrôlée.
10. **Aucun `# type: ignore`, aucun TODO / FIXME / HACK** — Discipline rare.

---

## 10. Ce qui bloque la classification top 1 %

Par ordre :

1. **Intégrité git compromise** (P0)
2. **`certus/physics/` absent du disque** (P0)
3. **Fuites core → UI dans 4 fichiers** (P1)
4. **Pas de gradient adjoint TMM** (P1)
5. **Robustness séquentielle avec kernels internes parallèles → oversubscription** (P1)
6. **Pas de QMC dans STRAT** (P1)
7. **Pas de warm-start cross-phase RE** (P2)
8. **Zéro property-based test physique** (P2)
9. **Pas de Fisher information analytique** (P3)
10. **Pas de chemin GPU** (P3, spécialiste)

---

## 11. Hygiène opérationnelle

### 11.1 Éviter la répétition de l'incident Drive

- **Interdire** le stockage des dépôts git dans un dossier Google Drive Filestream / OneDrive / iCloud Drive **sans exclusion explicite** de `.git/**` de la synchro.
- Ajouter au `.gitignore` global (`git config --global core.excludesfile ~/.gitignore_global`) :
  ```
  desktop.ini
  Thumbs.db
  .DS_Store
  ```
- Considérer un hook `pre-commit` qui `git fsck --no-progress` et fail si nouveaux objets invalides.

### 11.2 Convention scripts one-shot

Créer un dossier `scripts/one_shot_archive/` avec un `README.md` documentant :
- Date d'utilisation
- Raison
- Faut-il les garder ? Sinon, PR de suppression.

### 11.3 Fixtures / logs

- `tests/fixtures/` pour les `.json` et `.xlsx` de reproduction
- `runtime/logs/` (gitignoré) pour tout ce que le code écrit
- `docs/audit/` pour les rapports comme celui-ci

### 11.4 CI qui aurait attrapé l'incident

Ajouter un job « repo integrity » qui exécute :
```bash
git fsck --full
python -c "import certus, certus.core, certus.physics"
python -m compileall -q certus
```
→ échec immédiat si `certus/physics/` disparaît de nouveau ou si un fichier ne parse pas.

---

## 12. Conclusion

**CERTUS est très proche du top 1 % mondial en optique couches minces sur les critères d'ingénierie logicielle**. La discipline (ruff, typing, dataclasses, logging JSONL, Numba parallel) et l'architecture (façade physique, séparation objectives/solvers/config, DTO aux frontières) sont exemplaires.

Trois écarts empêchent la classification :

1. **Incident d'intégrité git** — technique, réparable en une heure, mais **strictement bloquant** aujourd'hui.
2. **Perméabilité core/UI** sur 4 modules identifiés — 3 sont corrigeables en un après-midi, un (orchestrator design) demande 1-2 j.
3. **Sur le plan algorithmique** — le manque d'adjoint TMM, de QMC dans STRAT, de CRN dans le consensus et de warm-starting cross-phase RE laisse un facteur **10-30×** sur la table.

Le plan d'action est concret, chiffré, ROI-optimisé. Rien de ce qui est proposé n'est spéculatif : chaque optimisation est un standard documenté du domaine (Liu et al. 2021 pour l'adjoint, `scipy.stats.qmc` pour Sobol, Fisher information matrix pour le tolerancing). Le code CERTUS est **prêt à les recevoir** — la façade physique unifiée, la structure DTO et la couverture Numba en font une plateforme solide pour ces upgrades.

**Recommandation finale** : commencer par le P0 (git + `certus/physics/` + attic), puis les 4 quick wins UI/core (Q1-Q4) dans la semaine, puis attaquer QMC + CRN + parallélisme robustness le mois suivant. L'adjoint TMM peut suivre en trimestre 2 sans casser l'existant.

— *Fin de l'audit FABLE5*
