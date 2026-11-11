# Imports laissés sans lecteur par les déplacements

Relevé de la Phase 8, par `tools/unread_imports.py 211d561b` (le commit de la Phase 0), sur l'arbre `fce0ee90`.

Un nom compte quand le module l'importe aujourd'hui au niveau module, l'importait et le lisait à la Phase 0, et ne le
lit plus : un déplacement lui a pris son dernier lecteur. **Aucun n'est retiré** : un module garde les noms qu'il
exposait (plan, principe 6), parce qu'un test ou un autre module peut le lire là, et que `ruff check --fix` est interdit
(CLAUDE.md, section 3). Les retirer est un chantier à part : pour chaque nom, chercher ses lecteurs dans `tests/` et
dans les autres modules, puis le retirer seul.

| Module (`certus_index_spline_…`) | Noms importés que le module ne lit plus | Nombre |
|---|---|---|
| `common` | `Event`, `SplineOptConfig`, `compute_regular_grid_rmse_profile`, `quick_pwlnk_refit_result_dict` | 4 |
| `corridor_gen` | `CertusTheme`, `pg`, `time` | 3 |
| `corridorui_mixin` | `Any`, `CertusCard`, `CertusScientificPlot`, `CertusTheme`, `ExcelTableWidget`, `NUMERICAL_FAULT_EXCEPTIONS`, `QApplication`, `QFrame`, `QHBoxLayout`, `QMessageBox`, `QScrollArea`, `QVBoxLayout`, `QWidget`, `Qt`, `atomic_open`, `create_styled_button`, `logger`, `normalize_corridor_live_payload`, `np`, `pg`, `wrap_scientific_plot_with_toolbar` | 21 |
| `eventsextras_mixin` | `CertusIndexSplineApp`, `GenericWorker`, `_fit_local_quadratic_rmse_profile`, `_lam_uniform_grid`, `_worker_curve_minimum_deep_refit`, `log_index_spline_d_trace` | 6 |
| `execution` | `Any` | 1 |
| `manualmesh_mixin` | `NUMERICAL_FAULT_EXCEPTIONS`, `logger` | 2 |
| `rendering` | `Any`, `QFont`, `_fit_local_quadratic_rmse_profile`, `normalize_corridor_live_payload`, `slider_corridor_half_stylesheet` | 5 |
| `settings` | `Any`, `GenericWorker`, `StepState`, `_log_index_spline_best_config`, `build_progress_snapshot`, `log_index_spline_d_trace`, `time`, `worker_run_corridor_profile_after_nl_choice` | 8 |
| `smart_init` | `Any`, `BaseModel`, `ConfigDict`, `dataclass`, `field` | 5 |
| `ui` | `_UIMixin` | 1 |

Total : 56 noms dans 10 modules.

Lecture : `corridorui_mixin` a donné presque toutes ses méthodes aux tranches (il ne garde que
`_launch_corridor_rmse_gap_heal`) ; `settings` a donné le cycle de vie d'un calcul à `corridor_run` ; `rendering` a
donné le tracé RMSE(d) ; `common` a donné les trois fonctions de calcul à `corridor_jobs` ; `smart_init` lit ses trois
classes dans `state_ui` depuis la Phase 2e.
