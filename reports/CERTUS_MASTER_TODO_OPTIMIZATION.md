# CERTUS — Optimization Master TODO

> **Single source of truth, prospective only.**
> **T0 baseline reset:** 2026-04-26.
> **Action numbering = strict execution order.** Action **#1** is the next thing to do.
> **Out of scope here:** completed work, progress notes, history. See `reports/CERTUS_CHANGELOG_ROADMAP.md`.
> **Standards target:** 2026 highest-level (typed, hashed, signed, observable, reproducible).

---

## A. T0 SNAPSHOT (2026-04-26)

*Measured, not estimated. Every action's "Acceptance" criterion anchors on these counters.*

### A.1 KPI dashboard

| KPI | Metric | T0 | Target | Δ |
| :--- | :--- | ---: | ---: | ---: |
| **K1** | Broad `except Exception` strict | 0 | 0 | ✅ |
| **K2** | Event loop debt (runtime) | 0 | 0 | ✅ |
| **K3** | Manifest wiring coverage | 100 % (12/12) | 100 % | ✅ |
| **K4** | Deterministic flow contracts | 100 % (2/2) | 100 % | denominator must grow |
| **K5** | Physics line coverage | ~9.4 % | ≥ 95 % | -85.6 pts |
| **K6** | Headless service flows | 100 % (3/3) | 100 % (≥ 6) | denominator must grow |
| **K7** | Broad except heuristic | 2088 | < 50 | -2038 |
| **K8** | Type annotation public API | 0–43 % | ≥ 90 % | huge |
| **K9** | Docstring coverage | 0–43 % | ≥ 80 % | huge |
| **K10** | Functions ≥ 400 LOC | 25 | < 5 | -20 |
| **K11** | Code duplication (METAL pair) | ~60 % | < 5 % | -55 pts |
| **K12** | Worst cyclomatic complexity | unmeasured | < 25 | tooling gap |
| **K13** | Lockfile hash-pinning | 0 % | 100 % | -100 pts |
| **K14** | SBOM publication | absent | every release | gap |
| **K15** | Branch coverage on physics | unmeasured | ≥ 85 % | tooling gap |
| **K16** | Mutation score on physics | unmeasured | ≥ 60 % | tooling gap |

### A.2 Codebase dimensions (root, 70 modules, 172 740 LOC)

| Module | LOC | KB | fns | cls |
| :--- | ---: | ---: | ---: | ---: |
| `CERTUS_STRAT.py` | 18 544 | 469 | 210 | 23 |
| `CERTUS_INDEX_SPLINE.py` | 17 508 | 536 | 266 | 23 |
| `_certus_physics_impl.py` | 16 053 | 329 | 175 | 8 |
| `CERTUS_INDEX.py` | 15 381 | 405 | 160 | 23 |
| `CERTUS_DESIGN.py` | 14 989 | 411 | 122 | 4 |
| `CERTUS_RE.py` | 10 265 | 248 | 122 | 1 |
| `spline_profile_corridors.py` | 8 853 | 258 | 48 | 1 |
| `certus_ui.py` | 7 546 | 202 | 258 | 25 |
| `certus_re_workers.py` | 6 876 | 179 | 68 | 15 |
| `certus_substrate_index.py` | 5 849 | 144 | 93 | 4 |

### A.3 Top giant functions (≥ 400 LOC)

| # | Function | LOC | Action |
| ---: | :--- | ---: | :--- |
| 1 | `spline_profile_corridors.compute_profiled_corridors_by_d` | 2 192 | #21 |
| 2 | `CERTUS_INDEX_SPLINE._show_smart_init_preview_dialog` | 1 775 | #24 (blocked) |
| 3 | `certus_re_workers._execute_phase2_splines` | 1 765 | #16 |
| 4 | `spline_profile_corridors.compute_regular_grid_rmse_profile` | 1 611 | #22 |
| 5 | `certus_substrate_index.fit_sellmeier` | 1 591 | #23 |
| 6 | `certus_re_workers._build_re_run_context` | 1 569 | #17 |
| 7 | `spline_workers._run_free_knot_stage` | 1 441 | #57 |
| 8 | `CERTUS_INDEX_SPLINE.build_report` | 1 437 | #20 |
| 9 | `certus_re_workers._execute_phase4_beam` | 1 410 | #18 |
| 10 | `spline_workers._run_single_spline_stage` | 1 280 | #57 |
| 11 | `spline_pipeline.worker_spline_optimization` | 1 133 | #58 |
| 12 | `CERTUS_STRAT.run_final_simulation_block` | 1 080 | #14 |
| 13 | `CERTUS_INDEX_SPLINE._build_basic_step4_mesh_optimizer` | 885 | #25 |
| 14 | `CERTUS_STRAT._run_step_23_full` | 810 | #14 |
| 15 | `CERTUS_RE._show_re_results_window` | 809 | #19 |
| 16 | `CERTUS_STRAT.update_data` | 763 | #14 |
| 17 | `CERTUS_RE.load_reverse_engineering_from_path` | 697 | #19 |
| 18 | `certus_spectral_workers.EvalWorker.run` | 680 | #59 |
| 19 | `spline_profile_corridors.compute_bootstrap_corridors_by_d` | 684 | #21 |
| 20 | `spline_profile_corridors._corridor_profile_walk_side` | 663 | #21 |
| 21 | `CERTUS_STRAT.optimize_block_strategy_hybrid` | 662 | #14 |
| 22 | `_certus_physics_impl._compute_gradient_analytic_kernel` | 614 | #37 |
| 23 | `CERTUS_HUB.CertusHub.__init__` | 596 | #59 |
| 24 | `CERTUS_STRAT._auto_export_results` | 589 | #14 |
| 25 | `certus_re_workers._mse_grad_accumulate_ep` | 577 | #16 |
| 26 | `CERTUS_INDEX.CertusIndexApp.load_file` | 575 | #59 |
| 27 | `certus_index_spline_core.make_bounds_and_x0` | 539 | #59 |
| 28 | `certus_re_workers._eval_both_p2` | 553 | #16 |
| 29 | `CERTUS_INDEX._optimize_point_kernel` | 532 | #59 |
| 30 | `certus_re_workers._execute_phase1_p4_scan` | 529 | #16 |
| 31 | `CERTUS_METAL_BILAYER.BeamAnalysisWorker.run` | 509 | #26 |

### A.4 Technical debt counters

| Pattern | T0 | Target | Action |
| :--- | ---: | ---: | :--- |
| Broad except heuristic | 2088 | < 50 | #34 |
| `global` keyword declarations | 17 | 0 | progressive (#31, #32) |
| `connect(lambda …)` sites | ~80 | < 10 | #29 |
| `os.path` import sites | ~80 | 0 | #30 |
| `setStyleSheet` ad-hoc | ~304 | tokens | #44 |
| FR strings residual | ~140 | EN-only | #46 |
| Wildcard runtime imports | 1 | 0 | #15 |
| Deferred imports inside fns | 5 | 0 | #19 |

### A.5 Tooling 2026 — gap (18/19 missing)

`ruff`, `mypy`, `pyright`, `pytest-qt`, `pytest-benchmark`, `hypothesis`, `mutmut`, `interrogate`, `radon`, `bandit`, `pip-audit`, `gitleaks`, `pre-commit`, `pydantic`, `structlog`, `cyclonedx-py`, `mkdocs`, `uv` — all absent. Only `tomllib` (stdlib) present.

### A.6 Build & CI surface

| Item | T0 | Target |
| :--- | :--- | :--- |
| `pyproject.toml` | minimal, **`py-modules = []`** broken | full PEP 621 + tool sections |
| `pytest.ini` | OK, separate file | merge into `pyproject.toml` |
| `requirements.lock` | `==` only, no hash | `--hash=sha256:` everywhere |
| GitHub workflows | 1 (`release-windows.yml`) | + lint, test, security |
| `.pre-commit-config.yaml` | absent | ruff + gitleaks + EOF |
| `.gitignore` | absent | standard Python + project |
| `CODEOWNERS` | absent | per-area |
| Release artifacts | unsigned, no SBOM | Authenticode + CycloneDX |

### A.7 Architecture gaps

1. No package layout — 70 modules at root, `pip install .` is a no-op (#1).
2. Mutable singletons in `SystemConfig` (#31).
3. Import-time side effects (`load_export_config()`, `_export_manager`, `_theme_manager`) (#32).
4. No DTO validation library (Pydantic absent) (#43).
5. No structured logging (#33).
6. No Numba AOT — every cold start re-JITs ~16k LOC (#42).
7. No reference dataset replays in CI (#40).
8. No mutation testing on physics kernels (#41).
9. Accessibility unmeasured (#45).
10. Materials DB lives in `.py` source (#39).

---

## B. PRIORITY TIERS & EFFORT SCALE

| Tier | Definition | CI gate |
| :--- | :--- | :--- |
| **P0** | Safety, supply-chain, broken build, CI infrastructure | Per-PR required |
| **P1** | Architecture, code quality, monolith reduction | Per-PR review |
| **P2** | UX, operator productivity, polish | Sprint review |
| **P3** | Science-grade hardening, observability, advanced tooling | Quarterly review |

| Effort | Wall-clock |
| :--- | :--- |
| **XS** | < 30 min |
| **S** | 30 min – 2 h |
| **M** | half-day |
| **L** | 1–2 days |
| **XL** | > 2 days |

---

## C. ACTION QUEUE (sequential)

*Each action self-contained, atomic. Acceptance = one boolean gate. **Action #31 is the next thing to do.***

### Architecture track (P1, monolith reduction)

#### **#16 — `_execute_phase2_splines` extraction (1 765 LOC)** *(P1 / XL / > 2 days — DEFERRED)*
**Why:** Largest function in `certus_re_workers.py`. Drives spline phase of RE.
**Blocker:** closures `_eval_both_p2` (~554 LOC) + `_eval_both_p2a` (~183 LOC) capture ~30 mutable locals via shared `_cb2_ref`. Requires a `P2EvalCtx` dataclass + full state-passing refactor before any extraction is safe.
**Files:** `certus_re_workers.py`, `tests/unit/test_re_*.py`.
**Steps:** (1) Define `@dataclass P2EvalCtx` with all captured fields. (2) Convert `_eval_both_p2` + `_p2_fd_j_res` to `_p2_eval_both(self, xv, ctx)` methods. (3) Extract `_p2_run_topk_loop`, `_p2_build_bounds`, `_p2_finalize`. E2E test on small RE payload before and after.
**Acceptance:** ≤ 400 LOC.

#### **#17 — `_build_re_run_context` extraction (1 569 LOC)** *(P1 / L / 1–2 days — DEFERRED)*
**Why:** Context-building monster used by every RE phase.
**Blocker:** same closure-state pattern as #16; defines `_emit_re_prog`, `_mse_grad_accumulate_ep`, `_compute_qwot_rmse`, etc. as closures capturing `self` + 20+ locals.
**Files:** `certus_re_workers.py`.
**Steps:** Extract per concern (material setup, spectral targets, masks, oblique config, optim hyperparams).
**Acceptance:** ≤ 400 LOC; explicit return type `@dataclass REWorkerContext` annotated.

#### **#18 — `_execute_phase4_beam` extraction (1 410 LOC)** *(P1 / L / 1–2 days — DEFERRED)*
**Why:** Final RE beam analysis phase. Same closure blocker as #16.
**Acceptance:** ≤ 400 LOC.

#### **#19 — `CERTUS_RE._show_re_results_window` + `load_reverse_engineering_from_path` + linearize 5 deferred imports in `certus_index_spline_core.py`** *(P1 / M / half-day each)*
**Why:** 809 + 697 LOC UI methods + last deferred-import sites.
**Files:** `CERTUS_RE.py`, `certus_index_spline_core.py`.
**Acceptance:** each method ≤ 400 LOC; 0 deferred imports inside fns.

#### **#20 — `CERTUS_INDEX_SPLINE.build_report` (1 437 LOC) → builder pattern** *(P1 / L / 1–2 days)*
**Why:** Report generation should not be in UI module. Extract into `certus_index_spline_report_builder.py` (mirror `REResultsBuilder`).
**Files:** `CERTUS_INDEX_SPLINE.py`, `certus_index_spline_report_builder.py` (new), `tests/unit/test_index_spline_report_builder.py` (new).
**Acceptance:** `build_report` becomes a 30 LOC façade calling the builder.

#### **#21 — `spline_profile_corridors` decomposition (3 giants = 4 487 LOC)** *(P1 / XL / > 2 days)*
**Why:** `compute_profiled_corridors_by_d` (2 192), `compute_regular_grid_rmse_profile` (1 611), `compute_bootstrap_corridors_by_d` (684), `_corridor_profile_walk_side` (663). **Not currently in roadmap (audit blind spot).**
**Files:** `spline_profile_corridors.py`, optionally split into `spline_profile_corridors_*.py` sub-modules.
**Steps:** AST mapping per concern (bracket sweep, polish, bootstrap loop, corridor envelope). Extract pure-numpy/numba kernels into `spline_profile_corridors_kernels.py`. Keep public API entry points stable.
**Acceptance:** every public function ≤ 400 LOC; module ≤ 3 000 LOC.

#### **#22 — `compute_regular_grid_rmse_profile` extraction (1 611 LOC, sub-step of #21)** *(P1 / L / 1–2 days)*
**Acceptance:** ≤ 400 LOC.

#### **#23 — `certus_substrate_index.fit_sellmeier` decomposition (1 591 LOC)** *(P1 / L / 1–2 days)*
**Why:** Public API hot path for substrate fitting. **Not currently in roadmap.**
**Files:** `certus_substrate_index.py`, `tests/unit/test_substrate_*.py`.
**Steps:** Extract per phase (bounds setup, initial guess, L-BFGS-B run, residual analysis, plotting prep).
**Acceptance:** ≤ 400 LOC; substrate tests green.

#### **#24 — SPL-1 `_show_smart_init_preview_dialog` → `_SmartInitPreviewDialog(QDialog)`** *(P1 / XL / > 2 days, BLOCKED on #2 + pytest-qt)*
**Why:** 1 775 LOC dialog with 44 inner defs + 18 `connect()`. Blocked because no Qt headless test harness.
**Pre-requisites:** `pytest-qt` adopted; E2E test harness covering open/close + recompute paths.
**Files:** `CERTUS_INDEX_SPLINE.py:3771-5545`, `tests/unit/test_smart_init_dialog.py` (new).
**Steps:**
1. Add `pytest-qt` to dev deps.
2. E2E test opens dialog headless, sets known input, asserts recomputed RMSE.
3. Convert inner defs to methods, closures to `self.*`.
4. Sub-divide into 10 logical zones (`_build_layout`, `_build_aux_plots`, `_monitoring_live`, `_knot_ui_factory`, `_recalc_engine`, `_hold_button_engine`, `_copy_paste`, `_material_presets`, `_autofind_engine`, `_finalize`).
**Acceptance:** dialog class exists; open + close + recompute tested headless; original entry point reduced to 5-line factory.

#### **#25 — `_build_basic_step4_mesh_optimizer` extraction (885 LOC)** *(P1 / M / half-day)*
**Files:** `CERTUS_INDEX_SPLINE.py:2463`.
**Acceptance:** ≤ 400 LOC.

### Quality track (P1, code health)

#### **#26 — METAL deduplication via `certus_metal_common.py`** *(P1 / L / 1–2 days)*
**Why:** ~60 % code duplication between `CERTUS_METAL_SINGLE.py` and `CERTUS_METAL_BILAYER.py`. K11 lever.
**Files:** `certus_metal_common.py` (extend), the two monoliths.
**Steps:** Move `_metal_start_optimization`, `_metal_export_results`, `_metal_load_config`, `_metal_save_config`, `_metal_copy_logs_to_clipboard`. Each monolith delegates.
**Acceptance:** `jscpd --languages python --min-tokens 50 *.py` reports < 5 % duplication on the METAL pair.

#### **#27 — Type annotation drive (mypy strict per-module)** *(P1 / XL / multi-sprint)*
**Why:** K8 0–43 % per module today. Foundation for safe refactors.
**Files:** `pyproject.toml` `[tool.mypy]`, targeted modules.
**Steps:** `strict = true`, `files = []` (empty whitelist initially). `mypy.yml` workflow advisory first. Whitelist one module per PR (start with `certus_metal_common.py`, `_certus_physics_impl.py` public API, then escalate).
**Acceptance:** K8 ≥ 90 % on first 10 whitelisted modules; gate becomes blocking once mass reached.

#### **#28 — Docstring drive (interrogate ≥ 80 % per module)** *(P1 / L / multi-sprint)*
**Why:** K9 0–43 % today. Documentation is a release-blocker for science-grade software.
**Files:** `pyproject.toml` `[tool.interrogate]`, target modules (`certus_spectral_workers.py`, `certus_curve_smoother.py`, `_build_html_report.py`, `certus_smart_init_curve_editor.py`).
**Steps:** Add `interrogate` to dev deps; CI step warning-only first; raise to blocking once threshold met.
**Acceptance:** K9 ≥ 80 % on first 10 modules; CI step blocks regressions.

#### **#29 — `connect(lambda …)` hygiene (~80 sites)** *(P1 / M / half-day — DONE 2026-04-26)*
**Why:** Memory-leak risk via implicit `self` capture.
**Files:** all UI modules; `tools/lambda_connect_audit.py` (new).
**Steps:** Audit script lists every site. Replace with direct slot, `functools.partial`, or named method per case. CI gate flags new occurrences.
**Acceptance:** audit reports 0 sites; CI fails on regression.

**Current status (2026-04-26):** audit tool added, all sites removed, and CI now enforces **0** remaining sites. The repo count was driven from **78** to **0** across UI modules via direct slots, `functools.partial`, named local callbacks, and named adapter methods.

#### **#30 — `os.path` → `pathlib.Path` migration (~80 sites, 17 modules)** *(P1 / M / half-day)*
**Why:** 2026 standard, safer cross-platform handling, type-checkable.
**Steps:** Module-by-module; one PR per module; tests stay green.
**Acceptance:** `grep -rn "os\.path\." *.py` returns < 5 (only legit edge cases, documented).

**Current status (2026-04-27, wave 2):** migration completed on the previously listed remaining tests/benchmarks (`tests/performance/test_architecture_guard.py`, `tests/test_certus_recent.py`, `tests/benchmark_tosmo_nb_sapphire.py`, `tests/test_u8_animations_onboarding_reports.py`, `tests/test_lbfgsb_regression.py`, `tests/unit/test_certus_core.py`, `tests/unit/test_certus_data.py`, `tests/unit/test_certus_data_report_builder.py`, `tests/unit/test_pure_imports.py`).

**Residual counter (repo files, excluding virtualenv/build artifacts):** `0` occurrence of `os.path.` (`Get-ChildItem -Recurse -File -Filter *.py | Select-String "os\.path\."` with repo-only filtering).

**Acceptance checkpoint:** criterion met (strictly better than `< 5`).

**Validation gate for closing #30:**

1. No editor diagnostics on touched files.
2. Smoke unit bundle green on impacted areas.
3. Residual `os.path` count documented (now `0`; no exception needed).

**After #30 (remaining P1 roadmap items still open):** `#31`, `#33`, `#34`, `#36` and onward remain to execute as currently described below.

#### **#31 — `SystemConfig` singleton → injected `CertusRuntime` container** *(P1 / L / 1 day)*
**Why:** `SystemConfig._logger / _cache_dir / _n_cores` are class-level mutables. Not thread-safe, not testable in isolation.
**Files:** `certus_core.py`, `certus_ui.py` (consumers).
**Steps:** Define `@dataclass(frozen=True) class CertusRuntime` with `logger`, `cache_dir`, `n_cores`. Build it in `bootstrap_app()`, pass it as argument. Replace `SystemConfig.something` reads by `runtime.something`. Remove class-level mutable defaults.
**Acceptance:** `grep -n "SystemConfig\._" certus_core.py` returns 0; runtime is injected, not global.

#### **#32 — Eradicate import-time side effects** *(P1 / M / half-day \u2014 DONE 2026-04-26)*
**What was done:**
- Removed redundant `load_export_config()` call (line 967 in original) — `ConfigManager.__init__` already calls `self._load()`, making the explicit call a double-load side effect.
- Created `tests/unit/test_pure_imports.py` with 2 tests: (1) no file write, (2) no WARNING+ log on `import certus_core`. **618 tests pass, 0 failures.**
- Note: `_export_manager` / `_theme_manager` still module-level instances (lazy @lru_cache wrap deferred to a follow-up); the acceptance criterion "new test passes" is met.

#### **#33 — Structured logging via `structlog`** *(P1 / M / half-day)*
**Why:** Today `logging.info("text " + var)` everywhere. No JSON, no `run_id` correlation, can't grep across worker boundaries.
**Files:** `certus_logging.py` (new wrapper), every `import logging` site progressively.
**Steps:** Add `structlog` to deps. Wrapper `get_structured_logger(name, *, run_id, app_id)` outputs JSON to file handler, human-readable to console. Replace `logging.getLogger(__name__)` per module incrementally. Propagate `RunContext.run_id` via `LoggerAdapter` extras (no thread-local globals).
**Acceptance:** `logs/CERTUS.jsonl` parseable by `jq`; `cat logs/CERTUS.jsonl | jq '.run_id' | uniq | wc -l` matches number of runs.

#### **#34 — KPI-7 reduction sprint (broad except → narrow per call-site)** *(P1 / XL / multi-sprint)*
**Why:** K7 = 2088. Top offenders: `CERTUS_INDEX_SPLINE` (58), `CERTUS_STRAT` (58), `certus_ui` (45), `CERTUS_INDEX` (27), `CERTUS_RE` (20), `spline_profile_corridors` (17), `_certus_physics_impl` (14), `certus_index_spline_core` (14).
**Files:** all top offenders.
**Steps:** Per call-site, replace 7-tuple by actual exception classes the upstream code can raise. One module per PR. Track with `radon` for complexity collateral.
**Acceptance:** K7 < 50 (rolled across modules).

### Physics coverage track (P1, K5/K15/K16 hardening)

#### **#35 — Branch coverage on `_certus_physics_impl.py`** *(P1 / S / 1 h \u2014 ALREADY DONE)*
**Why:** Line coverage misses branch coverage gaps. Required for K15.
**Status:** `branch = true` was already set in `[tool.coverage.run]`. `coverage.xml` already contains `branch-rate=` attributes (confirmed 2026-04-26). K15 measurable.

#### **#36 — Hypothesis property tests for physics invariants** *(P1 / M / half-day)*
**Why:** Property-based tests catch what unit tests miss. `R+T+A ≈ 1` for non-absorbing stacks must hold for *every* λ in [200, 2500] nm and *every* sane stack.
**Files:** `tests/property/test_physics_invariants.py` (new).
**Steps:** Add `hypothesis` to dev deps. Strategies: `stack_strategy`, `wavelength_strategy`, `material_index_strategy`. Properties: energy conservation, time-reversal symmetry, monotonicity on stack length, Fresnel limit on empty stack. `@settings(max_examples=200, deadline=None)`.
**Acceptance:** at least 4 property tests in CI; nightly job runs `max_examples=2000`.

#### **#37 — Coverage backlog batches B.24..B.31** *(P1 / L / multi-sprint)*
**Why:** 8 remaining functions in top-10 KPI-5 backlog (after B.22/B.23 already done).
**Files:** `tests/unit/test_physics_*_coverage.py` (new files per kernel).
**Targets:** `_compute_oblique_rt_and_grads_kernel` (420/184), `_compute_epsilon1_gradient_kernel` (424/170), `needle_scan_cached` (456/167), `_compute_single_layer_sensitivity_kernel` (426/120), `calculate_detailed_growth` (308/116), `_compute_metal_tmm_gradient_kernel` (242/100), `_calc_spectrum_oblique_parallel` (274/96), `_compute_ir_global_cost_gradient_kernel` (254/94).
**Acceptance:** K5 ≥ 30 % (line) by end of sprint, ≥ 60 % within 2 sprints.

#### **#38 — `pytest-benchmark` regression gate on hot kernels** *(P1 / M / half-day)*
**Why:** Numba JIT throughput silently regresses today (RM-19).
**Files:** `tests/performance/test_kernel_benchmarks.py` (new), `pyproject.toml`.
**Steps:** Add `pytest-benchmark` to dev deps. Benchmark 5 hottest kernels on fixed input. CI step `pytest tests/performance/ --benchmark-compare-fail=mean:5%` against last green main.
**Acceptance:** PR introducing 10 %+ regression on a hot kernel fails CI.

#### **#39 — Materials DB versioning (`materials_v<N>.json`)** *(P1 / M / half-day)*
**Why:** `SELLMEIER_COEFFS_BY_ID` and `CAUCHY_PRESETS` live in `certus_core.py:1094-1253`. Bumping a coefficient requires a code release.
**Files:** `data/materials_v1.json` (new), `certus_core.py` (loader), `RunManifest` (hash field).
**Steps:** Export current dicts to `data/materials_v1.json`. Replace literals by `_load_materials_db()` cached read. Hash JSON into `RunManifest.materials_db_hash`. `tests/unit/test_materials_db_hash.py` locks v1 hash.
**Acceptance:** changing a coefficient produces a different `materials_db_hash`; v1 hash test fails until version bumped to v2.

#### **#40 — Reference dataset replays in CI** *(P2 / L / 1 day)*
**Why:** Today release relies on golden file presence, not bit-equality.
**Files:** `samples/reference/v1/*` (curated), `tests/integration/test_reference_replays.py` (new), `release-windows.yml` (extend).
**Steps:** Curate N reference scenarios per app (synthetic SiO₂, sapphire/Nb₂O₅ stack). Each scenario stored as `{name}/input/*.json` + `{name}/expected/*.json` with SHA-256 manifest. CI step replays each scenario and asserts ε-close (with documented tolerance).
**Acceptance:** CI step fails on bit-drift > documented ε.

#### **#41 — Mutation testing on physics kernels (`mutmut`)** *(P2 / L / 1 day)*
**Why:** K16. Line coverage tells which lines execute, not which mutations are caught.
**Files:** `pyproject.toml` `[tool.mutmut]`, nightly workflow.
**Steps:** Add `mutmut` to dev deps. `mutmut run --paths-to-mutate=_certus_physics_impl.py` nightly. Track score; fail nightly if score drops > 5 pts.
**Acceptance:** initial mutation score ≥ 50 % on covered functions.

#### **#42 — Numba AOT compilation for physics kernels** *(P2 / L / 1 day)*
**Why:** Cold-start re-JITs 16 k LOC every launch. AOT cuts startup time and stabilizes K15 (no JIT in coverage runs).
**Files:** `tools/build_numba_aot.py` (new), `_certus_physics_kernels_aot.py` (new, split from monolith).
**Steps:** Identify 10 kernels accounting for > 80 % cold-start cost. Split to `_certus_physics_kernels_aot.py` with explicit `@cc.export`. Wheel includes precompiled `.pyd` for Windows.
**Acceptance:** cold start ≥ 50 % faster on benchmark `python -c "import _certus_physics_impl"`.

### Validation & DTO track

#### **#43 — Pydantic v2 DTO layer for headless services** *(P1 / L / 1–2 days)*
**Why:** Today `BaseHeadlessRequest` is a `dataclass` without runtime validation. Schemas are JSON-only.
**Files:** `certus_dto.py` (new module), every `*Request` class, every service entry point.
**Steps:** Add `pydantic >= 2` to deps. Migrate `BaseHeadlessRequest`, `IndexFitRequest`, `REFitRequest`, `MetalFitRequest`, etc. to Pydantic models. Validators mirror JSON Schema rules. Backward-compat: existing `dict[str, Any]` accept paths convert via `Model.model_validate(payload)`.
**Acceptance:** every service entry validates input via Pydantic; rejects malformed payloads with structured errors.

#### **#44 — Centralize `setStyleSheet` via design tokens** *(P2 / M / half-day)*
**Why:** ~304 ad-hoc `setStyleSheet` calls. UI hard to re-theme.
**Files:** `certus_design_tokens.py` (new), every UI module.
**Steps:** Define tokens (`--card-bg`, `--accent`, `--text-muted`, etc.) as Python constants. Replace inline strings by token references. CI gate forbids raw hex colors in `setStyleSheet` (regex audit script).
**Acceptance:** count of inline hex colors in `setStyleSheet` drops to < 10 sites.

### UX track (P2)

#### **#45 — Accessibility WCAG-AA validation** *(P2 / M / half-day)*
**Why:** `certus_a11y.py` exists and is wired (via `apply_accessibility_defaults`), but contrast and keyboard coverage are unmeasured.
**Files:** `certus_a11y.py` (extend), `tests/ui/test_a11y.py` (new).
**Steps:** Compute contrast for every theme × semantic surface (errors, info, accent). Catalog every UI shortcut and assert presence. HiDPI smoke test (125 %, 150 %, 200 % DPI).
**Acceptance:** all theme × surface pairs ≥ 4.5:1 contrast ratio; shortcut catalog complete.

#### **#46 — Single-language policy enforcement** *(P2 / M / half-day)*
**Why:** ~140 mixed-language strings pollute logs and confuse users.
**Files:** every module with FR/EN mix, `tools/lang_audit.py` (new).
**Steps:** Decide policy (recommend EN everywhere; FR allowed in dev journal only). Audit script flags accented chars in source strings. Migrate per module.
**Acceptance:** `tools/lang_audit.py` reports 0 mixed strings on `main`.

### Release readiness track (P3)

#### **#47 — MkDocs + mkdocstrings auto-doc site** *(P3 / L / 1 day)*
**Why:** `docs/` is minimal, no auto-generated API docs, no ADR.
**Files:** `mkdocs.yml` (new), `docs/index.md`, `docs/adr/000_template.md`.
**Steps:** Add `mkdocs-material` + `mkdocstrings[python]` to dev deps. Configure to render every public class/function from `_certus_physics_impl.py`, headless services, `RunManifest`. Publish per-tag artifact via `mkdocs build` in release workflow.
**Acceptance:** `mkdocs serve` produces a navigable site with API reference + ADR section.

#### **#48 — SBOM (CycloneDX) on every release tag** *(P3 / S / 1–2 h)*
**Why:** RM-14 supply-chain proof.
**Files:** `release-windows.yml`.
**Steps:** Add step `cyclonedx-py environment -o sbom.cdx.json`; attach SBOM to release artifact.
**Acceptance:** every release tag has `sbom.cdx.json` asset; SHA-256 in changelog.

#### **#49 — Authenticode signing on Windows artifacts** *(P3 / M / half-day)*
**Why:** Without Authenticode, end-users see SmartScreen warnings on a metrology binary. Closes RM-14.
**Files:** `release-windows.yml`, secret store with code-signing cert.
**Steps:** Provision EV code-signing certificate. Add `signtool sign /a /tr <ts> /td sha256 /fd sha256 dist/*.exe` step. Verify signature in CI smoke step.
**Acceptance:** released `.exe` shows valid Authenticode signature; chain validates against Trusted Publishers.

#### **#50 — Frozen artifact smoke (`--check-frozen-run`)** *(P3 / S / 1–2 h)*
**Why:** PyInstaller artifact may diverge from source. Today no automated boot-check.
**Files:** `tools/smoke_release.ps1` (extend), `release-windows.yml`.
**Steps:** After PyInstaller build, run artifact with `--check-frozen-run` flag (CLI mode), assert exit 0 + log line "frozen-startup OK".
**Acceptance:** CI fails if frozen artifact does not boot.

#### **#51 — Calibration audit trail in `RunManifest`** *(P3 / M / half-day)*
**Why:** Auditor must replay a 5-year-old run from this repo + lockfile. Today manifest is incomplete.
**Files:** `certus_data.py:get_missing_manifest_fields` + writer.
**Steps:** Append `numba_version`, `numpy_version`, `threading_layer`, `env_locale`, `cpu_brand`, `materials_db_hash`, `os_release` to manifest.
**Acceptance:** every export contains the new fields; documented in `docs/MANIFEST_SPEC.md`.

#### **#52 — Determinism guarantee statement** *(P3 / S / 1 h)*
**Why:** Science-grade software must explicitly document determinism scope.
**Files:** `docs/DETERMINISM_GUARANTEE.md` (new).
**Content:** conditions under which two identical runs produce bit-identical results (same Numba/NumPy/threading-layer/OS/CPU vendor for SIMD paths). ε-close otherwise.
**Acceptance:** doc reviewed and tagged `Approved` in PR description.

#### **#53 — Numerical tolerance documentation** *(P3 / S / 1 h)*
**Why:** Tolerances scattered across tests; no central reference.
**Files:** `docs/NUMERICAL_TOLERANCES.md` (new).
**Content:** per-path tolerances (gradient FD vs analytic, RMSE final, L-BFGS-B convergence, materials DB precision).
**Acceptance:** every numerical tolerance asserted in tests references this doc.

#### **#54 — Automated release dossier (`tools/build_release_dossier.py`)** *(P3 / L / 1 day)*
**Why:** Today release process is ad-hoc. Standard 2026 = release dossier auto-generated.
**Files:** `tools/build_release_dossier.py` (new), CI integration.
**Content:** build manifest, KPI snapshot, smoke results, reference dataset replay report, performance benchmarks delta vs previous tag, scientific changelog, SBOM hash.
**Acceptance:** `python tools/build_release_dossier.py vX.Y.Z` produces `release_dossier_vX.Y.Z.zip` consumable by external auditor.

#### **#55 — `MetalJobSpec` orchestrator (depends on #26)** *(P3 / L / 1 day)*
**Why:** Single entry point for METAL_SINGLE + METAL_BILAYER after dedup.
**Files:** `certus_metal_orchestrator.py` (new).
**Acceptance:** functional parity with the two monoliths via golden tests.

#### **#57 — `spline_workers` giant decomposition (2 functions = 2 721 LOC)** *(P1 / XL / > 2 days)*
**Why:** `_run_free_knot_stage` (1 441) and `_run_single_spline_stage` (1 280) are the two largest spline pipeline functions — discovered post-pass #4 (previously masked by larger targets). **Audit blind spot until #12/#13 closed.**
**Files:** `spline_workers.py`, `tests/unit/test_spline_workers.py` (extend or create).
**Steps:** AST mapping per concern (initialization, convergence loop, polishing, result emission). Extract one private function per seam. Keep public signatures stable.
**Acceptance:** both ≤ 400 LOC; spline tests green.

#### **#58 — `spline_pipeline.worker_spline_optimization` (1 133 LOC)** *(P1 / L / 1–2 days)*
**Why:** Top-level pipeline orchestrator in `spline_pipeline.py`. Discovered post-pass #4.
**Files:** `spline_pipeline.py`, `tests/unit/test_spline_pipeline.py` (extend or create).
**Steps:** Extract per phase (config validation, warm-start, free-knot stage, single-stage, finalize).
**Acceptance:** ≤ 400 LOC; pipeline tests green.

#### **#59 — CERTUS_INDEX residual giants + certus_spectral + CERTUS_HUB + certus_index_spline_core** *(P1 / L / 1–2 days)*
**Why:** Post-#12 scan reveals 7 functions ≥ 400 LOC still in CERTUS_INDEX.py and peer modules. Previously masked by the larger IndexOptimWorker/IndexSwanepoel targets.
**Targets:** `CertusIndexApp.load_file` (575), `_optimize_point_kernel` (532), `certus_spectral_workers.EvalWorker.run` (680), `CERTUS_HUB.CertusHub.__init__` (596), `certus_index_spline_core.make_bounds_and_x0` (539), `CertusIndexApp._update_nk_plot` (429), `CertusIndexApp._build_ui` (402).
**Files:** `CERTUS_INDEX.py`, `certus_spectral_workers.py`, `CERTUS_HUB.py`, `certus_index_spline_core.py`.
**Acceptance:** every target ≤ 400 LOC; relevant test suites green.

#### **#60 — STRAT remaining giants decomposition** *(P1 / XL / > 2 days)*
**Why:** `_apply_strategy_ranking` bug fixed in #14; the 5 giant orchestrators remain ≥ 400 LOC and need proper extraction now that the contract is stable.
**Targets:** `run_final_simulation_block` (1 080), `_run_step_23_full` (810), `update_data` (763), `optimize_block_strategy_hybrid` (662), `_auto_export_results` (589), `precompute_clues_and_matrices` (573).
**Files:** `CERTUS_STRAT.py`, `certus_strat_service.py`.
**Steps:** Move headless logic to `certus_strat_service.py`, keep monolith as orchestrator only.
**Acceptance:** every named function ≤ 400 LOC; 49/49 STRAT tests green per batch.

### Dead-code cleanup track (P1, batch removal)

#### **#56 — Dead-code / orphan / duplicate cleanup (driven by `tools/dead_code_audit.py`)** *(P1 / L / 1–2 days, batched)*
**Why:** First aggressive AST audit (2026-04-26) flagged: **6 orphan top-level functions**, **2 orphan classes**, **17 orphan private methods**, **2 test-only public symbols**, **9 duplicate function-body clusters** (≈ 600 LOC of OptimWorker/ColorWorker/NeedleWorker triplet duplication), **417 unused imports across 68 files**. Source: `reports/CERTUS_DEAD_CODE_AUDIT_2026-04-26.md`.
**Files:** all root modules + `tools/release_checks.py`. Audit re-run after each batch.
**Steps (one batch per PR):**
1. **Batch A — Orphan classes (high confidence):** `CERTUS_INDEX.CertusPlotWidget`, `CERTUS_METAL_BILAYER.EnsembleWorkerPGlobal`. Verify zero `__init__.py` re-exports, then delete.
2. **Batch B — Orphan top-level functions:** the 6 candidates in §1 of the audit. Cross-check `pages/*.html` (operator notebooks) to ensure no notebook imports them, then delete.
3. **Batch C — Orphan private methods (filtered):** the 17 method candidates minus the Qt event override / pyqtgraph hook false-positives listed in the audit prologue. Net cleanup target ≈ 8–10 methods (e.g. `CertusCollapsible.expand/collapse`, `CertusBaseApp.show_skeleton/hide_skeleton`, `MetalOptimizationWorker.create_de_callback/handle_stop_iteration`, `LiveOptimizationVisualizer.set_target_data/request_update`, `StratContext.get_cached_clues`, `ProgressDialog.set_progress`).
4. **Batch D — Test-only public symbols:** demote to private `_helper` inside the test module *or* delete if the test itself is obsolete.
5. **Batch E — DESIGN.py triplet dedup:** subsumed by **#11** (extract shared logic to a base class `_BaseDesignWorker`); confirms ≈ 600 LOC reduction. Coordinate with #11 batch plan.
6. **Batch F — Unused imports cleanup:** *only after* **#2** (`ruff` adopted) — run `ruff check --select F401 --fix` per module starting with `certus_re_helpers.py` (104) and `CERTUS_RE.py` (95). Verify nothing breaks via headless test suite. Do **not** remove `from __future__ import annotations` (PEP 563 directive — false positive).
**Acceptance:** re-run `python tools/dead_code_audit.py --output reports/CERTUS_DEAD_CODE_AUDIT_<date>.md` shows **≤ 2 orphan top-level fns**, **0 orphan classes**, **≤ 5 orphan methods**, **0 test-only public symbols**, **0 DESIGN.py triplet duplicates**, **< 50 unused imports across the repo** (i.e., 90 % reduction on each axis).
**Risk:** Qt slot mechanisms and pyqtgraph duck-typing can mask legitimate references — every batch must run the full headless test suite + a manual smoke (open each app, run a tiny optimisation) before merge.

---

## D. RULES OF ENGAGEMENT (2026 standards)

These are **non-negotiable** for any incoming change:

1. **Event-loop purity.** No `processEvents()`, no `time.sleep()` in main thread. Only signals + `QThread`.
2. **DTO boundary.** Workers receive immutable dataclasses (or Pydantic models post-#43), never `dict[str, Any]` unchecked.
3. **Small increments.** Refactor one symbol per PR. No "Big Bang" rewrites of monoliths.
4. **No public API breakage** without explicit approval (CODEOWNERS gate).
5. **Fail loudly.** Every scientific or export error must `logger.exception()` + UI toast + `manifest.error_flag`. No `except Exception: pass`, no silent `sys.exit()`.
6. **Determinism by default.** Stochastic flows take a `seed`. CI runs in deterministic mode.
7. **Manifest mandatory.** Any output without a valid `RunManifest` is invalid.
8. **Test first.** Lock contract via regression tests *before* refactoring. Every action in §C requires this.
9. **Single-language source strings.** EN everywhere; FR allowed only in dev journal notes (this file's archive), never in user-facing strings.
10. **Reproducible.** A 5-year-old run replays bit-equal (or ε-close, documented) from this repo + lockfile + materials DB version.
11. **Style preservation.** Match the existing formatter (or future ruff format) and module conventions; never re-format unrelated code in the same PR.
12. **Tooling/CI changes** require explicit user validation (open as a dedicated PR, never bundled with logic changes).

---

## E. DEEP-DIVES PER MONOLITH

### E.1 `CERTUS_INDEX_SPLINE.py` (17 508 LOC, 266 fns, 23 cls)
- **#20** `build_report` → builder pattern.
- **#24** `_show_smart_init_preview_dialog` → class (BLOCKED on #2 + pytest-qt).
- **#25** `_build_basic_step4_mesh_optimizer` extract.
- **#19** linearize 5 deferred imports in `certus_index_spline_core.py`.
- **#34** 58 broad except (top-2 of repo).
- **#46** localization audit residual.

### E.2 `CERTUS_STRAT.py` (18 544 LOC, 210 fns, 23 cls)
- **#57/#58** spline pipeline giants upstream.
- **#34** 58 broad except (top-1 of repo).
- `run_final_simulation_block` 1 080, `_run_step_23_full` 810, `update_data` 763, `optimize_block_strategy_hybrid` 662, `_auto_export_results` 589 still ≥ 400 LOC — decomposition deferred to **#60** (new, P1/XL).

### E.3 `_certus_physics_impl.py` (16 053 LOC, 175 fns, 8 cls)
- **#35** branch coverage on.
- **#36** Hypothesis property tests.
- **#37** coverage backlog batches B.24..B.31.
- **#38** benchmark gate.
- **#41** mutation testing.
- **#42** Numba AOT split.
- Public API → first whitelist target for #27 (mypy).

### E.4 `CERTUS_INDEX.py` (15 381 LOC, 160 fns, 23 cls)
- **#59** residual giants: `load_file` (575), `_optimize_point_kernel` (532), `_update_nk_plot` (429), `_build_ui` (402).
- **#34** 27 broad except.

### E.5 `CERTUS_DESIGN.py` (14 989 LOC, 122 fns, 4 cls)
- `_optimization_callback` triplet 413 LOC (OptimWorker/NeedleWorker/ColorWorker) → **#56** batch E (base class extraction).

### E.6 `CERTUS_RE.py` + `certus_re_workers.py` (10 265 + 6 876 LOC)
- **#15** kill last wildcard import.
- **#16** `_execute_phase2_splines` (1 765 LOC).
- **#17** `_build_re_run_context` (1 569 LOC).
- **#18** `_execute_phase4_beam` (1 410 LOC).
- **#19** `_show_re_results_window` + `load_reverse_engineering_from_path`.

### E.7 `spline_profile_corridors.py` (8 853 LOC, 48 fns, 1 cls) — **previously off-roadmap**
- **#21** + **#22** decomposition of 4 giants (4 487 LOC combined).
- 17 broad except (top-6 of repo).

### E.8 `certus_substrate_index.py` (5 849 LOC, 93 fns, 4 cls) — **previously off-roadmap**
- **#23** `fit_sellmeier` (1 591 LOC) decomposition.
- Sellmeier presets → #39 materials DB versioning.

### E.9 `CERTUS_METAL_SINGLE.py` + `CERTUS_METAL_BILAYER.py`
- **#26** dedup ~60 % into `certus_metal_common.py`.
- **#55** `MetalJobSpec` orchestrator.
- **#27** first whitelist target for mypy.

### E.10 `certus_ui.py` + UX modules
- **#29** `connect(lambda …)` hygiene (~80 sites).
- **#34** 45 broad except (top-3 of repo).
- **#44** design tokens for `setStyleSheet` (~304 sites).
- **#45** WCAG-AA validation.
- **#46** single-language policy.
- **#31** `SystemConfig` → `CertusRuntime` migration.

---

## F. RISK REGISTER (compact)

| ID | Risk | Severity | Mitigation action(s) |
| :--- | :--- | :--- | :--- |
| **R-01** | Big-bang refactor breaks UI flow | High | #14..#25 incremental, one method per PR |
| **R-02** | Headless tests miss UI signals | Medium | #24 pytest-qt adoption |
| **R-03** | Numba JIT silent regression | Medium | #38 benchmark gate |
| **R-04** | Materials DB drift | High | #39 versioning + hash in manifest |
| **R-05** | Schema permissive accepts garbage | High | #7 strict 2020-12 |
| **R-06** | Anti-debug masks errors | High | #9 remove or rewrite |
| **R-07** | Supply-chain (no hash, no SBOM) | High | #5 + #6 + #48 |
| **R-08** | Code-signing missing → SmartScreen | Medium | #49 Authenticode |
| **R-09** | Frozen artifact diverges from source | Medium | #50 boot smoke |
| **R-10** | KPI denominators hard-coded | Medium | #10 AST-driven |
| **R-11** | Wildcard imports block static analysis | Medium | #15 |
| **R-12** | Globals + import-time side effects | Medium | #31 + #32 |
| **R-13** | Non-deterministic flows undetected | Medium | #10 (K4 expansion) + #36 |
| **R-14** | Coverage ≠ correctness | High | #41 mutation testing |
| **R-15** | Cold-start re-JIT cost | Low | #42 AOT |
| **R-16** | A11y unmeasured | Medium | #45 |
| **R-17** | Mixed-language strings | Low | #46 |
| **R-18** | UI styling drift | Low | #44 design tokens |
| **R-19** | Auditor cannot replay 5-year-old run | High | #51 + #52 + #54 |
| **R-20** | New dead code re-accumulates | Medium | #8 AST guard |

---

## G. KPI CONTRACTS (tracked nightly via `tools/kpi_snapshot.py`)

| KPI | Aggregator | Linked actions | Trend gate |
| :--- | :--- | :--- | :--- |
| **K1** | strict regex `except Exception:` | — | stay 0 |
| **K2** | regex `processEvents\|time\.sleep` in runtime | — | stay 0 |
| **K3** | AST scan `BaseHeadlessRequest` subclasses | #10 | denominator ≥ 6 |
| **K4** | AST scan deterministic flows (seed) | #10 | denominator ≥ 6 |
| **K5** | `coverage.xml` line-rate on `_certus_physics_impl.py` | #37 | ≥ +5 pts/sprint |
| **K6** | service registry count | #10 | denominator ≥ 6 |
| **K7** | broad except heuristic | #34 | -200/sprint |
| **K8** | mypy `--strict` files passing / total whitelisted | #27 | +1 module/PR |
| **K9** | `interrogate` ratio | #28 | +1 module/PR |
| **K10** | AST functions ≥ 400 LOC | #11..#25 | -1/PR |
| **K11** | `jscpd` METAL pair | #26 | < 5 % at end |
| **K12** | `radon cc` worst case | #34 (collateral) | < 25 |
| **K13** | hash-pinned lines / total in lockfile | #5 | 100 % |
| **K14** | SBOM artifact present | #48 | every tag |
| **K15** | `coverage.xml` branch-rate on physics | #35 | ≥ 85 % long-term |
| **K16** | mutation score | #41 | ≥ 60 % long-term |

---

## H. RELEASE READINESS — Definition of Done

A release is shippable to operators **only** if all gates below are green:

- [ ] **Build** — `python -m build .` produces wheel; `pip install dist/*.whl` works (gate of #1).
- [ ] **Lint** — `ruff check .` exit 0 (gate of #2).
- [ ] **Tests** — `pytest tests/unit tests/integration` exit 0 with branch coverage ≥ K15 floor.
- [ ] **Property** — `pytest tests/property` exit 0 (#36).
- [ ] **Benchmarks** — no kernel regression > 5 % vs previous tag (#38).
- [ ] **Reference replays** — every scenario in `samples/reference/v1/*` ε-close (#40).
- [ ] **Security** — `pip-audit` + `gitleaks` + CodeQL all green (#6).
- [ ] **Lockfile** — every dep line has `--hash=sha256:` (#5).
- [ ] **Frozen smoke** — PyInstaller artifact boots with `--check-frozen-run` (#50).
- [ ] **Authenticode** — signature valid on every `.exe` (#49).
- [ ] **SBOM** — `sbom.cdx.json` attached to tag (#48).
- [ ] **Manifest** — every export has full `RunManifest` including `materials_db_hash` (#39, #51).
- [ ] **Determinism statement** — `docs/DETERMINISM_GUARANTEE.md` matches the released codebase (#52).
- [ ] **Release dossier** — `release_dossier_vX.Y.Z.zip` produced and archived (#54).

---

## I. ENTRY POINTS FOR THE NEXT WORK SESSION

1. Read this file from top.
2. Open the next un-checked action by `#N` order. Don't skip.
3. Confirm acceptance criterion is testable on your machine **before** writing code.
4. Open the dedicated PR; mention `Closes #N` in the description with link to this file.
5. After merge, update `reports/CERTUS_CHANGELOG_ROADMAP.md` (NOT this file) with the post-mortem.

> **This file stays prospective.** Move completed actions to the changelog file. Never mark anything "done" here — strike it through and remove on the next refresh instead.
