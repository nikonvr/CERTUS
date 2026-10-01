"""CERTUS STRAT ROBUSTNESS - the robustness task of ONE strategy, run in a worker (moved out of certus_strat_robustness.py, S5.2)."""

import logging
import numpy as np
from typing import Any

from certus_physics import (
    CRASH_LEVEL_UNREACHABLE,
    CRASH_NON_MONOTONIC,
    CRASH_SENTINEL_MIN,
    CRASH_SENTINEL_UNIT,
    CRASH_TP_MISCOUNT,
    PHOTOMETRIC_CURVATURE_AMP,
    NON_MONOTONIC_MODE_ATTENUATE,
    calculate_RT_batch_kernel,
    compute_batch_rmse,
    corridor_wl_range,
    simulate_stack_robustness_batch,
)
from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS
from certus.core.certus_strat_robustness_diagnostics import (
    _critical_layer,
    _margin_profile_sparse,
    _phase_a_forced_layers,
    _resolve_witness_resets,
    _worst_layer_swing,
)
from certus.core.certus_strat_robustness_gate import (
    CRASH_GATE_CONFIDENCE_KEY,
    CRASH_RATE_TOLERANCE,
    _crash_gate_rejects,
    crash_rate_lower_bound,
)
from certus.core.certus_strat_robustness_noise import (
    INDEX_CORRIDOR_DEFAULT,
    _affine_stream_seed,
    _get_cached_sobol_noise,
    _index_stream_seed,
    _resolution_noise_factor,
    _signal_noise_stream_seed,
)
from certus.core.certus_strat_robustness_slit import _strategy_resolution
from certus.core.certus_strat_robustness_wrappers import _IdxWrapper


def _test_strategy_robustness_task(
    strategy: dict[str, Any],
    _strat_idx: int,
    noise_levels: Any,
    num_runs: int,
    p_thick_nominal: Any,
    clues_at_wl: Any,
    params: dict[str, Any],
    wl_arr: np.ndarray,
    nH_arr: np.ndarray,
    nL_arr: np.ndarray,
    nSub_arr: np.ndarray,
    T_nom: Any,
    full_dyn_grid: Any,
    n_layers_matrix_precomp: Any = None,
    compute_layer_profile: bool = True,
) -> dict:
    from certus.core.certus_strat_config import SYM_DEFAULT_EXTREMA_WINDOW_OT, _emit_stat
    from certus.core.certus_strat_objectives import _compute_dT_dd_per_layer, _compute_strategy_symmetry_score_percent, _compute_theoretical_layer_profile, build_M_before_cache
    from certus.utils.certus_strat_service import compute_probe_offset_nm_from_ratio
    import numba

    numba.set_num_threads(2)
    logger = logging.getLogger("certus_strat")
    strategy = dict(strategy)
    blocks = strategy["blocks"]
    # ---- A18: the slit is a property of the STRATEGY, not of the run -------------
    #
    # 👤 "determining the optimal resolution for a given strategy... that resolution is
    # an integral part of the strategy to be found" (2026-08-09). So a strategy is no
    # longer (block partition, lambda per block) but (block partition, lambda per block,
    # SLIT), and the three are decided together.
    #
    # 🔴 THE FACTOR SCALES THE NOISE, IT NEVER TOUCHES THE SEED -- constraint C2, and
    # this is the one place it could have been broken invisibly. The draws come from
    # `_signal_noise_stream_seed(base_seed, noise_idx)` and `_get_cached_sobol_noise`,
    # neither of which sees the strategy: two slit variants of one strategy therefore
    # see the SAME random realisation, only sized differently. Folding the slit into the
    # seed would give the four widths four different worlds, and the gap between them
    # would stop being attributable to the slit -- while all four numbers still looked
    # perfectly plausible.
    strat_slit = strategy.get("monochromator_resolution_nm")
    if strat_slit is not None:
        rescale = _resolution_noise_factor({"monochromator_resolution_nm": strat_slit}) / (
            _resolution_noise_factor(params) or 1.0
        )
        if rescale != 1.0:
            noise_levels = [lv * rescale for lv in noise_levels]
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
    crash_count_max = 0    # ... and the COUNT behind it, which the rate throws away
    # 🔑 THE RATE PER NOISE LEVEL, AND IT EXISTED NOWHERE.
    #
    # `crash_rate_max` is a MAX over the three levels (`robustness_noise_factors`, by
    # default [0.5 · 1.0 · 2.0]), and it is what the crash gate compares with the 5 %
    # tolerance of 👤. The tolerance therefore applies to the WORST of the three, one of
    # which is TWICE the measured reading noise (§18-2: ±0.05 point, A = 5e-4). The 1x is
    # the machine; the 0.5x and 2x are robustness multipliers.
    #
    # 🔴 And the reduction by `max` is IRREVERSIBLE: no artefact of this repository carries
    # the rate at the REAL noise, so it cannot be known, on any existing run, whether a
    # rejected strategy was manufacturable on the machine of 👤. The detail is therefore kept.
    #
    # 🔒 What this does NOT do: change the gate. The rule stays the max, and it is a
    # decision of 👤 -- judging on the worst of the three may be exactly the margin they want.
    # What was not defensible is that nobody could MEASURE it.
    crash_rates_by_noise: dict[str, float] = {}
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
        # 🔴 THE READING NOISE IS ONE SINGLE CONTINUOUS PROCESS OVER THE WHOLE DEPOSITION,
        # and a campaign reads ONLY ITS SLICE of it.
        #
        # Without these two parameters, measuring a sub-stack in isolation gives it a noise
        # stream that RESTARTS AT ZERO. Three campaigns launched with the same seed -- which is
        # what must be done to share the index realisation -- then receive a reading noise
        # correlated at 76-79 % (measured on 2026-08-15), where two distinct seeds give
        # -0.09. Yet two layers deposited twenty minutes apart do not share the noise of their
        # photodetector.
        #
        # 🔑 The seed cannot solve this: it drives BOTH the index corridor -- which MUST be
        # shared, the materials are the same -- and the reading noise, which must be
        # INDEPENDENT. The two require opposite treatments. The same seed is therefore kept,
        # and the SLICE is shifted.
        #
        # Defaults: offset 0 and total = num_layers, i.e. exactly the former behaviour
        # (constraint C1).
        noise_total = int(params.get("noise_total_layers", 0) or 0) or num_layers
        noise_off = int(params.get("noise_layer_offset", 0) or 0)
        if noise_off < 0 or noise_off + num_layers > noise_total:
            raise ValueError(
                f"tranche de bruit hors bornes : offset {noise_off} + {num_layers} couches "
                f"> {noise_total}. Un sous-empilement doit declarer sa position DANS le depot."
            )
        raw_noise = _get_cached_sobol_noise(base_seed, noise_idx, num_runs, noise_total)
        if noise_total != num_layers:
            raw_noise = np.ascontiguousarray(raw_noise[:, noise_off:noise_off + num_layers])

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
        # 👤 the affine gain/offset stay OFF by default: the machine re-references
        # itself against dark and void every rotation, so a common multiplicative
        # drift cancels exactly. What survives is pinned at T=0 and T=1 and free in
        # between -- see PHOTOMETRIC_CURVATURE_AMP. The affine pair is kept as the
        # instrument that TESTS the invariance theorem of 12.1, not as a model of
        # the machine.
        photo_curvature_amp = float(
            params.get("photometric_curvature_amp", PHOTOMETRIC_CURVATURE_AMP) or 0.0
        )
        affine_offset_amp = float(params.get("affine_offset_amp", 0.0) or 0.0)
        poem_enabled = bool(params.get("poem_enabled", True))
        affine_seed = _affine_stream_seed(base_seed, noise_idx)
        smoothing_window = int(params.get("reading_smoothing_window", 1) or 1)
        index_corridor = float(params.get("index_corridor", INDEX_CORRIDOR_DEFAULT) or 0.0)
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
        # ---- SLIT BIAS, per layer (12.7) ------------------------------------
        #
        # 👤 "the OMS never computes spectral responses with a resolution problem, it is
        # always at perfect resolution -- that is why opening the slits too much is a
        # problem: the expected levels are not the right ones."
        #
        #   second_diff = T''.test_bw^2/8   (test_bw = 1 nm)
        #   bias = T''.B^2/24 = second_diff . B^2 / (3.test_bw^2)
        #
        # 🔴 ON BY DEFAULT since 2026-08-11. 👤 *"I do not want to be optimistic about
        # the slits but realistic."* The real machine has carried this bias all along;
        # a simulator that omits it is not simpler, it is wrong in a known direction.
        #
        # 📏 AND THE SIZE IS THE ARGUMENT. On the 48-layer dichroic, by direct boxcar
        # integration -- not by the expansion -- the bias at the nominal 2 nm slit is
        #
        #     450 nm   9.6e-4   192 % of the reading noise
        #     500 nm   9.4e-4   187 %
        #     544 nm   1.05e-2  2100 %      <- the edge
        #     600 nm   1.2e-5   2 %
        #
        # 🔑 It is proportional to the CURVATURE, the curvature is maximal at the edge,
        # and 17-42 measured that ALL TWENTY of the best strategies place their first
        # block within 3 nm of that edge. The simulator was therefore ignoring an error
        # TWENTY TIMES the noise it does model, at the exact wavelength every winner
        # uses.
        #
        # ⚠️ The second-order expansion was checked against direct integration over the
        # slit: ratios 0.90 to 1.19, so it holds -- worst at 5 nm on the edge, where it
        # overestimates by 19 %.
        #
        # 🔴 CONSEQUENCE, and it is not small: EVERY crash rate and EVERY SEEL measured
        # before this date was produced without this bias. They are not wrong, they are
        # ANSWERS TO A DIFFERENT QUESTION -- a machine with infinitely fine slits. Do not
        # compare across this date.
        slit_profiles = None
        if bool(params.get("slit_bias_enabled", True)):
            prof = strategy.get("slit_profile")
            if prof is not None and len(prof) == len(p_thick_nominal):
                slit_profiles = np.ascontiguousarray(prof, dtype=np.float64)

        rate_layers = strategy.get("rate_layers") or []
        rate_flags = None
        if rate_layers:
            rate_flags = np.zeros(len(p_thick_nominal), dtype=np.bool_)
            for _idx in rate_layers:
                if 0 <= int(_idx) < rate_flags.size:
                    rate_flags[int(_idx)] = True

        # MULTIPLE-TESTGLASS. 0-based indices of the layers at which a BARE witness is
        # rotated into the beam. The part is untouched -- it stays on the platter and
        # receives every layer; only the monitoring restarts from bare glass.
        #
        # 👤 2026-08-14: the swap is done by an under-vacuum carousel, so it costs no
        # vent, no pump-down and no contamination. The ONLY price is the one the growth
        # kernel produces on its own: the error accumulated before the cut becomes
        # invisible to the monitoring, hence permanently uncorrectable, and it stays
        # frozen in the part. That is what a cut buys and what it costs.
        #
        # ⚠️ Index 0 is meaningless and is dropped: layer 0 already grows on bare glass.
        # An empty list reproduces the single-witness behaviour exactly.
        # Two sources, and the order matters. A strategy that carries its own cut plan
        # wins; otherwise the RUN's plan applies to every strategy it evaluates. The
        # second form is what a sweep needs: one cut plan per batch, imposed on all
        # candidates, so two batches differ by the cut and by nothing else.
        witness_resets = _resolve_witness_resets(
            strategy.get("witness_reset_layers")
        ) or _resolve_witness_resets(params.get("witness_reset_layers"))
        witness_reset_flags = None
        if witness_resets:
            witness_reset_flags = np.zeros(len(p_thick_nominal), dtype=np.bool_)
            for _idx in witness_resets:
                if 0 < int(_idx) < witness_reset_flags.size:
                    witness_reset_flags[int(_idx)] = True
            if not witness_reset_flags.any():
                witness_reset_flags = None

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
            photo_curvature_amp,
            affine_seed,
            poem_enabled,
            smoothing_window,
            index_corridor,
            index_seed,
            corridor_lo,
            corridor_hi,
            rate_flags,
            slit_profiles,
            witness_reset_flags,
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
        _taux_ce_niveau = n_crash_run / max(1, num_runs)
        crash_rates_by_noise[f"{float(noise_val):g}"] = _taux_ce_niveau
        crash_rate_max = max(crash_rate_max, _taux_ce_niveau)
        # 🔑 KEEP THE COUNT, not only the ratio. A rate of 0.02 says nothing about how
        # well it is known: 1/50 and 6/300 are the same number and not the same evidence.
        # The confidence gate below needs the count; the ratio has already discarded it.
        crash_count_max = max(crash_count_max, n_crash_run)

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
    #
    # 🔴 AND THE COMPARISON ITSELF IS THE DEFECT -- see `crash_gate_confidence`.
    _gate_rejects = _crash_gate_rejects(crash_count_max, num_runs, crash_rate_max, params)
    if _gate_rejects:
        final_score = float("inf")

    # WHAT THE CONFIDENCE BOUND ACTUALLY SPARED -- instrumentation only, no path changes.
    #
    # Measured 2026-08-21 on `r75x2` at 2 nm, `deep`, seed 42: arming
    # `crash_gate_confidence = 0.95` produced counters BYTE-IDENTICAL to the reference --
    # halving 1368, full_rmse 211, score_non_fini 1116, engendrees 4226 -- and 0 depositable
    # either way. Two readings fit that, and they call for opposite repairs:
    #
    #   the key never reached this call  ->  a DEAD lever, the family of 24-33
    #   the key reached it and spared 0  ->  a live lever with nothing in range
    #
    # The crash bands could not separate them: their 5-10 % bucket held exactly ONE
    # candidate, and the bound only flips below ~7.3 % at N = 300 (21/300 passes, 25/300 does
    # not), so a single candidate in the upper half of that bucket explains the null result
    # without any defect. Counting the DISAGREEMENTS settles it directly: a line here means
    # the lever acted, silence means it had nothing to catch, and neither has to be inferred.
    if bool(params.get(CRASH_GATE_CONFIDENCE_KEY, 0.0) or 0.0):
        _hist_rejects = crash_rate_max >= CRASH_RATE_TOLERANCE
        if _hist_rejects != _gate_rejects:
            logger.info(
                f"   [GATE] strat {strategy.get('strategy_id', '?')}: the confidence bound "
                f"{'SPARES' if _hist_rejects else 'ALSO REJECTS'} -- crash "
                f"{crash_rate_max:.2%} ({crash_count_max}/{num_runs}), lower bound "
                f"{crash_rate_lower_bound(crash_count_max, num_runs, float(params.get(CRASH_GATE_CONFIDENCE_KEY))):.2%}"  # type: ignore[arg-type]
            )

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
        # The detail the `max` above throws away. See the comment of `crash_rates_by_noise`.
        "crash_rates_by_noise": dict(crash_rates_by_noise),
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
        # 🔴 THE STRATEGY'S OWN SLIT, not the run's. Since A18 they differ: the slit is a
        # searched variable, so reporting the run-level setting here would hand the
        # operator a width the winner was never evaluated at.
        "monochromator_resolution_nm": _strategy_resolution(strategy, params),
        "resolution_noise_factor": _resolution_noise_factor(
            {"monochromator_resolution_nm": _strategy_resolution(strategy, params)}
        ),
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
