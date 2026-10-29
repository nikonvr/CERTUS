# Bringing the 2026-10-27 findings into CERTUS DESIGN: implementation plan (to approve before coding)

The RICL ships a free copy of CERTUS DESIGN: what the article shows must be usable by its readers. Rules that apply:
- C1: a new option is inactive by default, and the inactive path keeps its bits; `c1_diff HEAD` before committing.
- The user's decision: an option is switched on by default only after DESIGN measures it as better on the 50/50 and on
  other examples (`scripts/design_bench.py`), keeping the switch.
- Architecture: `core` / `physics` never import Qt, `ui` holds no algorithm, and no new layering inversion.
- Validation: the full suite in series, the oracle before and after, then `c1_diff`.

## Feature 1: envelope search with a variable number of layers (what broke the 50/50 plateau)

**Source.** `envelope_v2/search.py`.
- Each N keeps up to 6 polished elites.
- Moves applied to them:
  - perturbations;
  - needles at the minima of the P-function;
  - TOT-preserving removal of thin layers;
  - thick insertions and dilation, which raise the TOT;
  - layer removal.
- Polish: trf with the exact Jacobian.

**DESIGN today.** DESIGN has a fixed-N memetic search (`certus/core/certus_design_memetic.py`) and a needle growth
driven from the orchestrator. Neither changes the TOT on purpose.

**Plan.**
- **New module** `certus/core/certus_design_envelope.py` (pure numpy and scipy):
  - `run_envelope(res_jac, n_idx_of, seq0, d0, minutes, n_max, floor, seed, stop_event, on_improve)`;
  - returns the best design per N, so DESIGN can show RMSE(N) and, with feature 2, R(N).
- **Kernel.** `certus.physics.design_fast_gauss_newton._res_jac_lossless_normal_kernel` (normal incidence, lossless,
  as in the study). It is called through a thin wrapper in `certus/physics/` that builds the per-sequence arrays, so the
  Numba cache keys stay unchanged.
- **Wiring.** `OptimWorker` runs it only when `envelope_minutes > 0` (a new `DESIGN_OPTIONAL_STEPS` key, default 0).
  Oblique or absorbing problems keep the existing workflow, and the log says why.
- **UI.** One spin box and one curve (RMSE against N) in the existing optimisation panel; no algorithm in `ui`.
- **Tests.**
  - Unit: each move keeps a valid stack (alternating materials, d >= floor).
  - The TOT-preserving removal keeps the TOT.
  - A test written to fail on the current code: on a small 50/50 (N <= 12, 2 min) the envelope reaches the RMSE of
    the study's curve at that N.
  - Oracle: the reported RMSE equals `tests/oracle/tmm_reference.py`.

## Feature 2: robust criterion and R(N) curve (their Eq. 5, made exact)

**Criterion.** R^2 = MSE + sum_i alpha_i^2 |dr/dd_i|^2, with alpha_i^2 = sigma_abs^2 + (sigma_rel d_i)^2 for physical
errors, or alpha_i = sigma_OT / n_i for errors in optical thickness. Cite Tikhonravov et al., SPIE 4829 (2003), Eq. 5.

**Plan.**
- A pure function `robust_cost(res, jac, alpha)` in `certus/physics/` (no TMM formula, only the residuals and the
  Jacobian already computed).
- A **"robust selection"** step: rank the envelope's designs, or the catalogue's, by R. This is the measured gain:
  it picks the right N.
- An optional **robust polish** with the stacked residual [r ; alpha J]. It gains under 0.5 % on the 50/50; keep it as
  an option, off by default.
- **Inputs:** `robust_sigma_ot_nm`, `robust_sigma_abs_nm` and `robust_sigma_rel` (all 0 = off).
- **UI:** the R(N) curve next to RMSE(N), and the recommended N.
- **Tests:**
  - the criterion equals E[MSE] by Monte Carlo within 5 % on a 10-layer design (the oracle drives the Monte Carlo);
  - with alpha = 0, the result is bit-identical to RMSE.

## Feature 3: spectral Monte Carlo of the RMSE

**DESIGN today.** It has a colour Monte Carlo worker only.

**Plan.**
- **Calculation:** a pure function in `certus/domain/` or `certus/physics/` that draws random errors (OT or absolute
  plus relative), with seeds fixed by (seed, draw, layer index) as C2 requires.
- **Outputs:** mean, CVaR95, and the yield for a corridor given by the user.
- **Worker:** a worker in `certus/workers/` calls it.
- **Test:** the oracle-computed RMSE of a perturbed design equals the kernel's.

## Candidates from 2026-10-28/29 (to measure before planning)

Measured in `envelope_v2/gradual.py`, not yet in DESIGN; each would be an option, off by default (C1):
- gradual evolution at imposed TOT, with Trubetskov 2020's step (one layer thickened to its next one-parameter
  minimum, `GRAD_GROW`): verdict of `campaign24.sh` pending;
- deep needle search (K candidates refined, best kept): better than classical from the same start;
- thin-layer cleaning after each convergence (`GRAD_CLEAN`): -25 to -30 % MF and about 20 fewer layers near a good
  basin, no gain from poor starts;
- one OpenBLAS thread per process with a process pool.

## Order, size and files

1. Feature 3 first: small, and it is the judge of the other two.
2. Feature 2 next (`physics`, `workers`, a few UI widgets).
3. Feature 1 last (the largest).

This is more than three files per feature, so each feature is approved and committed separately (C3). The defaults stay
off until `design_bench` measures them on the 50/50, the three-line filter and an AR, as the user ruled.
