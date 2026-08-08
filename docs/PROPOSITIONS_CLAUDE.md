# Recommendations for Physical Alignment: STRAT Simulation vs Real Machine

Document for Claude and the scientific team.

> [!IMPORTANT]
> This document has undergone multiple critical reviews. Each section includes
> an "Errata" block documenting errors found in previous drafts, so that Claude
> understands why the current formulation differs from what might seem intuitive.

---

## Context

The deposition simulation in `certus_strat_growth.py` (`simulate_growth_kernel`) is
remarkably faithful to the real optical monitoring process: Macleod auto-compensation,
POEM anchoring, photometric noise, and shutter noise are all modeled.

Four specific discrepancies between the real controller and the simulation kernel have
been identified. They are listed below in order of estimated physical impact.

---

## Gap 1 — A-priori index calibration uncertainty (δ_H, δ_L ≈ ±0.5%, constant per run)

### Physics (laboratory fact)
The refractive index of deposited materials is known to approximately **±0.5%**
(σ_calib = 0.005). This uncertainty is NOT random noise varying layer-to-layer. It is a
**global calibration bias constant for each material** throughout the entire run:
- All H-material layers (1, 3, 5, 7…) share the same offset δ_H.
- All L-material layers (2, 4, 6, 8…) share the same offset δ_L.

### Current kernel behavior
Indices n_H(λ) and n_L(λ) are treated as 100% deterministic (database nominal values).

### Physical impact
Because the offset is coherent across all 48 layers (not distributed randomly), it does
NOT average out. It induces a global spectral shift (≈ 2.5 nm at 500 nm) that the
optical monitoring (turning-point / POEM) attempts to auto-compensate by dynamically
adjusting the geometric thickness d_k of each layer during deposition. Not simulating
this means **overestimating** the nominal robustness of all strategies.

### Recommended implementation
Model the calibration uncertainty at the **run level** (drawn once per Monte Carlo run
in `_prepare_robustness_inputs`, NOT per layer):

$$n_H^{\text{run}}(\lambda) = n_H^{\text{nom}}(\lambda) \cdot (1 + \delta_H), \quad \delta_H \sim \mathcal{N}(0,\; 0.005^2)$$
$$n_L^{\text{run}}(\lambda) = n_L^{\text{nom}}(\lambda) \cdot (1 + \delta_L), \quad \delta_L \sim \mathcal{N}(0,\; 0.005^2)$$

δ_H and δ_L are drawn **once per run** and applied uniformly to all H and L layers
respectively. The perturbed indices must be injected into the kernel via the existing
`n_H`, `n_L` parameters — no kernel signature change is needed, only a pre-multiplication
at the call site in `certus_strat_batch.py`.

> [!WARNING]
> The parameter must be **inactive by default** (σ_calib = 0.0), and the inactive path
> must produce bit-identical results to the current code. See AGENTS.md rule §4.

---

## Gap 2 — Spatial sampling density on long blocks

### Architecture of the current scan grid (must be understood first)

The scan grid in `simulate_growth_kernel` has **two distinct regions**:
1. **Block history** (layers j0 … i_layer−1): `NPTS_PREV = 16` points per historical
   layer, scanning fraction f = 1/16 … 1 of each layer's real deposited thickness.
2. **Current layer scan**: `NPTS = 64` points spanning 0 … `D_SCAN × nominal_th`
   where `D_SCAN = 3.0`.

The 64 points are NOT spread over the entire block — they cover **3× the current
layer's nominal thickness only**.

### Errata from previous drafts
Previous versions of this document claimed the 64 points spanned the entire block.
That was **wrong**. Reading the code (lines 520–606 of `certus_strat_growth.py`):
- `n_hist = (i_layer - j0) * NPTS_PREV` → history grid
- `n_tot = n_hist + NPTS` → total grid = history + current layer
- `d_max = D_SCAN * nominal_th` → current layer scan range = 3× nominal thickness
- `step_s = d_max / (NPTS - 1)` → current layer step size

### Where the real concern lies
For a typical layer (nominal_th ≈ 100 nm), `d_max = 300 nm`, so
`step_s = 300/63 ≈ 4.76 nm`. This is coarse for locating turning points that might be
separated by 20–30 nm of growth.

However, the **block history** is where the real problem lurks: `NPTS_PREV = 16` points
per layer, scanning the full deposited thickness of that layer. For a 100 nm layer, that
is `100/16 ≈ 6.25 nm` per point. The code itself acknowledges this at line 506:
> "L'historique est donc echantillonné quatre fois plus grossièrement que la couche
> courante"

### Recommended implementation
Make both `NPTS` and `NPTS_PREV` adaptive based on the physical thickness they cover:

```
NPTS = max(64, ceil(D_SCAN * nominal_th))        # ≤ 1 nm step on current layer
NPTS_PREV = max(16, ceil(d_real_j))              # ≤ 1 nm step on each history layer
```

This guarantees Δd ≤ 1.0 nm everywhere. For a 100 nm layer: `NPTS = max(64, 300) = 300`
and `NPTS_PREV = max(16, 100) = 100`. Total grid for a 4-layer history block:
4×100 + 300 = 700 points, versus the current 4×16 + 64 = 128. Each TMM evaluation at
one grid point is a handful of complex multiplications — the cost increase is real but
bounded (sub-millisecond per layer per run for numba-compiled code).

> [!IMPORTANT]
> This changes the noise sampling alignment (see the common random numbers
> contract at lines 481–510). The seeded noise function `_seeded_noise_sample` uses
> `(group=j, elem=k)` indices. If NPTS_PREV or NPTS change, the elem index changes,
> which means **the exact noise realization changes**. This is acceptable (same
> distribution, different draw) but must be verified by running the benchmark:
> crash rate must not jump by more than the expected statistical fluctuation.

---

## Gap 3 — Signal scale for absolute thresholds (T_front vs T_measured)

### Physics
The kernel computes T_front: power transmitted from the incident medium through all
coating layers into the substrate. The TMM exit medium is `n_Sub` (line 618:
`dr = r00 + n_Sub * r01 + r10 + n_Sub * r11`), and the transmission formula
`T = 4 * n_Sub.real / |dr|²` gives the power entering the substrate.

What the real spectrophotometer measures includes **one additional interface**:
the substrate back surface (substrate → air). This Fresnel loss is:

$$T_{\text{back}} = \frac{4\,n_{\text{sub}}}{(n_{\text{sub}} + 1)^2}$$

For BK7 (n_sub = 1.52): T_back = 6.08 / 6.3504 ≈ 0.9574. So T_front is about
**4.4% larger** than T_measured, not 8% as stated in previous drafts.

### Errata from previous drafts
Previous versions claimed "≈ 8% plus grand". This double-counted the front substrate
surface, which is already included in the TMM calculation via the exit medium n_Sub.
Only the back surface is missing.

### Impact assessment
The affected thresholds are:
- `SWING_MIN = 0.04`: an amplitude of 0.042 in T_front corresponds to 0.040 in
  T_measured. The error is 0.002 in absolute terms — marginal.
- `tp_hysteresis`: similarly scaled down by ~4.3%.

### Recommendation
This gap is **minor**. The correction factor is small and the affected thresholds are
already empirically calibrated. If implemented, multiply the swing amplitude by
T_back before comparing to `SWING_MIN`. But this should be the **lowest priority**
of the four gaps.

---

## Gap 4 — Temporal sampling quantization (shutter overshoot)

### Physics
The real controller samples at fixed time intervals (Δt ≈ 100 ms). When the stop
condition is met between two samples, the shutter fires at the **next** sample
(causal: never early, always late). This produces a systematic positive overshoot
of at most Δd_sample = v × Δt ≈ 0.10 nm.

### Current kernel behavior
The kernel finds the exact continuous root d_stop via quadratic interpolation.

### Errata from previous drafts
A first draft proposed U(−0.05, +0.05) — a centered distribution. This violated
causality: the shutter cannot fire before the threshold is crossed. The correct
distribution is U(0, Δd_sample), strictly positive.

### Risk of double-counting
The existing parameter `noise_val_precalc` (line 748) already models shutter/trigger
noise by perturbing the target level: `target_T_noisy = target_level + noise_val_precalc`.
This is a **photometric** noise (perturbation in T-space), whereas quantization
overshoot is a **spatial** noise (perturbation in d-space). They are physically
independent effects:
- `noise_val_precalc` models uncertainty in **what level to target** (noisy reading).
- Quantization overshoot models uncertainty in **when the shutter fires** after the
  level is correctly detected.

So there is no double-counting. However, the quantization overshoot (±0.05 nm) is
**small compared to typical shutter noise** (σ_d ≈ 0.2–0.5 nm from `noise_val_precalc`).

### Recommendation
This gap is **real but small**. It should be implemented only after Gap 1 and Gap 2,
and its effect measured (Piège 1: if crash rate doesn't change with Δd_sample,
the measurement is an artifact).

---

## Summary of priorities

| Priority | Gap | Impact | Effort |
|----------|-----|--------|--------|
| **1** | Index calibration uncertainty (δ_H, δ_L) | High — changes strategy ranking | Low — pre-multiply at call site |
| **2** | Adaptive grid density (NPTS, NPTS_PREV) | Medium — affects TP detection on long blocks | Medium — kernel constant change + noise alignment |
| **3** | Quantization overshoot U(0, 0.10 nm) | Low — dominated by existing shutter noise | Low — add uniform draw |
| **4** | Back-surface scale on SWING_MIN | Negligible — 0.002 absolute error | Trivial |
