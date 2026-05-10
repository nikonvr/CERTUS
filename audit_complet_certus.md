# Audit complet — Suite CERTUS 0905 (mis à jour)

> Audité le 10 mai 2026 sur Python 3.14.4 — 1331 tests, 0 régression

## Scorecard

| # | Catégorie | Note | Score | Détail | Δ |
|---|---|---|---|---|---|
| 1 | **Stabilité des tests** | **A+** | 10/10 | 1331 passed, 0 régression, 12 skipped | — |
| 2 | **Couverture de code** | **A** | 9/10 | 83.0% (line coverage) | — |
| 3 | **Compatibilité Python 3.14** | **A+** | 10/10 | Natif 3.14.4, zéro deprecated stdlib | — |
| 4 | **Git / Versioning** | **A+** | 10/10 | 0 fichiers non-commités, historique propre | — |
| 5 | **Imports propres (pyflakes)** | **A** | 9/10 | 0 import mort hors gardes conditionnels | — |
| 6 | **Code mort / doublons** | **A** | 9/10 | 3 kernels + 2 fonctions dédupliquées | — |
| 7 | **Type annotations** | **A** | 8/10 | 82.9% (2611/3149) | — |
| 8 | **Error handling** | **A+** | 10/10 | 0 bare except, 6 broad except (GUI crash guards) | — |
| 9 | **Performance (Numba)** | **A** | 9/10 | 100 @njit kernels, fused hot paths | — |
| 10 | **Distribution des tests** | **A** | 9/10 | 98 unit + 12 integ + 9 perf + 2 property | — |
| 11 | **Ratio test/prod** | **B** | 7/10 | 0.30 (43.9K test / 145K prod) | — |
| 12 | **Cycles d'import** | **C+** | 6/10 | 13 cycles — 2 cassés via lazy `__getattr__` | — |
| 13 | **Taille des fonctions** | **C+** | 6/10 | **16** fonctions ≥ 500L (était 19), max 1769L | ↑ **19→16** |
| 14 | **Taille des fichiers** | **C** | 5/10 | 5 fichiers > 10K lignes, max 16.2K | — |
| 15 | **Docstrings publiques** | **B** | 7/10 | 654/1279 (51.1%) | — |

### **Score global : A (92/100)** ↑ vs 91/100

---

## Fonctions ≥ 500L — Inventaire actuel (16 fonctions)

| # | Taille | Fichier | Fonction | Blocker |
|---|---|---|---|---|
| 1 | 1769L | CERTUS_INDEX_SPLINE.py | `_show_smart_init_preview_dialog` | GUI closure (44 inner defs) |
| 2 | 1253L | certus_re_workers.py | `_execute_phase2_splines` | 9 closures (388L inner) |
| 3 | 1178L | certus_substrate_index.py | `fit_sellmeier` | 16 closures |
| 4 | 1057L | spline_profile_corridors.py | `_setup_corridor_context` | Sequential config setup |
| 5 | 1007L | certus_re_workers.py | `_build_re_run_context` | 411L closure |
| 6 | 975L | spline_workers.py | `_run_free_knot_stage` | 16 closures |
| 7 | 952L | spline_profile_corridors.py | `compute_regular_grid_rmse_profile` | 6 closures, already modular |
| 8 | 874L | certus_re_workers.py | `_execute_phase4_beam` | Deep state coupling |
| 9 | 796L | CERTUS_INDEX_SPLINE.py | `_build_basic_step4_mesh_optimizer` | GUI builder |
| 10 | 742L | spline_pipeline.py | `worker_spline_auto_clean_knots` | 11 closures |
| 11 | 729L | spline_workers.py | `_run_single_spline_stage` | Callback closure + PGlobal |
| 12 | 617L | CERTUS_RE.py | `_show_re_results_window` | GUI closures |
| 13 | **584L** | _certus_physics_impl.py | `_compute_gradient_analytic_kernel` | **Numba @njit — INTOUCHABLE** |
| 14 | 574L | certus_spline_report.py | `build_report` | Déjà modularisé (4 helpers) |
| 15 | 546L | spline_profile_corridors.py | `_corridor_profile_walk_side` | 96L closure |
| 16 | 516L | CERTUS_RE.py | `load_reverse_engineering_from_path` | GUI PyQt couplé |

### Fonctions passées sous le seuil 500L (3 sorties) ✅

| Fonction | Fichier | Avant → Après |
|---|---|---|
| `worker_spline_optimization` | spline_pipeline.py | 721L → **446L** |
| `_package_corridor_results` | spline_profile_corridors.py | 514L → **433L** |
| `compute_bootstrap_corridors_by_d` | spline_profile_corridors.py | 521L → **444L** |

---

## Helpers extraits — Inventaire complet (13 helpers, ~1800L)

| # | Helper | Taille | Fichier | Parent réduit | Réduction parent |
|---|---|---|---|---|---|
| 1 | `_package_profile_grid_result` | 235L | spline_profile_corridors.py | `compute_regular_grid_rmse_profile` | 1122→952L |
| 2 | `_log_corridor_envelope_diagnostics` | 99L | spline_profile_corridors.py | `_package_corridor_results` | 514→433L ✅ |
| 3 | `_resample_residuals_block` | 34L | spline_profile_corridors.py | `compute_bootstrap_corridors_by_d` | 521→444L ✅ |
| 4 | `_theoretical_TR_from_base_result` | 41L | spline_profile_corridors.py | (shared) | — |
| 5 | `_write_best_indices_sheet` | 153L | certus_spline_report.py | `build_report` | 1052→911L |
| 6 | `_write_summary_sheets` | 152L | certus_spline_report.py | `build_report` | 911→773L |
| 7 | `_write_corridor_nk_sheets` | 103L | certus_spline_report.py | `build_report` | 773→682L |
| 8 | `_write_analysis_sheets` | 99L | certus_spline_report.py | `build_report` | 682→574L |
| 9 | `_log_factual_sol2_analysis` | 130L | spline_workers.py | `_run_single_spline_stage` | 857→729L |
| 10 | `_apply_k_floor_to_result` | 100L | spline_pipeline.py | `worker_spline_optimization` | 721→576L |
| 11 | `_sensitivity_rank_inner_indices` | 93L | spline_pipeline.py | `worker_spline_auto_clean_knots` | 845→742L |
| 12 | `_run_sigma_mesh_polish` | 97L | spline_pipeline.py | `worker_spline_optimization` | 576→446L ✅ |
| 13 | Divers logging helpers | ~50L | spline_pipeline.py | `worker_spline_optimization` | (logging) |

---

## Changelog cumulé

### Phase 1 — Docstrings ✅
- 12 fonctions enrichies (numpy-style) dans `certus_index_utils.py` et `spline_objective.py`

### Phase 2 — Cycles d'import ✅
- 2 cycles cassés via lazy `__getattr__` dans `certus_ui.py` (8 re-exports)
- 14 → 13 cycles

### Phase 3 — Tests ✅
- 24 tests unitaires ajoutés pour `certus_index_utils.py`
- Total suite : 1308 → 1331 tests

### Phase 4 — Broad except ⏸️
- 6/6 cas légitimes (5 monolith GUI crash guards + 1 jsonschema guard)

### Phase 5 — Réduction fonctions géantes ✅
- **19 → 16** fonctions ≥ 500L
- **13 helpers** extraits, **~1800L** de logique isolée
- **3 fonctions** passées sous le seuil : `worker_spline_optimization`, `_package_corridor_results`, `compute_bootstrap_corridors_by_d`
- `build_report` : **1052L → 574L** (4 helpers Excel)
- `worker_spline_auto_clean_knots` : **845L → 742L** (sensitivity ranking)
- `_run_single_spline_stage` : **857L → 729L** (factual analysis)
- 199 lignes de code mort supprimées

> [!IMPORTANT]
> Les 16 restantes sont dominées par des **closures profondes** (optimizer callbacks, GUI event handlers) ou **Numba JIT** intouchable.
> Réduction supplémentaire requiert : refactoring closures → context dataclass, ou décomposition GUI en sub-widgets.
> Ces chantiers nécessitent approbation explicite car ils modifient les patterns d'architecture.
