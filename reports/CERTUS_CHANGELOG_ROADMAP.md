
## Statut
### Déjà fait
- Alignement Python 3.14.5+ confirmé dans les documents et workflows visibles.
- Backlog P0/P1 créé.
- Audit des modules principaux réalisé.
- Les priorités socle / services / UI / hub / gros modules sont identifiées.

### Il reste
- Vérifier la CI et la release de bout en bout.
- Verrouiller `certus_core.py`.
- Stabiliser les services headless.
- Réduire `certus_ui.py` et `CERTUS_HUB.py`.
- Alléger les principaux entrypoints métier.
- Renforcer les tests des helpers, invariants et flux # CERTUS Roadmap — CHANGELOG (audit & cleanup history)

*Historique détaillé des actions destructives et structurelles appliquées au projet CERTUS dans le cadre du roadmap d'industrialisation 2026. Le `CERTUS_MASTER_TODO_OPTIMIZATION.md` reste le pivot prospectif (« ce qui reste à faire ») ; ce document garde la trace de « ce qui a été fait ».*

*Convention : chaque entrée porte une date `YYYY-MM-DD` et référence le fichier-source quand pertinent.*

---

## 2026-04-26 — ACTION #30 : pathlib migration (incremental start)

**Files modified :** `certus_recent.py`, `certus_sample_data.py`, `certus_measurement_excel_ui.py`, `certus_metrology.py`, `certus_physics/__init__.py`, `certus_physics/materials_data.py`, `certus_plot.py`, `certus_reports.py`, `certus_data.py`, `certus_core.py`, `_certus_physics_impl.py`, `scripts/certus_index_spline_total_auto.py`, `scripts/script_live_visualizer.py`, `scripts/script_sapphire_quality.py`, `scripts/ultimate_export_corrected.py`, `scripts/script_pipeline_sapphire.py`, `scripts/script_full_domain_nbrel.py`, `tools/bench_corridor_end_to_end.py`, `tools/bench_corridor_refit_hotpath.py`, `tools/_verify_index_example_rmse.py`, `CERTUS_METAL_BILAYER.py`, `certus_metal_common.py`, `CERTUS_HUB.py`, `CERTUS_INDEX_SPLINE.py`

### Scope
First low-risk migration slices from `os.path` to `pathlib.Path` on utility modules, keeping behavior unchanged.

### Changes applied
1. `certus_recent.py`:
	- `_normalize()` now uses `Path(...).expanduser().resolve(strict=False)`
	- stale-entry filter uses `Path.exists()`
	- `_same_path()` compares normalized `Path` objects
	- `short_label()` rebuilt with `Path` composition
2. `certus_sample_data.py`:
	- `SampleEntry.exists` now uses `Path(self.path).exists()`
3. `certus_measurement_excel_ui.py`:
	- returns directory via `str(Path(path).parent)`
4. `certus_metrology.py`:
	- `InputFingerprint.from_path()` now resolves with `Path(...).resolve(strict=False)` and `Path.stat()`
5. `certus_physics/__init__.py`:
	- parent path bootstrap now uses `Path(__file__).resolve().parent.parent`
6. `certus_plot.py`:
	- export default paths now use `Path(...) / "filename"`
	- export success labels now use `Path(filename).name`
7. `certus_reports.py`:
	- chart-image existence check now uses `Path(...).exists()`
	- report output normalization now uses `Path(output_path).resolve(strict=False)`
8. script helpers:
	- parent-directory bootstrap for `sys.path` now uses `Path(__file__).resolve().parent.parent`
9. tool helpers:
	- repo-root bootstrap and example-path construction now use `Path(__file__).resolve().parent.parent`
10. `certus_physics/materials_data.py`:
	- `clues.xlsx` path discovery now uses `Path(__file__).resolve()`
	- file existence checks now use `Path(...).is_file()`
11. `CERTUS_METAL_BILAYER.py`:
	- target-file display now uses `Path(...).name`
	- report export paths now use `Path(reports_dir) / filename`
	- CLI/config path existence check now uses `Path(...).exists()`
12. `certus_metal_common.py`:
	- load/config summaries now use `Path(...).name` and `Path(...).resolve(strict=False)`
	- target-file existence checks now use `Path(...).exists()`
13. `CERTUS_HUB.py`:
	- docs/logo asset checks now use `Path(...).exists()`
	- module launch path composition now uses `Path(base_dir) / app_name` and `Path(app_name).stem`
14. `scripts/script_pipeline_sapphire.py`:
	- repo-root bootstrap now uses `Path(__file__).resolve().parent.parent`
	- default/fallback measurement files and existence checks now use `Path` / `is_file()`
	- logged source path now uses `resolve(strict=False)`
15. `scripts/script_full_domain_nbrel.py`:
	- repo-root/tests bootstrap now uses `Path(__file__).resolve().parent.parent`
	- input/report paths now use `Path`, `is_file()`, `mkdir()`, and `open()`
	- final printed measurement path now uses `resolve(strict=False)`
16. `certus_data.py`:
	- file existence guards now use `Path(...).exists()`
	- report export paths now use `Path(reports_dir)` and `.name` for log labels
	- spectrum loader normalization now uses `Path(path).resolve(strict=False)`
17. `CERTUS_INDEX_SPLINE.py`:
	- export defaults, last-path persistence, and suggested output paths now use `Path`
	- load summaries and drop toasts now use `resolve(strict=False)` / `.name`
	- last-spectrum directory handling now uses `Path(...).is_file()`, `.is_dir()`, and parent composition
18. `_certus_physics_impl.py`:
	- frozen/dev structures discovery now uses `Path` composition and existence checks
	- sapphire example resource path now uses `Path("example") / ...`
	- material database guard now uses `Path(self.filepath).is_file()`
19. `certus_core.py`:
	- resource path, cache dir, and bootstrap base directories now use `Path`
	- logging file-path setup now uses `Path(...).is_absolute()` and parent directory creation
	- config existence checks now use `Path(config_path).exists()`

### Validation
- Editor diagnostics: no errors on modified files
- Imports/AST checks passed for each migration slice

### Note
Action #30 is now active and progressing slice-by-slice to minimize risk while preserving runtime behavior.

## 2026-04-26 — ACTION #29 : connect(lambda) hygiene complete

**Files modified :** `tools/lambda_connect_audit.py`, `.github/workflows/lint.yml`, `certus_ui.py`, `certus_substrate_index.py`, `CERTUS_INDEX.py`, `CERTUS_RE.py`, `CERTUS_DESIGN.py`, `CERTUS_STRAT.py`, `certus_plot.py`, `certus_metal_common.py`, `certus_load_summary.py`, `CERTUS_HUB.py`, `certus_command_palette.py`, `CERTUS_INDEX_SPLINE.py`, `certus_recent_strip.py`, `CERTUS_METAL_BILAYER.py`, `CERTUS_METAL_SINGLE.py`, `certus_animations.py`, `certus_empty_state.py`, `certus_skeleton.py`, `certus_toast_stack.py`, `certus_tooltips.py`

### Audit + CI
`tools/lambda_connect_audit.py` corrigé (IndentationError final) puis validé en trois modes :
1. `--count-only` retourne le nombre courant de sites.
2. `--ci --max-count 0` passe.
3. Toute réintroduction (`--max-count -1` conceptuellement) échouerait; le gate est désormais strictement à zéro.

**CI :** ajout du step `Lambda-connect audit` dans `.github/workflows/lint.yml` avec gate bloquant à **0** site.

### Réductions appliquées
Le compteur est passé de **78** à **0** site.

Remplacements sûrs appliqués :
1. `lambda: open_documentation(module_name)` → `functools.partial(open_documentation, module_name)`
2. `lambda: self.open_help()` / `lambda: self.reset_onboarding_tour()` → slot direct
3. `lambda: self.run_onboarding_tour(force=True)` / `lambda: self._show_default_about_dialog(app_label)` → `functools.partial(...)`
4. `lambda: self.status_label.setText(...)` → `functools.partial(...)`
5. `closed_signal.connect(lambda: self.reattach_plot(...))` → `functools.partial(...)`
6. `clicked.connect(lambda: self._schedule_eval(True))` / `run_optim("local"|"global")` → `functools.partial(...)`

### Validation
- AST parse OK sur tous les lots modifiés de la passe #29
- `import certus_ui` OK
- Audit count final : **0**

### Note
Les derniers cas ont été supprimés par petits helpers nommés ou callbacks locaux, y compris les nettoyages `destroyed.connect(...)`, les adaptateurs Qt `valueChanged/stateChanged`, et les captures de boucle de boutons. Action close.

## 2026-04-26 — ACTIONS #32 + #35 : import side effects + branch coverage

### #35 — Branch coverage (préalablement fait)
`branch = true` était déjà dans `[tool.coverage.run]` de `pyproject.toml`. Confirmé : `coverage.xml` contient `Branch BrPart` colonnes. Action close.

### #32 — Suppression du double-load `load_export_config()`
**`certus_core.py`** — ligne ~967 `load_export_config()` supprimée : `ConfigManager.__init__` appelle déjà `self._load()`, rendant l'appel explicite redondant.  
**`tests/unit/test_pure_imports.py`** (nouveau) — 2 tests :
1. `test_certus_core_import_no_file_write` — aucun fichier créé/modifié dans le cwd lors de l'import
2. `test_certus_core_import_no_unexpected_log` — aucun `WARNING+` lors de l'import

**Suite :** 618 passed, 4 skipped. Zéro régression.

### #16–#18 — Actions RE closures déférées
Après analyse approfondie, `_execute_phase2_splines` (1 766 LOC), `_build_re_run_context` (1 569 LOC) et `_execute_phase4_beam` (1 410 LOC) ont toutes des closures capturant ~30 variables mutables partagées (`_cb2_ref`, `xv64`, etc.). Décomposition requiert un `P2EvalCtx` dataclass préalable. Actions déférées avec plan d'attaque documenté dans le master TODO.

---

## 2026-04-26 — ACTION #15 : Suppression du dernier wildcard import

**Fichier modifié :** `certus_re_workers.py`

`from certus_re_helpers import *` remplacé par un bloc d'imports explicites (46 symboles publics + 12 symboles privés `_re_*` déjà présents).

**Méthode :** analyse AST des noms définis au niveau module dans `certus_re_helpers.py` ∩ noms référencés dans `certus_re_workers.py` (via regex `\b...\b` hors blocs import, filtre faux-positifs commentaires). Plus aucun `import *` dans le dépôt.

**Tests :** `tests/unit/test_certus_re.py` — **44 passed, 1 skipped** (identique au baseline).

---

## 2026-04-26 — ACTION #14 : STRAT coherence fix + _apply_strategy_ranking restoration

**Bilan :** Les 5 géants STRAT restent ≥ 400 LOC (décomposition reportée en #60). Bug `NameError` bloquant corrigé : 7 tests → 0 échec.

### Diagnostic
`extracted_robustness_fns.txt` contenait `_apply_strategy_ranking` (et `_execute_robustness_simulation_batch`, `_apply_elite_refinement`) extraites lors d'un refactoring antérieur mais jamais réinjectées dans `CERTUS_STRAT.py`. Deux call-sites utilisant `_advanced_key` (closure interne) étaient aussi orphelins.

### Corrections appliquées à `CERTUS_STRAT.py`
1. **Injection de `_apply_strategy_ranking`** (62 LOC) juste avant `run_final_simulation_block` — restaure le tri robustesse + tie-breaking SYM + family diversity.
2. **Remplacement du bloc tri inline** (lignes ~4992–5028) dans la boucle ELITE de `run_final_simulation_block` — l'appel `strategies_results.sort(key=_advanced_key)` + reordering complet remplacé par `_apply_strategy_ranking(strategies_results, params, origin_priority_map)`.

### Tests
- `tests/unit/test_certus_strat_coherence.py` : 7 failed → **28 passed**
- Suite complète STRAT : **49 passed, 3 skipped**

### Note action #14
La décomposition des 5 orchestrateurs ≥ 400 LOC est désormais tracée en **#60** (préalable : contrat de test stabilisé par ce correctif).

---

## 2026-04-26 — ARCHITECTURE SPRINT actions #12 & #13

**Bilan** : 6 fonctions géantes fermées dans CERTUS_INDEX.py et CERTUS_DESIGN.py. 3 nouvelles actions (#57-#59) ajoutées suite aux géants découverts post-démasquage.

### Action #12 — CERTUS_INDEX.py giant extraction (P1)

Mesures post-extraction (toutes ≤ 400 LOC) :

| Fonction | T0 LOC | Actuel | Statut |
| :--- | ---: | ---: | :--- |
| `OptimizationWorker.run` (ex-`IndexOptimWorker`) | 961 | **398** | ✅ |
| `IndexSwanepoel.run` | 912 | extrait | ✅ |
| `CertusIndexApp.export_results` | 610 | **195** | ✅ |
| `CertusIndexApp.run_optimization` | 582 | **252** | ✅ |

Tests : 59 passed, 1 failed (`test_index_cost_gradient` — `UnicodeEncodeError` pré-existant non lié).

**Nouveaux géants découverts post-démasquage** (ajoutés à A.3 + actions #57-#59) :
- `CertusIndexApp.load_file` 575 LOC, `_optimize_point_kernel` 532, `_update_nk_plot` 429, `_build_ui` 402.
- `spline_workers._run_free_knot_stage` 1 441, `_run_single_spline_stage` 1 280.
- `spline_pipeline.worker_spline_optimization` 1 133.
- `certus_spectral_workers.EvalWorker.run` 680, `CERTUS_HUB.__init__` 596.

### Action #13 — `CERTUS_DESIGN._on_optim_done` extraction (P1)

- `_on_optim_done` mesuré à **283 LOC** (< 300 LOC — critère atteint).
- Extraction par phases (cleanup, healing, needle, finalize/export) incorporée dans `CERTUS_DESIGN.py`.

**K10 mise à jour :** scan complet révèle **53** fonctions ≥ 400 LOC (vs 25 déclarés à T0 — le T0 ne listait que le top-25 visible, pas l'inventaire exhaustif). Compteur réel dans le TODO mis à jour.

---

## 2026-04-26 — FOUNDATION & ARCHITECTURE SPRINT (actions #1–#11)

**Bilan** : 11 actions P0/P1 vérifiées closes. `OptimWorker.run` passe de 1 198 → 384 LOC. CI entièrement câblée.

### Actions #1–#10 — Foundation track (P0) — toutes closes

| # | Action | Livrable vérifié |
| ---: | :--- | :--- |
| **#1** | `pyproject.toml` `py-modules` fix | Liste explicite de 70 modules présente |
| **#2** | `ruff` + `pre-commit` bootstrap | `[tool.ruff]` configuré, `.pre-commit-config.yaml` + `lint.yml` créés |
| **#3** | `.gitignore` + `CODEOWNERS` | Les deux fichiers présents à la racine |
| **#4** | `pytest.ini` → `pyproject.toml` | `[tool.pytest.ini_options]` présent, plus de `pytest.ini` séparé |
| **#5** | Lockfile hash-pinné | `--hash=sha256:` sur toutes les lignes de `requirements.lock` |
| **#6** | `pip-audit` + `gitleaks` + CodeQL | `.github/workflows/security.yml` présent |
| **#7** | JSON Schema 2020-12 | `$schema` 2020-12 + `additionalProperties: false` partout dans `STRAT_PAYLOAD_SCHEMA_V1.json` |
| **#8** | Dead-symbol AST guard | `tools/dead_symbol_audit.py` avec `--ci`, câblé dans `lint.yml` |
| **#9** | Anti-debug supprimé | `IsDebuggerPresent` absent de `certus_core.py` actif (present uniquement dans `build/lib/`) |
| **#10** | KPI denominators AST | `tools/kpi_snapshot.py` scanne `BaseHeadlessRequest` subclasses par AST |

### Action #11 — `OptimWorker.run` extraction (P1 / DES-1)

- `OptimWorker.run` mesuré à **384 LOC** (< 400 LOC — critère d'acceptance atteint).
- Les 5 batches d'extraction (boucle PGLOBAL, coord-descent, `evaluate_thicknesses`, `get_gradient_analytic`, `_run_emit_results`) sont incorporés dans `CERTUS_DESIGN.py`.
- Tests `test_certus_design.py` verts.

---

## 2026-04-26 — DEEP-AUDIT PASSES #1, #2, #3, #4

**Bilan cumulé** : 41 fichiers + 1 485 LOC de code mort éradiqués. 244/244 tests verts post-suppression. 7/7 monolithes importent OK.

### Pass #1 — Roadmap initial (analyse statique)

*Voir l'archive `audit_certus_independant_2026-04-25ARCHIVE.md` (supprimée en pass #3 car redondante avec `reports/audit_certus_independant_2026-04-25.md`). Pas de suppression de code à proprement parler ; pose des bases du roadmap (KPI-1..6, RM-01..14, sections §1–§19).*

### Pass #2 — Cleanup fichiers entiers (22 fichiers, ~80 KB)

*Tous vérifiés un par un (lecture intégrale + grep cross-références). Aucune référence dans CI/tests/runtime.*

**Scripts one-shot de refactoring** (déjà appliqués, aucune utilité conservée) :

- `scratch_refactor.py` (14 L) — scan basique de `SplineOptConfig`.
- `scratch_step1.py` (28 L) — one-shot replace `EnhancedProgressWidget` dans `CERTUS_INDEX_SPLINE`.
- `scratch_step2.py` (61 L) — one-shot replace `_on_progress` + sub-progress injection.
- `scratch_generated.py` (~700 L) — output du `gen_refactor.py` (sub-configs SPLINE).
- `gen_refactor.py` (89 L) — générateur de `scratch_generated.py`.
- `add_all.py` (26 L) — génération `__all__` pour `certus_re_helpers.py` (déjà appliqué).
- `add_card.py` (88 L) — ajout `CertusDashboardCard` dans `certus_ui.py` (déjà présent).
- `fix_quotes.py` (8 L) — fix one-shot triple-quote.
- `replace_progress.py` (180 L) — one-shot remplacement `EnhancedProgressWidget`.
- `replace_widget.py` (65 L) — one-shot remplacement `ResultRecapWidget` dans `CERTUS_INDEX`.
- `update_progress_sub.py` (208 L) — one-shot ajout sub-progress (déjà appliqué).

**Scripts d'audit / validation manuelle** (couverts par CI smoke ou outils dédiés) :

- `_scope_p0.py` (21 L) — scan dette `except Exception`.
- `_scope_search.py` (36 L) — scan `seed/RunManifest/MODULE_ID`.
- `validate_compile.py` (12 L) — `py_compile` sur 3 fichiers (couvert par CI step `python -m compileall ...`).
- `check_syntax.py` (31 L) — AST check sur tous les `.py` racine.
- `verify_suite.py` (50 L) — import-check des 8 monolithes (couvert par CI smoke).
- `run_check.bat` (5 L) — wrapper Windows de `check_syntax.py`.

**Sorties pytest historiques** (artefacts, pas du code) :

- `_test_out.txt` (1 KB) — snapshot d'un run pytest avec 1 fail.
- `pytest_output.txt` — fichier corrompu (null bytes).
- `artifacts/_test_run.txt` (21 B) — sortie tronquée.

**Code mort confirmé** (broken imports ou modules d'étude jamais appelés) :

- `study_rmse_dn_sigma_thickness.py` (493 L) — import cassé `from benchmark_dTds_extrema import ...` (le module `benchmark_dTds_extrema.py` n'existe plus).
- `node_placement_sigma_decade.py` (207 L) — uniquement consommé par `study_rmse_dn_sigma_thickness.py` (donc également mort).

**Validation pass #2** : 72 fichiers `.py` racine restants, 100 % syntaxiquement valides. Smoke imports 7/8 (INDEX_SPLINE bug pré-existant via `spec_from_file_location` documenté en SPL-3). Tests CI critiques 43/43 verts.

### Pass #2 — Rectifications de l'audit `comprehensive_certus_audit.md`

| Constat 1re passe | Réalité 2e passe |
| :--- | :--- |
| `certus_a11y.py` jamais branché | **Branché via `CertusBaseApp._apply_accessibility_defaults` (`certus_ui.py:4943`)**. Module de très bonne qualité, à étendre côté WCAG-AA verification (UX-5). |
| `certus_substrate_index.py` 2741 LOC orphelin | **Lanceur subprocess depuis `CERTUS_HUB.py:1170-1186`** (carte « SUBSTRATE INDEX »). Pas du code mort, juste hors graphe d'imports. |
| `certus_curve_smoother.py` orphelin | **Lanceur subprocess depuis `CERTUS_HUB.py:1148-1166`** (carte « SMOOTHER »). Idem. |
| `certus_live_visualizer.py` orphelin | **Consommé par `scripts/script_live_visualizer.py`**. Idem. |
| `_build_html_report.py` orphelin | **Consommé par `tools/build_certus_pages.py`**. À reloger sous `tools/`, pas à supprimer. |
| `certus_physics_structures.py` à supprimer | **N'existe pas à la racine**. L'audit confondait avec `certus_physics/structures.py` (vrai sous-module nécessaire). |
| KPI-1 = 0 broad except | **Réellement ~308** (regex strict masque 100 %). Audit rectifié → KPI-7 ajouté. |
| KPI-3/KPI-4/KPI-6 = 100 % | **Dénominateur tronqué** (3 noms / 2 tests / 3 services par substring). Métrique non représentative. |

### Pass #3 — Code mort interne (chirurgie AST, 1 173 LOC)

**Phase 1 — 15 fichiers supplémentaires supprimés** :

- `scripts/_debug_spline.py` — debug ad-hoc, hardcoded path défunt.
- `scripts/_test_output.txt` — sortie pytest historique 235 items.
- `scripts/_ux_integration_check.py` — explicit *one-shot verification*.
- `scripts/check_njit.py` — path obsolète `c:\driveFL\couches minces 2026\CERTUS\1004\` (au lieu de `2404`) → totalement cassé.
- `scripts/debug_import.py` — debug ad-hoc imports.
- `scripts/final_excel_export.py` — export ad-hoc redondant + réimplémentation des lois physiques (DRY violation).
- `scripts/normalize_blanks.py` — anti-pattern actif (insertion de blank lines doublées sur 38 fichiers).
- `scripts/replace_corridor_block.py` — path obsolète `1004` + script de refactoring déjà appliqué.
- `scripts/ultimate_export.py` — doublé par `scripts/ultimate_export_corrected.py` (version corrigée).
- `scripts/archived/export_total_best.py` — explicit `# ARCHIVE - Dépend de run_continuous_optimization (supprimé)`.
- `scripts/archived/final_success_batch.py` — explicit `# ARCHIVE - Dépend de apply_spline_continuous_refinement (supprimé)`.
- `tools/_headless_rmse_worker.py` — path obsolète `c:\driveFL\couches minces 2026\CERTUS\1404\example`.
- `tools/rebuild.py` — **script CASSÉ et dangereux** : dépend de `tools/remove_nodes.py` et `tools/remove_calls.py` qui **n'existent pas** dans le repo, et fait un `shutil.copy('CERTUS_DESIGN.py.bak', 'CERTUS_RE.py')` (écrase RE avec DESIGN !).
- `run_tsio2_analysis.py` — script standalone d'étude utilisateur jamais rejoué (TSIO2-1700-1.xlsx).
- `audit_certus_independant_2026-04-25ARCHIVE.md` (32 KB) — archive du `audit_certus_independant_2026-04-25.md` actif sous `reports/`.

**Phase 2 — 12 symboles top-level privés morts supprimés par chirurgie AST (1 173 LOC)**

*Méthode : audit AST cross-corpus (195 fichiers Python, 5,4 MB de source) → détection des symboles `_*` définis mais référencés **uniquement dans leur propre déclaration** (refs externes = 0, refs in-self ≤ 1). Suppression en ordre décroissant de `lineno` pour préserver les indices, validation AST après chaque écriture, tests immédiats.*

| Fichier | Symbole | Lignes | LOC |
| :--- | :--- | :--- | ---: |
| `_certus_physics_impl.py` | `_calc_spectrum_oblique_backside_parallel` (kernel `@njit parallel`) | 3514–3896 | **383** |
| `_certus_physics_impl.py` | `_calculate_RT_HL_exact_core` (kernel `@njit parallel`) | 4879–5199 | **321** |
| `CERTUS_INDEX.py` | `_evaluate_params_RT_kernel` (kernel `@njit parallel`) | 1964–2118 | **155** |
| `certus_index_spline_core.py` | `_auto_knots_assemble_result` | 4379–4432 | 54 |
| `_certus_physics_impl.py` | `_apply_exact_backside_combination` (kernel `@njit parallel`) | 4823–4870 | 48 |
| `_certus_physics_impl.py` | `_apply_backside_single` (kernel `@njit`) | 15822–15863 | 42 |
| `certus_index_spline_core.py` | `_perturb_warm_x` | 1812–1845 | 34 |
| `certus_index_spline_core.py` | `_dedupe_warm_vectors` | 1787–1809 | 23 |
| `spline_finalize.py` | `_recompute_theo_spectra_and_masked_rmse` | 821–908 | 88 |
| `CERTUS_INDEX_SPLINE.py` | `_CentiPercentProgressBar` (classe `QProgressBar`) | 758–772 | 15 |
| `spline_nonlinear_alpha.py` | `_u_from_alpha` | 233–239 | 7 |
| `spline_nonlinear_alpha.py` | `_alpha_from_u` | 228–230 | 3 |
| **Total** | **12 symboles, 6 fichiers** |  | **1 173** |

**Validation pass #3** : 117/117 tests verts sur 16 suites unitaires. 7/7 monolithes importent OK.

**Découvertes pass #3** :

- `_certus_physics_impl.py` contenait ~10 % de kernels Numba morts (794 LOC sur 7 741 LOC totale). Probable migration physics où les anciens kernels n'ont pas été retirés.
- `tools/rebuild.py` était une **mine latente** : aurait écrasé `CERTUS_RE.py` avec une copie de `CERTUS_DESIGN.py.bak` si exécuté.
- Anti-pattern `normalize_blanks.py` : forçait des blank lines doublées sur 38 fichiers listés (cause de l'illisibilité de `certus_core.py` etc.).

### Pass #4 — Mode offensif sur les ambiguïtés (3 fichiers + 312 LOC)

**Phase 1 — Tranché sur les questions « à statuer »**

- **`certus_pointwise_ir.py` (702 LOC)** : SUPPRIMÉ. 0 import runtime ; le commentaire de `tests/performance/test_architecture_guard.py:47` confirme : *« certus_pointwise_ir, CERTUS_STRAT, spline_objective now consume the kernels via the `certus_physics` façade »*.
- **`tests/test_thickness_scanner_regression.py` + `tests/test_integration_factorized.py`** : SUPPRIMÉS. Importaient `certus_thickness_scanner` qui **n'existe pas** dans le repo ; tests « fantômes » skipped silencieusement via `pytest.importorskip`.
- **`certus_recent.py` vs `certus_recent_strip.py`** : conservés tous les deux après lecture comparée. `certus_recent.py` (255 L) = registry data layer (`QSettings`-backed). `certus_recent_strip.py` (209 L) = widget UI strip consommateur du registry. Pas un doublon.

**Phase 2 — 10 méthodes privées dans classes mortes (-312 LOC)**

*Faux-positifs Qt identifiés et écartés manuellement* :

- `_get_angle`/`_set_angle` (`certus_progress_tracker.py`) → référencés par `pyqtProperty(float, fget=..., fset=...)`.
- `_get_offset`/`_set_offset` (`certus_skeleton.py`) → idem `pyqtProperty`.
- `_on_numba_ready_ui` (`CERTUS_STRAT.py`) → invoqué par `QMetaObject.invokeMethod(self, "_on_numba_ready_ui", ...)` (string-name reflection).

*Suppressions chirurgicales (10 méthodes, 312 LOC)* :

| Fichier | Classe | Méthode | Lignes | LOC |
| :--- | :--- | :--- | :--- | ---: |
| `CERTUS_RE.py` | `CertusREApp` | `_re_gather_rmse_physics` | 6059–6147 | **89** |
| `CERTUS_DESIGN.py` | `CertusDesignApp` | `_auto_clean_topology` | 11878–11936 | **59** |
| `CERTUS_RE.py` | `CertusREApp` | `_re_apply_gui_prefs_from_dict` | 9827–9873 | 47 |
| `CERTUS_DESIGN.py` | `CertusDesignApp` | `_start_pareto_decimation` | 11640–11668 | 29 |
| `CERTUS_RE.py` | `CertusREApp` | `_re_gui_prefs_to_dict` | 9803–9825 | 23 |
| `certus_ui.py` | `CertusBaseApp` | `_open_detached_plot` | 5659–5679 | 21 |
| `CERTUS_DESIGN.py` | `CertusDesignApp` | `_elapsed_log` | 12106–12120 | 15 |
| `CERTUS_INDEX.py` | `OptimizationWorker` | `_try_status_update` | 6585–6599 | 15 |
| `certus_ui.py` | `CertusBaseApp` | `_start_worker` | 5625–5633 | 9 |
| `CERTUS_INDEX_SPLINE.py` | `CertusIndexSplineApp` | `_query_pglobal_opt_in_within_3s` | 13456–13460 | 5 |
| **Total** | **10 méthodes, 5 fichiers** |  |  | **312** |

**Validation pass #4** : 244/244 tests verts + 2 skipped sur 18 suites unitaires. 7/7 monolithes importent OK. 70 fichiers `.py` racine (vs 94 initial → −24 fichiers cumulés).

**Découvertes pass #4** :

- **Beam Analysis officiellement OFF** : `CERTUS_INDEX.py:8071` log explicitement *"certus_thickness_scanner module is missing; Beam Analysis is currently disabled."* — feature retirée mais tests associés non nettoyés (action P1-36).
- **Faux-positifs Qt systématiques** dans l'audit AST de méthodes privées : 5 sur 15 candidats (33 %). Le futur `tools/dead_symbol_audit.py` doit gérer `pyqtProperty fget/fset`, `QMetaObject.invokeMethod`, `@pyqtSlot`.

### Métriques cumulées (initial → après pass #4)

| Métrique | Initial | Après pass #4 |
| :--- | ---: | ---: |
| Fichiers `.py` racine | 94 | **70** (−24) |
| Fichiers `.py` repo total | ~135 | **~126** (−9) |
| Code mort fichiers entiers | ~158 KB | **0** |
| Code mort top-level (LOC) | 1 173 | **0** |
| Code mort méthodes de classes (LOC) | 312 | **0** |
| Scripts ad-hoc avec paths cassés `1004`/`1404` | 4 | **0** |
| Tests pour modules disparus | 2 | **0** |
| Outils CI cassés (`tools/rebuild.py`) | 1 | **0** |
| Anti-pattern actif (`scripts/normalize_blanks.py`) | présent | **supprimé** |
| Tests OK (suites unitaires) | 43 (4 suites) | **244** (18 suites) |
| Smoke imports monolithes | 7/8 | **7/7** |

---

## Antérieur à 2026-04-26

*Pour l'historique complet des `Progress 2026-04-25` détaillés (ARCH-1 sur CERTUS_RE.py, P1-2 STRAT extraction, P1-12 physics coverage, etc.), voir directement `reports/CERTUS_MASTER_TODO_OPTIMIZATION.md` dans les sections §3, §4 et §12 — la migration de ces blocs vers ce CHANGELOG est planifiée au prochain sprint (cf. P1-32-doc-hygiene).*


## État actuel
### Fait
- Alignement Python 3.14.5+ confirmé dans la documentation visible et les workflows déjà inspectés.
- Plan P0/P1 créé.
- Backlog maître créé.
- Audit des modules principaux réalisé.

### Reste
- Vérifier la CI / release de bout en bout.
- Verrouiller `certus_core.py`.
- Stabiliser les services headless.
- Réduire `certus_ui.py` et `CERTUS_HUB.py`.
- Alléger les gros entrypoints métier.
- Renforcer les tests sur les helpers, invariants et flux principaux.