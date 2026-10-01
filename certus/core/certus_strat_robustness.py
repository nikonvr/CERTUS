"""
CERTUS STRAT ROBUSTNESS
=======================
Part of CERTUS Suite (Refactoring 2026)

Contains, here:
- run_final_simulation_block (Phase B robustness screening)
- _execute_robustness_tasks (the pool: it looks up `_test_strategy_robustness_task`, `_calculate_strategy_spectral_resolution`
  and `get_safe_worker_count` in THIS module, which is what the tests patch)
- _prepare_robustness_inputs, _prepare_robustness_nominal_optics (`calculate_RT_vectorized_real_HL`, patched as well)
- _expand_with_resolution_variants, _ablation_profile

and, in the modules it imports back (S5.2, 2026-10-01; every name is still importable from here):
- certus_strat_robustness_wrappers    _IdxWrapper, _SafeLocalClues
- certus_strat_robustness_noise       noise levels, resolution noise factor, Sobol and stream seeds
- certus_strat_robustness_gate        the crash-rate gate, the filter of finite scores
- certus_strat_robustness_diagnostics margin profile, critical layer, forced layers, witness resets
- certus_strat_robustness_rate        the deposition-rate variants (RATE_* constants)
- certus_strat_robustness_slit        spectral resolution and slit-bias profiles
- certus_strat_robustness_task        _test_strategy_robustness_task (one strategy, in a worker)
- certus_strat_robustness_results     finalization and the transmission-floor check

None of them imports a module of the strat import cycle at module level (they do it inside the function that needs it), so
the cycle of tests/architecture_debt.json does not grow.
"""

import logging
import concurrent.futures
import time
import numpy as np
from typing import Any

from certus_physics import SLIT_PROFILE_NODES, arange_inclusive, calculate_RT_vectorized_real_HL

from certus.core.certus_core import (
    NUMERICAL_FAULT_EXCEPTIONS,
    get_safe_worker_count,
)

from certus.utils.certus_exclusions import filter_params_for_gui

from certus.core.certus_strat_config import (  # type: ignore[attr-defined]
    APP_CONTEXT,
    RobustnessContext,
    precompute_clues_and_matrices,
    _emit_stat,
)

from certus.core.certus_strat_ranking import STRATEGY_ID_SLIT_BASE, _filter_valid_robustness_strategies

# What moved out (S5.2) is imported back here, every name: this module stays the one place where the callers, the scripts and the
# tests import them from, and where the tests PATCH the four names that the functions below look up (see `_execute_robustness_tasks`).
from certus.core.certus_strat_robustness_wrappers import (
    _IdxWrapper,
    _SafeLocalClues,
)
from certus.core.certus_strat_robustness_noise import (
    INDEX_CORRIDOR_DEFAULT,
    RESOLUTION_NOISE_FACTOR,
    _SOBOL_NOISE_CACHE,
    _affine_stream_seed,
    _get_cached_sobol_noise,
    _index_stream_seed,
    _parse_noise_factors,
    _resolution_noise_factor,
    _resolve_robustness_noise_levels,
    _signal_noise_stream_seed,
)
from certus.core.certus_strat_robustness_gate import (
    CRASH_GATE_CONFIDENCE_KEY,
    CRASH_RATE_TOLERANCE,
    _crash_gate_rejects,
    _filter_finite_robustness_scores,
    _worst_finite_rmse,
    crash_rate_lower_bound,
)
from certus.core.certus_strat_robustness_diagnostics import (
    _CAUSE_WORDS,
    _MARGIN_REPORT_CEILING_A,
    _critical_layer,
    _margin_profile_sparse,
    _phase_a_forced_layers,
    _resolve_witness_resets,
    _worst_layer_swing,
)
from certus.core.certus_strat_robustness_rate import (
    RATE_MAX_VARIANTS_PER_STRATEGY,
    RATE_MIN_LAYER,
    RATE_MIN_LAYERS_PER_BLOCK,
    RATE_SWING_MIN_DEFAULT,
    RATE_VARIANT_TOP_N_DEFAUT,
    _RateSwingContext,
    _expand_with_rate_variants,
    _optical_prefix_variants,
    _rate_candidate_layers,
    _rate_swing_candidates,
    _variant_id,
    _wl_de_la_couche,
)
from certus.core.certus_strat_robustness_slit import (
    NOMINAL_RESOLUTION_NM,
    RESOLUTION_SEARCH_SET,
    _SLIT_CACHE_MAX,
    _SLIT_GL_W,
    _SLIT_GL_X,
    _SLIT_PROFILE_CACHE,
    _calculate_strategy_spectral_resolution,
    _slit_bias_profiles,
    _strategy_resolution,
    phase_a_slit_profiles,
)
from certus.core.certus_strat_robustness_task import (
    _test_strategy_robustness_task,
)
from certus.core.certus_strat_robustness_results import (
    _build_layer_wavelengths_from_strategy,
    _finalize_robustness_results,
    _get_best_noise_results,
    _validate_strategy_min_transmission_floor,
)


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
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

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
    expand_variants: bool = True,
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
    # 🔑 EXPANSION ONLY ON THE PASS THAT DECIDES. On the screening pass this is False,
    # so 241 candidates stay 241 instead of becoming 3856; the survivors are expanded
    # afterwards. See `run_final_simulation_block`.
    if expand_variants:
        # 🔑 `opti_results` already carries these -- `_prepare_robustness_nominal_optics`
        # reads `clues_at_wl` from it a few lines above in this same module, and the
        # pipeline (`certus_strat_pipeline.py:105-106`) fills the other two. Nothing new
        # is computed here; this only makes them reach the one function that needs them
        # to place Rate candidates by SWING instead of by block boundary alone.
        all_strategies = _expand_with_rate_variants(
            all_strategies, params, num_layers, logger,
            p_thick_nominal=p_thick_nominal,
            nominal_matrix_cache=opti_results.get("nominal_matrix_cache"),
            all_wls=opti_results.get("all_wls"),
            clues_at_wl=opti_results.get("clues_at_wl"),
        )
        # A18 AFTER the Rate variants, so a Rate layer is evaluated at each slit too: the
        # two degrees of freedom are independent, nothing couples them here.
        all_strategies = _expand_with_resolution_variants(
            all_strategies, params, logger, p_thick_nominal
        )
    # 🔴 The curvature must be attached BEFORE the simulation runs, not after.
    # `_calculate_strategy_spectral_resolution` was already called on every strategy --
    # but AFTERWARDS, to fill `min_resolution` in the result. Too late to feed a bias
    # into the very simulation that produced it. Computed here it costs the same call,
    # simply moved, and ONLY when the bias is asked for.
    if bool(params.get("slit_bias_enabled", True)):
        _slit_b = float(params.get("monochromator_resolution_nm", 2.0) or 2.0)
        _n_before = len(_SLIT_PROFILE_CACHE)
        _t0 = time.perf_counter()
        for _st in all_strategies:
            try:
                # 🔴 EACH STRATEGY AT ITS OWN SLIT (A18). The bias goes as B^2, so handing
                # every variant the run-level width would make the four widths differ only
                # by their NOISE and not by their BIAS -- half the effect, silently.
                _st["slit_profile"] = _slit_bias_profiles(
                    _st, p_thick_nominal, params, _strategy_resolution(_st, params)
                )
            except Exception:  # noqa: BLE001 -- a missing profile disables the bias
                _st["slit_profile"] = None                    # for that strategy alone
        n_ok = sum(1 for _st in all_strategies if _st.get("slit_profile") is not None)
        logger.info(
            f"[SLIT] slit bias active, {n_ok}/{len(all_strategies)} strategies "
            f"-- slit {_slit_b:g} nm, profile of {SLIT_PROFILE_NODES} nodes, "
            f"{len(_SLIT_PROFILE_CACHE) - _n_before} NEW profiles in "
            f"{time.perf_counter() - _t0:.1f} s (cache: {len(_SLIT_PROFILE_CACHE)})"
        )
    return all_strategies, noise_levels or [], p_thick_nominal, num_layers


def _expand_with_resolution_variants(
    strategies: list[dict[str, Any]],
    params: dict[str, Any],
    logger: logging.Logger,
    p_thick_nominal: list[float] | None = None,
) -> list[dict[str, Any]]:
    """A18 -- put the four slit widths in competition, as part of the strategy.

    🔑 WHY PHASE B AND NOWHERE ELSE. 12.7 settled the placement and the reasoning is
    worth keeping: **Phase A cannot** decide it, because it judges one layer at a time
    while the slit is a compromise over the whole run -- the binding layer is not known
    until the strategy exists. **The DP cannot** either: it minimises a SUM of per-layer
    costs, and the slit is a single global choice that does not decompose additively;
    putting it in the DP state would multiply that state by four and buy nothing. Phase B
    is the only stage that measures the quantity that decides.

    🔑 AND THE INTERESTING EFFECT IS NOT THE FOUR-WAY CHOICE -- it is that the slit
    changes WHICH WAVELENGTHS ARE GOOD. A lambda sitting in a spectrally smooth region
    tolerates the 5 nm slit and pockets the /1.5 noise bonus; one near the band edge
    demands 1 nm and pays the x2. The worth of a wavelength therefore now depends on the
    smoothness of its neighbourhood, not only on its dynamic range.

    🔴 ON BY DEFAULT since 2026-08-12 — 👤 *"the slit is systematically searched, it is a
    PREREQUISITE"*. A strategy that does not carry its own slit is not executable in the
    chamber: the operator would have to pick a width the search never evaluated. Like the
    slit bias, Rate and the index corridor, this breaks C1 deliberately; the historical
    path is `search_resolution: false`.

    🔑 AND `min_resolution` IS NOW A PREFILTER -- but only after it was counted, which
    is what 20-control 4 demanded. 📏 Measured 2026-08-12 on the judge of paix, the rule
    `slit <= res_limit` rejects **31 % of (layer, lambda) pairs at 5 nm**, 14 % at 2 nm,
    2 % at 1 nm and 0.5 % at 0.5 nm. It is therefore precisely good at one thing: spotting
    when the WIDE slit is inadmissible. Using it as a general couperet would prune 12 %
    and buy nothing; using it where it discriminates costs the same and closes nothing.

    ⚠️ THE RUN'S OWN SLIT IS NEVER SKIPPED, whatever the curvature says. The criterion is
    a diagnostic, not a verdict (12.7): a strategy whose binding layer forbids even 2 nm
    must still be evaluated and reported as such, not made to vanish. Only the GENERATED
    variants are filtered.

    🔴 AND WHY THE 5 nm SETTING IS KEPT AT ALL. 📏 Two nominal runs, 2026-08-12: on the
    48-layer dichroic no 5 nm strategy is ranked at all -- the bias reaches 33 % of the
    swing on the deep layers and nothing terminates. But on the three-cavity bandpass,
    **36 of 380 ranked strategies use 5 nm, the best at rank 41**: it works there, it is
    merely beaten. Deleting the setting would take from STRAT the ability to say so on a
    component with coarser spectral structure, where the /1.5 noise bonus would be free.
    """
    if not bool(params.get("search_resolution", True)):
        return strategies
    base = float(params.get("monochromator_resolution_nm", NOMINAL_RESOLUTION_NM)
                 or NOMINAL_RESOLUTION_NM)
    out: list[dict[str, Any]] = []
    next_id = STRATEGY_ID_SLIT_BASE
    skipped: dict[float, int] = {}
    for strat in strategies:
        # The widest slit the curvature of THIS strategy tolerates. `None` when it
        # cannot be computed: nothing is filtered then, rather than filtering on an
        # invented value.
        res_lim = None
        if p_thick_nominal is not None:
            try:
                res_lim = float(
                    _calculate_strategy_spectral_resolution(strat, p_thick_nominal, params)[0]
                )
            except Exception:  # noqa: BLE001 -- an unavailable criterion filters nothing
                res_lim = None
        # The strategy as given keeps its identity and the run's slit: the comparison is
        # against itself, so the baseline must stay bit-identical to a no-search run.
        s0 = dict(strat)
        s0["monochromator_resolution_nm"] = base
        out.append(s0)
        for slit in RESOLUTION_SEARCH_SET:
            if slit == base:
                continue
            if res_lim is not None and slit > res_lim:
                skipped[slit] = skipped.get(slit, 0) + 1
                continue
            v = dict(strat)
            v["blocks"] = list(strat.get("blocks") or [])
            v["monochromator_resolution_nm"] = slit
            v["strategy_id"] = _variant_id(strat.get("strategy_id"), next_id)
            v["origin"] = f"SLIT{slit:g}(from {strat.get('strategy_id', '?')})"
            next_id += 1
            out.append(v)
    # 🔴 What is skipped is COUNTED and SAID. A silent pruning reads as full coverage,
    # and that is the failure mode this repository has been paying for since the
    # beginning: it does not produce an error, it produces a plausible result.
    sk = "  |  saute par la courbure : " + ", ".join(
        f"{k:g} nm x{v}" for k, v in sorted(skipped.items(), reverse=True)
    ) if skipped else ""
    logger.info(
        f"[SLIT] A18 recherche de fente : {len(strategies)} strategies x "
        f"{len(RESOLUTION_SEARCH_SET)} fentes {list(RESOLUTION_SEARCH_SET)} "
        f"-> {len(out)} candidates{sk}"
    )
    return out


#: The error sources switched off one by one, with the params key to neutralise
#: and the name the operator will read. The READING NOISE is deliberately one of them: it
#: serves as a control. 📏 Measured on 2026-08-12, it weighs ~0 % on both components -- and
#: that is expected, it is noise, it averages out over the draws whereas the other three
#: are BIASES that push every draw the same way. An ablation where the noise came out
#: dominant would signal a set-up error, not a result.
ABLATION_SOURCES: tuple[tuple[str, str, object], ...] = (
    ("slit_bias_enabled", "biais de fente", False),
    ("index_corridor", "corridor d'indice", 0.0),
    ("photometric_curvature_amp", "courbure photometrique", 0.0),
    ("trigger_tolerance_zero", "bruit de lecture", None),
)

#: Monte-Carlo depth of the ablation. Deliberately lower than that of the
#: ranking: a RELATIVE CONTRIBUTION is measured, not a score. 64 draws give
#: ~12 % dispersion, which is ample to separate a 60 % source from a 2 % one --
#: and would not be enough to separate two strategies, which is not done here.
ABLATION_NUM_RUNS: int = 64

#: Number of profiled strategies. 👤 2026-08-12: "for each of the 20 best
#: strategies, rank the influence of each defect source".
ABLATION_TOP_K: int = 20


def _ablation_profile(
    strategy: dict[str, Any],
    base_score: float,
    *,
    params: dict[str, Any],
    p_thick_nominal: list[float],
    clues_at_wl: dict,
    wl_arr,
    nH_arr,
    nL_arr,
    nSub_arr,
    T_nom,
    full_dyn_grid: dict,
    logger,
) -> list[dict[str, Any]]:
    """Ranking of the defect sources by their contribution, FOR THIS strategy.

    👤 2026-08-12: *"I would like to know which defect is the most problematic... for
    each of the 20 best strategies, it will let the user better understand where the
    problems come from."*

    Each source is switched off in turn and the score is read again. The contribution is
    `1 - score_without / score_with`: the share of the score that disappears when the
    source disappears.

    🔴 WHAT THIS NUMBER IS NOT. The contributions DO NOT ADD UP to 100 %. The sources
    interact -- the corridor distorts the thickness AND the index of the finished
    filter, the slit moves the anchor POEM will use next -- so switching off two sources
    does not remove the sum of their two shares. Reading these figures as slices of a
    cake would be a mistake. They are DERIVATIVES: "by how much the score drops if I
    remove this one", each taken alone.

    📏 What it gives, measured on the winners of 2026-08-12: on the dichroic the index
    corridor weighs **69 %** against 1 % for the curvature and 0 % for the slit -- one
    source crushes everything. On the bandpass, slit **16 %** and corridor **15 %**:
    nobody dominates, it is already a compromise. **The same model thus gives two
    opposite diagnoses depending on the component**, which is exactly why this profile
    belongs in the report rather than in a general note.

    ⚠️ And for the corridor, the displayed share is rather an UNDERESTIMATE: it acts
    twice, on the deposited thicknesses and on the real index of the finished filter,
    whereas some of the metrics only see the first.
    """
    if not (base_score and base_score > 0.0):
        return []
    out: list[dict[str, Any]] = []
    for key, label, neutral in ABLATION_SOURCES:
        try:
            p2 = dict(params)
            if key == "trigger_tolerance_zero":
                rs = dict(p2.get("reality_sim_params") or {})
                rs["trigger_tolerance"] = 0.0
                p2["reality_sim_params"] = rs
                p2["thickness_tolerance_nm"] = 0.0
            else:
                p2[key] = neutral
            # A single strategy, a reduced depth: this is a diagnostic.
            res = _execute_robustness_tasks(
                all_strategies=[strategy],
                noise_levels=_resolve_robustness_noise_levels(p2),
                num_runs=ABLATION_NUM_RUNS,
                p_thick_nominal=p_thick_nominal,
                clues_at_wl=clues_at_wl,
                params_safe=p2,
                wl_arr=wl_arr,
                nH_arr=nH_arr,
                nL_arr=nL_arr,
                nSub_arr=nSub_arr,
                T_nom=T_nom,
                full_dyn_grid=full_dyn_grid,
                params=p2,
                logger=logger,
                n_layers_matrix_precomp=None,
            )
            if not res:
                continue
            s2 = float(res[0].get("robustness_score", float("nan")))
            if not np.isfinite(s2):
                continue
            out.append({
                "source": label,
                "score_without": s2,
                # Positive = removing the source IMPROVES, so it does harm. Negative =
                # removing it degrades, which happens and must show rather than being
                # clipped to zero: a source can MASK another one.
                "contribution": 1.0 - s2 / base_score,
            })
        except Exception as exc:  # noqa: BLE001 -- a diagnostic never breaks a run
            logger.debug(f"[ABLATION] {label} : {exc!r}")
    out.sort(key=lambda d: -d["contribution"])
    return out


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
    if len(all_strategies) > 1:
        logger.info(
            f"Running robustness tests on {len(all_strategies)} strategies (ThreadPoolExecutor with {max_workers} workers)..."
        )
    else:
        logger.debug(
            f"Running robustness tests on 1 strategy (ThreadPoolExecutor with {max_workers} workers)..."
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
                    min_res, bad_layer, _curv = _calculate_strategy_spectral_resolution(
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
                        min_res, bad_layer, _curv = _calculate_strategy_spectral_resolution(
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


# _select_best_strat_result has been moved to certus_strat_ranking.py


def run_final_simulation_block(
    opti_results: dict[str, Any],
    params: dict[str, Any],
    num_runs: int = 150,
    noise_levels: list[float] | None = None,
    expand_variants: bool = True,
) -> dict[str, Any]:
    """Phase B robustness screening: evaluate every candidate strategy under noise.

    ``expand_variants`` -- generate the Rate and slit variants of each strategy.

    🔑 FALSE ON THE SCREENING PASS, and that is the whole point. Rate multiplies the
    candidate count by up to 4 and the slit search by 4 again: 📏 measured 2026-08-12 on
    the judge of paix, 241 strategies became **3856**, and all 3856 went through every
    stage. 👤 asked for the Rate trial *"on the ten best strategies"* -- on the best, not
    on all of them; the expansion sat before the screening out of implementation
    convenience, not necessity.

    Screening 241, keeping ~30 and expanding THOSE gives ~721 strategy-evaluations
    instead of 3856 -- a factor 5.3, with no physics touched. And it is the sounder
    order: screening a Rate variant of a mediocre strategy spends Monte-Carlo to rank
    two bad answers against each other.

    ⚠️ THE RESERVATION, and it is real. A strategy that is mediocre under POEM might be
    good with one Rate layer or a different slit, and the screening would drop it before
    it could show that. It cannot be excluded without measuring. Keeping 30 survivors
    rather than 10 costs little and largely closes the question -- 17-27 measured that
    opening the screening wider finds nothing better on this stack.
    """
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
        expand_variants=expand_variants,
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

    wls_to_fetch: set[float] = set()
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
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

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

    # ---- ABLATION PROFILE on the best ones, 👤 2026-08-12 -------------------
    #
    # "for each of the 20 best strategies, rank the influence of each defect
    # source. It will let the user better understand where the problems come from."
    #
    # 🔴 AFTER the ranking, never before: it is a DIAGNOSTIC, it must not be able to
    # influence the order. And only on the best ones -- profiling 400 strategies would
    # cost four times the run to explain candidates nobody will deposit.
    if bool(params.get("ablation_profile", True)) and strategies_results:
        top = sorted(strategies_results,
                     key=lambda r: float(r.get("robustness_score", 1e18)))[:ABLATION_TOP_K]
        t_abl = time.perf_counter()
        for res in top:
            res["ablation"] = _ablation_profile(
                res.get("strategy") or {},
                float(res.get("robustness_score", 0.0) or 0.0),
                params=params, p_thick_nominal=p_thick_nominal, clues_at_wl=clues_at_wl,
                wl_arr=wl_arr, nH_arr=nH_arr, nL_arr=nL_arr, nSub_arr=nSub_arr,
                T_nom=T_nom, full_dyn_grid=full_dyn_grid, logger=logger,
            )
        done = [r for r in top if r.get("ablation")]
        if done:
            first = done[0]["ablation"][0]
            logger.info(
                f"[ABLATION] {len(done)} strategies profiled in "
                f"{time.perf_counter() - t_abl:.1f} s -- dominant source of the 1st: "
                f"{first['source']} ({first['contribution']:+.0%})"
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

        _consensus_tasks: list[tuple[int, str, tuple, int, tuple, concurrent.futures.Future | None]] = []
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
                for local_idx, sid, _strat_sig, seed, cache_key, _ in _consensus_tasks:
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

        for _local_idx, item in enumerate(candidates):
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


