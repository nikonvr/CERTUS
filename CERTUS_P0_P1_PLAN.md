# CERTUS P0 / P1 Action Plan

Date: 2026-05-15

## Goal
Execute the smallest set of changes that most improves CERTUS stability, release confidence, maintainability, and UX under Python 3.14.5+.

## Status
### Done
- Python 3.14.5+ alignment pass completed in docs/workflows/comments.
- P0/P1 action plan created.
- Incremental refactoring of `spline_profile_corridors.py` (Phase 3 & Bonus) completed and validated.
- Verification of CI configurations, release scripts, and critical entrypoints.

### Remaining
- Finalize fine-grained architectural enhancements and continue test coverage boost.

---

# P0 — Must fix first

## P0.1 Python version truth
- [x] Keep `Python 3.14.5+` as the only supported runtime everywhere.
- [x] Remove any remaining references to `3.10`, `3.11`, `3.12`, `3.13`, or `3.14.4` from code, docs, workflows, and comments.
- [x] Reconfirm `pyproject.toml`, `README.md`, CI, and release checks match.

## P0.2 Release and CI reliability
- [x] Verify `release-windows.yml` end to end.
- [x] Verify `lint.yml` end to end.
- [x] Keep lockfile hash validation aligned with real lockfile format.
- [x] Make sure release checks pass in the actual workflow path.
- [x] Remove stale matrix guards and assumptions.

## P0.3 Core stability
- [x] Freeze `certus_core.py` as the foundation layer.
- [x] Test resources, timestamps, frozen/dev mode, and optional dependency handling.
- [x] Prevent new unrelated responsibilities from leaking into the core.

## P0.4 Minimize the largest entrypoints
- [x] Reduce `CERTUS_HUB.py` to navigation and composition.
- [x] Reduce `CERTUS_DESIGN.py` to clear orchestration plus UI.
- [x] Reduce `CERTUS_STRAT.py` to clear orchestration plus UI.
- [x] Reduce `CERTUS_RE.py` and `CERTUS_INDEX.py` around dedicated responsibilities.
- [x] Keep `CERTUS_INDEX_SPLINE.py` dense only where it truly needs to be.

## P0.5 Critical user journeys
- [x] Verify launch, load, compute, cancel, and export flows remain clear.
- [x] Verify long-running operations show usable feedback.
- [x] Verify fatal errors are actionable.

---

# P1 — Highest-value follow-ups

## P1.1 Architecture boundaries
- [ ] Separate bootstrap, orchestration, UI, and numeric computation more clearly.
- [ ] Reduce global imports in large modules.
- [ ] Extract pure helpers from Qt-heavy files.
- [ ] Formalize module boundaries.

## P1.2 Data contracts
- [ ] Replace free-form dicts with typed requests/responses where practical.
- [ ] Standardize DTO naming across Design / Strat / RE / Index.
- [ ] Reduce public `Any` usage.

## P1.3 Headless service layer
- [ ] Keep `certus_services.py` as the clean headless boundary.
- [ ] Keep `certus_strat_service.py` thin and deterministic.
- [ ] Prefer injectable runners and explicit manifests.

## P1.4 UX cleanup
- [ ] Improve the hub hierarchy and launch clarity.
- [ ] Improve Design and Strat workflow clarity.
- [ ] Improve RE and Index result readability.
- [ ] Improve feedback, empty states, and accessibility.

## P1.5 Tests
- [ ] Strengthen unit tests around pure helpers.
- [ ] Strengthen integration tests for main workflows.
- [ ] Add targeted UI smoke coverage where it matters.
- [ ] Add invariant and regression checks for scientific correctness.

---

# Immediate execution order
1. Finish the Python version / CI consistency pass.
2. Keep `certus_core.py` under strict control.
3. Reduce the largest entrypoints.
4. Harden headless services.
5. Clean up UX on the critical flows.
6. Expand tests where gaps remain.

---

# Success criteria
- One runtime standard: Python 3.14.5+
- CI and release paths agree with the runtime standard
- Core stays stable and minimal
- Main entrypoints become thinner
- Headless services stay clean and testable
- UX is clearer on the main workflows
- Tests prove the critical contracts

## État actuel
### Fait
- Alignement Python 3.14.5+ confirmé dans la documentation visible et les workflows déjà inspectés.
- Plan P0/P1 créé.
- Backlog maître créé.
- Audit des modules principaux réalisé.
- Refactoring incrémental de `spline_profile_corridors.py` (Phase 3 et Bonus) finalisé.
- Validation des configurations de release et des entrypoints critiques.

### Reste
- Finaliser les optimisations fines de l'architecture.
- Continuer à renforcer la couverture de tests spécifiques au besoin.