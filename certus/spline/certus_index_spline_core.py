#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CERTUS-INDEX-SPLINE  Global fit of n(lambda), k(lambda) as piecewise-linear in sigma=1/lambda (ln k at nodes).

Standalone: no imports from CERTUS_INDEX nor certus_swanepool. PGlobal from certus_physics.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from functools import lru_cache
from typing import Any, Callable

import numpy as np
import pandas as pd

from certus.core.certus_array_utils import as_float64_1d, sorted_float64, interp_sorted

from certus.core.certus_core import (
    K_MAX_LIMIT,
    N_MAX_LIMIT,
    N_MIN_LIMIT,
    SUBSTRATES,
    SUBSTRATE_LIST,
    create_module_environment,
)
from certus_physics import (
    calculate_RT_vectorized_real,
    clip_to_bounds,
)
from certus.utils.certus_index_utils import (
    log_structured_json_event,
    DataType,
)


# Bootstrap
_env = create_module_environment(__file__, "CERTUS_INDEX_SPLINE")
_SCRIPT_DIR = _env["script_dir"]
logger = logging.getLogger("CERTUS_INDEX_SPLINE")

# Avoid repeating the same INFO line on every call (canonical_spline_sigma_knots is highly solicited).
_CANONICAL_IR_MESH_INFO_SEEN: set[tuple[float, int, int]] = set()

_QS_SPLINE_ORG = "CERTUS"
_QS_SPLINE_APP = "INDEX_SPLINE"
_QS_LAST_SPECTRUM = "last_spectrum_path"

# Exclude k < 1e-9 (L = ln k >= ln(1e-9)); knot bounds, warm start, post-PWL clipping.
K_MIN_PHYS: float = 1e-9
L_LNK_MIN_PHYS: float = float(np.log(K_MIN_PHYS))

# k floor consistent with SplineOptConfig.k_clip_lo (default 1e-5).
K_FLOOR_DEFAULT: float = 1e-5

# Minimum relative separation between consecutive sigma nodes (log-softmax codec).
SIGMA_KNOTS_MIN_SEP_REL: float = 0.005


# Standard numerical-fault exceptions caught at boundaries of optimisation /
# diagnostic blocks (degraded-but-recoverable). Centralised so the safety net
# stays consistent across the spline pipeline / corridors / smart-init.
NUMERICAL_FAULT_EXCEPTIONS: tuple[type[BaseException], ...] = (
    ValueError,
    TypeError,
    RuntimeError,
    AttributeError,
    KeyError,
    IndexError,
    FileNotFoundError,
)


def _enforce_sigma_min_sep(sk: np.ndarray, s_lo: float, s_hi: float) -> np.ndarray:
    """Forward sweep enforcing SIGMA_KNOTS_MIN_SEP_REL between consecutive knots.

    Same eps_s as ``sigma_knots_decode`` so that encode→decode is a no-op on
    a mesh that already satisfies the constraint.
    """
    sk = sorted_float64(sk)
    if sk.size < 2:
        return sk
    eps_s = max(1e-10, SIGMA_KNOTS_MIN_SEP_REL * max(s_hi - s_lo, 1e-12))
    for i in range(1, sk.size):
        sk[i] = max(sk[i], sk[i - 1] + eps_s)
    # Preserve exact upper boundary.
    sk[-1] = max(s_hi, sk[-1])
    return sk


def enforce_k_floor_on_nodes(
    sigma_knots: np.ndarray,
    L_nodes: np.ndarray,
    k_floor: float = K_FLOOR_DEFAULT,
    *,
    eps_rel: float = 0.05,
    allow_insert: bool = True,
) -> tuple[np.ndarray, np.ndarray, bool]:
    """Enforce k >= k_floor on L = ln(k) nodes of a PWL spline.

    1. Clamp: L_j = max(L_j, ln(k_floor)) for all j.

    2. Flat: if both nodes of a segment are <= k_floor*(1+eps),

               set them exactly to ln(k_floor) (removes micro-slopes).

    3. Insert: if a segment crosses the threshold (one node above, one below

               *before* clamp), insert an intermediate knot sigma* at intersection

               point to keep the sub-threshold side perfectly flat.

    Returns (sigma_knots_new, L_nodes_new, modified).

    ``sigma_knots_new`` may be larger than input if nodes are inserted

    (disabled if ``allow_insert=False``, e.g. intermediate packing without resizing x).

    """

    sk = as_float64_1d(sigma_knots, copy=True)

    LL = as_float64_1d(L_nodes, copy=True)

    if sk.size < 2 or LL.size != sk.size:
        return sk, LL, False

    L_floor = float(np.log(max(k_floor, 1e-30)))

    L_near = float(np.log(max(k_floor * (1.0 + eps_rel), 1e-30)))

    modified = False

    # --- Step 3: insertion of intermediate nodes (BEFORE clamp) ---

    if allow_insert:
        inserts: list[tuple[float, float]] = []  # (sigma_star, L_floor)

        for j in range(sk.size - 1):
            L_a, L_b = float(LL[j]), float(LL[j + 1])

            if (L_a < L_floor and L_b > L_near) or (L_b < L_floor and L_a > L_near):
                s_a, s_b = float(sk[j]), float(sk[j + 1])

                dL = L_b - L_a

                if abs(dL) > 1e-30:
                    t = (L_floor - L_a) / dL

                    t = float(np.clip(t, 0.01, 0.99))

                    sigma_star = s_a + t * (s_b - s_a)

                    inserts.append((sigma_star, L_floor))

        if inserts:
            for s_ins, L_ins in inserts:
                sk = np.append(sk, s_ins)

                LL = np.append(LL, L_ins)

            order = np.argsort(sk)

            sk = sk[order]

            LL = LL[order]

            modified = True

    # --- Step 1: individual clamp ---

    below = LL < L_floor

    if np.any(below):
        LL[below] = L_floor

        modified = True

    # --- Step 2: flattening of segments close to the floor (vectorized) ---
    mask = (LL[:-1] <= L_near) & (LL[1:] <= L_near)
    if np.any(mask):
        set_floor = np.zeros_like(LL, dtype=bool)
        set_floor[:-1] |= mask
        set_floor[1:] |= mask
        
        to_modify = set_floor & (LL != L_floor)
        if np.any(to_modify):
            LL[to_modify] = L_floor
            modified = True

    return sk, LL, modified


# n monotonicity in sigma=1/lambda (nm): n increases with sigma, therefore decreases with lambda.


# lambda band by default (GUI): from short spectral edge to min(lambda_max, cap) nm.


N_MONO_BAND_HI_CAP_NM: float = 2000.0


N_MONO_XI_BOUNDS: tuple[float, float] = (-14.0, 14.0)


def default_n_mono_band_nm_from_spectrum(
    lam_nm: np.ndarray,
    *,
    hi_cap_nm: float = N_MONO_BAND_HI_CAP_NM,
) -> tuple[float, float] | None:
    """Band [lambda_min, min(lambda_max, hi_cap)] for ξ reparameterization (n non-decreasing in sigma on segments overlapping the band).

    Returns ``None`` if spectrum is empty or if min(lambda_max, hi_cap) <= lambda_min.

    """

    lam = np.asarray(lam_nm, dtype=np.float64).ravel()

    lam = lam[np.isfinite(lam)]

    if lam.size == 0:
        return None

    lo = float(np.min(lam))

    hi = min(float(np.max(lam)), float(hi_cap_nm))

    if hi <= lo + 1e-9:
        return None

    return (lo, hi)


def _mono_sigmoid(z: float | np.ndarray) -> np.ndarray:

    z = np.asarray(z, dtype=np.float64)

    return 1.0 / (1.0 + np.exp(-np.clip(z, -60.0, 60.0)))


def _mono_logit(p: float) -> float:

    p = float(np.clip(p, 1e-9, 1.0 - 1e-9))

    return float(np.log(p / (1.0 - p)))


def n_mono_segment_flags(sigma_knots: np.ndarray, lam_lo_nm: float, lam_hi_nm: float) -> np.ndarray:
    """True on segment [sigma_j,sigma_{j+1}] when the corresponding lambda interval intersects [lam_lo, lam_hi] (nm)."""

    sk = np.asarray(sigma_knots, dtype=np.float64).ravel()

    K = int(sk.size)

    if K < 2:
        return np.zeros(0, dtype=bool)

    lam_a = float(min(lam_lo_nm, lam_hi_nm))

    lam_b = float(max(lam_lo_nm, lam_hi_nm))

    if lam_b <= 0.0:
        return np.zeros(max(0, K - 1), dtype=bool)

    lam_a = max(0.0, lam_a)

    s0, s1 = sk[:-1], sk[1:]
    slo, shi = np.minimum(s0, s1), np.maximum(s0, s1)
    
    lam_max_seg = 1.0 / np.maximum(slo, 1e-18)
    lam_min_seg = 1.0 / np.maximum(shi, 1e-18)
    
    true_min = np.minimum(lam_min_seg, lam_max_seg)
    true_max = np.maximum(lam_min_seg, lam_max_seg)
    
    out = (true_max >= lam_a) & (true_min <= lam_b)
    return out


def n_lambda_rising_with_wavelength_penalty(
    cfg: "SplineOptConfig",
    sigma_knots_n: np.ndarray,
    n_nodes: np.ndarray,
) -> float:
    """

    Penalty: n increasing with lambda (typical "impossible" dispersion) on PWL

    segments whose lambda interval overlaps ``n_lambda_rising_penalty_band_nm``.

    On a segment sigma_j->sigma_{j+1} (sigma increasing, lambda decreasing along the index), if n_j > n_{j+1},

    then n increases when lambda increases along the segment; we accumulate

    relu(n_j - n_{j+1} - slack)^2 if ``n_lambda_rising_penalty_slack`` > 0.

    """

    w = float(getattr(cfg, "n_lambda_rising_penalty_weight", 0.0) or 0.0)

    band = getattr(cfg, "n_lambda_rising_penalty_band_nm", None)

    slack = float(getattr(cfg, "n_lambda_rising_penalty_slack", 0.0) or 0.0)

    if slack < 0.0:
        slack = 0.0

    if w <= 0.0 or band is None:
        return 0.0

    lam_lo = float(min(float(band[0]), float(band[1])))

    lam_hi = float(max(float(band[0]), float(band[1])))

    sk = np.asarray(sigma_knots_n, dtype=np.float64).ravel()

    nn = np.asarray(n_nodes, dtype=np.float64).ravel()

    if sk.size < 2 or nn.size != sk.size:
        return 0.0

    eps = 1e-12
    s0 = sk[:-1]
    s1 = sk[1:]
    valid = s1 > (s0 + eps)
    if not np.any(valid):
        return 0.0

    lam_min_seg = 1.0 / np.maximum(s1, 1e-30)
    lam_max_seg = 1.0 / np.maximum(s0, 1e-30)
    seg_lo = np.minimum(lam_min_seg, lam_max_seg)
    seg_hi = np.maximum(lam_min_seg, lam_max_seg)

    in_band = (seg_hi >= lam_lo) & (seg_lo <= lam_hi) & valid
    if not np.any(in_band):
        return 0.0

    viol = nn[:-1] - nn[1:]
    ve = np.maximum(viol - slack, 0.0)
    active = in_band & (viol > eps) & (ve > 0.0)
    if not np.any(active):
        return 0.0

    acc = float(np.dot(ve[active], ve[active]))
    return w * acc


def n_mono_knot_chains(seg_mono: np.ndarray) -> list[tuple[int, int]]:
    """Partition knot indices 0..K-1 into chains where n is non-decreasing along sigma."""

    K = int(seg_mono.size) + 1

    chains: list[tuple[int, int]] = []

    start = 0

    for j in range(len(seg_mono)):
        if not seg_mono[j]:
            chains.append((start, j))

            start = j + 1

    chains.append((start, K - 1))

    return chains


def decode_xi_n_to_physical_n(
    xi_n: np.ndarray,
    chains: list[tuple[int, int]],
    n_min: float,
    n_max: float,
) -> np.ndarray:
    """Map  to physical n: within each chain, n_{i+1} = n_i + (n_max-n_i)*sigmoid(_{i+1})."""

    xi_n = np.asarray(xi_n, dtype=np.float64).ravel()

    K = int(xi_n.size)

    n_out = np.zeros(K, dtype=np.float64)

    lo, hi = float(n_min), float(n_max)
    span0 = hi - lo
    
    # Pre-compute all sigmoids to avoid function call overhead in loop
    sigmoids = _mono_sigmoid(xi_n)

    for a, b in chains:
        n_out[a] = lo + span0 * float(sigmoids[a])
        prev = float(n_out[a])

        for idx in range(a + 1, b + 1):
            span = hi - prev

            if span < 1e-14:
                n_out[idx] = prev
            else:
                prev = prev + span * float(sigmoids[idx])
                n_out[idx] = prev

    np.clip(n_out, lo, hi, out=n_out)

    return n_out


def project_n_pwl_monotone_chains(n: np.ndarray, chains: list[tuple[int, int]]) -> np.ndarray:

    n = np.asarray(n, dtype=np.float64).ravel().copy()

    for a, b in chains:
        for idx in range(a + 1, b + 1):
            n[idx] = max(n[idx], n[idx - 1])

    return n


def encode_physical_n_to_xi_n(
    n_phys: np.ndarray,
    chains: list[tuple[int, int]],
    n_min: float,
    n_max: float,
) -> np.ndarray:
    """Apply per-chain isotonic projection, then inverse sigmoid reparameterization."""

    n_phys = project_n_pwl_monotone_chains(np.clip(np.asarray(n_phys, dtype=np.float64).ravel(), n_min, n_max), chains)

    K = int(n_phys.size)

    xi = np.zeros(K, dtype=np.float64)

    lo, hi = float(n_min), float(n_max)

    span0 = hi - lo

    for a, b in chains:
        ra = (float(n_phys[a]) - lo) / max(span0, 1e-30)

        xi[a] = _mono_logit(float(np.clip(ra, 1e-6, 1.0 - 1e-6)))

        prev = float(n_phys[a])

        for idx in range(a + 1, b + 1):
            span = hi - prev

            if span < 1e-14:
                xi[idx] = float(N_MONO_XI_BOUNDS[0])

            else:
                r = (float(n_phys[idx]) - prev) / span

                r = float(np.clip(r, 1e-8, 1.0 - 1e-8))

                xi[idx] = _mono_logit(r)

            prev = float(n_phys[idx])

    return xi


def x_slice_n_to_physical_nodes(
    x_n: np.ndarray,
    sigma_knots: np.ndarray,
    n_mono_band_nm: tuple[float, float] | None,
) -> np.ndarray:
    """Decode x slice (physical n or ξ) to physical n at sigma knots."""

    if n_mono_band_nm is None:
        return np.asarray(x_n, dtype=np.float64).ravel().copy()

    lam_lo, lam_hi = float(n_mono_band_nm[0]), float(n_mono_band_nm[1])

    seg = n_mono_segment_flags(sigma_knots, lam_lo, lam_hi)

    chains = n_mono_knot_chains(seg)

    return decode_xi_n_to_physical_n(x_n, chains, float(N_MIN_LIMIT), float(N_MAX_LIMIT))


def physical_nodes_to_x_slice_n(
    n_phys: np.ndarray,
    sigma_knots: np.ndarray,
    n_mono_band_nm: tuple[float, float] | None,
) -> np.ndarray:
    """Encode physical n nodes to x slice (physical n or ξ) for optimization bounds."""

    if n_mono_band_nm is None:
        return np.clip(
            np.asarray(n_phys, dtype=np.float64).ravel(),
            float(N_MIN_LIMIT),
            float(N_MAX_LIMIT),
        )

    lam_lo, lam_hi = float(n_mono_band_nm[0]), float(n_mono_band_nm[1])

    seg = n_mono_segment_flags(sigma_knots, lam_lo, lam_hi)

    chains = n_mono_knot_chains(seg)

    return encode_physical_n_to_xi_n(
        np.asarray(n_phys, dtype=np.float64).ravel(),
        chains,
        float(N_MIN_LIMIT),
        float(N_MAX_LIMIT),
    )


def _reflectance_absolute_backside_from_nk(
    lam_nm: np.ndarray,
    n_l: np.ndarray,
    k_l: np.ndarray,
    d_nm: float,
    n_sub: np.ndarray,
) -> np.ndarray:
    """R(lambda) consistent with ``SplinePWLObjective``: TMM single layer, incoherent backside."""

    lam_nm = np.asarray(lam_nm, dtype=np.float64).ravel()

    n_l = np.asarray(n_l, dtype=np.float64).ravel()

    k_l = np.asarray(k_l, dtype=np.float64).ravel()

    n_sub = np.asarray(n_sub, dtype=np.float64).ravel()

    n_pts = int(lam_nm.size)

    _thick = np.empty(1, dtype=np.float64)
    _thick[0] = float(d_nm)

    n_layers_all = (n_l - 1j * k_l).reshape(n_pts, 1)

    r_th, _ = calculate_RT_vectorized_real(_thick, n_layers_all, n_sub, lam_nm, with_backside=True)

    return np.asarray(r_th, dtype=np.float64).ravel()


# Adaptive mesh + needle: mandatory local descent (seed / after probe)




# Automation / perf presets (overridden by explicit fields if provided)


SPLINE_PERF_PRESETS: dict[str, dict[str, float | int | None]] = {
    "standard": {},
    "fast": {
        "pglobal_max_iter": 18,
        "pglobal_max_feval": 84000,
        "pglobal_max_time": 240.0,
        "polish_maxfun": 10000,
        "pglobal_local_search_budget": 12000,
    },
    "quality": {
        "pglobal_max_iter": 55,
        "pglobal_max_feval": 280000,
        "pglobal_max_time": 720.0,
        "polish_maxfun": 28000,
        "pglobal_local_search_budget": 104000,
    },
    "max": {
        "pglobal_max_iter": 88,
        "pglobal_max_feval": 760000,
        "pglobal_max_time": 3200.0,
        "polish_maxfun": 64000,
        "pglobal_local_search_budget": 240000,
    },
}


def gui_perf_preset_only(preset_name: str) -> dict[str, float | int]:
    """Subset for GUI: no PGlobal iterations (defined by dedicated spinbox)."""

    d = dict(SPLINE_PERF_PRESETS.get(preset_name, {}))

    d.pop("pglobal_max_iter", None)

    return d

from certus.spline.certus_index_spline_io import export_spline_result_jsonable


# --- sigma PWL Model ----------------------------------------------------------------
#
# Physical reminder: between two consecutive sigma nodes, n(sigma) and ln k(sigma)
# are linear in sigma = 1/lambda.  The number of segments controls the resolution at
# which n and k can be curved as a function of wavelength; far IR (high lambda, small
# sigma) often has only one wide segment with the 12-point "log sigma" grid — hence the
# optional extension below.
#
# INDEX SPLINE: "canonical" mesh used by the entire worker (SOL2, SOL3, exports).
#   • Always 12 nodes as a first approximation: uniform distribution in log(sigma),
#     equivalent to a geometric progression of lambda between lambda_min and lambda_max
#     (not a constant step in nm).
#   • If the spectrum extends far into the IR (lambda_max > threshold), exactly 2 more
#     nodes are added to better capture n/k between ~4000 nm and the last wavelength.

SPLINE_PWL_K_NODES: int = 12
SPLINE_PWL_N_SEG: int = SPLINE_PWL_K_NODES - 1

# Threshold (nm): if max(lambda) <= this value, the mesh stays at K=12 (no regression
# for classic VIS / near-IR spectra).
SPLINE_EXTRA_IR_KNOTS_LAM_MAX_THRESHOLD_NM: float = 4000.0


def min_relative_lambda_spacing_ratio(
    sk: np.ndarray,
    lam_min_nm: float,
    lam_max_nm: float,
) -> float:
    """min_i (lambda_{i+1}-lambda_i) / lambdā with sorted lambda (nm), lambdā = (file lambda_min + file lambda_max) / 2."""

    sk = np.sort(np.asarray(sk, dtype=np.float64).ravel())

    if int(sk.size) < 2:
        return float("inf")

    lam = 1.0 / np.maximum(sk, 1e-30)

    lam_sorted = np.sort(lam)

    gaps = np.diff(lam_sorted)

    lo = float(min(lam_min_nm, lam_max_nm))

    hi = float(max(lam_min_nm, lam_max_nm))

    lam_mean = 0.5 * (lo + hi)

    if lam_mean <= 1e-30 or gaps.size == 0:
        return float("inf")

    return float(np.min(gaps) / lam_mean)


def build_sigma_knots_log_uniform(lam_min_nm: float, lam_max_nm: float, n_seg: int) -> np.ndarray:
    """K = n_seg+1 sigma nodes, uniform log(sigma) distribution on [1/lambda_max, 1/lambda_min] (same logic as K=12)."""

    lo = float(min(lam_min_nm, lam_max_nm))

    hi = float(max(lam_min_nm, lam_max_nm))

    sig_min = 1.0 / max(hi, 1e-9)

    sig_max = 1.0 / max(lo, 1e-9)

    k = max(2, int(n_seg) + 1)

    return np.exp(np.linspace(np.log(sig_min), np.log(sig_max), k)).astype(np.float64)


@lru_cache(maxsize=128)
def _canonical_sigma_knots_cached(lam_min_nm: float, lam_max_nm: float, min_delta_lambda_over_lambda_mean: float | None) -> tuple[float, ...]:
    """Cache the canonical mesh key to avoid rebuilding identical grids repeatedly."""

    kw = {}
    if min_delta_lambda_over_lambda_mean is not None:
        kw["min_delta_lambda_over_lambda_mean"] = float(min_delta_lambda_over_lambda_mean)
    return tuple(canonical_spline_sigma_knots(lam_min_nm, lam_max_nm, **kw).tolist())


def _canonical_knots_min_lambda_kw(cfg: SplineOptConfig | None) -> dict[str, float]:
    """Optional arguments for ``canonical_spline_sigma_knots`` from config."""

    if cfg is None:
        return {}

    v = getattr(cfg, "spline_min_delta_lambda_over_lambda_mean", 0.02)

    try:
        fv = float(v)

    except (TypeError, ValueError):
        return {}

    if fv <= 0.0 or not np.isfinite(fv):
        return {}

    return {"min_delta_lambda_over_lambda_mean": fv}


def _insert_two_equi_lambda_in_last_sigma_segment(sk_base: np.ndarray) -> np.ndarray:
    """Refines only the last lambda interval (long lambda side) by two equidistant lambda nodes.

    sigma table convention throughout the module: ``sk`` is sorted by increasing sigma.

      • sk[0] = smallest sigma = 1 / lambda_max  ("long IR" end, last wavelength of the fit).

      • sk[1] = next sigma = 1 / lambda_pen      where lambda_pen is the **2nd largest** lambda among base mesh nodes.

    Other nodes (UV -> near IR) are untouched: only two sigma abscissae strictly

    between sk[0] and sk[1] are inserted, at positions lambda = lambda_pen + (j/3)(lambda_max - lambda_pen)

    for j ∈ {1, 2}, then sigma_j = 1/lambda_j. This yields three PWL sub-segments in lambda

    on the often "difficult" zone (reststrahlen, atypical index behaviors beyond ~4 µm).

    Returns: new sorted sigma vector, size len(sk_base) + 2 on numerical success.

    """

    sk = np.sort(np.asarray(sk_base, dtype=np.float64).ravel())

    if int(sk.size) < 2:
        return sk.copy()

    # sigma[0] < sigma[1] < … : recall, lambda decreases when sigma index increases.

    s0, s1 = float(sk[0]), float(sk[1])

    lam_max = 1.0 / max(s0, 1e-30)  # red edge of the spectrum (last lambda point)

    lam_pen = float(1.0 / max(s1, 1e-30))  # penultimate node in increasing lambda order

    if not (lam_pen < lam_max):
        # Pathological case (sigma duplicates or degenerate mesh): do not modify.

        return sk.copy()

    dlam = lam_max - lam_pen

    # Thirds in lambda (not sigma): uniform distribution on [lambda_pen, lambda_max].

    lam_a = lam_pen + dlam / 3.0

    lam_b = lam_pen + 2.0 * dlam / 3.0

    sa = 1.0 / max(lam_a, 1e-30)

    sb = 1.0 / max(lam_b, 1e-30)

    merged = np.unique(np.sort(np.append(sk, [sa, sb])))

    if int(merged.size) != int(sk.size) + 2:
        # Floating collisions (very rare): slight relative offset to force uniqueness.

        span = max(s1 - s0, 1e-18)

        eps = max(1e-14, 1e-9 * span)

        merged = np.unique(np.sort(np.append(sk, [sa + eps, sb - eps])))

    return merged.astype(np.float64, copy=False)


def canonical_spline_sigma_knots(
    lam_min_nm: float,
    lam_max_nm: float,
    *,
    min_delta_lambda_over_lambda_mean: float | None = None,
) -> np.ndarray:
    """Constructs the sigma mesh used by the INDEX SPLINE optimizer for this spectrum.

    Steps:

      1) Base grid K = n_seg+1 (nominal n_seg=11 -> K=12), uniform log sigma, unless

         ``min_delta_lambda_over_lambda_mean`` > 0: n_seg is reduced until

         min(Deltalambda)/lambdā >= this threshold (lambdā = arithmetic average of file lambda_min, lambda_max).

      2) If max(lambda) <= ``SPLINE_EXTRA_IR_KNOTS_LAM_MAX_THRESHOLD_NM`` -> no IR extension.

      3) Otherwise -> insertion of 2 nodes on the last lambda segment (K=14) if the Deltalambda/lambdā

         constraint remains satisfied; otherwise extension omitted.

    The entire chain (``make_bounds_and_x0``, Smart Init "Continue", worker) must rely on **this**

    function so that sizes of x0, bounds, and ``sigma_knots`` remain consistent.

    """

    lo = float(min(float(lam_min_nm), float(lam_max_nm)))

    hi = float(max(float(lam_min_nm), float(lam_max_nm)))

    lam_mean = 0.5 * (lo + hi)

    sig_lo = 1.0 / max(hi, 1e-9)

    sig_hi = 1.0 / max(lo, 1e-9)

    ratio_req: float | None = None

    if min_delta_lambda_over_lambda_mean is not None:
        r = float(min_delta_lambda_over_lambda_mean)

        if r > 0.0 and np.isfinite(r) and lam_mean > 1e-30:
            ratio_req = r

    if ratio_req is None:
        sk12 = build_sigma_knots(lam_min_nm, lam_max_nm, SPLINE_PWL_N_SEG)

    else:
        sk12 = None

        for n_seg_try in range(int(SPLINE_PWL_N_SEG), 0, -1):
            cand = build_sigma_knots_log_uniform(lam_min_nm, lam_max_nm, n_seg_try)

            if min_relative_lambda_spacing_ratio(cand, lo, hi) >= ratio_req - 1e-15:
                sk12 = cand

                if n_seg_try < int(SPLINE_PWL_N_SEG):
                    logger.info(
                        "INDEX_SPLINE: sigma mesh reduced to n_seg=%d (K=%d) for min(Deltalambda)/lambdā >= %.5g "
                        "(lambdā=%.1f nm).",
                        n_seg_try,
                        int(cand.size),
                        ratio_req,
                        lam_mean,
                    )

                break

        if sk12 is None:
            sk12 = build_sigma_knots_log_uniform(lam_min_nm, lam_max_nm, 1)

            logger.warning(
                "INDEX_SPLINE: repli maillage K=2 - min(Deltalambda)/lambdā pourrait rester < %.5g.",
                ratio_req,
            )

    if hi <= SPLINE_EXTRA_IR_KNOTS_LAM_MAX_THRESHOLD_NM:
        return _enforce_sigma_min_sep(sk12, sig_lo, sig_hi)

    out = _insert_two_equi_lambda_in_last_sigma_segment(sk12)

    if int(out.size) != int(sk12.size) + 2:
        logger.warning(
            "INDEX_SPLINE: IR extension (2 equi-lambda knots) ignored - degeneracy; K=%d.",
            int(sk12.size),
        )

        return _enforce_sigma_min_sep(sk12, sig_lo, sig_hi)

    out = _enforce_sigma_min_sep(out, sig_lo, sig_hi)

    if ratio_req is not None and min_relative_lambda_spacing_ratio(out, lo, hi) < ratio_req - 1e-12:
        logger.info(
            "INDEX_SPLINE: extension IR (2 nœuds lambda) omise - violerait min(Deltalambda)/lambdā >= %.5g.",
            ratio_req,
        )

        return _enforce_sigma_min_sep(sk12, sig_lo, sig_hi)

    _mesh_sig = (
        round(float(hi), 1),
        int(out.size),
        int(out.size - sk12.size),
    )

    if _mesh_sig in _CANONICAL_IR_MESH_INFO_SEEN:
        logger.debug(
            "INDEX_SPLINE: lambda_max=%.1f nm > %.0f nm - canonical mesh K=%d (+%d equi-lambda knots, last lambda segment).",
            hi,
            SPLINE_EXTRA_IR_KNOTS_LAM_MAX_THRESHOLD_NM,
            int(out.size),
            int(out.size - sk12.size),
        )

    else:
        _CANONICAL_IR_MESH_INFO_SEEN.add(_mesh_sig)

        logger.info(
            "INDEX_SPLINE: lambda_max=%.1f nm > %.0f nm - canonical mesh K=%d (+%d equi-lambda knots, last lambda segment).",
            hi,
            SPLINE_EXTRA_IR_KNOTS_LAM_MAX_THRESHOLD_NM,
            int(out.size),
            int(out.size - sk12.size),
        )

    return out


def _extract_smart_preview_override(cfg: SplineOptConfig, over: tuple, k: int) -> tuple[np.ndarray | None, np.ndarray | None, float | None]:
    """Validate and normalize a smart-preview override tuple."""

    n_ov, L_ov = over
    n_ov = np.asarray(n_ov, dtype=np.float64).ravel()
    L_ov = np.asarray(L_ov, dtype=np.float64).ravel()
    if not (n_ov.size == k and L_ov.size == k):
        return None, None, None
    d_ov = getattr(cfg, "smart_preview_d_nm_override", None)
    return n_ov, L_ov, d_ov


def _apply_smart_preview_exact_mesh(cfg: SplineOptConfig, sk_exact, pair_ex, lam_min: float, lam_max: float) -> int:
    """Rebuild the worker mesh from manual smart-preview knots."""

    sk_e = np.asarray(sk_exact, dtype=np.float64).ravel()
    ne, Le = pair_ex
    ne = np.asarray(ne, dtype=np.float64).ravel()
    Le = np.asarray(Le, dtype=np.float64).ravel()
    cfg.smart_preview_exact_sigma_knots = None
    cfg.smart_preview_exact_n_L = None
    if not (sk_e.size >= 2 and ne.size == sk_e.size and Le.size == sk_e.size):
        return sk_e, None, None
    _mdl = getattr(cfg, "spline_min_delta_lambda_over_lambda_mean", 0.02)
    try:
        _mdl_f = float(_mdl)
    except (TypeError, ValueError):
        _mdl_f = 0.0
    sk_canon = bridge_sigma_knots_preserve_manual(sk_e, lam_min, lam_max, rmse_fit_lambda_nm=getattr(cfg, "rmse_fit_lambda_nm", None), min_delta_lambda_over_lambda_mean=_mdl_f if _mdl_f > 0.0 else None)
    from certus.spline.spline_smart_init import interp_n_L_pwlnk_to_sigmas
    ne, Le = interp_n_L_pwlnk_to_sigmas(sk_e, ne, Le, sk_canon, diag_log=logger if int(sk_e.size) != int(sk_canon.size) else None, diag_tag="INDEX_SPLINE_smart_init_Ksrc_to_worker_mesh")
    cfg.n_seg = int(sk_canon.size) - 1
    d_ex = getattr(cfg, "smart_preview_d_nm_override", None)
    d_use = float(d_ex) if (d_ex is not None and np.isfinite(float(d_ex))) else None
    bounds, x0 = build_x0_smart_preview_exact(cfg, sk_canon, ne, Le, d_use)
    acc_rmse = getattr(cfg, "smart_preview_accepted_rmse", None)
    rmse_s = ""
    if acc_rmse is not None and np.isfinite(float(acc_rmse)):
        rmse_s = f" RMSE (spline objective, √MSE) after manual tuning: {float(acc_rmse):.6f};"
    logger.info(
        "INDEX_SPLINE [Smart Init]: restarting on worker mesh K=%s sigma nodes / %s segments "
        "(manual nodes preserved + additions if needed); "
        "n and ln k: dialogue snap + linear sigma interp. + edge extrap. (no plateau);%s d=%.2f nm.",
        int(sk_canon.size),
        int(cfg.n_seg),
        rmse_s,
        float(x0[0]),
    )
    return sk_canon, bounds, x0


def bridge_sigma_knots_preserve_manual(
    sigma_src: np.ndarray,
    lam_min_nm: float,
    lam_max_nm: float,
    *,
    rmse_fit_lambda_nm: tuple[float, float] | None = None,
    min_delta_lambda_over_lambda_mean: float | None = None,
) -> np.ndarray:
    """Worker K-canonical mesh while preserving manual mode knots.

    Strategy:

      - Target K = len(canonical_spline_sigma_knots(...)).

      - If K_src >= target_K: canonical return (no ad-hoc reduction/pruning here).

      - If K_src < target_K: we **add** knots (manual knots are not moved).

        Addition candidates come from the canonical grid, plus the RMSE window bounds

        (if active) to limit extrapolation in the noted zone.

    """

    sk_src = np.sort(np.asarray(sigma_src, dtype=np.float64).ravel())

    _can_kw: dict[str, float] = {}

    if min_delta_lambda_over_lambda_mean is not None:
        r = float(min_delta_lambda_over_lambda_mean)

        if r > 0.0 and np.isfinite(r):
            _can_kw["min_delta_lambda_over_lambda_mean"] = r

    sk_canon = np.sort(canonical_spline_sigma_knots(lam_min_nm, lam_max_nm, **_can_kw))

    if int(sk_src.size) < 2 or int(sk_src.size) >= int(sk_canon.size):
        return sk_canon

    s_min = float(min(1.0 / max(lam_max_nm, 1e-30), 1.0 / max(lam_min_nm, 1e-30)))

    s_max = float(max(1.0 / max(lam_max_nm, 1e-30), 1.0 / max(lam_min_nm, 1e-30)))

    sel = sk_src[(sk_src >= s_min - 1e-15) & (sk_src <= s_max + 1e-15)].copy()

    if int(sel.size) < 2:
        return sk_canon

    # Force spectral edges (especially useful if preview is truncated by rmse_fit_lambda_nm).

    # Do not duplicate existing sigma (mesh extremes ~ 1/lambda_max, 1/lambda_min within epsilon).

    tol_e = max(1e-14, 1e-9 * max(float(np.max(sel) - np.min(sel)), 1e-12))

    _edge_extra: list[float] = []

    if not np.any(np.abs(sel - s_min) <= tol_e):
        _edge_extra.append(s_min)

    if not np.any(np.abs(sel - s_max) <= tol_e):
        _edge_extra.append(s_max)

    if _edge_extra:
        sel = np.unique(np.concatenate((sel, np.asarray(_edge_extra, dtype=np.float64))))

    tol = max(1e-14, 1e-9 * max(float(np.max(sel) - np.min(sel)), 1e-12))

    cand = list(np.asarray(sk_canon, dtype=np.float64).ravel())

    if rmse_fit_lambda_nm is not None:
        lo_w = float(min(rmse_fit_lambda_nm[0], rmse_fit_lambda_nm[1]))

        hi_w = float(max(rmse_fit_lambda_nm[0], rmse_fit_lambda_nm[1]))

        if lo_w > 0.0 and hi_w > 0.0:
            cand.extend([1.0 / hi_w, 1.0 / lo_w])

    cands = np.asarray(cand, dtype=np.float64).ravel()

    cands = cands[(cands >= s_min - tol) & (cands <= s_max + tol)]

    target_k = int(sk_canon.size)

    need = target_k - int(sel.size)

    if need > 0:
        missing: list[float] = []

        for s in sk_canon:
            sf = float(s)

            if not np.any(np.abs(sel - sf) <= tol):
                missing.append(sf)

        # Common case: K=12 preview = exact subset of worker mesh (e.g., +2 IR nodes).

        # Fill with missing canonical sigma (fixed order) rather than greedy which may diverge.

        if len(missing) == need:
            out = np.sort(np.unique(np.concatenate((sel, np.asarray(missing, dtype=np.float64)))))

            if int(out.size) == target_k:
                return out.astype(np.float64, copy=False)

            sel = out

            need = target_k - int(sel.size)

    while int(sel.size) < target_k:
        best = None

        best_dist = -1.0

        for s in cands:
            if np.any(np.abs(sel - s) <= tol):
                continue

            d = float(np.min(np.abs(sel - s)))

            if d > best_dist:
                best_dist = d

                best = float(s)

        if best is None:
            break

        sel = np.unique(np.concatenate((sel, np.asarray([best], dtype=np.float64))))

    out = np.sort(np.asarray(sel, dtype=np.float64).ravel())

    if int(out.size) != target_k:
        return sk_canon

    return out


def build_sigma_knots(lam_min_nm: float, lam_max_nm: float, n_seg: int) -> np.ndarray:
    """Constructs a list of sigma on [1/lambda_max, 1/lambda_min]; used by ``canonical_spline_sigma_knots`` (K=12).

    For ``n_seg == 11`` (canonical K=12) delegates to :func:`build_sigma_knots_log_uniform`
    (uniform in log(sigma)). For other ``n_seg`` keeps the legacy linear-in-sigma layout used
    by external tools / tests outside the canonical 12-node pipeline.
    """

    k = int(n_seg) + 1

    if k == 12:
        # Nominal INDEX SPLINE case: uniform in log(sigma) -> geometric progression in lambda.
        return build_sigma_knots_log_uniform(lam_min_nm, lam_max_nm, n_seg)

    lo = float(min(lam_min_nm, lam_max_nm))

    hi = float(max(lam_min_nm, lam_max_nm))

    sig_min = 1.0 / max(hi, 1e-9)

    sig_max = 1.0 / max(lo, 1e-9)

    # Other tools / tests: linear mesh in sigma (outside the canonical 12-node pipeline).

    return np.linspace(sig_min, sig_max, k, dtype=np.float64)


def _to_fraction_T(y: np.ndarray) -> np.ndarray:

    arr = np.asarray(y, float)

    if float(np.nanmedian(arr)) > 2.5:
        return arr / 100.0

    return arr


def ensure_lam_nm_array(lam: np.ndarray) -> np.ndarray:
    """If max(lambda) < 100, interpret as um and convert to nm (consistent with nm optics)."""

    v = np.asarray(lam, dtype=np.float64).ravel()

    if v.size and float(np.nanmax(v)) < 100.0:
        return (v * 1000.0).astype(np.float64, copy=False)

    return v


def prepare_exp_TR_for_fit(
    lam_nm: np.ndarray,
    n_sub: np.ndarray,
    t_exp: np.ndarray | None,
    r_exp: np.ndarray | None,
    *,
    t_is_ratio: bool,
) -> tuple[np.ndarray | None, np.ndarray | None]:
    """Applies ``_to_fraction_T`` (% -> fraction if needed). Does not divide by T_sub.

    In ratio mode (``t_is_ratio`` in config), the file already contains the same

    ratio as the model (T_film/bare T_sub, R_film/bare T_sub with backside). A second

    division by T_sub would be an error. ``lam_nm`` / ``n_sub`` remain for calling compatibility.

    """

    _ = lam_nm, n_sub, t_is_ratio

    t_o = (
        None
        if t_exp is None
        else _to_fraction_T(np.asarray(t_exp, dtype=np.float64).ravel()).astype(np.float64, copy=False)
    )

    r_o = (
        None
        if r_exp is None
        else _to_fraction_T(np.asarray(r_exp, dtype=np.float64).ravel()).astype(np.float64, copy=False)
    )

    return t_o, r_o


_LAMBDA_NAMES = (
    "lambda",
    "Lambda",
    "wavelength",
    "Wavelength",
    "Wavelength, nm",
    "wl",
    "WL",
    "nm",
)


def _find_lambda_column(df: pd.DataFrame) -> str | None:

    for name in _LAMBDA_NAMES:
        if name in df.columns:
            return name

    for c in df.columns:
        cl = str(c).strip().lower()

        if "wavelength" in cl or cl.endswith(", nm") or cl == "lambda (nm)":
            return c

    return None


def _find_transmission_column(df: pd.DataFrame, lam_col: str) -> str | None:

    for name in ("T", "t", "Trans", "Transmission", "T_rel", "Tr", "fab1", "FAB1"):
        if name in df.columns and str(name) != lam_col:
            return name

    for c in df.columns:
        if str(c) == lam_col:
            continue

        cl = str(c).lower()

        if "reflect" in cl:
            continue

        if "trans" in cl or cl.startswith("t") or "rel" in cl or cl == "fab1":
            return str(c)

    candidates = [c for c in df.columns if c != lam_col and pd.api.types.is_numeric_dtype(df[c])]

    if len(candidates) == 1:
        return str(candidates[0])

    return None


def normalize_spectrum_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Renames to lambda / T / R for the rest of the pipeline."""

    if df is None or df.empty:
        return df

    out = df.copy()

    lam_c = _find_lambda_column(out)

    if not lam_c:
        numeric_cols = [c for c in out.columns if pd.api.types.is_numeric_dtype(out[c])]
        if numeric_cols:
            lam_c = str(numeric_cols[0])
        elif len(out.columns) >= 1:
            lam_c = str(out.columns[0])
        else:
            raise ValueError("Wavelength column not found (expected e.g. 'lambda', 'Wavelength, nm').")

    if lam_c != "lambda":
        out.rename(columns={lam_c: "lambda"}, inplace=True)

    t_c = _find_transmission_column(out, "lambda")

    if t_c and t_c != "lambda":
        out.rename(columns={t_c: "T"}, inplace=True)

    for rname in ("R", "r", "Reflect", "Reflection"):
        if rname in out.columns and rname != "T":
            out.rename(columns={rname: "R"}, inplace=True)

            break

    if "lambda" not in out.columns:
        raise ValueError("Invalid wavelength or spectrum column after normalization.")

    return out



def substrate_id_from_name(name: str) -> int:

    from certus.core.certus_core import substrate_sellmeier_id

    sid = substrate_sellmeier_id(name)

    if sid is None:
        raise KeyError(name)

    return int(sid)


def allowed_substrate_names() -> list[str]:

    from certus.core.certus_core import substrate_sellmeier_id

    return [n for n in SUBSTRATE_LIST if substrate_sellmeier_id(n) is not None]


# --- P4 Refactor: Sub-configs ---
from certus.spline.certus_index_spline_config import *

def reset_smart_init_preview_guard(cfg: SplineOptConfig | None = None) -> None:
    """Allows the Smart Init dialog again for a new run (``cfg.smart_init_preview_shown = False``)."""

    if cfg is not None:
        cfg.smart_init_preview_shown = False


def _flog_spectral_rmse_field(x: Any) -> str:

    if x is None:
        return "n/a"

    try:
        fx = float(x)

    except (TypeError, ValueError):
        return "n/a"

    return f"{fx:.8f}" if np.isfinite(fx) else "n/a"


def _log_smart_coaching_advice(logger: logging.Logger, r: dict) -> None:
    """Proactive coaching: analyzes results to suggest pipeline or config improvements."""

    prefix = "SMART COACHING |"

    # 1. Analyze RMSE

    rmse = r.get("rmse")

    if rmse is not None:
        try:
            frmse = float(rmse)

            if frmse > 0.05:
                logger.debug("%s High RMSE (%.4f) detected.", prefix, frmse)
            elif frmse > 0.02:
                logger.debug("%s Moderate RMSE (%.4f).", prefix, frmse)

        except (ValueError, TypeError):
            pass

    # 2. Analyze n hitting bounds

    n_nodes = r.get("n_nodes_physical")

    if n_nodes is not None:
        n_nod = np.asarray(n_nodes, dtype=np.float64)

        if np.any(n_nod <= N_MIN_LIMIT + 0.01) or np.any(n_nod >= N_MAX_LIMIT - 0.01):
            logger.debug(
                "%s Index 'n' is hitting physical limits (%.2f-%.2f). Thickness or substrate index might be off.",
                prefix,
                N_MIN_LIMIT,
                N_MAX_LIMIT,
            )

    # 3. Analyze k hitting floor

    L_nodes = r.get("L_nodes")

    if L_nodes is not None:
        L_nod = np.asarray(L_nodes, dtype=np.float64)

        k_val = np.exp(L_nod)

        # Using a typical floor heuristic

        if np.any(k_val <= 1.1e-4):
            logger.debug("%s Extinction 'k' is hitting the floor (normal for transparent films).", prefix)

    # 4. Check mesh polish

    rs = r.get("spectral_rmse_seg_spline_sigma")

    rref = r.get("spectral_rmse_segments")

    if rs is not None and rref is not None:
        try:
            frs = float(rs)

            frref = float(rref)

            if frs > frref * 1.5:
                logger.debug(
                    "%s Cubic polish significantly increased RMSE. Suggestion: Your node grid might be too sparse.",
                    prefix,
                )

        except (ValueError, TypeError):
            pass


def _log_spectral_mesh_polish_rmse_block(logger: logging.Logger, r: dict) -> None:
    """Spectral RMSE: sigma-spline mesh polish + solver ref before polish + best model."""

    rs = r.get("spectral_rmse_seg_spline_sigma")

    rref = r.get("spectral_rmse_segments")

    if (rs is not None and np.isfinite(float(rs))) or (rref is not None and np.isfinite(float(rref))):
        logger.debug(
            "Spectral RMSE (mesh polish) - cubic sigma-spline=%s | solver ref (before polish)=%s",
            _flog_spectral_rmse_field(rs),
            _flog_spectral_rmse_field(rref),
        )

    _log_smart_coaching_advice(logger, r)

    bl = r.get("spectral_rmse_best_label")

    bv = r.get("spectral_rmse_best_value")

    if bl is not None and bv is not None and np.isfinite(float(bv)):
        logger.debug(
            "Best model (spectral RMSE): %s = %.8f",
            str(bl),
            float(bv),
        )


def _log_index_spline_best_config(
    logger: logging.Logger | None,
    r: dict,
    rmse: float,
    title: str = "[BEST RMSE]",
) -> None:
    """Log RMSE, thickness, mesh polish RMSE block, node table (if consistent)."""

    if logger is None:
        return

    sk = np.asarray(r.get("sigma_knots", []), dtype=np.float64).ravel()

    k = int(sk.size)

    if k == 0:
        logger.info("%s RMSE=%.8f | missing sigma_knots in result snapshot", title, float(rmse))

        return

    n_n = np.asarray(r.get("n_nodes_physical", []), dtype=np.float64).ravel()

    L_n = np.asarray(r.get("L_nodes", []), dtype=np.float64).ravel()

    xa_raw = r.get("x")

    xa = np.asarray(xa_raw, dtype=np.float64).ravel() if xa_raw is not None else None

    n_mono = r.get("n_mono_band_nm")

    if (n_n.size != k) and xa is not None and xa.size == 1 + 2 * k:
        n_n = x_slice_n_to_physical_nodes(xa[1 : 1 + k], sk, n_mono)

    if (L_n.size != k) and xa is not None and xa.size == 1 + 2 * k:
        L_n = np.asarray(xa[1 + k : 1 + 2 * k], dtype=np.float64).ravel()

    if n_n.size != k or L_n.size != k:
        logger.info(
            "%s RMSE=%.8f | d_nm=%s | node shape mismatch (K=%d, len(n)=%d, len(L)=%d)",
            title,
            float(rmse),
            r.get("d_nm"),
            k,
            int(n_n.size),
            int(L_n.size),
        )

        if xa is not None:
            logger.info("  x = %s", np.array2string(xa, precision=12, separator=", ", max_line_width=240))

        _log_spectral_mesh_polish_rmse_block(logger, r)

        return

    d_from_dict = float(r.get("d_nm", float("nan")))

    d_from_x = float(xa[0]) if xa is not None and xa.size > 0 else float("nan")

    # After mesh polish or rmse/mse recalculation, dict d_nm may differ from x[0] (solver vector).

    if np.isfinite(d_from_dict):
        d_nm = d_from_dict

    elif np.isfinite(d_from_x):
        d_nm = d_from_x

    else:
        d_nm = float("nan")

    if np.isfinite(d_from_dict) and np.isfinite(d_from_x) and abs(d_from_dict - d_from_x) > 0.01:
        logger.info(
            "%s note d_nm: dict=%.6f nm ≠ solver x[0]=%.6f nm - displaying dict thickness (the exported result dict carries the promoted thickness aligned with recalculated rmse/mse).",
            title,
            d_from_dict,
            d_from_x,
        )

    x_encoding = str(r.get("x_encoding", "?"))

    logger.info(
        "%s RMSE=%.8f | d_nm=%.6f nm | K=%d sigma knots | x_encoding=%s", title, float(rmse), d_nm, k, x_encoding
    )

    _log_spectral_mesh_polish_rmse_block(logger, r)

    for i in range(k):
        sig = float(sk[i])
        lam_i = 1.0 / max(sig, 1e-30)
        logger.debug(
            "  #%02d sigma=%.10e nm^-1 | lambda=%.4f nm | n=%.8f | ln(k)=%.8f",
            i,
            sig,
            lam_i,
            float(n_n[i]),
            float(L_n[i]),
        )

    if xa is not None:
        logger.debug(
            "  x [%d] (d, then n or xi, then L=ln(k)): %s",
            xa.size,
            np.array2string(xa, precision=12, separator=", ", max_line_width=240),
        )


def log_index_spline_d_trace(log: logging.Logger, action: str, d_nm: float | None = None, *, detail: str = "") -> None:
    """Logs thickness trace changes for the spline pipeline."""
    parts = [f"[D-TRACE] {action}"]
    if d_nm is not None:
        parts.append(f"d={float(d_nm):.6f} nm")
    if detail:
        parts.append(detail)
    log.info(" | ".join(parts))


def _log_spline_pipeline_json(log: logging.Logger, event: str, *, seq: str | None = None, **fields: Any) -> None:
    """Structured spline pipeline log (grep: SPLINE_PIPELINE_JSON)."""

    log_structured_json_event(log, "SPLINE_PIPELINE_JSON", event, seq=seq, **fields)


def reconcile_spline_x_warm_for_config(
    x: np.ndarray,
    sigma_knots: np.ndarray,
    *,
    n_mono_target: tuple[float, float] | None,
    x_encoding_in: str,
    n_mono_band_for_xi_decode: tuple[float, float] | None = None,
) -> np.ndarray:
    """Adapts a loaded ``x`` vector (JSON export, other run) to current mono config."""

    x = np.asarray(x, dtype=np.float64).ravel().copy()

    sk = np.asarray(sigma_knots, dtype=np.float64).ravel()

    K = int(sk.size)

    if x.size != 1 + 2 * K:
        return x

    n_part = x[1 : 1 + K]

    if n_mono_target is not None and x_encoding_in == "n_physical":
        x[1 : 1 + K] = physical_nodes_to_x_slice_n(n_part, sk, n_mono_target)

    elif n_mono_target is None and x_encoding_in == "xi_n_mono":
        band = n_mono_band_for_xi_decode

        if band is not None:
            x[1 : 1 + K] = x_slice_n_to_physical_nodes(n_part, sk, band)

    return x


def _rmse_fit_lambda_inside_mask(
    lam_nm: np.ndarray,
    rmse_fit_lambda_nm: tuple[float, float] | None,
) -> np.ndarray:
    """Boolean mask True on lambda in the RMSE window (all True if no window)."""

    lam = np.asarray(lam_nm, dtype=np.float64).ravel()

    if rmse_fit_lambda_nm is None:
        return np.ones(lam.size, dtype=bool)

    lo = float(min(rmse_fit_lambda_nm[0], rmse_fit_lambda_nm[1]))

    hi = float(max(rmse_fit_lambda_nm[0], rmse_fit_lambda_nm[1]))

    return (lam >= lo) & (lam <= hi) & np.isfinite(lam)


def nan_nk_outside_rmse_lambda_window(
    lam_nm: np.ndarray,
    n_lam: np.ndarray,
    k_lam: np.ndarray,
    rmse_fit_lambda_nm: tuple[float, float] | None,
) -> tuple[np.ndarray, np.ndarray]:
    """Copies n, k with NaN outside the ``rmse_fit_lambda_nm`` band (display / export)."""

    n_out = np.asarray(n_lam, dtype=np.float64).copy()

    k_out = np.asarray(k_lam, dtype=np.float64).copy()

    if rmse_fit_lambda_nm is None:
        return n_out, k_out

    lam = np.asarray(lam_nm, dtype=np.float64).ravel()

    if lam.size != n_out.size or lam.size != k_out.size:
        return n_out, k_out

    ins = _rmse_fit_lambda_inside_mask(lam, rmse_fit_lambda_nm)

    n_out[~ins] = np.nan

    k_out[~ins] = np.nan

    return n_out, k_out


def apply_rmse_fit_window_nk_nan_to_result(
    out: dict[str, Any],
    rmse_fit_lambda_nm: tuple[float, float] | None,
) -> dict[str, Any]:
    """

    Sets n_lam, k_lam (and displayed derived fields) to NaN outside the RMSE window.

    ``t_theo`` / ``r_theo`` remain on the full spectral grid.

    """

    if rmse_fit_lambda_nm is None:
        return out

    lam = np.asarray(out.get("lam_nm"), dtype=np.float64).ravel()

    if not lam.size or "n_lam" not in out or "k_lam" not in out:
        return out

    n_new, k_new = nan_nk_outside_rmse_lambda_window(lam, out["n_lam"], out["k_lam"], rmse_fit_lambda_nm)

    out["n_lam"] = n_new

    out["k_lam"] = k_new

    if "ln_k_lam" in out:
        lk = np.asarray(out["ln_k_lam"], dtype=np.float64).ravel().copy()

        if lk.size == lam.size:
            ins = _rmse_fit_lambda_inside_mask(lam, rmse_fit_lambda_nm)

            lk[~ins] = np.nan

            out["ln_k_lam"] = lk

    # Corridors (profiling on d): mask in the same way as n_lam/k_lam.

    for key in (
        "corridor_n_lo",
        "corridor_n_hi",
        "corridor_k_lo",
        "corridor_k_hi",
        "corridor_reference_n_lam",
        "corridor_reference_k_lam",
        "boot_corridor_n_lo",
        "boot_corridor_n_hi",
        "boot_corridor_k_lo",
        "boot_corridor_k_hi",
        "boot_corridor_L_lo",
        "boot_corridor_L_hi",
    ):
        arr = out.get(key)

        if arr is None:
            continue

        a = np.asarray(arr, dtype=np.float64).ravel().copy()

        if a.size != lam.size:
            continue

        ins = _rmse_fit_lambda_inside_mask(lam, rmse_fit_lambda_nm)

        a[~ins] = np.nan

        out[key] = a

    return out


def snapshot_result_with_rmse_fit_meta(
    cfg: SplineOptConfig,
    d: dict[str, Any],
) -> dict[str, Any]:
    """Copies result + ``rmse_fit_lambda_nm`` key (title / SMART) then masks n,k outside the band."""

    o = dict(d)

    o["rmse_fit_lambda_nm"] = cfg.rmse_fit_lambda_nm

    return apply_rmse_fit_window_nk_nan_to_result(o, cfg.rmse_fit_lambda_nm)


def _bounds_x0_for_sigma_knots(
    cfg: SplineOptConfig,
    sk: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, float, float]:
    """Bounds and default x0 for a given sigma grid (K = len(sk) knots)."""

    sk = np.asarray(sk, dtype=np.float64).ravel()

    k = int(sk.size)

    dim = 1 + 2 * k

    k_hi = float(min(max(cfg.k_clip_hi, cfg.k_clip_lo * 1.0001), float(K_MAX_LIMIT)))
    L_lo = float(max(np.log(max(cfg.k_clip_lo, 1e-30)), L_LNK_MIN_PHYS))
    L_hi = float(np.log(k_hi))

    bounds = np.empty((dim, 2), dtype=np.float64)

    d_lo = float(min(cfg.d_lo, cfg.d_hi))
    d_hi = float(max(cfg.d_lo, cfg.d_hi))
    bounds[0] = (d_lo, d_hi)

    xi_lo, xi_hi = N_MONO_XI_BOUNDS
    n_lo, n_hi = (N_MIN_LIMIT, N_MAX_LIMIT) if cfg.n_mono_band_nm is None else (float(xi_lo), float(xi_hi))
    bounds[1 : 1 + k] = (n_lo, n_hi)
    bounds[1 + k : 1 + 2 * k] = (L_lo, L_hi)

    x0 = bounds.mean(axis=1)
    x0[0] = float(np.clip(0.5 * (cfg.d_lo + cfg.d_hi), d_lo, d_hi))

    if cfg.n_mono_band_nm is None:
        x0[1 : 1 + k] = 1.65
    else:
        x0[1 : 1 + k] = physical_nodes_to_x_slice_n(np.full(k, 1.65, dtype=np.float64), sk, cfg.n_mono_band_nm)

    x0[1 + k : 1 + 2 * k] = np.clip(np.log(1e-3), L_lo, L_hi)

    return bounds, x0, L_lo, L_hi


def build_x0_smart_preview_exact(
    cfg: SplineOptConfig,
    sk: np.ndarray,
    ne: np.ndarray,
    Le: np.ndarray,
    d_nm: float | None,
    *,
    relax_n_mono: bool = False,
) -> tuple[np.ndarray, np.ndarray]:
    """(bounds, x0) identical to the ``sk_exact`` block of ``make_bounds_and_x0`` (without cfg mutation)."""

    sk_a = np.asarray(sk, dtype=np.float64).ravel()
    ne_a = np.asarray(ne, dtype=np.float64).ravel()
    Le_a = np.asarray(Le, dtype=np.float64).ravel()

    k = int(sk_a.size)
    if ne_a.size != k or Le_a.size != k:
        raise ValueError("build_x0_smart_preview_exact: mismatching sizes for ne, Le and sk")

    bounds, x0, L_lo, L_hi = _bounds_x0_for_sigma_knots(cfg, sk_a)

    relax_eff = bool(relax_n_mono) and cfg.n_mono_band_nm is not None
    if cfg.n_mono_band_nm is None or relax_eff:
        x0[1 : 1 + k] = np.clip(ne_a, N_MIN_LIMIT, N_MAX_LIMIT)
    else:
        x0[1 : 1 + k] = physical_nodes_to_x_slice_n(ne_a, sk_a, cfg.n_mono_band_nm)

    x0[1 + k : 1 + 2 * k] = np.clip(Le_a, L_lo, L_hi)
    if d_nm is not None and np.isfinite(float(d_nm)):
        x0[0] = float(np.clip(float(d_nm), bounds[0, 0], bounds[0, 1]))

    return bounds, x0


def make_bounds_and_x0(
    cfg: SplineOptConfig, *, skip_smart_init: bool = False
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Build the canonical spline bounds and warm-start vector."""

    from certus.spline.spline_smart_init import compute_smart_init_spectral_preview, guess_smart_x0_from_extrema

    skip_x0_warm = False
    lam_min = float(np.min(cfg.lam_nm))
    lam_max = float(np.max(cfg.lam_nm))
    sk = np.asarray(_canonical_sigma_knots_cached(lam_min, lam_max, getattr(cfg, "spline_min_delta_lambda_over_lambda_mean", 0.02)), dtype=np.float64)
    k = int(sk.size)
    cfg.n_seg = k - 1

    rfw = getattr(cfg, "rmse_fit_lambda_nm", None)
    if rfw is not None:
        lo_w = float(min(rfw[0], rfw[1]))
        hi_w = float(max(rfw[0], rfw[1]))
        try:
            from certus.spline.spline_objective import _spline_objective_lam_mask
            n_pix_obj = int(np.count_nonzero(_spline_objective_lam_mask(cfg)))
        except NUMERICAL_FAULT_EXCEPTIONS:
            logger.debug("_spline_objective_lam_mask failed in make_bounds_and_x0", exc_info=True)
            n_pix_obj = -1
        if lam_max > hi_w + 0.5 or lam_min < lo_w - 0.5:
            logger.info(
                "INDEX_SPLINE | File lambda [%.2f, %.2f] nm -> canonical sigma mesh K=%d (e.g. IR node at lambda~%.1f nm) ; "
                "rmse_fit_lambda_nm [%.2f, %.2f] nm -> **%d pixels** in spectral MSE only "
                "(lambda > %.2f nm do not count in error, but sigma nodes remain anchored on file lambda_max).",
                lam_min,
                lam_max,
                k,
                lam_max,
                lo_w,
                hi_w,
                n_pix_obj,
                hi_w,
            )

    if cfg.sigma_knots_override is not None:
        logger.info(
            "INDEX_SPLINE: sigma_knots_override ignored - fixed mesh K=%d sigma knots (%d segments).",
            k,
            int(cfg.n_seg),
        )

    bounds, x0, L_lo, L_hi = _bounds_x0_for_sigma_knots(cfg, sk)
    has_exact = getattr(cfg, "smart_preview_exact_sigma_knots", None) is not None
    has_over = getattr(cfg, "smart_preview_node_override", None) is not None
    preview_hook = getattr(cfg, "smart_init_preview_hook", None)
    preview_shown = bool(getattr(cfg, "smart_init_preview_shown", False))

    logger.debug(
        "INDEX_SPLINE [Smart Init GATE] skip=%s exact=%s over=%s x0_warm=%s hook=%s shown=%s",
        skip_smart_init,
        has_exact,
        has_over,
        cfg.x0_warm is None,
        preview_hook is not None,
        preview_shown,
    )

    if not skip_smart_init and not (has_exact or has_over) and cfg.x0_warm is None and cfg.t_exp is not None and getattr(cfg, "n_sub", None) is not None:
        logger.info(
            "INDEX_SPLINE [Smart Init]: launching Swanepoel on fixed mesh (%s segments -> %s sigma knots) ; manual dialog: values re-interpolated on canonical grid if needed.",
            int(cfg.n_seg),
            int(k),
        )
        smart_n, smart_L = guess_smart_x0_from_extrema(cfg.lam_nm, cfg.t_exp, cfg.n_sub, 0.5 * (cfg.d_lo + cfg.d_hi), sk)
        if smart_n is not None and smart_L is not None:
            n_prev = np.asarray(smart_n, dtype=np.float64).ravel()
            L_prev = np.asarray(smart_L, dtype=np.float64).ravel()
            x0[1 : 1 + k] = np.clip(smart_n, N_MIN_LIMIT, N_MAX_LIMIT) if cfg.n_mono_band_nm is None else physical_nodes_to_x_slice_n(smart_n, sk, cfg.n_mono_band_nm)
            x0[1 + k : 1 + 2 * k] = np.clip(smart_L, L_lo, L_hi)
            logger.info("INDEX_SPLINE [Smart Init]: success - injecting n and L profiles from interference extrema.")
        else:
            logger.warning("INDEX_SPLINE [Smart Init]: failed (not enough clear fringes or very noisy). Standard fallback (1.65 / 1e-3).")
            n_prev = np.clip(x0[1 : 1 + k], N_MIN_LIMIT, N_MAX_LIMIT) if cfg.n_mono_band_nm is None else x_slice_n_to_physical_nodes(x0[1 : 1 + k], sk, cfg.n_mono_band_nm)
            L_prev = np.clip(x0[1 + k : 1 + 2 * k], L_lo, L_hi)
            logger.info("INDEX_SPLINE [Smart Init]: manual dialog with standard x0 (Swanepoel unavailable).")
        if preview_hook is not None and not preview_shown:
            pv = compute_smart_init_spectral_preview(cfg, sk, n_prev, L_prev, uniform_sigma_nodes=11)
            if pv is not None and not preview_hook(pv):
                raise SmartInitPreviewCancelled
            cfg.smart_init_preview_shown = True
            over = getattr(cfg, "smart_preview_node_override", None)
            exact_pending = getattr(cfg, "smart_preview_exact_sigma_knots", None) is not None
            if over is not None and not exact_pending:
                n_ov, L_ov, d_ov = _extract_smart_preview_override(cfg, over, k)
                if n_ov is not None and L_ov is not None:
                    x0[1 : 1 + k] = np.clip(n_ov, N_MIN_LIMIT, N_MAX_LIMIT) if cfg.n_mono_band_nm is None else physical_nodes_to_x_slice_n(n_ov, sk, cfg.n_mono_band_nm)
                    x0[1 + k : 1 + 2 * k] = np.clip(L_ov, L_lo, L_hi)
                    if d_ov is not None and np.isfinite(float(d_ov)):
                        x0[0] = float(np.clip(float(d_ov), bounds[0, 0], bounds[0, 1]))
                    skip_x0_warm = True
                cfg.smart_preview_node_override = None
                cfg.smart_preview_d_nm_override = None
            elif over is not None and exact_pending:
                cfg.smart_preview_node_override = None

    sk_exact = getattr(cfg, "smart_preview_exact_sigma_knots", None)
    pair_ex = getattr(cfg, "smart_preview_exact_n_L", None)
    if sk_exact is not None and pair_ex is not None:
        sk_canon, b_new, x_new = _apply_smart_preview_exact_mesh(cfg, sk_exact, pair_ex, lam_min, lam_max)
        if b_new is not None and x_new is not None:
            sk = sk_canon
            bounds = b_new
            x0 = x_new
            k = int(sk.size)
            cfg.pglobal_trust_rho_hi = 0.14
            cfg.fixed_sigma_knots_count = k
            skip_x0_warm = True

    if cfg.x0_warm is not None and not skip_x0_warm:
        xw = np.asarray(cfg.x0_warm, float).ravel()
        if xw.size == int(bounds.shape[0]):
            x0 = clip_to_bounds(xw.astype(np.float64, copy=True), bounds[:, 0], bounds[:, 1])
            enc = cfg.x0_warm_encoding
            if enc is not None:
                x0 = reconcile_spline_x_warm_for_config(x0, sk, n_mono_target=cfg.n_mono_band_nm, x_encoding_in=str(enc), n_mono_band_for_xi_decode=(cfg.x0_warm_n_mono_band_for_decode or cfg.n_mono_band_nm))
    return bounds, x0, sk


def rmse_at_spline_stage_x0_init(
    cfg: SplineOptConfig,
    sk: np.ndarray,
    ne: np.ndarray,
    Le: np.ndarray,
    d_nm: float | None,
    *,
    relax_n_mono: bool = False,
) -> tuple[float, float]:
    """MSE and RMSE at x0_init (clip bounds): same scalar as the 1st ``obj(x0_init)`` of the stage before L-BFGS-B."""

    from certus.spline.spline_objective import SplinePWLObjective

    bounds, x0 = build_x0_smart_preview_exact(cfg, sk, ne, Le, d_nm, relax_n_mono=relax_n_mono)

    sk_a = np.asarray(sk, dtype=np.float64).ravel()

    k = int(sk_a.size)

    x0_init = np.asarray(x0, dtype=np.float64).copy()

    relax_eff = bool(relax_n_mono) and cfg.n_mono_band_nm is not None

    if relax_eff:
        x0_init[0] = float(np.clip(x0_init[0], bounds[0, 0], bounds[0, 1]))

        x0_init[1 : 1 + k] = np.clip(x0_init[1 : 1 + k], N_MIN_LIMIT, N_MAX_LIMIT)

        for i in range(k):
            x0_init[1 + k + i] = float(np.clip(x0_init[1 + k + i], bounds[1 + k + i, 0], bounds[1 + k + i, 1]))

    else:
        x0_init = clip_to_bounds(x0_init, bounds[:, 0], bounds[:, 1])

    cfg_eval = cfg.replace(n_mono_band_nm=None) if relax_eff else cfg

    mse = float(SplinePWLObjective(cfg_eval, sk_a)(x0_init))

    return mse, float(np.sqrt(max(mse, 0.0)))


def log_rmse_mesh_bridge_diagnosis(
    cfg: SplineOptConfig,
    sk_dialog: np.ndarray,
    n_dialog: np.ndarray,
    L_dialog: np.ndarray,
    sk_canon: np.ndarray,
    n_canon: np.ndarray,
    L_canon: np.ndarray,
    d_nm: float,
    log: logging.Logger,
    *,
    relax_preview_mono: bool,
    tag: str = "DIAG_RMSE_BRIDGE",
) -> None:
    """Logs spectral MSE vs penalties for dialog K and canonical K (same cfg, same masked lambda grid).

    Explains a factor like 0.007 -> 0.04: often multiplied ``MSE_spectral`` because the **sigma mesh**

    (K, knot positions, edge extrapolation) differs between preview and worker, not a lambda grid bug.

    """

    sk_d = np.asarray(sk_dialog, dtype=np.float64).ravel()

    sk_c = np.asarray(sk_canon, dtype=np.float64).ravel()

    if int(sk_d.size) == int(sk_c.size) and np.allclose(np.sort(sk_d), np.sort(sk_c), rtol=0, atol=1e-12):
        return

    def _x0_after_rmse_clip(bounds: np.ndarray, x0: np.ndarray, sk: np.ndarray, *, relax_n_mono: bool) -> np.ndarray:

        k = int(sk.size)

        xi = np.asarray(x0, dtype=np.float64).ravel().copy()

        relax_eff = bool(relax_n_mono) and cfg.n_mono_band_nm is not None

        if relax_eff:
            xi[0] = float(np.clip(xi[0], bounds[0, 0], bounds[0, 1]))

            xi[1 : 1 + k] = np.clip(xi[1 : 1 + k], N_MIN_LIMIT, N_MAX_LIMIT)

            for i in range(k):
                xi[1 + k + i] = float(np.clip(xi[1 + k + i], bounds[1 + k + i, 0], bounds[1 + k + i, 1]))

        else:
            xi = clip_to_bounds(xi, bounds[:, 0], bounds[:, 1])

        return xi

    try:
        from certus.spline.spline_objective import decompose_spline_pwl_objective

        b_d, x0_d = build_x0_smart_preview_exact(cfg, sk_d, n_dialog, L_dialog, d_nm, relax_n_mono=relax_preview_mono)

        x_d = _x0_after_rmse_clip(b_d, x0_d, sk_d, relax_n_mono=relax_preview_mono)

        relax_eff = bool(relax_preview_mono) and cfg.n_mono_band_nm is not None

        cfg_prev = cfg.replace(n_mono_band_nm=None) if relax_eff else cfg

        msp_d, pen_d, tot_d = decompose_spline_pwl_objective(cfg_prev, sk_d, x_d)

        b_c, x0_c = build_x0_smart_preview_exact(cfg, sk_c, n_canon, L_canon, d_nm, relax_n_mono=False)

        x_c = _x0_after_rmse_clip(b_c, x0_c, sk_c, relax_n_mono=False)

        msp_c, pen_c, tot_c = decompose_spline_pwl_objective(cfg, sk_c, x_c)

        # If the preview is in relax mono, x_c contains ξ (not physical n): evaluate "like the preview"

        # (cfg without n_mono_band_nm) first requires ξ -> n, otherwise nk_from_x interprets ξ as n -> absurd RMSE.

        cfg_canon_relax = cfg.replace(n_mono_band_nm=None) if relax_eff else cfg

        if relax_eff:
            kc = int(sk_c.size)

            xi_blk = np.asarray(x_c[1 : 1 + kc], dtype=np.float64).ravel()

            n_phys_c = np.clip(
                x_slice_n_to_physical_nodes(xi_blk, sk_c, cfg.n_mono_band_nm),
                N_MIN_LIMIT,
                N_MAX_LIMIT,
            )

            L_blk = np.asarray(x_c[1 + kc : 1 + 2 * kc], dtype=np.float64).ravel()

            x_cr = np.concatenate((x_c[0:1], n_phys_c, L_blk))

            msp_cr, _, tot_cr = decompose_spline_pwl_objective(cfg_canon_relax, sk_c, x_cr)

        else:
            _, _, tot_cr = float("nan"), float("nan"), float("nan")

        rm_d = float(np.sqrt(max(tot_d, 0.0)))

        rm_c = float(np.sqrt(max(tot_c, 0.0)))

        rm_cr = float(np.sqrt(max(tot_cr, 0.0))) if relax_eff else float("nan")

        log.info(
            "%s | === RMSE Smart Init Bridge (read [A] then [B] — same story as ``GUI Smart Init [Keep] | Thread``) ===",
            tag,
        )

        log.info(
            "%s | [A] Preview / dialog  K=%2d  RMSE=%.6f  (often relax_n_mono, same K as the window).",
            tag,
            int(sk_d.size),
            rm_d,
        )

        log.info(
            "%s | [B] Worker mesh    K=%2d  RMSE=%.6f  (real objective at startup of INDEX_SPLINE / PGlobal).",
            tag,
            int(sk_c.size),
            rm_c,
        )

        if relax_eff and np.isfinite(rm_cr):
            log.info(
                "%s | [C] Same mesh as [B], spectrum only (n_mono cut)  K=%2d  RMSE=%.6f  — isolates remesh + edge extrapolation.",
                tag,
                int(sk_c.size),
                rm_cr,
            )

            log.info(
                "%s | Why [A] < [B] is possible: not the same objective ([B]: mono ξ, penalties, K often larger).",
                tag,
            )

            log.info(
                "%s | Why [C] ≠ [A]: spectral weighting close, but K and σ differ (remesh / nodes).",
                tag,
            )

        else:
            log.info(
                "%s | If [A] ≠ [B]: generally extra nodes, edge extrapolation, or σ positions — not a λ mask bug.",
                tag,
            )

        log.info(
            "%s | Detail  [A] MSE_sp=%.6e pen.=%.6e total=%.6e  |  [B] MSE_sp=%.6e pen.=%.6e total=%.6e",
            tag,
            msp_d,
            pen_d,
            tot_d,
            msp_c,
            pen_c,
            tot_c,
        )

        ratio_tot = tot_c / max(tot_d, 1e-30)

        ratio_sp = msp_c / max(msp_d, 1e-30)

        log.info(
            "%s | Rapports  total[B]/[A]=%.3f  MSE_sp[B]/[A]=%.3f  (>1 → surtout maillage / extrap / encodage ξ).",
            tag,
            ratio_tot,
            ratio_sp,
        )

        log.info(
            "%s | Remember: the RMSE of [B] is the one that aligns FACTUAL SOL2 and the line ``INDEX_SPLINE ... RMSE start``.",
            tag,
        )

    except NUMERICAL_FAULT_EXCEPTIONS as exc:
        log.warning("%s | diagnostic failed: %s", tag, exc, exc_info=True)


# --- QSettings and Default GUI Constants ---
_QS_SPECTRUM_FIT_R = "spectrum_fit_r"
_QS_SPECTRUM_FIT_TREL = "spectrum_fit_trel"
_QS_SPECTRUM_FIT_T = "spectrum_fit_t"
_QS_SPECTRUM_WR = "spectrum_weight_r"
_QS_SPECTRUM_WT = "spectrum_weight_t"
_QS_SPLINE_UNCERTAINTY_DEFAULTS_REV = "spline_uncertainty_defaults_rev"
_UNCERTAINTY_DEFAULTS_REV = 12
_QS_MAIN_SPLITTER_LAYOUT_REV = "main_splitter_layout_rev"
_MAIN_SPLITTER_LAYOUT_REV = 4
_QS_MAIN_SPLITTER_STATE = "main_splitter_state"
_QS_RIGHT_SPLITTER_STATE = "right_splitter_state"
SIO2_DEFAULT_D_HI_NM = 1800.0
SIO2_DEFAULT_D_LO_NM = 1600.0

