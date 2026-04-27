# CERTUS MASTER TODO: QUALIFICATION & OPTIMIZATION ROADMAP
**Date:** 2026-04-25
**Status:** In Execution (P0-6 + ARCH-4 runtime completed; ARCH-3 transversal pilot completed; next hard focus: ARCH-1 + P1-2 + P1-12)
**Target Standard:** 2026 World-Class Python & PyQt6.10+ Architecture
**Objective:** Elevate CERTUS from a functional prototype to a **certified, 100% traceable, and flawlessly decoupled Metrology Instrument**, enforcing strict thread-safety, absolute reproducibility, and zero-defect release control.

This document serves as the **single source of truth** for the remaining optimization work. Tasks must be executed sequentially by priority, strictly adhering to the rule of small, reversible increments.

---

## 1. COMPREHENSIVE RISK MATRIX
*Based on full static analysis of the 200,000+ line codebase.*

| Risk ID | Risk Area | Impact | Probability | Mitigation Strategy (Action Item) |
|---|---|---|---|---|
| RM-01 | **Silent Failures in UI/Exports** | High (Corrupted runs without notice) | High | Eradicate `except Exception:` (190+ instances), enforce `ValidationStatus` & explicit logging (P0-6). |
| RM-02 | **Stochastic Non-Reproducibility** | Critical (Audit failure) | High | Enforce global persisted `random_seed` down to all workflows (RE, STRAT, DESIGN) (P0-2b). |
| RM-03 | **Uncontrolled Model Assumptions** | Critical (Incomparable results) | Medium | Deploy `RunManifest` containing all model assumptions, input hashes, and env vars (P0-1b, P0-3). |
| RM-04 | **Monolithic Regression** | High (Bug fix breaks another app) | High | Extract headless services from 10k+ line files (`CERTUS_INDEX_SPLINE`, `CERTUS_STRAT`) (ARCH-1, P1-2). |
| RM-05 | **Unversioned/Corrupt Configs** | Medium (Runtime instability) | Medium | JSON schema validation, strict versioning, and explicit migration logic (P1-5). |
| RM-06 | **API & Documentation Divergence** | Medium (Dev/User confusion) | Low | CI enforcement testing API snippets against real codebase (P1-7). |
| RM-07 | **Unjustified Uncertainty Variations** | High (Loss of metrological credibility) | Medium | Standardized `UncertaintyBudget` across all apps, not just SPLINE (P2-1). |
| RM-08 | **Blind Spots in Core Physics Tests** | Critical (Math errors undetected) | High | Re-integrate `_certus_physics_impl.py` into coverage, enforce direct kernel tests (P1-12). |
| RM-09 | **UI-Worker State Coupling** | High (Race conditions, freezes) | High | Enforce strict DTO (Data Transfer Object) pattern for all QThread workers (ARCH-3). |
| RM-10 | **Event Loop Corruption (PyQt6)** | Critical (Nested loops, crashes) | High | **Eradicate `QApplication.processEvents()`** (50+ instances found) and `time.sleep()`. Replace with asynchronous QThread/Signals (ARCH-4). |
| RM-11 | **Hard Exit Vulnerabilities** | Medium (State loss on close) | Medium | Fix double `sys.exit()` calls (e.g., in `CERTUS_STRAT`) and implement graceful shutdown hooks (ARCH-5). |

---

## 2. PHASE A: METROLOGICAL RELIABILITY & RUN-CONTROL (IMMEDIATE)
*Objective: Guarantee that no result can be generated non-reproducibly or with silent errors.*

- [x] **P0-1b: Total Manifest Deployment.** 
  - Apply `RunManifest` to ALL secondary and utility export paths (beyond `build_standard_report`).
  - Enforce a single entry point for manifest generation to prevent divergence.
  - **Progress 2026-04-25:** central manifest entry point hardened in `certus_services.BaseHeadlessService` with canonical `source_paths` normalization (trim/deduplicate/empty-filter) + non-regression unit test.
  - **Progress 2026-04-25:** shared manifest completeness gate extracted to `certus_data.get_missing_manifest_fields` and wired in `build_standard_report`, `CERTUS_STRAT`, and `CERTUS_RE` to remove duplicated required-fields logic.
  - **Progress 2026-04-25:** INDEX_SPLINE Excel export now uses the same shared manifest completeness gate and blocks export on incomplete manifests (manual + auto paths).
  - **Progress 2026-04-25:** DESIGN Pareto HTML export now generates a run manifest through headless service entry point, enforces shared manifest completeness gate, and embeds manifest table in the report.
  - **Progress 2026-04-25:** INDEX_SPLINE secondary exports (`corridor envelope xlsx`, `n-k csv`, `corridor csv`) now enforce the same shared manifest completeness gate before writing files.
  - **Progress 2026-04-25:** DESIGN full `export_results()` path now generates/validates run manifest with shared gate and injects a Manifest section in both Excel and HTML exports.
  - **Progress 2026-04-25:** RE `targets vs theory` Excel export now generates/validates run manifest with shared gate and injects a `Manifest` sheet.
  - **Scope note:** this closure covers scientific result/report exports; plot-only utility exports (PNG/SVG/clipboard/quick CSV views) remain intentionally outside manifest gating scope.
- [x] **P0-2b: Global Seed Propagation.**
  - Propagate the validated `seed` mechanism to the remaining stochastic flows: `CERTUS_RE`, `CERTUS_STRAT`, `CERTUS_DESIGN`, `CERTUS_METAL_*`.
  - **Progress 2026-04-25:** seed sourcing hardened on `CERTUS_RE`, `CERTUS_STRAT`, `CERTUS_DESIGN`, and `certus_metal_common` with deterministic fallback chain + safe `int` normalization.
- [x] **P0-3: Traceability Hashes.**
  - Calculate and systematically include SHA-256 fingerprints for input spectrum files, the material database, and substrate reference files in all manifests and exports.
  - **Progress 2026-04-25:** source-path wiring hardened on STRAT/RE/SUBSTRATE + DESIGN/METAL flows to include DB/substrate/measurement/config files when available, enabling SHA-256 capture through `RunContext.input_fingerprints`.
  - **Progress 2026-04-25:** non-regression unit test added to enforce multi-file fingerprint capture (`tests/unit/test_certus_services.py`).
- [x] **P0-6: Silent Failure Eradication (Critical Runtime/Export Scope).**
  - Over 190 instances of `except Exception:` exist in the codebase. Identify and replace all broad `except` blocks (especially on UI and export paths) with `logger.exception()` + UI toast alert + error flag in the run manifest.
  - **Progress 2026-04-25:** completed on active codebase modules (runtime + UI utilities + reporting layer).
  - Remaining debt is now limited to legacy archive code (`archive/2404_cleanup/...`).
- [ ] **P0-8: Spline Model Transparency.**
  - Add an explicit banner in the INDEX_SPLINE UI and reports stating the exact mathematical nature of the model (*PWL in σ=1/λ, piece-wise linear ln(k), T/R mode*).

---

## 3. PHASE B: MODERN PYQT6 ARCHITECTURE & DECOUPLING
*Objective: Progressively dismantle GUI monoliths to enable pure business logic unit testing and perfect UI fluidity.*

- [x] **ARCH-4: Event Loop Purity (Runtime Scope Completed).**
  - **CRITICAL:** The codebase relies heavily on `QApplication.processEvents()` (e.g., in `CERTUS_STRAT`, `CERTUS_INDEX_SPLINE`) and `time.sleep()` to prevent UI freezing during heavy tasks. This is a PyQt6 anti-pattern causing nested event loops and instability. 
  - **Action:** Replace all pseudo-asynchronous blocking loops with pure `QThread` / `QRunnable` architectures emitting strict Signals.
  - **Progress 2026-04-25:** runtime modules purged (`CERTUS_INDEX_SPLINE`, `CERTUS_STRAT`, `CERTUS_INDEX`, `CERTUS_DESIGN`, `CERTUS_RE`, `certus_substrate_index`, `CERTUS_METAL_SINGLE`, `CERTUS_METAL_BILAYER`, `certus_curve_smoother`, `certus_reset_framework`).
  - Remaining occurrences are documentation/tests/archive references.
- [ ] **ARCH-3: Strict DTO Pattern for Workers.**
  - Workers currently read directly from the UI state. Refactor all QThread implementations to use pure Data Transfer Objects (DTO) (Payload In, Result Out) ensuring total thread-safety and enabling headless execution.
  - **Status 2026-04-25:** DTO pattern input+output now operational across core worker domains (`CERTUS_RE`, `certus_spectral_workers`, `CERTUS_DESIGN`) and established on `CERTUS_STRAT.WorkerThread` (steps 0/2/3/23/33), with legacy payload compatibility preserved at signal/report boundaries.
  - **Milestone 2026-04-25:** **ARCH-3 pilot transversal completed** (RE + SPECTRAL + DESIGN + STRAT). Remaining work is industrialization/coverage extension, not pilot feasibility.
  - **Progress 2026-04-25:** pilot DTO boundary introduced for RE worker input (`REWorkerRequest`) with backward-compatible legacy cfg adapter and unit tests.
  - **Progress 2026-04-25 (step 2):** RE phase-1 output now built via typed DTO (`REPhase1Result`) then adapted through a compatibility mapper (`to_legacy_dict`) to preserve existing downstream behavior while reducing worker/UI coupling.
  - **Progress 2026-04-25 (step 3):** RE phase-2 spline/joint output now built via typed DTO (`REPhase2Result`) with optional substrate Cauchy fields and legacy compatibility mapping; dedicated unit tests added for both with/without Cauchy payload variants.
  - **Progress 2026-04-25 (step 4):** RE phase-3 shake refinement output now built via typed DTO (`REPhase3Result`) with legacy compatibility mapping, keeping phase orchestration behavior stable while reducing raw dict coupling.
  - **Progress 2026-04-25 (step 5):** RE phase-4 beam/aperture output now built via typed DTO (`REPhase4Result`) including aperture summary fields and optional substrate Cauchy coefficients, still exported through legacy mapper for zero-regression migration.
  - **Progress 2026-04-25 (step 6):** Phase-4 aperture scan fallback no longer clones raw dicts directly; it now rehydrates a typed `REPhase4Result` from legacy payload (`from_legacy_dict`) and re-emits via DTO mapper, closing the remaining P4 dict-coupling path.
  - **Progress 2026-04-25 (step 7):** phase-4 execution now consumes a typed `best_res_dto` (`REPhase4Result.from_legacy_dict`) for initialization and NFEV propagation, replacing key direct `best_res["..."]` lookups in the critical setup path while preserving legacy output boundaries.
  - **Progress 2026-04-25 (step 8):** RE finalization/ranking path now materializes a single typed top-result view (`_top_dto`) right after sorting, and uses it for final RMSE metrics, stop-spectrum emission, and substrate Cauchy diagnostics, reducing repeated `results[0]["..."]` raw dict reads.
  - **Progress 2026-04-25 (step 9):** introduced `_top_result_dto(...)` helper and applied it in phase 2/3 transition paths (live spectrum emit + improvement checks), replacing additional direct `results[0]` reads with typed DTO access; helper coverage added in unit tests.
  - **Progress 2026-04-25 (step 10):** removed remaining direct `results[0]["..."]`/`results[0].get(...)` reads in RE worker hot paths (staged-order milestone, top-K merge check, P4 best tracker, final ranking suffix) by consistently using typed DTO views, while preserving legacy dict boundaries for external consumers.
  - **Progress 2026-04-25 (step 11):** generalized typed read access with `_result_dto_at(results, idx)` and migrated residual indexed reads (`results[1]` merge comparator and fallback sites), with dedicated unit-test coverage for index bounds and selection semantics.
  - **Progress 2026-04-25 (step 12):** added a minimal typed result gateway for mutations (`_set_top_result_dto`, `_prepend_result_dto`) and applied it to phase-3 top replacement + phase-4 insertions, reducing direct dict mutation patterns while maintaining legacy payload shape at boundaries.
  - **Progress 2026-04-25 (step 13):** extended typed mutation gateway with `_replace_all_with_top_dto` and migrated phase-2 best-candidate assignment (`results[:] = [best]`) to typed pathway; unit tests now cover set/prepend/replace-all helper semantics.
  - **Progress 2026-04-25 (step 14):** migrated staged-order step 2/3 (`_execute_phase1_p4_scan`) to typed top-input + typed prepend output (`REPhase4Result` + `_prepend_result_dto`), removing another direct dict insertion path while keeping ranking/output compatibility.
  - **Progress 2026-04-25 (step 15):** started DTO rollout on a second worker domain (`certus_spectral_workers.EvalWorker`) with immutable input boundary (`EvalWorkerRequest`) and legacy-adapter constructor support (`dict | EvalWorkerRequest`), plus dedicated unit tests for defensive copy/non-dict handling.
  - **Progress 2026-04-25 (step 16):** extended DTO rollout to a third worker domain (`CERTUS_DESIGN.OptimWorker`) using a dedicated DTO module (`certus_design_workers_dto.OptimWorkerRequest`) and backward-compatible constructor (`dict | OptimWorkerRequest`), with focused unit tests validating legacy payload adaptation.
  - **Progress 2026-04-25 (step 17):** completed first-pass DESIGN worker DTO alignment by adding `ColorWorkerRequest` and `NeedleWorkerRequest` and wiring backward-compatible constructors (`dict | *WorkerRequest`) for `ColorWorker` and `NeedleWorker`; DTO unit coverage expanded accordingly.
  - **Progress 2026-04-25 (step 18):** introduced first non-RE worker output DTO (`EvalWorkerResult`) in `certus_spectral_workers`, routing `signals.finished` payload through typed-to-legacy mapping (`to_legacy_dict`) to preserve UI contract while establishing a structured result boundary.
  - **Progress 2026-04-25 (step 19):** added first DESIGN-side output DTO (`ColorWorkerResult`) and wired `ColorWorker` finished-signal payload through typed-to-legacy mapping, with unit tests for success/failure payload shape compatibility.
  - **Progress 2026-04-25 (step 20):** added `OptimWorkerResult` output DTO and migrated `OptimWorker` success/failure finished payloads to typed-to-legacy mapping, completing the same output-boundary pattern for the main DESIGN optimization worker.
  - **Progress 2026-04-25 (step 21):** added `NeedleWorkerResult` output DTO (including `from_legacy` bridge for split-result payloads) and migrated all `NeedleWorker` finished-signal exits (`max_layers_reached`, `empty_init`, `split/none`) through typed-to-legacy mapping.
  - **Progress 2026-04-25 (step 22):** normalized worker-output DTO nomenclature with explicit constructors (`success`, `failure`, `action_only`) across DESIGN/SPECTRAL DTOs and updated worker call-sites, improving contract readability while preserving unchanged legacy payload shapes.
  - **Progress 2026-04-25 (step 23):** started ARCH-3 extension to `CERTUS_STRAT.WorkerThread` with `WorkerThreadRequest` input DTO (`certus_strat_workers_dto`) and backward-compatible constructor adaptation (`step|WorkerThreadRequest` + copied legacy fields), validated by dedicated unit tests.
  - **Progress 2026-04-25 (step 24):** added `WorkerThreadResult` output DTO for STRAT and migrated `WorkerThread` finished payloads for steps 0/2/3 (`nominal_results+seel_data`, `opti_results`, `final_results`) to typed-to-legacy mapping, with focused DTO serialization tests.
  - **Progress 2026-04-25 (step 25):** extended STRAT output DTO coverage to the combined workflow path (`step 23`) by routing the `{opti_results, final_results}` finished payload through `WorkerThreadResult.for_step_23(...).to_legacy_dict()`.
  - **Progress 2026-04-25 (step 26, superseded by step 27):** STRAT `step 33` had no dedicated `signals.finished` payload at audit time (table/plot/excel side-signals only); explicit serialization test for `WorkerThreadResult.for_step_3` added.
  - **Progress 2026-04-25 (step 27):** added an explicit `signals.finished` payload for STRAT `step 33` and routed it through `WorkerThreadResult.for_step_33(...).to_legacy_dict()`, aligning step 33 completion contract with the rest of WorkerThread DTO output paths.
- [ ] **ARCH-1: Reverse Engineering Decoupling (`CERTUS_RE.py`)**
  - Extract a dedicated `REResultsBuilder` (similar to the SPLINE equivalent).
  - Break down the massive `REWorker` into isolated, testable phases (P4 scan, splines, shakes, beam).
  - **CRITICAL:** Remove wildcard imports (`from certus_re_helpers import *`) to enforce explicit dependency tracking.
- [ ] **ARCH-5: Graceful Shutdown & Lifecycle.**
  - Remove duplicate `sys.exit(app.exec())` calls (found in `CERTUS_STRAT.py`). Implement `closeEvent` overrides to cleanly terminate Numba threads and save states before exiting.
- [ ] **P1-2: Headless Services Deployment.**
  - Implement Qt-independent service contracts for remaining domains relying on the new DTO architecture:
    - `MetalFitService`
    - `ReverseEngineeringService`
    - `SubstrateIndexService`
    - `DesignSynthService`
    - `StratStrategyService`

---

## 4. PHASE C: BUSINESS LOGIC HARDENING & SOFTWARE QUALITY
*Objective: Standardize physics rules, unify uncertainties, and certify the pipeline via reference datasets.*

- [ ] **P1-12: Core Physics Test Coverage.**
  - Remove `_certus_physics_impl.py` from the `omit` list in `pytest.ini`. Relying solely on indirect coverage for an 8,000+ line math file is a critical metrological risk. Write direct unit tests for all mathematical kernels to achieve >90% coverage.
- [ ] **STRAT-1: STRAT Hardening (`CERTUS_STRAT.py`)**
  - **P1-8:** Strict and systematic validation of business payloads against `STRAT_PAYLOAD_SCHEMA_V1.json`.
  - **P1-9:** Replace floating-point wavelengths with strict integer indexing (Numba SYM V2 phase 1 spec).
  - **P1-10:** Implement a purely deterministic ranking mode for CI (absolute rules for tie-breakers).
- [ ] **RD-1: METAL Fusion.**
  - Consolidate `METAL_SINGLE` and `METAL_BILAYER` under a single orchestrator module via `MetalJobSpec` (after strict validation of functional parity on real spectra).
- [ ] **P1-11: Versioned Substrate Datasheets.**
  - Modify `certus_substrate_index.py` to generate exportable reference datasheets (material, model, coeffs, uncertainties, source hash, CERTUS version).
- [ ] **P2-1: Transverse Uncertainty Budget.**
  - Create and integrate a common `UncertaintyBudget` class/layer across INDEX, METAL, RE, DESIGN, and SUBSTRATE. Systematically make explicit "Uncertainty not computed" where applicable.
- [ ] **P1-3: Reference Datasets & Benchmarks.**
  - Freeze integration datasets per module (Source File + Expected Output + Acceptable Tolerances). Introduce automated performance regression benchmarks tracking exact execution times for heavily optimized Numba JIT paths.

---

## 5. PHASE D: PREMIUM OPERATOR UX
*Objective: Smooth the user experience and unify the interface under a professional standard.*

- [ ] **UX-1: `CertusDashboardCard` Deployment.**
  - Generalize the use of cards across METAL, RE, DESIGN, and STRAT. Unify the semantics of the confidence color code (Green/Yellow/Red).
- [ ] **UX-2: `CertusStepper` Workflow.**
  - Deploy step-by-step navigation with logical locks (Data -> Config -> Run -> Results) in INDEX, RE, DESIGN, and METAL.
- [ ] **UX-3: Rich Transverse Reports.**
  - Extend the `_build_report_sections` builder to inject highly detailed PDF/Excel reports (Cover + Manifest + Graphs + Stats) into RE, METAL, DESIGN, STRAT, and SUBSTRATE_INDEX.

---

## 6. PHASE E: RELEASE CONTROL & PACKAGING
*Objective: Industrialize delivery, packaging, and automatic compliance checks.*

- [ ] **P1-4: CI Windows & Packaging.**
  - Maintain the `pyproject.toml` (PEP 621) and absolute dependency lockfile (Python 3.10-3.12 support).
  - Optimize the existing GitHub Actions pipeline (`release-windows.yml`) to parallelize PyInstaller frozen builds and offscreen smoke tests.
- [ ] **P1-7: Docs ↔ Code Alignment.**
  - Add a blocking test suite validating that documentation matches the code (e.g., presence and validity of `MODULE_ID`, performance claims, worker policy).
- [ ] **P1-6: Offline Resilience.**
  - Package `MathJax`/`Mermaid` locally for HTML rendering or introduce a graceful degradation banner when offline.
- [ ] **P3-1: Automated Release Dossier.**
  - Create a tool that automatically generates the build manifest, Smoke Suite results, reference dataset execution report, performance benchmark diffs, and a scientific changelog before each Release/Tag validation.

---

### 🛑 STRICT 2026 REFACTORING RULES
1.  **Zero-Tolerance for Nested Event Loops:** Never use `processEvents()`.
2.  **DTO Boundary:** Workers must receive pure immutable dataclasses, not references to GUI widgets.
3.  **One File / One Function:** Make small, reversible pull-requests. Do not attempt a "Big Bang" rewrite of monolithes like `CERTUS_STRAT.py` (9,800 lines). Extract classes one by one.
4.  **No Public API Breakage:** Do not modify public contracts without explicit approval.
5.  **Test First:** Rely on existing tests or write a minimal test validating the modified zone before touching logic.
6.  **Fail Loudly:** Any scientific/export failure must be explicit (`logger.exception`, UI alert, manifest flag).
7.  **Manifest Is Mandatory:** Any generated result without a complete manifest is considered invalid.
8.  **Determinism by Default:** CI paths must execute in deterministic mode (seeded + deterministic ranking/tie-breakers).

---

## 7. EXECUTION ORDER (NEXT 6 SPRINTS)
*Objective: Convert the roadmap into a deterministic delivery pipeline.*

### Sprint 1 (Safety Baseline)
- [x] Execute **ARCH-4 inventory**: list all `processEvents()` and `time.sleep()` occurrences by file and function.
- [x] Start **P0-6** on the highest-risk flows first (export/report/UI commit actions).
- [x] Add run-level assertion: block report/export generation when manifest is missing required fields.

### Sprint 2 (Reproducibility Foundation)
- [x] Complete **P0-2b** for RE and STRAT paths.
- [x] Start **P0-3** (input hashes for spectra + database + substrate references).
- [x] Add deterministic CI smoke run for one dataset per critical module.
  - **Progress 2026-04-25:** deterministic seeded smoke checks added in `tests/unit/test_certus_services.py` (INDEX/RE/SUBSTRATE service paths) and executed in the existing CI "Unit contracts" step.

### Sprint 3 (Architecture Stabilization)
- [x] Implement **ARCH-3 DTO** boundary in one pilot domain (`CERTUS_RE`) and validate thread-safe execution.
- [ ] Launch **ARCH-1** extraction of `REResultsBuilder` + first REWorker split.
- [ ] Remove at least one wildcard import and replace by explicit contracts.

### Sprint 4 (Physics Hardening)
- [ ] Start **P1-12** with direct kernel tests in `_certus_physics_impl.py`.
- [ ] Deliver first **reference dataset pack** (`P1-3`) with tolerances and expected artifacts.
- [ ] Add deterministic benchmark baseline for one hot JIT path.

### Sprint 5 (Cross-Module Standardization)
- [ ] Start **P2-1** `UncertaintyBudget` integration in INDEX + RE.
- [ ] Progress **P1-11** substrate datasheet export with source hashes.
- [ ] Validate STRAT payload schema checks on all business entry points.

### Sprint 6 (Release Readiness)
- [ ] Finalize **P1-4** build parallelization and offscreen smoke tests in CI.
- [ ] Implement **P1-7** docs-vs-code blocking checks.
- [ ] Deliver initial **P3-1 release dossier** generator prototype.

---

## 8. DEFINITION OF DONE (PER TASK)
*A task is complete only if all criteria are met.*

- [ ] Code merged in small reversible PRs with explicit scope.
- [ ] Unit/integration tests added or updated for the touched logic.
- [ ] Deterministic behavior validated when relevant (seed, tie-breakers, repeatable output).
- [ ] Manifest/report/docs updated to reflect the new behavior.
- [ ] No new broad `except Exception:` in modified files.
- [ ] No `processEvents()` or `time.sleep()` introduced in UI execution paths.
- [ ] Lint/type/test checks pass in CI for impacted modules.

---

## 9. DELIVERY KPIS (MANDATORY TRACKING)
*Track weekly, publish in engineering review.*

- **KPI-1: Broad Exception Debt** = remaining `except Exception:` instances (target: monotonic decline to 0 on critical paths first).
- **KPI-2: Event Loop Purity Debt** = remaining `processEvents()` + `time.sleep()` in GUI paths.
- **KPI-3: Manifest Coverage** = `% of result/export paths emitting complete RunManifest`.
- **KPI-4: Deterministic Coverage** = `% of core workflows validated with fixed seed in CI`.
- **KPI-5: Physics Direct Coverage** = line/function coverage on `_certus_physics_impl.py`.
- **KPI-6: Headless Service Coverage** = `% of business flows executable without Qt UI context.

### KPI Snapshot (2026-04-25, post P0-6/ARCH-4 pass)
- **KPI-1 (active codebase):** `except Exception` = **0** (legacy archive excluded).
- **KPI-1 (including archive):** residual debt remains in archive scope (**25** occurrences).
- **KPI-2 (runtime modules):** `processEvents` + `time.sleep` = **0** in main application modules.
- **KPI-2 (residual non-runtime):** remaining `processEvents` references are in docs/tests/archive.
- **KPI-3 (static manifest wiring proxy):** **100.0%** (`9/9` request sites wired with non-empty `source_paths`).
- **KPI-4 (deterministic CI contract proxy):** **100.0%** (`2/2` deterministic test contracts declared).
- **KPI-5 (physics direct baseline):** improved baseline available (`line=9.4%`, `function-proxy=93.3%`) from `reports/KPI_SNAPSHOT_2026-04-25.md` after targeted hot-path physics tests.
- **KPI-6 (headless service coverage proxy):** **100.0%** (`3/3` headless service flows covered by dedicated unit tests).
- **Automation:** weekly snapshot script available at `tools/kpi_snapshot.py` (AST-based request wiring analysis + KPI-6 proxy + optional KPI-5 runtime mode). CI workflow now generates KPI snapshot plus a bounded best-effort KPI-5 runtime pass (`continue-on-error`, timeout) and uploads KPI artifacts on py311 runs. Latest report: `reports/KPI_SNAPSHOT_2026-04-25.md`.

---

## 10. GOVERNANCE & REVIEW CADENCE
- **Daily:** 15 min risk triage (RM-01, RM-02, RM-10 blockers first).
- **Weekly:** roadmap checkpoint with KPI update and next sprint lock.
- **Per PR:** architecture gate (DTO boundary, determinism, manifest compliance).
- **Per release candidate:** mandatory release dossier (`P3-1`) + reference dataset replay.

---

## 11. IMMEDIATE NEXT ACTIONS (UPDATED)
1. Start **ARCH-1** on `CERTUS_RE`: extract first `REResultsBuilder` slice and remove one wildcard import with explicit dependencies.
2. Launch **P1-2** first headless service extraction outside RE (prioritize `StratStrategyService` contract boundaries).
3. Begin **P1-12** execution: remove `_certus_physics_impl.py` omission and add first direct kernel test pack with CI baseline.
4. Open three small PR tracks in parallel:
   - Track A: Decoupling (`ARCH-1`, `P1-2`)
   - Track B: Scientific quality (`P1-12`, `P1-3` benchmarks)
   - Track C: Release control (`P1-4`, `P1-7`)
