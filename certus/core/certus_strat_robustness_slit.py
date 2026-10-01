"""CERTUS STRAT ROBUSTNESS - the spectral resolution of a strategy and its slit-bias profiles (moved out of certus_strat_robustness.py, S5.2)."""

import logging
from typing import Any

import numpy as np

from certus_physics import D_SCAN_VAL, MAX_LOOKBACK_VAL, SLIT_PROFILE_NODES

#: Nominal slit, the one the measured noise amplitude corresponds to (👤 2026-08-09).
NOMINAL_RESOLUTION_NM: float = 2.0


def _calculate_strategy_spectral_resolution(strategy: dict[str, Any], p_thick_nominal: Any, params: dict[str, Any]) -> tuple:
    from certus.core.certus_strat_config import APP_CONTEXT
    from certus.utils.certus_strat_service import calculate_RT_normal_real
    blocks = strategy["blocks"]
    nH_id, nL_id, nSub_id = params["nH_id"], params["nL_id"], params["nSub_id"]
    db_local = params.get("materials_db_instance") or params.get("materials_db") or APP_CONTEXT.get("materials_db")
    test_bw = 1.0
    half_bw = test_bw / 2.0

    try:
        T_tolerance = float(params["reality_sim_params"]["trigger_tolerance"]) / 100.0
    except KeyError, ValueError, TypeError:
        T_tolerance = 0.001

    min_resolution = 999.0
    worst_layer = -1
    # 🔴 THE PER-LAYER CURVATURE IS KEPT, not collapsed. This function computed it for
    # all 48 layers and returned only the minimum `res_limit` -- the THIRD time this
    # exact pattern was found on 2026-08-11, after `crashed_cells` reduced on the layer
    # axis and `avg_dynamics` averaged away. It is the quantity the slit bias needs:
    #
    #     bias(B) = <T>_B - T(lambda_mon) = T''(lambda_mon) . B^2 / 24
    #
    # ⚠️ SIGNED, unlike `curvature` above which takes an absolute value for the
    # resolution limit. The sign is the physics: T'' > 0 near a minimum and < 0 near a
    # maximum, so the bias always pushes TOWARDS THE INSIDE of the curve. Near a turning
    # point -- where POEM takes its anchors -- it shrinks the measured swing. Dropping
    # the sign would make the bias push the wrong way half the time.
    signed_curvature = np.zeros(len(p_thick_nominal), dtype=np.float64)
    layer_to_wl = {}

    for block in blocks:
        for layer_idx in range(block["start"], block["end"]):
            layer_to_wl[layer_idx] = float(block["wavelength"])

    num_layers = len(p_thick_nominal)
    for i_layer in range(num_layers):
        wl_mon = layer_to_wl.get(i_layer, float(params.get("l0", 550.0)))
        current_stack_thick = p_thick_nominal[: i_layer + 1]
        wls_check = [max(0.1, wl_mon - half_bw), wl_mon, wl_mon + half_bw]

        RT = calculate_RT_normal_real(wls_check, nH_id, nL_id, nSub_id, current_stack_thick, db_instance=db_local)  # type: ignore[arg-type]  # the wrapper converts the list
        T_vals = RT[:, 1]

        if len(T_vals) == 3:
            second_diff = (T_vals[0] + T_vals[2]) / 2.0 - T_vals[1]
            # second_diff = T''.test_bw^2/8, so T'' = 8.second_diff/test_bw^2 and the
            # boxcar bias T''.B^2/24 becomes second_diff . B^2 / (3.test_bw^2).
            signed_curvature[i_layer] = second_diff
            curvature = abs(second_diff)
            if curvature > 1e-9:
                # 🔴 THE FACTOR 3 IS THE SLIT SHAPE, and it was missing -- 12.7.
                #
                # 👤 the slit is RECTANGULAR (2026-08-09), so the measured signal is the
                # UNIFORM average of T over [lam - B/2 ; lam + B/2] and its second-order
                # error is T''.B^2/24. But `curvature` above is a SECOND DIFFERENCE over
                # +/- test_bw/2, which is T''.test_bw^2/8. The two are not the same
                # quantity, and the ratio of the true limit to the coded one is
                # sqrt(24/8) = sqrt(3) = 1.732.
                #
                # 📏 Verified numerically against a direct boxcar integration: 1.7321 on
                # a pure quadratic, 1.7323 / 1.7305 / 1.7252 on cosines of period 200 /
                # 20 / 10 nm -- the small drift being the second-order expansion giving
                # way when the structure gets fine compared with B.
                #
                # 🟢 The correction WIDENS the admissible slits, so it hands back the
                # /1.5 noise bonus to strategies that were denied it for nothing.
                res_limit = test_bw * np.sqrt(3.0 * T_tolerance / curvature)
            else:
                res_limit = 100.0

            if res_limit < min_resolution:
                min_resolution = res_limit
                worst_layer = i_layer + 1

    return min_resolution, worst_layer, signed_curvature


#: Gauss-Legendre nodes and weights for the boxcar average over the slit. Three nodes
#: integrate a degree-5 polynomial exactly, so a profile built on them is exact through
#: the FOURTH order in B where the second-difference model stopped at the second -- and
#: the odd orders vanish by symmetry, so 3 nodes buy two orders, not one.
_SLIT_GL_X, _SLIT_GL_W = np.polynomial.legendre.leggauss(3)


#: Profiles live longer than one call, because `_prepare_robustness_inputs` runs many
#: times per pipeline -- screening, local search, each block, the final ranking.
#:
#: 📏 Measured 2026-08-11 on a reference run: a per-call cache made the precomputation
#: **28 calls, 64.1 s, 8.8 % of RUN_S = 725.8 s**, when a single call costs 2.3 s. The
#: same profiles were being rebuilt twenty-eight times. 👤 asked for fidelity "without
#: exploding the time budget" -- so this is not an optimisation, it is the constraint.
#:
#: ⚠️ THE KEY CARRIES THE SUBSTACK, not just the layer index. Two runs on two different
#: designs share this process; keying on (layer, wavelength) alone would hand the second
#: one the first one's curvature, which is the silent-wrong-answer failure this project
#: exists to avoid. Nominal thicknesses are exact float64 read from the design, so they
#: compare exactly -- this is a lookup, never a tolerance.
_SLIT_PROFILE_CACHE: dict[tuple, np.ndarray] = {}


#: Bounded so a long session cannot grow it without limit. 48 layers x ~250 candidate
#: wavelengths is ~12000 entries of 17 float64 -- about 1.6 MB, so this ceiling is
#: generous on memory and still bounds the worst case.
_SLIT_CACHE_MAX: int = 60000


#: One-shot guard so the warning below names the problem without flooding 48 layers of log.
_SLIT_PHASE_A_WARNED: bool = False


def _slit_bias_profiles(
    strategy: dict[str, Any],
    p_thick_nominal: list[float],
    params: dict[str, Any],
    slit_b: float,
    cache: dict[tuple, np.ndarray] | None = None,
    only_layers: range | None = None,
) -> np.ndarray:
    """Slit bias of every layer as a FUNCTION of its thickness, shape (n_layers, nodes).

    Replaces the single number per layer that `signed_curvature` fed. Two things change,
    and only the first is the point:

    🔑 1. THE BIAS NOW VARIES ALONG THE GROWTH. A constant added to the read signal is
    exactly the ``b`` of ``T -> a.T + b``, which 12.1 proved POEM rigorously invariant
    to. The old model therefore gave POEM the one shape it absorbs for free. 📏 Measured
    on the judge of paix at 544 nm with B = 2 nm, the bias moves by up to **62 A** inside
    a single layer while its mean magnitude is 35 A -- so the part that was modelled was
    the harmless one and the part that bites was absent.

    2. THE BOXCAR IS INTEGRATED, NOT EXPANDED. `<T>_B - T(lambda)` is evaluated by
    Gauss-Legendre instead of truncated at `T''.B^2/24`. The expansion was checked
    against direct integration and sat within 0.90 to 1.19 of the truth -- acceptable,
    but free to remove, and it degrades exactly where the structure gets fine compared
    with B, which is where the bias matters most.

    ⚠️ THE PROFILE IS BUILT ON THE NOMINAL STACK, once per (layer, wavelength), OUTSIDE
    the Monte-Carlo. Per draw the substack below differs by a few nm and the true
    curvature with it; modelling that would put a spectral integration inside the hot
    loop, which is the cost 12.7 warned about. The systematic part -- the whole of the
    effect at first order -- is captured; the draw-to-draw modulation of it is not, and
    that is a stated approximation, not an oversight.

    The cache is shared across strategies AND across calls, which is what makes this
    affordable: strategies differ in how they GROUP layers, far less in which wavelengths
    they use, so the same profiles are requested over and over.
    """
    from certus.core.certus_strat_config import APP_CONTEXT
    from certus.utils.certus_strat_service import calculate_RT_normal_real
    if cache is None:
        cache = _SLIT_PROFILE_CACHE
        if len(cache) > _SLIT_CACHE_MAX:
            cache.clear()
    nH_id, nL_id, nSub_id = params["nH_id"], params["nL_id"], params["nSub_id"]
    db_local = (
        params.get("materials_db_instance")
        or params.get("materials_db")
        or APP_CONTEXT.get("materials_db")
    )
    layer_to_wl: dict[int, float] = {}
    for block in strategy["blocks"]:
        for layer_idx in range(block["start"], block["end"]):
            layer_to_wl[layer_idx] = float(block["wavelength"])

    n_layers = len(p_thick_nominal)
    out = np.zeros((n_layers, SLIT_PROFILE_NODES), dtype=np.float64)
    # The axis the kernel reads on: u = d / d_nominal over [0, D_SCAN_VAL].
    us = np.linspace(0.0, D_SCAN_VAL, SLIT_PROFILE_NODES)
    half = slit_b / 2.0

    # Identity of the optical problem, shared by every layer of this call.
    mat_key = (nH_id, nL_id, nSub_id, round(slit_b, 6), id(db_local))
    # Phase A only ever needs the rows the kernel will read -- the current layer and at
    # most MAX_LOOKBACK_VAL of block history. Computing all 48 for each of ~250 candidate
    # wavelengths would be a fivefold waste on the one stage where the count is large.
    for i_layer in (range(n_layers) if only_layers is None else only_layers):
        wl_mon = layer_to_wl.get(i_layer, float(params.get("l0", 550.0)))
        # 🔴 The SUBSTACK is part of the key, not just the layer index -- see the note on
        # `_SLIT_PROFILE_CACHE`. Two designs sharing a process must not share a curvature.
        key = (mat_key, round(wl_mon, 4), tuple(p_thick_nominal[: i_layer + 1]))
        hit = cache.get(key)
        if hit is not None:
            out[i_layer, :] = hit
            continue
        # The three quadrature wavelengths, then the monochromatic centre LAST so the
        # subtraction below reads off a fixed index.
        wls = [max(0.1, wl_mon + half * x) for x in _SLIT_GL_X] + [wl_mon]
        d_nom = float(p_thick_nominal[i_layer])
        base = list(p_thick_nominal[:i_layer])
        row = np.zeros(SLIT_PROFILE_NODES, dtype=np.float64)
        for iu, u in enumerate(us):
            RT = calculate_RT_normal_real(
                wls, nH_id, nL_id, nSub_id, base + [u * d_nom], db_instance=db_local  # type: ignore[arg-type]
            )
            T = RT[:, 1]
            row[iu] = float(np.dot(_SLIT_GL_W, T[:3]) / 2.0 - T[3])
        cache[key] = row
        out[i_layer, :] = row
    return out


#: The four widths the machine offers, widest first. 👤 12.7: four settings, four table
#: entries, never a law -- a law would authorise widths that do not exist on the OMS.
RESOLUTION_SEARCH_SET: tuple[float, ...] = (5.0, 2.0, 1.0, 0.5)


def _strategy_resolution(strategy: dict[str, Any], params: dict[str, Any]) -> float:
    """Slit width this strategy is evaluated at. Falls back to the run-level setting."""
    raw = strategy.get("monochromator_resolution_nm")
    if raw is None:
        raw = params.get("monochromator_resolution_nm", NOMINAL_RESOLUTION_NM)
    return float(raw or NOMINAL_RESOLUTION_NM)


def phase_a_slit_profiles(
    candidate_wls: np.ndarray,
    p_thick_nominal: list[float],
    params: dict[str, Any],
    i_layer: int,
) -> np.ndarray | None:
    """Per-CANDIDATE slit profiles for Phase A, shape (n_candidates, n_layers, nodes).

    🔴 WHY PHASE A NEEDS THIS AT ALL. 12.2 requires both stages to model the same
    machine, and 17-23 already lists six model parameters Phase A leaves at their neutral
    value. The slit was the seventh, and it is the one that changes WHICH WAVELENGTH gets
    picked: Phase A ranks candidates by dynamic range, the best dynamic range sits at the
    band edge, and 📏 at 48 layers the spectral ripple there has a period of 7.2 nm for a
    2 nm slit -- the machine averages over a quarter of a ripple. Judging blind to that is
    choosing precisely the wavelengths the real instrument cannot use.

    ⚠️ ONE PROFILE MATRIX PER CANDIDATE, because the bias depends on the monitoring
    wavelength and that is exactly what this stage varies. Handing every candidate the
    same matrix would be a filter that cannot discriminate -- 20-control 4, the inert
    rule that rejects nothing and reports no error.

    Returns None when the bias is off, which the kernel reads as "no slit effect" and
    which is bit-identical to the historical path.
    """
    if not bool(params.get("slit_bias_enabled", True)):
        return None
    # ⚠️ NOT a silent fallback -- 17-25. Some callers of Phase A hand it a params dict
    # without the material ids (narrow unit tests of the plumbing, where the physics is
    # monkeypatched away). Crashing them would be wrong, but so would dropping the bias
    # without saying so: "no profile" IS a physics change. Hence one loud warning, once.
    if any(params.get(k) is None for k in ("nH_id", "nL_id", "nSub_id")):
        global _SLIT_PHASE_A_WARNED
        if not _SLIT_PHASE_A_WARNED:
            _SLIT_PHASE_A_WARNED = True
            logging.getLogger(__name__).warning(
                "[SLIT] Phase A without nH_id/nL_id/nSub_id: the slit bias is NOT "
                "applied to the wavelength selection. Phase A therefore judges a "
                "perfect monochromator while Phase B simulates a slit (12.2)."
            )
        return None
    slit_b = float(params.get("monochromator_resolution_nm", 2.0) or 2.0)
    n_layers = len(p_thick_nominal)
    if i_layer < 0 or i_layer >= n_layers:
        return None
    rows = range(max(0, i_layer - MAX_LOOKBACK_VAL), i_layer + 1)
    out = np.zeros((len(candidate_wls), n_layers, SLIT_PROFILE_NODES), dtype=np.float64)
    for c_idx, wl in enumerate(candidate_wls):
        strat = {"blocks": [{"start": rows.start, "end": i_layer + 1,
                             "wavelength": float(wl)}]}
        prof = _slit_bias_profiles(strat, p_thick_nominal, params, slit_b,
                                   only_layers=rows)
        out[c_idx, rows.start : i_layer + 1, :] = prof[rows.start : i_layer + 1, :]
    return out
