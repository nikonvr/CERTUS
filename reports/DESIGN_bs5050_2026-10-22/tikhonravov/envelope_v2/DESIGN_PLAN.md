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

## Status and decision of 2026-10-29

Features 2 and 3 are in DESIGN (`7f849f42`). 👤 decided on 2026-10-29 that DESIGN will integrate all the tools of
this study, so that the article can say they are in the software: feature 1 (envelope), the gradual evolution below,
the alignment distance (`design_distance.py`) and the barrier (`barrier.py`). Defaults follow 👤's rule of 2026-10-27:
a gain measured in DESIGN itself is switched on by default, the switch kept to restore the old path, and the commit says
that C1 changes on purpose.

## Candidates from 2026-10-28/29 (to measure before planning)

Measured in `envelope_v2/gradual.py`, not yet in DESIGN:
- gradual evolution at imposed TOT, with Trubetskov 2020's step (one layer thickened to its next one-parameter
  minimum, `GRAD_GROW`) with cleaning at 2 nm: 0.0193 at 14 480 nm from the bare substrate (old step ≈ 0.054,
  Trubetskov 0.0128); the TOT must stay imposed during refinements (`GRAD_FREE`: 2-3 times more layers, worse MF);
- deep needle search (K candidates refined, best kept): better than classical from the same start;
- thin-layer cleaning after each convergence (`GRAD_CLEAN`): -25 to -30 % MF and about 20 fewer layers near a good
  basin, no gain from poor starts;
- one OpenBLAS thread per process with a process pool.

## Compute time: what the study's gains mean for DESIGN (read 2026-10-29, not measured)

- **One OpenBLAS thread per process** (×2.5 on a search step in the study) came from `scipy.optimize.least_squares`
  (trf: QR/SVD in LAPACK) running in 7 processes. DESIGN's hot loops are Numba kernels (cost and gradient, Gauss-Newton
  with its own Cholesky, cached needle scan); its memetic polish is L-BFGS-B (BLAS level 1 only). Expected direct gain:
  small. To measure: oversubscription, since `certus_core` sets `OPENBLAS_NUM_THREADS` and the Numba OpenMP threads both
  to the core count in one process.
- **Parallelism over candidates** (the study's real gain: 7 single-threaded processes on independent polishes): DESIGN
  polishes memetic children one by one and parallelizes inside each kernel call, over wavelengths. On small problems
  (50/50: 1601 wavelengths, 34 layers) that inner parallelism is likely inefficient. Polishing a batch of children in
  parallel threads (the kernels are `nogil`) could gain a factor of several; it changes the order of replacements,
  hence the trajectory: a switch, measured in `design_bench`, default per 👤's rule.
- **Exact P-function from one Jacobian call** (`gradual.py`): DESIGN's cached needle scan is already O(W) per position;
  the exact P-function removes the probe thickness (accuracy), with no clear time gain.
- **Early termination of refinements** (Trubetskov 2020, Sec. 3): DESIGN already has a screening polish
  (`screen_maxiter`); comparing each refinement with stored trajectories could cut deep-search candidates early.
- Measured 2026-10-30 01:26, machine otherwise idle (`design_speed_check.py 300 7`, `design_speed_check.out`):
  `compute_gradient_all_layers_analytic` on the 50/50, one caller with 8 Numba threads 193 calls/s, one thread 120/s,
  7 callers with one thread each 313/s, 7 callers with 8 threads 319/s. Polishing candidates in parallel would give
  DESIGN about ×1.6 on this call; inner parallelism alone uses the 8 cores at ≈ 20 %.

## Order, size and files

1. Feature 3, then feature 2: done (`7f849f42`).
2. Gradual evolution at imposed TOT (deep, Trubetskov's step, thin-layer cleaning at 2 nm): verdict given 2026-10-29
   (best path measured), next to port.
3. Feature 1 (envelope search with the monotonicity certificate).
4. Distance and barrier: coded 2026-10-29 (`certus/core/certus_design_landscape.py`, `BarrierWorker`, "Compare" tab in
   `certus/ui/certus_design_ui_compare.py`; tests `tests/unit/test_design_landscape.py`, `tests/ui/test_design_compare.py`);
   nothing on the optimization path. Committed `02b25ed7` (2026-10-30): C1 holds; the study's barrier recomputed
   with the module to every printed digit (string 29.5694, straight 35.6288); full unit suite not rerun after the
   lambda fix (targeted tests 19 passed).

This is more than three files per feature, so each feature is approved and committed separately (C3). A default is
switched on only after `design_bench` measures it better on the 50/50, the three-line filter and the hot mirror.
