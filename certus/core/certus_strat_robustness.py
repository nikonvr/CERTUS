"""
CERTUS STRAT ROBUSTNESS
=======================
Part of CERTUS Suite (Refactoring 2026)

Contains:
- run_final_simulation_block (Phase B robustness screening)
- _IdxWrapper helper
- _test_strategy_robustness_task
- _execute_robustness_tasks
- _prepare_robustness_inputs
- _resolve_robustness_noise_levels
- _prepare_robustness_nominal_optics
- _filter_valid_robustness_strategies
- _finalize_robustness_results
- _calculate_strategy_spectral_resolution
- _build_layer_wavelengths_from_strategy
- _validate_strategy_min_transmission_floor
"""

import logging
import concurrent.futures
import numpy as np
import pandas as pd
from typing import Any

from certus_physics import (
    CRASH_LEVEL_UNREACHABLE,
    CRASH_NON_MONOTONIC,
    CRASH_SENTINEL_MIN,
    CRASH_SENTINEL_UNIT,
    CRASH_TP_MISCOUNT,
    NON_MONOTONIC_MODE_ATTENUATE,
    arange_inclusive,
    calculate_RT_batch_kernel,
    calculate_RT_vectorized_real_HL,
    compute_batch_rmse,
    corridor_wl_range,
    precompute_matrix_cache_kernel,
    simulate_stack_robustness_batch,
)

from certus.core.certus_core import (
    NUMERICAL_FAULT_EXCEPTIONS,
    get_safe_worker_count,
)

from certus.utils.certus_exclusions import filter_params_for_gui

from certus.core.certus_strat_config import (
    APP_CONTEXT,
    RobustnessContext,
    SYM_DEFAULT_EXTREMA_WINDOW_OT,
    precompute_clues_and_matrices,
    _emit_stat,
)

from certus.core.certus_strat_objectives import (
    _compute_dT_dd_per_layer,
    build_M_before_cache,
    _compute_theoretical_layer_profile,
    _compute_strategy_symmetry_score_percent,
)

from certus.utils.certus_strat_context import (
    _validate_strategy_blocks_contract,
    _strategy_signature,
)

from certus.utils.certus_strat_service import (
    compute_probe_offset_nm_from_ratio,
    select_best_strat_result,
    calculate_RT_normal_real,
)

from certus.core.certus_strat_ranking import (
    _filter_valid_robustness_strategies,
    _select_best_strat_result,
)


# Non-terminating deposition rate beyond which a strategy is ELIMINATED.
#
# A non-terminating deposition is a lost run in the cleanroom, not a quality
# compromise: the strategy is removed from the ranking instead of being penalized. Below
# the threshold, the randomness is deemed acceptable given the potential spectral gain.
#
# rmse_p95 CANNOT replace this check: being a 95th percentile, it is
# structurally blind to any event occurring in less than 5% of the runs.
CRASH_RATE_TOLERANCE = 0.05


class _IdxWrapper:
    """Dict-like wrapper supporting both ``dict.get`` and ``list[idx]`` access."""

    __slots__ = ("obj", "_is_dict")

    def __init__(self, obj) -> None:
        self.obj = obj
        self._is_dict = hasattr(obj, "get")

    def __getitem__(self, k) -> Any:
        return self.obj.get(k) if self._is_dict else self.obj[k]

    def __contains__(self, k) -> bool:
        if hasattr(self.obj, "__contains__"):
            return k in self.obj
        if self._is_dict:
            return self.obj.get(k) is not None
        return False


class _SafeLocalClues(dict):
    """Fallback cache dictionary for clues, optimized for Top 1%."""

    __slots__ = ("_original",)

    def __init__(self, original, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original = _IdxWrapper(original)

    def get(self, wl: float, default=None) -> Any:
        wl_f = float(wl)
        if super().__contains__(wl_f):
            return super().__getitem__(wl_f)
        try:
            res = self._original[wl_f]
            self[wl_f] = res
            return res
        except Exception:
            return default

    def __getitem__(self, wl) -> Any:
        res = self.get(wl)
        if res is None:
            raise KeyError(wl)
        return res

    def __contains__(self, wl) -> bool:
        wl_f = float(wl)
        if super().__contains__(wl_f):
            return True
        return wl_f in self._original


def _parse_noise_factors(raw_factors) -> list[float]:
    if isinstance(raw_factors, str):
        try:
            cleaned = raw_factors.replace("[", "").replace("]", "").strip()
            return [float(x.strip()) for x in cleaned.split(",") if x.strip()]
        except Exception:
            return [0.5, 1.0, 2.0]
    if isinstance(raw_factors, list):
        return [float(x) for x in raw_factors]
    return [0.5, 1.0, 2.0]


#: 👤 Noise factor on A for each available monochromator slit, 2026-08-09.
#:
#: 🔴 A TABLE, NEVER A LAW, and the distinction is not pedantry. These four values are
#: 👤 *"estimated by me at feeling"* -- a modelling postulate like 9bis, not a
#: constructor specification. Fitting a power law to them would invent a model on
#: invented numbers, AND it would let the search propose slits the machine does not
#: have. Four settings, four table entries.
#:
#: ⚠️ Any conclusion drawn from these is physics only if it SURVIVES their uncertainty.
#: 12.7 requires a sensitivity control -- redo the comparison with /1.2 and x3 instead
#: of /1.5 and x5; if the winning resolution changes, the conclusion rests on a feeling
#: and that must be said in the same sentence.
RESOLUTION_NOISE_FACTOR: dict[float, float] = {5.0: 1.0 / 1.5, 2.0: 1.0, 1.0: 2.0, 0.5: 5.0}

#: Nominal slit, the one the measured noise amplitude corresponds to (👤 2026-08-09).
NOMINAL_RESOLUTION_NM: float = 2.0


def _resolution_noise_factor(params: dict[str, Any]) -> float:
    """Noise multiplier for the configured slit. 1.0 at the nominal 2 nm, hence C1.

    🔴 IT MULTIPLIES THE SAMPLE, NEVER THE SEED -- constraint C2, and the failure it
    prevents would be invisible. Folding the slit into the seed would make the four
    resolutions see four DIFFERENT random realisations, so the gap between them would no
    longer be attributable to the resolution. All four figures would look perfectly
    plausible. Scaling the amplitude keeps the draws identical and only their size
    changes.
    """
    raw = params.get("monochromator_resolution_nm")
    if raw is None:
        return 1.0
    try:
        slit = float(raw)
    except (TypeError, ValueError):
        return 1.0
    factor = RESOLUTION_NOISE_FACTOR.get(slit)
    if factor is None:
        # An unavailable slit is a configuration error, not something to interpolate:
        # a law over four estimated points would authorise settings the machine has not.
        raise ValueError(
            f"monochromator_resolution_nm={slit} is not one of "
            f"{sorted(RESOLUTION_NOISE_FACTOR)} -- the four values the machine offers. "
            "There is no law to interpolate between them (12.7)."
        )
    return factor


def _resolve_robustness_noise_levels(params: dict[str, Any]) -> list[float]:
    """Resolve robustness noise-level vector from STRAT params."""
    noise_factors = _parse_noise_factors(params.get("robustness_noise_factors", [0.5, 1.0, 2.0]))
    if params.get("thickness_tolerance_nm") is not None:
        base_tol = float(params.get("thickness_tolerance_nm"))
        return [base_tol * f * _resolution_noise_factor(params) for f in noise_factors]

    try:
        base_noise = float(params["reality_sim_params"]["trigger_tolerance"])
    except KeyError, TypeError:
        base_noise = float(params.get("trigger_tolerance", 0.5))
    return [base_noise * f * _resolution_noise_factor(params) for f in noise_factors]


#: 👤 The cause is named in PHYSICAL WORDS, never by its sentinel. `CRASH_TP_MISCOUNT`
#: tells a chamber operator nothing about what to watch; "ripple too faint to be seen"
#: does. Decided 2026-08-10.
_CAUSE_WORDS = {
    "level": "niveau d'arret hors d'atteinte",
    "missed": "ondulation trop faible pour etre vue",
    "fabricated": "point tournant fabrique par le bruit",
}


#: Above this many multiples of A a margin carries no ranking information: the draws are
#: bounded, so the event is impossible and one impossibility does not beat another. Kept
#: well above the 2 A verdict threshold so the boundary itself stays visible.
_MARGIN_REPORT_CEILING_A = 5.0


def _margin_profile_sparse(
    margin_profile: dict[str, np.ndarray], noise_amp: float
) -> dict[str, dict[str, float]]:
    """Per-layer margins, in multiples of A, keeping only what can ever matter.

    Sparse on purpose. A healthy stack has most layers far from any failure, so a dense
    48-long list per cause per strategy would be mostly `null` -- weight without
    information, and 228 strategies of it. Absence of a layer therefore reads as "not
    constrained here", which is the honest statement.

    ⚠️ Rounded to 3 decimals: the margin inherits the ~6 % Monte-Carlo dispersion of the
    run (17-26), so further digits are noise dressed as precision.
    """
    if noise_amp <= 0.0:
        return {}
    out: dict[str, dict[str, float]] = {}
    for cause, arr in margin_profile.items():
        hits = {
            str(i): round(float(v) / noise_amp, 3)
            for i, v in enumerate(arr)
            if np.isfinite(v) and v / noise_amp < _MARGIN_REPORT_CEILING_A
        }
        if hits:
            out[cause] = hits
    return out


def _critical_layer(margin_profile: dict[str, np.ndarray], noise_amp: float) -> dict[str, Any]:
    """The layer that will give way first, its cause, and its margin in multiples of A.

    🔑 WHY A MARGIN AND NOT A RATE. On this stack every strategy reads 0 crashes out of
    150 draws, which says p < 2 % and nothing more. A rate cannot rank what never
    failed. A margin is continuous, always defined, and it designates the binding layer
    even when the yield is a perfect 100 %.

    🔴 AND WHY MULTIPLES OF A. The draws of this model are BOUNDED -- reading noise
    lives in +/-A, the corridor respects |a|+|b| <= delta_max. So a margin larger than
    the largest possible perturbation does not mean "unlikely", it means the event
    CANNOT HAPPEN. A23 fixes the reporting rule that follows: beyond 2 A one writes
    "impossible", never a probability. Writing "0.1 %" there would be false, and false
    in the direction that makes a good strategy be discarded.

    ⚠️ `inf` means "this cause never constrained this layer", which is not the same as
    a large margin and is why it is filtered rather than averaged.
    """
    if noise_amp <= 0.0:
        return {}
    best_key, best_layer, best_margin = "", -1, np.inf
    for key, arr in margin_profile.items():
        if arr.size == 0:
            continue
        finite = np.isfinite(arr)
        if not finite.any():
            continue
        idx = int(np.argmin(np.where(finite, arr, np.inf)))
        val = float(arr[idx])
        if val < best_margin:
            best_key, best_layer, best_margin = key, idx, val
    if best_layer < 0:
        return {}
    in_a = best_margin / noise_amp
    # Multiplicity matters as much as the minimum: one layer at 0.6 A is not the same
    # profile as twelve under 1 A, and an operator reads that difference immediately.
    n_below_2a = int(sum(
        int(np.count_nonzero(np.isfinite(arr) & (arr < 2.0 * noise_amp)))
        for arr in margin_profile.values()
    ))
    return {
        "layer": best_layer,                 # 0-based, as everywhere in the kernel
        "cause": _CAUSE_WORDS.get(best_key, best_key),
        "margin_in_A": in_a,
        # 🔴 The rule that is not negotiable: bounded draws mean p = 0 EXACTLY beyond
        # the largest possible perturbation, so no probability is quoted there.
        "verdict": "PEUT ECHOUER" if in_a <= 2.0 else "impossible",
        "n_layers_below_2A": n_below_2a,
    }


def _phase_a_forced_layers(params: dict[str, Any]) -> dict[str, Any]:
    """How many layers Phase A had NO admissible wavelength for -- 17-37.

    When no candidate meets the crash tolerance on a layer, Phase A keeps the least
    bad one and logs a warning. That is the right behaviour -- returning nothing would
    stop the search -- but it means the wavelength was **not chosen, it was forced**,
    and until now nothing said so beyond a per-layer log line.

    🔴 WHY THIS MATTERS ENOUGH TO CARRY IN EVERY RESULT. Measured on 2026-08-11, at a
    corridor of 0.010 on seed 77: 108 candidates offered, 103 forbidden, a median of
    ONE survivor per layer, and 32 of 48 layers on the fallback -- at a minimum
    observed crash rate of 0.7 %, seven times the tolerance. Phase B then found that
    strategy crashes 100 % of the time. And the final result announced a winner with a
    score and a SEEL, indistinguishable from a healthy run.

    A strategy built on 32 forced layers is not comparable to a freely chosen one. This
    is a run-level property: every strategy of a given Phase A inherits the same forced
    layers, so it qualifies the whole candidate pool, not one candidate.
    """
    stats = params.get("phase_a_admissibility_stats") or []
    if not stats:
        return {}
    forced = [int(s.get("layer", 0)) for s in stats if s.get("fallback_on_min_crash")]
    return {
        "n_forced": len(forced),
        "n_layers": len(stats),
        "layers": forced,                       # 1-based, as the admissibility census is
    }


def _worst_layer_swing(results_per_noise: list[dict[str, Any]]) -> dict[str, Any]:
    """Poorest optical swing across layers, and where it sits.

    The batch already returns the average dynamic range per layer; it was stored and
    never read. The MINIMUM over layers is the quantity that binds: 14-5 states that
    the trigger is precise in proportion to the swing, so the layer with the poorest
    swing is the one whose stopping level is most exposed to reading noise.

    Read at the NOMINAL noise level only. Mixing noise levels here would compare a
    strategy against itself under three different machines -- and the swing is a
    property of the signal, not of the noise.
    """
    for entry in results_per_noise:
        dyns = entry.get("avg_dynamics")
        if not dyns:
            continue
        arr = np.asarray(dyns, dtype=np.float64)
        if arr.size == 0:
            continue
        idx = int(np.argmin(arr))
        return {
            "layer": idx,          # 0-based, as everywhere in the kernel
            "swing": float(arr[idx]),
            "median_swing": float(np.median(arr)),
            "n_below_swing_min": int(np.count_nonzero(arr < 0.04)),  # SWING_MIN
        }
    return {}


def _prepare_robustness_nominal_optics(
    params: dict[str, Any],
    p_thick_nominal: list[float],
    opti_results: dict[str, Any] | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Generates nominal wavelength and index arrays, plus nominal transmission."""
    wl_range_scan = params["wl_range"]
    wl_step = float(params["wl_step"])
    wl_arr = arange_inclusive(wl_range_scan[0], wl_range_scan[1], wl_step)

    clues_at_wl = opti_results.get("clues_at_wl") if opti_results else None

    db_bypassed = False
    if clues_at_wl:
        try:
            # Safely check if clues are accessible either by float or object
            from certus.core.certus_strat_config import _IdxWrapper

            idx_dict = _IdxWrapper(clues_at_wl)

            nH_list = []
            nL_list = []
            nSub_list = []
            for w in wl_arr:
                val = idx_dict[float(w)]
                nH_list.append(val["H"])
                nL_list.append(val["L"])
                nSub_list.append(val["substrate"])

            nH_arr = np.array(nH_list, dtype=np.complex128)
            nL_arr = np.array(nL_list, dtype=np.complex128)
            nSub_arr = np.array(nSub_list, dtype=np.complex128)
            db_bypassed = True
        except Exception:
            pass

    if not db_bypassed:
        local_db = params.get("materials_db_instance") or params.get("materials_db") or APP_CONTEXT.get("materials_db")
        from certus.core.certus_strat_config import get_refractive_clues_vectorized

        nH_arr = get_refractive_clues_vectorized(params["nH_id"], wl_arr, db_instance=local_db)
        nL_arr = get_refractive_clues_vectorized(params["nL_id"], wl_arr, db_instance=local_db)
        nSub_arr = get_refractive_clues_vectorized(params["nSub_id"], wl_arr, db_instance=local_db)

    p_thick_nom_arr = np.array(p_thick_nominal, dtype=np.float64)
    _, T_nom = calculate_RT_vectorized_real_HL(wl_arr, nH_arr, nL_arr, nSub_arr, p_thick_nom_arr)
    return wl_arr, nH_arr, nL_arr, nSub_arr, T_nom


# _filter_valid_robustness_strategies has been moved to certus_strat_ranking.py


def _prepare_robustness_inputs(
    opti_results: dict[str, Any],
    params: dict[str, Any],
    num_runs: int,
    noise_levels: list[float] | None,
    logger: logging.Logger,
) -> tuple[list[dict[str, Any]], list[float], list[float], int]:
    """Validates and prepares robustness initial inputs."""
    if not opti_results or "all_strategies" not in opti_results:
        raise ValueError("Invalid optimization results for simulation.")
    if noise_levels is None:
        noise_levels = _resolve_robustness_noise_levels(params)
    if noise_levels:
        total_mc_runs = num_runs * len(noise_levels)
        _emit_stat("MCS", total_mc_runs)
    all_strategies_in = opti_results["all_strategies"]
    p_thick_nominal = opti_results["p_thick_nominal"]
    num_layers = len(p_thick_nominal)
    all_strategies = _filter_valid_robustness_strategies(
        all_strategies_in,
        num_layers=num_layers,
        logger=logger,
    )
    all_strategies = _expand_with_rate_variants(all_strategies, params, num_layers, logger)
    return all_strategies, noise_levels or [], p_thick_nominal, num_layers


#: At most this many Rate variants per strategy, and the DEEPEST boundaries win.
#: 👤 asked for the trial "on the 10 best strategies", not on everything: an unbounded
#: expansion costs a factor 6 on the whole Monte-Carlo for candidates nobody asked about.
RATE_MAX_VARIANTS_PER_STRATEGY: int = 3

#: Below this many layers per block, a "block boundary" says nothing -- every layer is
#: one. See the measurement in `_rate_candidate_layers`.
RATE_MIN_LAYERS_PER_BLOCK: float = 3.0


def _rate_candidate_layers(strategy: dict[str, Any], num_layers: int) -> list[int]:
    """Layers where a Rate is CHEAPEST: the last layer of each block.

    👤 2026-08-11: *"test the rate on layers i whose control wavelength changes at layer
    i+1, because there will be no POEM on the next layer anyway"*. Verified in the
    kernel and it is exact -- `block_start[i+1] = i+1` at a wavelength change, so
    `n_hist = 0` and the next layer starts with no inherited anchors whatever layer i
    did. 14-10 lists three costs for a Rate layer and a block boundary already pays two
    of them: the lost anchors, and the turning-point count that restarts anyway.

    ⚠️ The last layer of the stack is deliberately EXCLUDED. It has no successor, so the
    downstream cost is nil there too -- but it is also the last chance to correct
    everything accumulated since layer 1, and the two pull opposite ways. It deserves
    its own experiment, not a free ride in this one (A24).
    """
    blocks = strategy.get("blocks") or []
    if not blocks:
        return []
    # 🔴 A "block boundary" only carries information when blocks ARE blocks. Measured
    # 2026-08-11: on a 48-block strategy -- one wavelength per layer -- EVERY layer is a
    # boundary, and the placement degenerates into the exhaustive sweep this was chosen
    # to avoid: 47 variants from a single strategy, 1122 over the reference ranking, a
    # sixfold Monte-Carlo cost. Below this many layers per block the insight is vacuous.
    if num_layers / len(blocks) < RATE_MIN_LAYERS_PER_BLOCK:
        return []
    out: list[int] = []
    for blk in blocks:
        end = int(blk.get("end", 0))
        last = end - 1                       # last layer of this block
        if 0 <= last < num_layers - 1:       # excludes the final layer of the stack
            out.append(last)
    # Deepest first: A24 measured that a Rate layer inherits an error falling as
    # 1/sqrt(n) with the number of reference layers of its material, so it is at its
    # most accurate late in the stack -- which is also where 17-36 measured that every
    # crash happens. The cap therefore keeps the boundaries that matter most.
    out.sort(reverse=True)
    return out[:RATE_MAX_VARIANTS_PER_STRATEGY]


def _expand_with_rate_variants(
    strategies: list[dict[str, Any]],
    params: dict[str, Any],
    num_layers: int,
    logger: logging.Logger,
) -> list[dict[str, Any]]:
    """Add Rate variants of each strategy, so the ranking can compare them side by side.

    👤 *"The user must be able, in the final table, to allow or refuse the rate. Then the
    best strategies appear."* So Rate is not a hidden fallback: it produces ADDITIONAL
    candidates that stand or fall on the same statistics as everything else.

    🔴 OFF BY DEFAULT (`allow_rate`), and that is C1: with the key absent the list comes
    back untouched and every downstream bit is what it was.

    ⚠️ ONE Rate layer per variant, deliberately. Two Rate layers interact -- the second
    inherits an estimate the first already froze -- and 12.3's lesson is that two things
    changed at once cannot be attributed. Combinations come after single layers are
    understood, not before.
    """
    if not bool(params.get("allow_rate", False)):
        return strategies
    variants: list[dict[str, Any]] = []
    skipped = 0
    next_id = 990_000_000
    for strat in strategies:
        cands = _rate_candidate_layers(strat, num_layers)
        if not cands:
            skipped += 1
        for layer in cands:
            v = dict(strat)
            v["blocks"] = list(strat.get("blocks") or [])
            v["rate_layers"] = [layer]
            v["strategy_id"] = next_id
            v["origin"] = f"RATE_L{layer}(from {strat.get('strategy_id', '?')})"
            next_id += 1
            variants.append(v)
    if variants or skipped:
        logger.info(
            f"[RATE] {len(variants)} variantes sur {len(strategies)} strategies, "
            f"{RATE_MAX_VARIANTS_PER_STRATEGY} au plus chacune, frontieres les plus "
            f"PROFONDES d'abord. {skipped} strategie(s) ecartee(s) : moins de "
            f"{RATE_MIN_LAYERS_PER_BLOCK:g} couches par bloc, ou une frontiere ne dit rien."
        )
    return strategies + variants


def _calculate_strategy_spectral_resolution(strategy, p_thick_nominal, params) -> tuple:
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
    layer_to_wl = {}

    for block in blocks:
        for l in range(block["start"], block["end"]):
            layer_to_wl[l] = float(block["wavelength"])

    num_layers = len(p_thick_nominal)
    for i_layer in range(num_layers):
        wl_mon = layer_to_wl.get(i_layer, float(params.get("l0", 550.0)))
        current_stack_thick = p_thick_nominal[: i_layer + 1]
        wls_check = [max(0.1, wl_mon - half_bw), wl_mon, wl_mon + half_bw]

        RT = calculate_RT_normal_real(wls_check, nH_id, nL_id, nSub_id, current_stack_thick, db_instance=db_local)
        T_vals = RT[:, 1]

        if len(T_vals) == 3:
            curvature = abs((T_vals[0] + T_vals[2]) / 2.0 - T_vals[1])
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

    return min_resolution, worst_layer


def _filter_finite_robustness_scores(
    strategies_results: list[dict[str, Any]],
    *,
    logger,
) -> list[dict[str, Any]]:
    """Keep only strategies with finite robustness score.

    🔴 WITH A MANDATORY FALLBACK: this filter must NEVER return an empty list.

    Crash rate COMPOSES across stack height. On 48 layers, holding 5% at strategy
    level requires 1 - (1 - 0.05)^(1/48) = 0.107% per layer. It is a cliff, not a continuous ranking:
    either all strategies pass, or none.

    Measurement on 48-layer dichroic pass-band filter:
        mined strategies .................. 240
        valid after contract .............. 240
        crash_rate ......... min 0.833  median 1.000
        survivors ........................   0   <- STRAT returned NOTHING

    Returning an empty list propagates `all_strategies_results = []` up to the runner,
    displaying RESULT=None. It is better to return the least risky strategy with explicit reporting.
    """
    filtered_results: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for item in strategies_results:
        score = float(item.get("robustness_score", np.inf))
        if np.isfinite(score):
            filtered_results.append(item)
        else:
            rejected.append(item)
            logger.warning(
                f"[ROBUSTNESS] Dropped non-finite score for strategy "
                f"{item.get('strategy', {}).get('strategy_id', '?')}: {score}"
            )

    if filtered_results or not rejected:
        return filtered_results

    # No survivor: we re-rank the eliminated ones by increasing risk and we
    # return a finite score to them, otherwise they would be lost later.
    def _fallback_key(it: dict[str, Any]) -> tuple[float, float]:
        return (float(it.get("crash_rate", 1.0)), _worst_finite_rmse(it))

    rejected.sort(key=_fallback_key)
    best_crash = float(rejected[0].get("crash_rate", 1.0))
    logger.error(
        f"[ROBUSTNESS] 🔴 NONE of the {len(rejected)} strategies holds under "
        f"{CRASH_RATE_TOLERANCE:.0%} of non-terminating depositions. The rate compounds "
        f"over the height of the stack: the best candidate crashes in "
        f"{best_crash:.1%} of the draws. We still return the ranking by increasing "
        f"risk — but NONE of these strategies is usable as is, and "
        f"the component likely requires another monitoring paradigm."
    )
    for item in rejected:
        item["robustness_score"] = _worst_finite_rmse(item)
        item["crash_eliminated"] = True
    return rejected


def _worst_finite_rmse(item: dict[str, Any]) -> float:
    """Worst finite RMSE on the noise levels, to re-rank an eliminated one."""
    worst = 0.0
    for r in item.get("results_per_noise", []) or []:
        val = float(r.get("rmse_p95", r.get("rmse_mean", 0.0)) or 0.0)
        if np.isfinite(val) and val > worst:
            worst = val
    return worst


def _execute_robustness_tasks(
    all_strategies: list[dict[str, Any]],
    noise_levels: list[float],
    num_runs: int,
    p_thick_nominal: list[float],
    clues_at_wl: dict[str, Any],
    params_safe: dict[str, Any],
    wl_arr: np.ndarray,
    nH_arr: np.ndarray,
    nL_arr: np.ndarray,
    nSub_arr: np.ndarray,
    T_nom: np.ndarray,
    full_dyn_grid: dict[str, Any],
    params: dict[str, Any],
    logger: logging.Logger,
    n_layers_matrix_precomp: np.ndarray | None = None,
) -> list[dict[str, Any]]:
    import multiprocessing

    max_workers = max(1, multiprocessing.cpu_count() // 2)
    logger.info(
        f"Running robustness tests on {len(all_strategies)} strategies (ThreadPoolExecutor with {max_workers} workers)..."
    )

    num_layers = len(p_thick_nominal)
    if n_layers_matrix_precomp is None:
        nH_c128 = nH_arr.astype(np.complex128)
        nL_c128 = nL_arr.astype(np.complex128)
        parity = np.arange(num_layers) % 2 == 0
        n_layers_matrix_precomp = np.where(
            parity[np.newaxis, :],
            nH_c128[:, np.newaxis],
            nL_c128[:, np.newaxis],
        )

    strategies_results = []
    enable_halving = bool(params.get("enable_successive_halving", False))
    if enable_halving and len(all_strategies) >= 10 and num_runs >= 30:
        logger.info(
            f"[HALVING] Successive Halving enabled on {len(all_strategies)} candidate strategies (target={num_runs} runs)..."
        )
        stage_budgets = [
            max(10, num_runs // 4),
            max(20, num_runs // 2),
        ]
        candidates = [(idx, strat) for idx, strat in enumerate(all_strategies)]
        executor_cls = concurrent.futures.ThreadPoolExecutor

        for stage_idx, stage_runs in enumerate(stage_budgets):
            stage_results = []
            with executor_cls(max_workers=max_workers) as executor:
                futures_dict = {
                    executor.submit(
                        _test_strategy_robustness_task,
                        strat,
                        idx,
                        noise_levels,
                        stage_runs,
                        p_thick_nominal,
                        clues_at_wl,
                        params_safe,
                        wl_arr,
                        nH_arr,
                        nL_arr,
                        nSub_arr,
                        T_nom,
                        full_dyn_grid,
                        n_layers_matrix_precomp=n_layers_matrix_precomp,
                        compute_layer_profile=False,
                    ): (idx, strat)
                    for idx, strat in candidates
                }
                for f in concurrent.futures.as_completed(futures_dict):
                    idx, strat = futures_dict[f]
                    try:
                        res = f.result()
                        score = float(res.get("robustness_score", np.inf))
                        crash_rate = float(res.get("crash_rate", 0.0))
                        if np.isfinite(score) and crash_rate < 0.25:
                            stage_results.append((score, idx, strat))
                    except Exception as e:
                        logger.warning(f"[HALVING] Candidate {idx} evaluation failed: {e}")

            if not stage_results:
                break
            stage_results.sort(key=lambda x: x[0])
            keep_count = max(8, len(stage_results) // 2)
            candidates = [(idx, strat) for _sc, idx, strat in stage_results[:keep_count]]
            logger.info(
                f"[HALVING] Stage {stage_idx+1}/{len(stage_budgets)} (runs={stage_runs}): "
                f"retained {len(candidates)}/{len(stage_results)} candidates."
            )

        all_strategies = [strat for _idx, strat in candidates]
        logger.info(f"[HALVING] Final stage ({num_runs} runs) on top {len(all_strategies)} candidates.")

    if max_workers <= 1:
        for idx, strat in enumerate(all_strategies):
            try:
                res = _test_strategy_robustness_task(
                    strat,
                    idx,
                    noise_levels,
                    num_runs,
                    p_thick_nominal,
                    clues_at_wl,
                    params_safe,
                    wl_arr,
                    nH_arr,
                    nL_arr,
                    nSub_arr,
                    T_nom,
                    full_dyn_grid,
                    n_layers_matrix_precomp=n_layers_matrix_precomp,
                )
                try:
                    min_res, bad_layer = _calculate_strategy_spectral_resolution(
                        res["strategy"], p_thick_nominal, params
                    )
                except Exception:
                    min_res, bad_layer = 999.0, -1
                res["min_resolution"] = min_res
                res["limiting_layer"] = bad_layer
                strategies_results.append(res)
            except Exception as e:
                logger.error(f"Strategy simulation failed: {e}", exc_info=True)
    else:
        results_by_idx: list[dict[str, Any] | None] = [None] * len(all_strategies)
        executor_cls = concurrent.futures.ThreadPoolExecutor

        with executor_cls(max_workers=max_workers) as executor:
            futures = {}
            for idx, strat in enumerate(all_strategies):
                f = executor.submit(
                    _test_strategy_robustness_task,
                    strat,
                    idx,
                    noise_levels,
                    num_runs,
                    p_thick_nominal,
                    clues_at_wl,
                    params_safe,
                    wl_arr,
                    nH_arr,
                    nL_arr,
                    nSub_arr,
                    T_nom,
                    full_dyn_grid,
                    n_layers_matrix_precomp=n_layers_matrix_precomp,
                )
                futures[f] = idx
            for f in concurrent.futures.as_completed(futures):
                idx = futures[f]
                try:
                    res = f.result()
                    try:
                        min_res, bad_layer = _calculate_strategy_spectral_resolution(
                            res["strategy"], p_thick_nominal, params
                        )
                    except Exception:
                        min_res, bad_layer = 999.0, -1
                    res["min_resolution"] = min_res
                    res["limiting_layer"] = bad_layer
                    results_by_idx[idx] = res
                except Exception as e:
                    logger.error(f"Strategy simulation failed: {e}", exc_info=True)
        strategies_results = [r for r in results_by_idx if r is not None]

    return _filter_finite_robustness_scores(strategies_results, logger=logger)


_SOBOL_NOISE_CACHE = {}

def _get_cached_sobol_noise(base_seed: int, noise_idx: int, num_runs: int, num_layers: int) -> np.ndarray:
    key = (base_seed, noise_idx, num_runs, num_layers)
    if key in _SOBOL_NOISE_CACHE:
        return _SOBOL_NOISE_CACHE[key]
        
    import math
    from scipy.stats import qmc, norm
    # Multiplicative mixing, NOT a sum.
    #
    # `base_seed + noise_idx` makes distinct pairs collide: the consensus
    # generates its seeds by `base_seed + i * stride` with a stride of 1 by default
    # (certus/utils/certus_strat_context.py:598 and :610), so (seed 42, level 1) and
    # (seed 43, level 0) both gave local_seed = 43 — the SAME noise.
    # The overlap is triangular and massive:
    #     3 seeds x 3 levels =  9 draws ->  5 distincts (44% lost)
    #     5 seeds x 4 levels = 20 draws ->  8 distincts (60% lost)
    #     8 seeds x 5 levels = 40 draws -> 12 distincts (70% lost)
    # Yet the consensus is supposed to average over INDEPENDENT seeds: sharing the
    # noise between members inflates their apparent agreement, thus overestimating robustness.
    #
    # The two constants are odd integers close to 2^32/phi and 2^16/phi:
    # they scatter the low-order bits, which are precisely the ones that varied
    # here (small and consecutive indices).
    #
    # NOTE: this fix changes the draws, so the robustness results are not
    # numerically comparable to before. It is inevitable — the old ones
    # were statistically biased.
    local_seed = (base_seed * 2_654_435_761 + noise_idx * 40_503) % (2**31)
    sobol_engine = qmc.Sobol(d=num_layers, seed=local_seed)
    n_pow2 = 2 ** math.ceil(math.log2(num_runs)) if num_runs > 0 else 0
    sobol_samples = sobol_engine.random(n=n_pow2)[:num_runs]
    
    # Inverse CDF transform (uniform to normal distribution N(0, 1/3))
    raw_noise = norm.ppf(sobol_samples, loc=0.0, scale=1.0 / 3.0)
    raw_noise = np.clip(raw_noise, -1.0, 1.0).astype(np.float64)
    
    _SOBOL_NOISE_CACHE[key] = raw_noise
    return raw_noise


def _signal_noise_stream_seed(base_seed: int, noise_idx: int) -> int:
    """Seed of the READ noise stream of the monitoring signal (axis 1.1).

    🔴 IT DEPENDS ONLY ON THE DRAW CONFIGURATION, NEVER ON THE STRATEGY.
    This is the condition for common random numbers: two strategies evaluated
    at the same (seed, noise level) see exactly the same read noise,
    and the difference in their scores remains attributable to the strategy alone. The same achievement
    as `_get_cached_sobol_noise` protects for the stopping noise — `_strat_idx` is
    deliberately unused there.

    Multiplicative and non-additive mixing, for the reason explained in
    `_get_cached_sobol_noise`: the consensus generates its seeds by
    `base_seed + i * stride` with a stride of 1 by default, so a sum
    would collide (seed 42, level 1) and (seed 43, level 0).

    The final constant distances this stream from the nucleation one, which calls the
    same `_seeded_noise_sample` with an unshifted `seed_base`.
    """
    mixed = int(base_seed) * 2_246_822_519 + int(noise_idx) * 668_265_263 + 0x5F35_6495
    return mixed % (2**53)


def _affine_stream_seed(base_seed: int, noise_idx: int) -> int:
    """Seed of the affine distortion stream (axis 1.1).

    🔴 IT DEPENDS ONLY ON THE DRAW CONFIGURATION, NEVER ON THE STRATEGY.
    This is the condition for common random numbers.
    """
    mixed = int(base_seed) * 3_266_489_917 + int(noise_idx) * 1_274_126_177 + 0x7E2A_8431
    return mixed % (2**53)


def _index_stream_seed(base_seed: int, noise_idx: int) -> int:
    """Seed of the index uncertainty stream (T5)."""
    mixed = int(base_seed) * 2_654_435_761 + int(noise_idx) * 850_507 + 0x3F1B_79C5
    return mixed % (2**53)


def _test_strategy_robustness_task(
    strategy,
    _strat_idx,
    noise_levels,
    num_runs,
    p_thick_nominal,
    clues_at_wl,
    params,
    wl_arr,
    nH_arr,
    nL_arr,
    nSub_arr,
    T_nom,
    full_dyn_grid,
    n_layers_matrix_precomp=None,
    compute_layer_profile: bool = True,
) -> dict:
    import numba

    numba.set_num_threads(2)
    logger = logging.getLogger("certus_strat")
    strategy = dict(strategy)
    blocks = strategy["blocks"]
    p_thick_nom_arr = np.array(p_thick_nominal, dtype=np.float64)
    num_layers = len(p_thick_nominal)
    offset_val = compute_probe_offset_nm_from_ratio(params)
    factor_val = float(params.get("non_monotonic_error_factor", 2.0))
    # Default MAINTAINED at 1.2, contrary to what I had done at one time.
    #
    # This factor increases the noise of the FIRST layer of each block to
    # represent the loss of history at the wavelength change. I had
    # thought I could neutralize it by implementing POEM, on the grounds that the benefit
    # of the blocks would become structural. IT WAS WRONG, and it must be said:
    #
    #   POEM as implemented sweeps from d = 0 of the CURRENT layer
    #   (certus_strat_growth.py) and only sees its own signal segment. It
    #   thus captures the INTRA-LAYER swing, but not the history of extrema
    #   observed during the previous layers of the same block.
    #
    # Monochromatic block history continuity: at unchanged wavelength the signal
    # is continuous, so previously observed turning points remain usable.
    # Zideluns et al., Opt. Express 29, 33398 (2021): "self-compensation operates
    # only at the monitored wavelength and diminishes when layers are monitored at
    # different wavelengths".
    penalty_factor = float(params.get("wavelength_change_penalty", 1.0))
    penalty_vector = np.ones(num_layers, dtype=np.float64)

    sorted_blocks = sorted(blocks, key=lambda b: b["start"])
    prev_wl = -1.0
    for i, blk in enumerate(sorted_blocks):
        current_wl = float(blk["wavelength"])
        if i > 0 and abs(current_wl - prev_wl) > 1e-3:
            start_layer_idx = blk["start"]
            if start_layer_idx < num_layers:
                penalty_vector[start_layer_idx] = penalty_factor
        prev_wl = current_wl

    results_per_noise = []
    crash_rate_max = 0.0  # worst non-terminating deposition rate across noise levels
    # Breakdown of crashes by CAUSE, worst case across noise levels.
    crash_rates_by_cause = {
        "p_level_unreachable": 0.0,
        "p_tp_miscount": 0.0,
        "p_non_monotonic": 0.0,
    }
    # A23 stage 0: crash count PER LAYER and per cause, worst case across noise levels.
    # Already computed inside the batch; only the reduction threw it away.
    # 🔴 NOT `layer_profile`: that name is reassigned at the theoretical-profile loop
    # below, from a dict of floats. Reusing it clobbered this accumulator silently and
    # the only symptom was an AttributeError three hundred lines later.
    n_lay_prof = len(p_thick_nominal)
    crash_layer_profile = {
        k: np.zeros(n_lay_prof, dtype=int)
        for k in ("total", "level_unreachable", "tp_miscount", "non_monotonic")
    }
    # A23 stage 2. inf = "never constrained by this cause on this layer", which is NOT
    # a large margin and must never be averaged into one.
    margin_profile = {
        k: np.full(n_lay_prof, np.inf) for k in ("level", "missed", "fabricated")
    }
    unique_wls = len(set(b["wavelength"] for b in blocks))
    complexity = unique_wls / len(blocks) if blocks else 0

    _, T_clean_batch = calculate_RT_batch_kernel(
        wl_arr,
        nH_arr.astype(np.complex128),
        nL_arr.astype(np.complex128),
        nSub_arr.astype(np.complex128),
        p_thick_nom_arr.reshape(1, -1),
    )
    T_nom_aligned = T_clean_batch[0].astype(np.float64)

    # ── AXIS 3: RANK AGAINST TARGET, NOT AGAINST NOMINAL ───────────────────────
    #
    # "The most important aspect is respecting the spectral target." Previously STRAT ranked on
    # deviation from the NOMINAL spectrum (unweighted), and never received targets —
    # zero occurrences of `targets` in the module. It answered "which strategy
    # best reproduces designed thickness spectrum?", not "which best respects target?".
    #
    # ⚠️ DISTINCTION TO PRESERVE (Physical): The TARGET POINT during growth
    # remains the frozen nominal — this is the auto-compensation mechanism itself, see
    #comment in `simulate_growth_kernel`. Only the RANKING FIGURE OF MERIT
    # switches to weighted target. This block touches nothing in growth kernel.
    #
    # The functional is the one that DESIGN already minimizes (`prepare_targets_vectorized`:
    # linear interpolation from tmin to tmax on the zone, weight = user weight x
    # spectral quadrature in d ln lambda). Both modules thus become coherent
    # instead of optimizing two different things.
    #
    # DOCUMENTED FALLBACK: without a provided target, we keep the unweighted nominal — therefore the
    # previous behavior, bit for bit. It is the presence of `targets` that activates
    # axis 3, not an additional flag.
    T_rank_target = T_nom_aligned
    rank_weights = None
    _raw_targets = params.get("targets")
    if _raw_targets:
        try:
            from certus_physics import prepare_targets_vectorized
            from certus_physics.structures import Target

            _tgts = [
                t
                if isinstance(t, Target)
                else Target(
                    lmin=float(t["lmin"]),
                    lmax=float(t["lmax"]),
                    tmin=float(t["tmin"]),
                    tmax=float(t["tmax"]),
                    w=float(t.get("w", 1.0)),
                    on=bool(t.get("on", True)),
                )
                for t in _raw_targets
            ]
            _vals, _w = prepare_targets_vectorized(wl_arr.astype(np.float64), _tgts)
            if float(np.sum(_w)) > 0.0:
                T_rank_target = np.asarray(_vals, dtype=np.float64)
                rank_weights = np.asarray(_w, dtype=np.float64)
            else:
                logger.warning(
                    "[TARGET] %d zone(s) provided but none covers the grid "
                    "%.0f-%.0f nm: fallback to the nominal spectrum.",
                    len(_tgts),
                    float(wl_arr[0]),
                    float(wl_arr[-1]),
                )
        except NUMERICAL_FAULT_EXCEPTIONS as exc:
            logger.error(
                "[TARGET] unusable zones (%r): fallback to the nominal spectrum. "
                "The ranking then DOES NOT measure compliance with the target.",
                exc,
            )

    layer_wavelengths = np.zeros(num_layers, dtype=np.float64)
    n_H_vals = np.zeros(num_layers, dtype=np.complex128)
    n_L_vals = np.zeros(num_layers, dtype=np.complex128)
    n_Sub_vals = np.zeros(num_layers, dtype=np.complex128)

    if n_layers_matrix_precomp is not None:
        n_layers_matrix = n_layers_matrix_precomp
    else:
        nH_c128 = nH_arr.astype(np.complex128)
        nL_c128 = nL_arr.astype(np.complex128)
        parity = np.arange(num_layers) % 2 == 0
        n_layers_matrix = np.where(
            parity[np.newaxis, :],
            nH_c128[:, np.newaxis],
            nL_c128[:, np.newaxis],
        )

    idx_dict = _IdxWrapper(clues_at_wl)
    for block in blocks:
        b_wl = float(block["wavelength"])
        idx_data = idx_dict[b_wl]
        b_nH = idx_data["H"]
        b_nL = idx_data["L"]
        b_nSub = idx_data.get("substrate", 1.0)
        for i in range(block["start"], block["end"]):
            layer_wavelengths[i] = b_wl
            n_H_vals[i] = b_nH
            n_L_vals[i] = b_nL
            n_Sub_vals[i] = b_nSub

    # Matrix cache built ONCE and shared.
    #
    # It used to be twice per strategy: a first time in
    # _compute_dT_dd_per_layer, a second time below for the theoretical profile
    # of the layers — same inputs, same result. On the profile of
    # example/example_strat, these two constructions weighed 69.5% and 63.8%
    # of the samples.
    _M_before_cache = build_M_before_cache(
        layer_wavelengths,
        n_H_vals,
        n_L_vals,
        p_thick_nom_arr,
        num_layers,
    )

    is_absolute = params.get("thickness_tolerance_nm") is not None
    dT_dd = None
    if is_absolute:
        dT_dd = _compute_dT_dd_per_layer(
            layer_wavelengths,
            n_H_vals,
            n_L_vals,
            n_Sub_vals,
            p_thick_nominal,
            M_before_all=_M_before_cache,
        )

    base_seed = int(params.get("robustness_seed", 42)) if params.get("robustness_seed") is not None else 42

    # ── AXIS 1.1: noise the monitoring SIGNAL, not only the stopping point ───────
    #
    # Flag INACTIVE BY DEFAULT. It is a first-order model change:
    # it will increase crash rates and lower the apparent benefit of POEM,
    # and it is the measurement that must decide, not intuition. See the
    # "READ NOISE" block in certus/physics/certus_strat_growth.py.
    signal_noise_on = bool(params.get("poem_anchor_noise", False))

    # ── AXIS 1.2: Turning point detection rule ─────────────────────
    #
    # Expressed as a MULTIPLE of the noise amplitude, because that is where it is
    # derived from: the draw being bounded at +/- A, the maximum apparent difference that the noise
    # ALONE can produce between two readings is 2A. From 2 onwards, the noise can
    # therefore no longer manufacture a turning point.
    #
    # 👤 This threshold IS NOT the 4% starting amplitude criterion: "the 4%,
    # for me, it was a wild guess, to be sure we would make it" (2026-08-06).
    # The 4% is a wavelength pre-selection; this is the machine's READ rule,
    # and its reference quantity is the noise, which is measured.
    #
    # Default 0.0 = historical rule, so unchanged path. The value is not set
    # here: it is swept and decided by measurement.
    tp_hysteresis_factor = float(params.get("tp_hysteresis_factor", 0.0) or 0.0)
    for noise_idx, noise_val in enumerate(noise_levels):
        raw_noise = _get_cached_sobol_noise(base_seed, noise_idx, num_runs, num_layers)

        if is_absolute:
            noise_matrix = dT_dd * raw_noise * noise_val * penalty_vector
        else:
            noise_matrix = raw_noise * (noise_val / 100.0) * penalty_vector

        # Same sigma as the stopping reading, and through the same conversion path.
        #
        # ⚠ WITHOUT `penalty_vector`, deliberately. This vector increases the STOPPING noise
        # of the first layer of each block to represent the loss of
        # history at the lambda change — it is a band-aid, and axis 1.1
        # is precisely what should make this effect STRUCTURAL. Applying it a
        # second time to the read noise would count the same effect twice.
        # `signal_noise_scale` is therefore the BARE sigma of the instrument.
        signal_noise_scale = None
        signal_noise_seed = 0
        if signal_noise_on:
            if is_absolute:
                # `dT_dd` is signed; only its amplitude makes a noise scale,
                # and a negative scale would deactivate the noise in the kernel.
                signal_noise_scale = np.abs(np.asarray(dT_dd, dtype=np.float64)) * noise_val
            else:
                signal_noise_scale = np.full(num_layers, noise_val / 100.0, dtype=np.float64)
            signal_noise_seed = _signal_noise_stream_seed(base_seed, noise_idx)

        # The hysteresis follows the current NOISE LEVEL, just like the noise itself: it is
        # a read rule relative to what the instrument fluctuates. In
        # "nm tolerance" mode it depends on the layer via dT/dd, so we keep the
        # median — the kernel takes a scalar, and refining it makes no sense until
        # the value of the factor is decided.
        tp_hysteresis = 0.0
        if tp_hysteresis_factor > 0.0:
            if is_absolute:
                tp_hysteresis = tp_hysteresis_factor * float(
                    np.median(np.abs(np.asarray(dT_dd, dtype=np.float64)))
                ) * noise_val
            else:
                tp_hysteresis = tp_hysteresis_factor * noise_val / 100.0

        affine_scale_amp = float(params.get("affine_scale_amp", 0.0) or 0.0)
        affine_offset_amp = float(params.get("affine_offset_amp", 0.0) or 0.0)
        poem_enabled = bool(params.get("poem_enabled", True))
        affine_seed = _affine_stream_seed(base_seed, noise_idx)
        smoothing_window = int(params.get("reading_smoothing_window", 1) or 1)
        index_corridor = float(params.get("index_corridor", 0.0) or 0.0)
        index_seed = _index_stream_seed(base_seed, noise_idx)

        # ONE computation of the corridor normalisation interval, passed to both the
        # growth batch and the scoring kernel. 12.3, decided 2026-08-10: the envelope
        # of the spectral grid and the monitoring wavelengths.
        corridor_lo, corridor_hi = corridor_wl_range(
            wl_arr.astype(np.float64), layer_wavelengths
        )

        # 👤 Rate layers are a property OF THE STRATEGY, chosen deliberately (14-8),
        # not a fallback the machine trips into. `rate_layers` is a list of 0-based
        # layer indices; absent or empty = pure POEM = the historical path, bit for bit.
        rate_layers = strategy.get("rate_layers") or []
        rate_flags = None
        if rate_layers:
            rate_flags = np.zeros(len(p_thick_nominal), dtype=np.bool_)
            for _idx in rate_layers:
                if 0 <= int(_idx) < rate_flags.size:
                    rate_flags[int(_idx)] = True

        nm_mode = params.get("non_monotonic_mode", NON_MONOTONIC_MODE_ATTENUATE)
        (
            sim_thick_batch, avg_dyns_batch,
            m_level_batch, m_missed_batch, m_fab_batch,
        ) = simulate_stack_robustness_batch(
            p_thick_nom_arr,
            layer_wavelengths,
            n_H_vals,
            n_L_vals,
            n_Sub_vals,
            noise_matrix,
            offset_val,
            factor_val,
            nm_mode,
            signal_noise_scale,
            signal_noise_seed,
            tp_hysteresis,
            affine_scale_amp,
            affine_offset_amp,
            affine_seed,
            poem_enabled,
            smoothing_window,
            index_corridor,
            index_seed,
            corridor_lo,
            corridor_hi,
            rate_flags,
        )

        for i_layer in range(num_layers):
            wl_sel = float(layer_wavelengths[i_layer])
            if wl_sel > 0.1:
                theory_dyn = full_dyn_grid.get(i_layer, {}).get(wl_sel, -1.0)
                sim_dyn = avg_dyns_batch[i_layer]
                diff = abs(theory_dyn - sim_dyn)
                if theory_dyn >= 0.0 and diff > 0.02:
                    logger.warning(
                        f"   [DYN-ALERT] Discrepancy L{i_layer + 1} @ {wl_sel:.0f}nm | Phase A (Grid): {theory_dyn * 100:.2f}% | Phase B (Sim): {sim_dyn * 100:.2f}% | DIFF: {diff * 100:.2f}%"
                    )
                else:
                    if theory_dyn >= 0.0:
                        logger.info(
                            f"   [DYN-OK] L{i_layer + 1} @ {wl_sel:.0f}nm | A={theory_dyn * 100:.2f}% | B={sim_dyn * 100:.2f}%"
                        )

        # NON-TERMINATING DEPOSITIONS, AND NOW BROKEN DOWN BY CAUSE.
        #
        # `simulate_growth_kernel` increases the thickness by a multiple of 1e6 depending on the
        # cause: level never reached, divergent extrema count, or T(d) non-
        # monotonic in REJECT mode. In all three cases the machine cannot terminate
        # the layer, so the test `> 1e5` and the overall rate are UNCHANGED.
        #
        # These events are DISCRETE and rmse_p95 cannot see them below 5%:
        # a crash rate of 2% would go totally unnoticed while it makes
        # the strategy unusable in production. Hence an explicit count.
        #
        # 🔴 AND THE BREAKDOWN IS NOT A DISPLAY AMENITY. The 👤 three
        # questions of the benchmark — "do we see the turning points? do we risk
        # miscounting them? do we risk never reaching the level?" — are only
        # measurements if we count them separately. An aggregate rate of 1.3% does not tell
        # which mechanism to correct, and 📏 this is precisely what blocked the
        # diagnosis of the sigma-independent floor.
        crashed_cells = sim_thick_batch > CRASH_SENTINEL_MIN
        crash_cause = np.where(crashed_cells, np.floor(sim_thick_batch / CRASH_SENTINEL_UNIT), 0.0)
        n_crash_run = int(np.count_nonzero(np.any(crashed_cells, axis=1)))
        crash_rate_max = max(crash_rate_max, n_crash_run / max(1, num_runs))

        # By cause, at RUN level: a run is attributed to a cause as soon as at least
        # one of its layers suffered it. The rates per cause can thus overlap,
        # and their sum exceed the overall rate — this is intended, a run can fail in
        # two different ways on two different layers.
        for cause_id, cause_key in (
            (CRASH_LEVEL_UNREACHABLE, "p_level_unreachable"),
            (CRASH_TP_MISCOUNT, "p_tp_miscount"),
            (CRASH_NON_MONOTONIC, "p_non_monotonic"),
        ):
            rate = float(np.count_nonzero(np.any(crash_cause == cause_id, axis=1))) / max(1, num_runs)
            crash_rates_by_cause[cause_key] = max(crash_rates_by_cause[cause_key], rate)

        # A23 stage 2 -- THE MARGIN, per layer and per cause.
        #
        # 17-31 measured that the optical swing, the best cheap proxy available,
        # identifies the failing layer only 28 % of the time. The margin is the
        # quantity the proxy approximates: how far this layer actually was from
        # crossing, on the simulated noisy signal rather than assumed from the clean
        # one. It is CONTINUOUS and defined at zero crashes, which is the whole point --
        # 0/150 says p < 2 % and nothing more, and every strategy here reads 0.
        #
        # ⚠️ Expressed in multiples of A, the reading noise amplitude, because that is
        # the only unit COMPARABLE ACROSS THE CAUSES (A23): a level is in points of T,
        # a ripple is too but elsewhere, a fabrication is an excursion. The worst case
        # over runs is taken, then the minimum over layers -- the binding layer.
        for _key, _mat in (
            ("level", m_level_batch), ("missed", m_missed_batch), ("fabricated", m_fab_batch)
        ):
            finite = _mat[_mat < 1e17]
            if finite.size:
                per_layer_min = np.where(
                    (_mat < 1e17).any(axis=0), np.where(_mat < 1e17, _mat, np.inf).min(axis=0), np.inf
                )
                prev = margin_profile[_key]
                margin_profile[_key] = np.minimum(prev, per_layer_min)

        # A23 stage 0 -- STOP COLLAPSING THE LAYER AXIS.
        #
        # `crashed_cells` is (n_runs, n_layers). Every reduction above uses `np.any`
        # on axis 1, which answers "did this run fail?" and throws away "WHERE did it
        # fail?" -- information that costs nothing because it is already computed.
        # Summing on axis 0 instead gives the count per layer, and doing it per cause
        # keeps the three failure modes apart, which is the whole point: they have
        # neither the same physics nor the same remedy.
        #
        # ⚠️ "where it stops" is NOT "what is responsible". The sentinel is written on
        # the layer where the deposition halts; a badly deposited layer upstream can
        # make a downstream one fail by propagation -- which is precisely what the
        # compensation chain is about. Report both, never conflate them.
        per_layer = crashed_cells.sum(axis=0).astype(int)
        if per_layer.sum():
            crash_layer_profile["total"] = np.maximum(crash_layer_profile["total"], per_layer)
            for cause_id, cause_key in (
                (CRASH_LEVEL_UNREACHABLE, "level_unreachable"),
                (CRASH_TP_MISCOUNT, "tp_miscount"),
                (CRASH_NON_MONOTONIC, "non_monotonic"),
            ):
                counts = (crash_cause == cause_id).sum(axis=0).astype(int)
                crash_layer_profile[cause_key] = np.maximum(crash_layer_profile[cause_key], counts)

        run_thicknesses = sim_thick_batch.tolist()
        # The finished filter really carries the perturbed index, so its spectrum must
        # be evaluated with it. Scoring at the nominal index measures a filter that was
        # never deposited, and hides the CROSSED mode entirely -- see 12.3 and 17-10.
        # `corridor_lo/hi` come from the single computation above, the very same pair
        # the growth batch received.
        run_rmses = compute_batch_rmse(
            sim_thick_batch,
            wl_arr.astype(np.float64),
            np.empty(0, dtype=np.complex128),
            np.empty(0, dtype=np.complex128),
            nSub_arr.astype(np.complex128),
            T_rank_target,
            n_layers_matrix,
            rank_weights,
            index_corridor,
            index_seed,
            corridor_lo,
            corridor_hi,
        )
        rmse_p95 = float(np.percentile(run_rmses, 95))
        rmse_p99 = float(np.percentile(run_rmses, 99))

        # ── P95 vs CVaR95: DECIDED BY MEASUREMENT, on 2026-08-06 ────────────────
        #
        # CVaR95 (average of the 5% worst) was tried as a ranking
        # functional, on the argument that a quantile is decided by very few points
        # (only one at N=6, one or two at N=25, about seven at N=150) while CVaR
        # averages the tail. The argument is correct on the PRECISION of the estimator, and
        # wrong on what interests us.
        #
        # Measurement, scripts/probe_functional_stability.py, 1281 captures, half-samples
        # from the SAME draw (fair protocol: each functional is judged on its
        # ability to find ITS OWN ranking):
        #
        #     noise   N     rho_p95   rho_cvar   winner
        #     0.025    25    +0.782    +0.725     P95
        #     0.050    25    +0.752    +0.650     P95
        #     0.100    25    +0.717    +0.650     P95
        #     0.025   150    +0.919    +0.924     CVaR (+0.005)
        #     0.050   150    +0.903    +0.863     P95
        #     0.100   150    +0.928    +0.931     CVaR (+0.003)
        #
        # At N=25 P95 wins clearly; at N=150 it is a tie. And the paradox is
        # instructive: CVaR IS a more precise estimator of itself — its
        # bootstrap coefficient of variation is better in five out of six cases — but
        # it COMPRESSES THE GAPS BETWEEN STRATEGIES, because averaging the tail brings
        # them closer. P95 is noisier individually and more DISCRIMINating
        # collectively.
        #
        # We want a RANKING, not a value. P95 is kept, CVaR removed.
        results_per_noise.append(
            {
                "noise_level": noise_val,
                "rmse_mean": float(np.mean(run_rmses)),
                "rmse_std": float(np.std(run_rmses)),
                "rmse_p95": rmse_p95,
                "rmse_p99": rmse_p99,
                "rmse_all": run_rmses.tolist(),
                "thicknesses_all": run_thicknesses,
                "avg_dynamics": avg_dyns_batch.tolist(),
            }
        )

    total_mc_sims = num_runs * len(noise_levels)
    _emit_stat("MCS", total_mc_sims)
    #Ranking functional: P95, decided by measurement (see comment block
    # in the loop above). CVaR95 was tried and REMOVED.
    final_score = max(r.get("rmse_p95", r["rmse_mean"] + r["rmse_std"]) for r in results_per_noise)

    # ELIMINATION ON CRASH RISK.
    #
    # A strategy whose deposition risks not terminating is unusable,
    # regardless of its spectral performance: it is not a quality compromise,
    # it is a lost run in the cleanroom. So we remove it from the ranking rather
    # than penalize it, unless the event remains below the tolerance threshold.
    #
    # Threshold at 1%: below, the randomness is deemed acceptable given the
    # potential spectral gain. Above, straightforward elimination.
    if crash_rate_max >= CRASH_RATE_TOLERANCE:
        final_score = float("inf")

    # This block is computed AFTER final_score and results_per_noise, on which it
    # does not depend. Yet it is the most expensive in the function: it calls
    # _compute_theoretical_layer_profile once per layer, where the two
    # most expensive lines of the STRAT profile live (certus_strat_objectives.py:489
    # compute_T_front_profile at 107.2%, and :497 calculate_extrema_distances at
    # 106.7%, cf. docs/REPRISE_PERF.md §6).
    #
    # Two out of three callers completely discard its result:
    #   - consensus rescoring (certus_strat_robustness.py, _consensus_score_from_result)
    #     only reads robustness_score;
    #   - ELITE halving (certus_strat_consensus.py) only reads rmse_p95 and
    #     re-pushes the INPUT strategy, not res["strategy"].
    # Only the main pass and the full ELITE evaluation exploit it,
    # the latter via full_res["strategy"] for the spectral resolution.
    #
    # The True default preserves the behavior of any unmodified caller.
    if compute_layer_profile:
        extrema_dist_info = []
        theoretical_layer_profile = []
        #_M_before_cache: already built above, shared with dT/dd.

        for i_layer in range(num_layers):
            wl_sel = float(layer_wavelengths[i_layer])
            M_before = _M_before_cache[i_layer]
            n_current = n_H_vals[i_layer] if i_layer % 2 == 0 else n_L_vals[i_layer]
            layer_profile = _compute_theoretical_layer_profile(
                wl_sel,
                n_current,
                n_Sub_vals[i_layer],
                float(p_thick_nominal[i_layer]),
                M_before,
            )
            dist_ps = float(layer_profile["dist_prev_start"])
            dist_ns = float(layer_profile["dist_next_start"])
            dist_pe = float(layer_profile["dist_prev_end"])
            dist_ne = float(layer_profile["dist_next_end"])
            extrema_dist_info.append(
                {
                    "prev_start": dist_ps,
                    "next_start": dist_ns,
                    "prev_end": dist_pe,
                    "next_end": dist_ne,
                }
            )
            theoretical_layer_profile.append(layer_profile)

        strategy["extrema_distances"] = extrema_dist_info
        strategy["theoretical_layer_profile"] = theoretical_layer_profile
        strategy["symmetry_score_pct"] = _compute_strategy_symmetry_score_percent(
            theoretical_layer_profile,
            float(params.get("sym_extrema_window", SYM_DEFAULT_EXTREMA_WINDOW_OT)),
        )

    if crash_rate_max > 0.0:
        logger.info(
            f"   [CRASH-CAUSE] strat {strategy.get('strategy_id', '?')} : total "
            f"{crash_rate_max:.1%} | unreachable level "
            f"{crash_rates_by_cause['p_level_unreachable']:.1%} | divergent count "
            f"{crash_rates_by_cause['p_tp_miscount']:.1%} | non monotonic "
            f"{crash_rates_by_cause['p_non_monotonic']:.1%}"
        )

    return {
        "strategy_id": strategy["strategy_id"],
        "strategy": strategy,
        "results_per_noise": results_per_noise,
        "robustness_score": final_score,
        "crash_rate": crash_rate_max,
        # The three failure modes, separately. 👤 "If 95% of depositions
        # work, it's a win" — but knowing WHY the 5% fail is what
        # allows correcting the strategy rather than rejecting it.
        "crash_causes": dict(crash_rates_by_cause),
        # A23 stage 0. WHERE it fails, per cause, not just how often. Reported even
        # when everything is zero: a profile of zeros is the normal case on this stack
        # and it is what makes the margin work necessary -- a rate of 0/150 tells you
        # p < 2 % and nothing else, whereas a margin is defined and informative there.
        "crash_by_layer": {k: v.tolist() for k, v in crash_layer_profile.items()},
        # The poorest optical swing over the layers, at the nominal noise level: the
        # binding layer, the one 14-5 says governs trigger precision. Already computed
        # per layer by the batch, and averaged away until now.
        "worst_layer_swing": _worst_layer_swing(results_per_noise),
        # 17-37. Run-level, not per-strategy: every strategy inherits the same Phase A.
        # Carried on each result anyway so it can never be separated from the score it
        # qualifies -- that separation is exactly how the collapse went unnoticed.
        "phase_a_forced": _phase_a_forced_layers(params),
        # 👤 The table must show WHICH layers ran in Rate: a strategy is not executable
        # in the chamber without it, and two strategies differing only by their Rate
        # layers would otherwise be indistinguishable in the ranking.
        "rate_layers": list(rate_layers),
        # 👤 A strategy is (blocks, wavelengths, rate layers, SLIT). The first three were
        # reported and the fourth was not, so what came out was not executable as it
        # stood. The noise factor that goes with it is 12.7's table, applied to the
        # sample and never to the seed.
        "monochromator_resolution_nm": float(params.get("monochromator_resolution_nm", 2.0) or 2.0),
        "resolution_noise_factor": _resolution_noise_factor(params),
        # A23 stage 2: WHICH layer will give way, WHY, and BY HOW MUCH. Defined even
        # when nothing crashed, which is the whole reason it exists.
        # ⚠️ NOMINAL noise level, not the worst of the three. The margin is normalised
        # by the amplitude A the MACHINE actually has; dividing by the 2x level would
        # report a strategy as twice as safe as it is.
        "critical_layer": _critical_layer(
            margin_profile, float(noise_levels[len(noise_levels) // 2]) / 100.0
        ),
        # The profile itself, sparsely. 🔴 NEEDED FOR RANKING, and the reduced
        # `critical_layer` above cannot replace it: measured 2026-08-11, nine of the ten
        # tied strategies returned the SAME margin (0.83 A, layer 6) because they share
        # a first block at 544 nm -- layer 6 is literally the same physics in all nine.
        # The reduction is correct and it describes what they SHARE, so it cannot rank
        # them. Ranking needs the margin restricted to the layers where they DIFFER,
        # which only a caller seeing the whole set can work out.
        "margin_by_layer": _margin_profile_sparse(
            margin_profile, float(noise_levels[len(noise_levels) // 2]) / 100.0
        ),
        "symmetry_score_pct": float(strategy.get("symmetry_score_pct", 0.0)),
        "num_unique_wavelengths": unique_wls,
        "complexity_score": complexity,
    }


# _select_best_strat_result has been moved to certus_strat_ranking.py


def _finalize_robustness_results(
    strategies_results: list[dict[str, Any]],
    params: dict[str, Any],
    logger: logging.Logger,
) -> dict[str, Any]:
    """Reduce memory usage and format final output for robustness ranking."""
    keep_full_mc_top_k = int(params.get("keep_full_mc_top_k", 30))
    for res in strategies_results[keep_full_mc_top_k:]:
        for r in res.get("results_per_noise", []):
            r["rmse_all"] = []
            r["thicknesses_all"] = []

    best = _select_best_strat_result(strategies_results)
    if best:
        logger.info(
            f"🏆 Best Strategy ID: {best['strategy_id']} ({best['strategy'].get('origin', '?')}) - Score: {float(best.get('robustness_score', best.get('rmse', 0.0))):.5f}"
        )

    return {
        "results_per_noise": (best["results_per_noise"] if best else []),
        "optimal_blocks": (best["strategy"]["blocks"] if best else []),
        "best_strategy": (best["strategy"] if best else None),
        "all_strategies_results": strategies_results,
    }


def _build_layer_wavelengths_from_strategy(strategy: dict[str, Any], num_layers: int, l0: float) -> list[float]:
    """Build layer wavelengths from strategy."""
    blocks = strategy["blocks"]
    layer_wavelengths = [l0] * num_layers
    for block in blocks:
        for i in range(block["start"], block["end"]):
            layer_wavelengths[i] = block["wavelength"]
    return layer_wavelengths


def _validate_strategy_min_transmission_floor(
    strategy: dict[str, Any],
    p_thick_nominal: list[float],
    clues_at_wl: Any,
    nominal_matrix_cache: np.ndarray,
    all_wls: np.ndarray,
    min_t_floor: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Validate strategy minimum transmission floor."""
    num_layers = len(p_thick_nominal)
    layer_wavelengths = _build_layer_wavelengths_from_strategy(strategy, num_layers, float(strategy.get("l0", 550.0)))

    tmin_report = []
    tmin_violations = []

    idx_dict = _IdxWrapper(clues_at_wl)
    for i in range(num_layers):
        wl = layer_wavelengths[i]
        clue = idx_dict[wl]
        n_current = clue["H"] if i % 2 == 0 else clue["L"]
        n_sub = clue.get("substrate", 1.0)

        # Calculate theoretical transmission at nominal thickness
        from certus_physics import compute_T_front_at_layer

        # We need to map wavelength float to cache index
        wl_idx = np.searchsorted(all_wls, wl)
        if wl_idx < len(all_wls) and abs(all_wls[wl_idx] - wl) < 1e-5:
            # The cumulative matrix must be read at THE SAME wavelength as that at
            # which T is evaluated. Wavelength index was previously hardcoded to 0:
            # M_before thus always came from all_wls[0], while T_val is computed at
            # `wl`. The T_min post-check was comparing a partial stack taken at one
            # wavelength with a transmission computed at another.
            # Shape cache (num_layers, n_wls, 2, 2) — see certus_strat_config.py:436.
            M_before = (
                np.eye(2, dtype=np.complex128)
                if i == 0
                else nominal_matrix_cache[i - 1, wl_idx, :, :]
            )

            # cur_M is computed at layer i
            T_val = compute_T_front_at_layer(
                float(wl),
                complex(n_current),
                complex(n_sub),
                complex(M_before[0, 0]),
                complex(M_before[0, 1]),
                complex(M_before[1, 0]),
                complex(M_before[1, 1]),
                float(p_thick_nominal[i]),
            )
        else:
            T_val = 1.0  # Fallback

        tmin_report.append({"layer": i + 1, "wl": wl, "t_min": T_val})
        if T_val < min_t_floor:
            tmin_violations.append({"layer": i + 1, "wl": wl, "t_min": T_val})

    return tmin_report, tmin_violations


def run_final_simulation_block(
    opti_results: dict[str, Any],
    params: dict[str, Any],
    num_runs: int = 150,
    noise_levels: list[float] | None = None,
) -> dict[str, Any]:
    """Phase B robustness screening: evaluate every candidate strategy under noise."""
    logger = params["logger"]

    # Defer imports of solvers functions to run-time to completely avoid circular dependencies
    from certus.core.certus_strat_consensus import (
        _unpack_consensus_cfg,
        _init_consensus_runtime_state,
        _should_apply_consensus_ranking,
        _select_consensus_candidates,
        _log_consensus_ranking_enabled,
        _init_consensus_map,
        _consensus_strategy_identity,
        _build_params_consensus,
        _consensus_cache_key,
        _consume_cached_consensus_score,
        _store_and_consume_consensus_score,
        _consensus_score_from_result,
        _log_consensus_seed_failure,
        _should_skip_consensus_registration,
        _register_consensus_score_for_strategy,
        _apply_consensus_scores_to_results,
        _log_consensus_rescore_summary,
        _rank_and_filter_strategies,
        _apply_elite_refinement_if_enabled,
    )

    all_strategies, noise_levels, p_thick_nominal, num_layers = _prepare_robustness_inputs(
        opti_results=opti_results,
        params=params,
        num_runs=num_runs,
        noise_levels=noise_levels,
        logger=logger,
    )

    if not all_strategies:
        logger.warning("[ROBUSTNESS] No valid strategy to evaluate after contract checks.")
        return {
            "results_per_noise": [],
            "optimal_blocks": [],
            "best_strategy": None,
            "all_strategies_results": [],
        }

    clues_at_wl = opti_results.get("clues_at_wl")
    if clues_at_wl is None:
        logger.info("[ROBUSTNESS] 'clues_at_wl' not found in opti_results. Recomputing clues on the fly.")
        clues_at_wl, _, _ = precompute_clues_and_matrices(params, p_thick_nominal, logger)

    wls_to_fetch = set()
    if hasattr(clues_at_wl, "wls"):
        wls_to_fetch.update(float(w) for w in clues_at_wl.wls)
    elif hasattr(clues_at_wl, "keys"):
        wls_to_fetch.update(float(w) for w in clues_at_wl.keys())
    for strat in all_strategies:
        for blk in strat.get("blocks", []):
            wls_to_fetch.add(float(blk["wavelength"]))

    idx_dict = _IdxWrapper(clues_at_wl)
    local_clues = _SafeLocalClues(clues_at_wl)
    for wl in wls_to_fetch:
        try:
            local_clues[wl] = idx_dict[wl]
        except Exception:
            pass

    clues_at_wl = local_clues
    opti_results = dict(opti_results)
    opti_results["clues_at_wl"] = clues_at_wl

    full_dyn_grid = opti_results.get("full_dynamics_grid", {})

    wl_arr, nH_arr, nL_arr, nSub_arr, T_nom = _prepare_robustness_nominal_optics(
        params=params,
        p_thick_nominal=p_thick_nominal,
        opti_results=opti_results,
    )

    params_safe = filter_params_for_gui(params)

    nH_c128 = nH_arr.astype(np.complex128)
    nL_c128 = nL_arr.astype(np.complex128)
    parity = np.arange(num_layers) % 2 == 0
    n_layers_matrix_precomp = np.where(
        parity[np.newaxis, :],
        nH_c128[:, np.newaxis],
        nL_c128[:, np.newaxis],
    )

    strategies_results = _execute_robustness_tasks(
        all_strategies=all_strategies,
        noise_levels=noise_levels,
        num_runs=num_runs,
        p_thick_nominal=p_thick_nominal,
        clues_at_wl=clues_at_wl,
        params_safe=params_safe,
        wl_arr=wl_arr,
        nH_arr=nH_arr,
        nL_arr=nL_arr,
        nSub_arr=nSub_arr,
        T_nom=T_nom,
        full_dyn_grid=full_dyn_grid,
        params=params,
        logger=logger,
        n_layers_matrix_precomp=n_layers_matrix_precomp,
    )

    (
        consensus_enabled,
        consensus_top_k,
        consensus_mode,
        consensus_std_weight,
        consensus_num_runs,
        consensus_seeds,
    ) = _unpack_consensus_cfg(params, num_runs=num_runs)

    noise_signature, robustness_score_cache = _init_consensus_runtime_state(noise_levels)

    def _apply_consensus_ranking_inplace(results_in: list[dict[str, Any]], stage_tag: str) -> None:
        if not _should_apply_consensus_ranking(
            consensus_enabled=consensus_enabled,
            consensus_seeds=consensus_seeds,
            results_in=results_in,
        ):
            return

        top_k_eval, candidates = _select_consensus_candidates(
            results_in,
            consensus_top_k=consensus_top_k,
        )

        _log_consensus_ranking_enabled(
            logger=logger,
            stage_tag=stage_tag,
            top_k_eval=top_k_eval,
            consensus_seeds=consensus_seeds,
            consensus_mode=consensus_mode,
            consensus_num_runs=consensus_num_runs,
        )

        consensus_map = _init_consensus_map()

        _consensus_tasks: list[tuple[int, str, tuple, int, tuple, concurrent.futures.Future]] = []
        _consensus_cached: dict[str, list[float]] = {}

        for local_idx, item in enumerate(candidates):
            strat = item.get("strategy", {})
            sid, strat_sig = _consensus_strategy_identity(strat)
            if sid not in _consensus_cached:
                _consensus_cached[sid] = []
            for seed in consensus_seeds:
                params_consensus = _build_params_consensus(params_safe, seed=seed)
                cache_key = _consensus_cache_key(
                    strat_sig,
                    seed=seed,
                    consensus_num_runs=consensus_num_runs,
                    noise_signature=noise_signature,
                )
                if _consume_cached_consensus_score(
                    robustness_score_cache=robustness_score_cache,
                    cache_key=cache_key,
                    seed_scores=_consensus_cached[sid],
                ):
                    continue
                _consensus_tasks.append((local_idx, sid, strat_sig, seed, cache_key, None))

        if _consensus_tasks:
            _consensus_max_workers = min(len(_consensus_tasks), get_safe_worker_count())
            _task_futures: list[tuple[str, int, tuple, concurrent.futures.Future]] = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=_consensus_max_workers) as _cexec:
                for local_idx, sid, strat_sig, seed, cache_key, _ in _consensus_tasks:
                    item = candidates[local_idx]
                    strat = item.get("strategy", {})
                    params_consensus = _build_params_consensus(params_safe, seed=seed)
                    f = _cexec.submit(
                        _test_strategy_robustness_task,
                        strat,
                        local_idx,
                        noise_levels,
                        consensus_num_runs,
                        p_thick_nominal,
                        clues_at_wl,
                        params_consensus,
                        wl_arr,
                        nH_arr,
                        nL_arr,
                        nSub_arr,
                        T_nom,
                        full_dyn_grid,
                        n_layers_matrix_precomp=n_layers_matrix_precomp,
                        # _consensus_score_from_result only reads robustness_score,
                        # then res_consensus is abandoned: the theoretical profile
                        # would be calculated for nothing.
                        compute_layer_profile=False,
                    )
                    _task_futures.append((sid, seed, cache_key, f))

                for sid, seed, cache_key, f in _task_futures:
                    try:
                        res_consensus = f.result()
                        score_c = _consensus_score_from_result(res_consensus)
                        _store_and_consume_consensus_score(
                            robustness_score_cache=robustness_score_cache,
                            cache_key=cache_key,
                            score_c=score_c,
                            seed_scores=_consensus_cached[sid],
                        )
                    except NUMERICAL_FAULT_EXCEPTIONS as e:
                        _log_consensus_seed_failure(
                            logger=logger,
                            sid=sid,
                            seed=seed,
                            error=e,
                        )

        for local_idx, item in enumerate(candidates):
            strat = item.get("strategy", {})
            sid, strat_sig = _consensus_strategy_identity(strat)
            seed_scores = _consensus_cached.get(sid, [])

            if _should_skip_consensus_registration(seed_scores):
                continue

            _register_consensus_score_for_strategy(
                consensus_map=consensus_map,
                sid=sid,
                seed_scores=seed_scores,
                consensus_mode=consensus_mode,
                consensus_std_weight=consensus_std_weight,
                consensus_seeds=consensus_seeds,
            )

        _apply_consensus_scores_to_results(
            results_in=results_in,
            consensus_map=consensus_map,
            consensus_mode=consensus_mode,
        )

        _log_consensus_rescore_summary(
            logger=logger,
            consensus_map=consensus_map,
            results_in=results_in,
            stage_tag=stage_tag,
        )

    strategies_results = _rank_and_filter_strategies(
        strategies_results=strategies_results,
        stage_tag="pre-elite",
        params=params,
        logger=logger,
        apply_consensus_fn=_apply_consensus_ranking_inplace,
    )

    ctx = RobustnessContext(
        params=params,
        params_safe=params_safe,
        logger=logger,
        noise_levels=noise_levels,
        num_runs=num_runs,
        p_thick_nominal=p_thick_nominal,
        num_layers=num_layers,
        clues_at_wl=clues_at_wl,
        wl_arr=wl_arr,
        nH_arr=nH_arr,
        nL_arr=nL_arr,
        nSub_arr=nSub_arr,
        T_nom=T_nom,
        full_dyn_grid=full_dyn_grid,
        n_layers_matrix_precomp=n_layers_matrix_precomp,
    )

    strategies_results = _apply_elite_refinement_if_enabled(
        strategies_results=strategies_results,
        ctx=ctx,
        apply_consensus_fn=_apply_consensus_ranking_inplace,
    )

    return _finalize_robustness_results(
        strategies_results=strategies_results,
        params=params,
        logger=logger,
    )


def _get_best_noise_results(final_results: dict[str, Any], logger: logging.Logger) -> dict[str, Any] | None:
    """Return the best noise results from final robustness results."""
    results_list = final_results.get("results_per_noise", [])
    if not results_list:
        logger.error("No robustness results available!")
        return None

    target_idx = None
    for i, res in enumerate(results_list):
        if abs(res.get("noise_level", 0.0) - 1.0) < 1e-6:
            target_idx = i
            break

    if target_idx is None:
        best_dist = float("inf")
        best_i = 0
        for i, res in enumerate(results_list):
            dist = abs(res.get("noise_level", 0.0) - 1.0)
            if dist < best_dist:
                best_dist = dist
                best_i = i
        target_idx = best_i

    selected_results = results_list[target_idx]
    if "thicknesses_all" not in selected_results or not selected_results["thicknesses_all"]:
        logger.error("No successful simulations in thicknesses_all for selected noise level!")
        return None

    return selected_results
