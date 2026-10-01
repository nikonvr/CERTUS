"""CERTUS STRAT ROBUSTNESS - the finalization of the results and the transmission-floor check (moved out of certus_strat_robustness.py, S5.2)."""

import logging
import numpy as np
from typing import Any

from certus.core.certus_strat_robustness_wrappers import _IdxWrapper


def _finalize_robustness_results(
    strategies_results: list[dict[str, Any]],
    params: dict[str, Any],
    logger: logging.Logger,
) -> dict[str, Any]:
    """Reduce memory usage and format final output for robustness ranking."""
    from certus.core.certus_strat_ranking import _select_best_strat_result
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
