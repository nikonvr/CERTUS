# Numerical Tolerances

## Purpose

This file centralizes numerical tolerances used to validate scientific regressions.

## Baseline tolerance classes

- **Strict kernel equivalence**
  - `rtol = 1e-9`
  - `atol = 1e-12`
  - Use for deterministic scalar/vector kernels with stable arithmetic paths.

- **Solver-level equivalence**
  - `rtol = 1e-6`
  - `atol = 1e-9`
  - Use for optimization outputs and fitted parameter vectors.

- **Cross-environment equivalence**
  - `rtol = 1e-5`
  - `atol = 1e-8`
  - Use when CPU/OS/threading stack differs.

## Domain-specific guidance

- **Energy conservation checks (`R + T + A`)**
  - Prefer `atol <= 1e-10` on normalized quantities.

- **Spline RMSE profile comparisons**
  - Compare within the same grid/mask first.
  - Use relative tolerance when RMSE scales differ across datasets.

- **Reference replay scenarios**
  - Store per-scenario tolerance in `samples/reference/v*/<scenario>/input.json`.
  - Keep expected outputs immutable; bump scenario version when intentionally changed.

## Change policy

Any tolerance relaxation must include:

- rationale in PR description,
- affected test list,
- before/after error envelopes,
- confirmation that no hidden regression is masked.
