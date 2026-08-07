# =============================================================================
# CERTUS STRAT - Core numerical and physics logic
# =============================================================================
import sys
import os
from pathlib import Path
import concurrent.futures

import ctypes

import hashlib

import io

import json

import logging

import queue

import threading

import time

import traceback

from collections import deque

from typing import Any, Dict
from dataclasses import dataclass

import numpy as np

import pandas as pd
from pydantic import ValidationError

from concurrent.futures import ThreadPoolExecutor




# Import access config
from certus.core.certus_core import (
    NUMERICAL_FAULT_EXCEPTIONS,
    SUBSTRATE_MAPPING,
    get_export_config,
    get_resource_path,
    get_safe_worker_count,
    certus_timestamp_display,
    certus_timestamp_file,
    setup_module_logging,
)

from certus.utils.certus_data import (
    OPENPYXL_AVAILABLE,
    PerformanceMonitor,
    SharedArrayManager,
    SharedArrayWorker,
    SharedIndicesManager,
    SharedIndicesWorker,
    TimingLogger,
    generate_html_report,
    get_missing_manifest_fields,
    numpy_encoder,
    to_csv_robust,
    to_excel_robust,
)

from certus_physics import (  # STRAT-specific kernels (previously imported from certus.core._certus_physics_impl)
    K_MAX_LAYER_BACKSIDE,
    K_MAX_SUBSTRATE_BACKSIDE,
    MaterialDatabase,
    NON_MONOTONIC_MODE_ATTENUATE,
    NON_MONOTONIC_MODE_REJECT,
    arange_inclusive,
    calculate_detailed_growth,
    calculate_RT_batch_kernel,
    calculate_RT_vectorized_real_HL,
    calculate_extrema_distances,
    compute_batch_rmse,
    compute_T_front_at_layer,
    compute_T_front_profile,
    compute_dT_dd_kernel,
    find_nucleation_adaptive_kernel,
    get_refractive_index,
    get_refractive_clues_vectorized,
    precompute_matrix_cache_kernel,
    rank_nucleation_candidates_kernel,
    simulate_growth_kernel,
    simulate_stack_robustness_batch,
    update_run_states_kernel,
    validate_wavelengths_batch,
    validate_backside_real_clues,
)

# Import context system (replaces global variables)

from certus.utils.certus_strat_context import (
    StratContext,
    get_context,
    SYM_MISSING_DISTANCE,
    FAST_AUTO_BLOCKS_DIVIDER_PRESETS,
    _clamp01,
    _compute_local_extrema_symmetry_score,
    _build_symmetry_bonus_map,
    _build_layer_importance_map,
    _compute_blocks_range_contractual,
    _compute_blocks_range_for_params,
    _validate_strategy_blocks_contract,
    _augment_solution_cost_with_sym,
    _origin_family,
    _parse_origin_priority_map,
    _origin_priority_from_map,
    _apply_family_diversity,
    _blocks_signature,
    _strategy_signature,
    _strategy_id_sort_token,
    _extract_rmse_p95_for_noise,
    _dedupe_preserve_order_int,
    _default_consensus_seeds,
    _resolve_consensus_top_k,
    _resolve_consensus_num_seeds,
    _resolve_consensus_seed_stride,
    _resolve_consensus_num_runs,
)

# Robust db clues (fixed xlsx)

from certus.utils.certus_strat_db import RobustMaterialDatabase
from certus.utils.certus_dto import StratConfigDTO


from certus.utils.certus_export import show_copy_excel_feedback

from certus.utils.certus_load_summary import build_summary_plain_text, show_load_summary_dialog
from certus.utils.certus_ux import build_premium_overrides, OBJ
from certus.core.certus_metrology import ValidationStatus
from certus.utils.certus_services import IndexFitRequest, IndexFitService
from certus.workers.certus_strat_workers_dto import WorkerThreadRequest, WorkerThreadResult
import certus.utils.certus_strat_service as _strat_service_module
from certus.utils.certus_strat_service import (
    StratStrategyService,
    calculate_nominal_properties,
    calculate_RT_normal_real,
    calculate_dynamics_ULTIMATE,
    _select_candidates_phase_a,
    _validate_candidates_phase_a as _service_validate_candidates_phase_a,
    compute_probe_offset_nm_from_ratio,
    generate_noise_array,
    NOISE_DISTRIBUTION_GAUSSIAN,
    select_best_strat_result,
    extract_best_rmse,
)


_validate_phase_a_bridge_lock = threading.Lock()

from certus.core.certus_strat_utils import _IdxWrapper

# Global scientific display configuration

PERF_MONITOR = PerformanceMonitor()

# setup_numba_cache skipped (handled by configure_numba_env + file lock)

# PyQtGraph configured via COMMON utility

    # setup_pyqtgraph_defaults moved to UI initialization

# === CACHE SYSTEM FOR PLOTS ===
# PlotCache and ThreadSafeCounter have been extracted to certus_strat_context.
# Imported here for full backward compatibility.
from certus.utils.certus_strat_context import PlotCache, ThreadSafeCounter  # noqa: E402


import certus.core.certus_strat_config as _config
for _k, _v in _config.__dict__.items():
    if not _k.startswith("__"):
        globals()[_k] = _v

def _run_phase_a_hybrid_loop(
    params: dict[str, Any],
    p_thick_nominal: list[float],
    clues_at_wl: dict[str, Any],
    scan_wl_range: np.ndarray,
    num_layers: int,
    logger: logging.Logger,
    progress_signal: Any,
    l0: float,
) -> tuple[dict[int, list[dict[str, float]]], dict[int, dict[float, float]], dict[str, Any], bool]:
    raw_results_thickness: dict[int, list[dict[str, float]]] = {}
    full_dynamics_grid: dict[int, dict[float, float]] = {}
    num_runs = int(params.get("mc_runs_block", 100))
    phase_a_observability = {
        "layers": [],
        "scan_wl_count": int(len(scan_wl_range)),
        "mc_runs_block": int(num_runs),
    }
    run_states = [{"p_thick_sim": [], "M_cache_sim": {}} for _ in range(num_runs)]

    # Le logger est un argument nomme de cette fonction, mais il n'etait pas dans
    # params : _validate_candidates_phase_a le lisait donc a vide et l'elimination
    # de la Phase A etait entierement muette. setdefault pour ne pas ecraser le
    # logger que certus_strat_workers y place deja sur d'autres chemins d'entree.
    # ⚠️ PAS `setdefault` : `params` n'est pas toujours un dict. Sur le chemin
    # `phase_a_only=True` (certus_strat_workers.py, _execute_nucleation_and_cost_mapping)
    # c'est un `StratParamsDTO`, qui herite de `Mapping` et non de `MutableMapping` :
    # il expose `get` et `__setitem__` mais PAS `setdefault`. Un `setdefault` y levait
    # `AttributeError` et tuait le pipeline entier en 13 s, avec RESULT=None.
    if params.get("logger") is None:
        params["logger"] = logger
    # Recensement par couche remis a zero : params peut etre reutilise d'un run a l'autre.
    params["phase_a_admissibility_stats"] = []

    try:
        noise_tol = float(params.get("reality_sim_params", {}).get("trigger_tolerance", 0.1)) / 100.0
    except KeyError:
        noise_tol = 0.001
    phase_a_seed = int(params.get("phase_a_seed", params.get("robustness_seed", 42)))
    params["phase_a_seed"] = phase_a_seed
    phase_a_rng = np.random.default_rng(phase_a_seed)

    global_noise_matrix = generate_noise_array(
        (num_runs, num_layers),
        noise_tol,
        NOISE_DISTRIBUTION_GAUSSIAN,
        rng=phase_a_rng,
    )

    idx_dict_opt = _IdxWrapper(clues_at_wl)
    block_start_running = 0

    for i_layer in range(num_layers):
        if params.get("stop_requested", False):
            logger.warning(f"Stop requested during Phase A at layer {i_layer}")
            break
        if progress_signal:
            pct = int((i_layer / num_layers) * 40)
            progress_signal.emit(pct, f"Phase A: Computing Layer {i_layer + 1}/{num_layers}")

        current_avg_stack = []
        if i_layer > 0:
            for j in range(i_layer):
                avg_t = np.mean([run["p_thick_sim"][j] for run in run_states])
                current_avg_stack.append(avg_t)

        n_H_scan = np.array([idx_dict_opt[float(wl)]["H"] for wl in scan_wl_range], dtype=np.complex128)
        n_L_scan = np.array([idx_dict_opt[float(wl)]["L"] for wl in scan_wl_range], dtype=np.complex128)

        layer_matrix_cache = precompute_matrix_cache_kernel(
            scan_wl_range.astype(np.float64),
            n_H_scan,
            n_L_scan,
            np.array(current_avg_stack, dtype=np.float64),
            i_layer,
        )

        if i_layer > 0:
            prev_data = raw_results_thickness.get(i_layer - 1, [])
            params["prev_layer_wl"] = float(prev_data[0]["wl"]) if prev_data else -1.0
        else:
            params["prev_layer_wl"] = -1.0

        # --- ERREUR AMONT REELLEMENT ACCUMULEE, mesuree et non postulee -------
        #
        # C'est l'echelle sur laquelle le gain de compensation se convertit en
        # nanometres : gain x erreur_amont = ce que la couche courante herite.
        # On la prend sur les etats Monte-Carlo effectivement propages, au meme
        # percentile que le cout local (P95), pour que les deux termes du cout
        # soient la meme statistique de la meme grandeur.
        params["phase_a_prev_error_nm"] = 0.0
        if i_layer > 0:
            prev_sim = np.array(
                [run["p_thick_sim"][i_layer - 1] for run in run_states], dtype=np.float64
            )
            dev = np.abs(prev_sim - float(p_thick_nominal[i_layer - 1]))
            dev = dev[dev < 1e5]  # les runs plantes ne sont pas une erreur d'epaisseur
            if dev.size:
                params["phase_a_prev_error_nm"] = float(np.percentile(dev, 95))

        # --- DEBUT DU BLOC MONOCHROMATIQUE EN COURS ---------------------------
        # A lambda inchangee le signal de monitoring est continu : les points
        # tournants deja traverses restent exploitables. C'est ce qui donne leur
        # valeur aux blocs, et la Phase A y etait aveugle. block_start_running est
        # tenu a jour en fin d'iteration : il vaut ici l'indice de la premiere
        # couche du bloc auquel appartient la couche i_layer - 1.
        params["phase_a_block_start"] = block_start_running

        candidates, layer_full_dyn = _select_candidates_phase_a(
            scan_wl_range,
            i_layer,
            p_thick_nominal,
            clues_at_wl,
            layer_matrix_cache,
            scan_wl_range,
            params,
            l0,
            current_avg_stack=current_avg_stack,
        )
        full_dynamics_grid[i_layer] = layer_full_dyn

        results_thickness, sim_updates = _service_validate_candidates_phase_a(
            candidates,
            i_layer,
            num_runs,
            p_thick_nominal,
            clues_at_wl,
            params,
            run_states,
            global_noise_matrix[:, i_layer],
        )

        if i_layer == 0:
            nucleation_active = params.get("nucleation_wl") is not None
            if not nucleation_active:
                attenuation_factor = float(params.get("layer1_cost_attenuation_factor", 1.0))
                if 0.0 < attenuation_factor < 1.0:
                    for item in results_thickness:
                        item["cost"] *= attenuation_factor
                        item["std_dev"] *= attenuation_factor
                    logger.info(f"   -> Layer 1: Costs attenuated by factor {attenuation_factor}.")
                else:
                    logger.info("   -> Layer 1: No attenuation (factor >= 1.0).")
            else:
                logger.info("   -> Layer 1: Costs preserved (Smart Nucleation active).")

        raw_results_thickness[i_layer] = results_thickness
        best_cost = float(results_thickness[0]["cost"]) if results_thickness else None
        best_wl = float(results_thickness[0]["wl"]) if results_thickness else None

        best_entry = results_thickness[0] if results_thickness else {}
        phase_a_observability["layers"].append(
            {
                "layer": int(i_layer + 1),
                "selected_candidates_count": int(len(candidates)),
                "validated_candidates_count": int(len(results_thickness)),
                "best_wl": best_wl,
                "best_cost": best_cost,
                # Les trois grandeurs qui decident maintenant du classement, pour
                # qu'un ecart de choix soit lisible apres coup sans reinstrumenter.
                "best_cost_local": best_entry.get("cost_local"),
                "best_compensation_gain": best_entry.get("compensation_gain"),
                "best_crash_rate": best_entry.get("crash_rate"),
                "prev_error_nm": float(params.get("phase_a_prev_error_nm", 0.0)),
                "block_start": int(block_start_running),
                # Recensement de la regle d'admissibilite pour cette couche :
                # offertes, interdites sur plantage, interdites sur gain<0,
                # survivantes, taux de plantage minimal observe.
                "admissibility": next(
                    (
                        s
                        for s in reversed(params.get("phase_a_admissibility_stats", []))
                        if s.get("layer") == i_layer + 1
                    ),
                    None,
                ),
            }
        )

        # Le bloc courant se prolonge tant que la longueur d'onde retenue ne
        # change pas ; sinon un bloc neuf s'ouvre a cette couche.
        prev_wl_for_block = float(params.get("prev_layer_wl", -1.0))
        if i_layer == 0 or best_wl is None or prev_wl_for_block < 0.0 or abs(best_wl - prev_wl_for_block) > 0.1:
            block_start_running = i_layer

        for r_idx in range(num_runs):
            run_states[r_idx]["p_thick_sim"].append(sim_updates[r_idx])

    return raw_results_thickness, full_dynamics_grid, phase_a_observability, params.get("stop_requested", False)

def _normalize_phase_a_results(
    raw_results_thickness: dict[int, list[dict[str, float]]],
    num_layers: int,
) -> dict[int, list[dict[str, float]]]:
    total_sum_thick = 0.0
    total_count_thick = 0
    for i in range(num_layers):
        t_data = raw_results_thickness.get(i, [])
        if t_data:
            total_sum_thick += sum(item["cost"] for item in t_data)
            total_count_thick += len(t_data)
    mean_thickness = (total_sum_thick / total_count_thick) if total_count_thick > 0 else 1.0
    if abs(mean_thickness) < 1e-12:
        mean_thickness = 1.0

    raw_results_sq: dict[int, list[dict[str, float]]] = {}
    for i in range(num_layers):
        t_data = raw_results_thickness.get(i, [])
        if not t_data:
            continue
        sq_layer = []
        for item in t_data:
            cost_raw = item["cost"]
            cost_norm = cost_raw / mean_thickness
            sq_layer.append(
                {
                    "wl": item["wl"],
                    "cost": (cost_norm**2),
                    "cost_raw": cost_raw,
                }
            )
        sq_layer.sort(key=lambda x: x["cost"])
        raw_results_sq[i] = sq_layer
    return raw_results_sq

def build_M_before_cache(
    layer_wavelengths: np.ndarray,
    n_H_vals: np.ndarray,
    n_L_vals: np.ndarray,
    p_thick_arr: np.ndarray,
    num_layers: int,
) -> np.ndarray:
    """Matrices M_before de chaque couche, un appel de noyau par bloc spectral.

    Ce cache ne depend que de l'empilement nominal et du decoupage en blocs de
    longueur d'onde. Il etait construit DEUX FOIS par strategie evaluee, a
    l'identique : ici pour dT/dd, et une seconde fois dans
    ``_test_strategy_robustness_task`` pour le profil theorique des couches.
    """
    M_before_all = np.zeros((num_layers, 2, 2), dtype=np.complex128)
    if num_layers == 0:
        return M_before_all
    M_before_all[0] = np.eye(2, dtype=np.complex128)

    # Precompute M_before per wavelength block to avoid O(N²) recomputation (C2 fix).
    # Within a block all layers share the same monitoring wavelength, so one
    # precompute_matrix_cache_kernel call covers every layer in that block.
    block_starts = [0]
    for i in range(1, num_layers):
        if abs(float(layer_wavelengths[i]) - float(layer_wavelengths[block_starts[-1]])) > 1e-3:
            block_starts.append(i)

    for b_idx in range(len(block_starts)):
        b_start = block_starts[b_idx]
        b_end = block_starts[b_idx + 1] if b_idx + 1 < len(block_starts) else num_layers
        wl_b = float(layer_wavelengths[b_start])
        if wl_b < 0.1 or b_end <= 1:
            continue
        last_layer = b_end - 1
        if last_layer > 0:
            cache = precompute_matrix_cache_kernel(
                np.array([wl_b], dtype=np.float64),
                np.array([n_H_vals[b_start]], dtype=np.complex128),
                np.array([n_L_vals[b_start]], dtype=np.complex128),
                p_thick_arr[:last_layer],
                last_layer,
            )
            for i in range(max(1, b_start), b_end):
                if i - 1 < cache.shape[0]:
                    M_before_all[i] = cache[i - 1, 0, :, :]

    return M_before_all


def _compute_dT_dd_per_layer(
    layer_wavelengths: np.ndarray,
    n_H_vals: np.ndarray,
    n_L_vals: np.ndarray,
    n_Sub_vals: np.ndarray,
    p_thick_nominal: list[float],
    h_nm: float = 0.5,
    M_before_all: np.ndarray | None = None,
) -> np.ndarray:
    """

    Compute dT/dd at nominal thickness for each layer (transmission sensitivity).

    Used when noise_domain is thickness_nm to convert thickness noise to transmission noise.

    ``M_before_all`` evite de reconstruire le cache de matrices quand l'appelant
    le possede deja ; laisse a None, le comportement est inchange.
    """

    num_layers = len(p_thick_nominal)

    p_thick_arr = np.array(p_thick_nominal, dtype=np.float64)

    if M_before_all is None:
        M_before_all = build_M_before_cache(
            layer_wavelengths, n_H_vals, n_L_vals, p_thick_arr, num_layers
        )

    # Boucle finale deportee dans un seul noyau compile : elle enchainait deux
    # appels njit par couche depuis Python.
    return compute_dT_dd_kernel(
        np.ascontiguousarray(layer_wavelengths, dtype=np.float64),
        np.ascontiguousarray(n_H_vals, dtype=np.complex128),
        np.ascontiguousarray(n_L_vals, dtype=np.complex128),
        np.ascontiguousarray(n_Sub_vals, dtype=np.complex128),
        p_thick_arr,
        M_before_all,
        float(h_nm),
    )

def _extract_local_extrema_points(d_vals: np.ndarray, t_vals: np.ndarray, eps: float = 1e-10) -> list[dict[str, float]]:
    """Find local extrema from sampled T(d) curve."""

    extrema: list[dict[str, float]] = []

    if len(d_vals) < 3 or len(t_vals) < 3:
        return extrema

    # Comparaisons vectorisees, puis boucle sur les SEULS extrema.
    #
    # La version precedente parcourait toute la grille en Python — un tour par
    # nanometre d'epaisseur — et convertissait trois scalaires numpy en float a
    # chaque tour, alors que les extrema se comptent sur les doigts d'une main.
    # Les comparaisons strictes et l'ordre de sortie sont conserves.
    prev_v = t_vals[:-2]
    cur_v = t_vals[1:-1]
    next_v = t_vals[2:]

    is_max = ((cur_v - prev_v) > eps) & ((cur_v - next_v) > eps)
    is_min = ((prev_v - cur_v) > eps) & ((next_v - cur_v) > eps)

    for j in np.flatnonzero(is_max | is_min):
        i = int(j) + 1
        extrema.append(
            {
                "type": "max" if is_max[j] else "min",
                "d_nm": float(d_vals[i]),
                "T": float(t_vals[i]),
            }
        )

    return extrema

def _compute_theoretical_layer_profile(
    wl_nm: float,
    n_current: complex,
    n_sub: complex,
    nominal_thickness: float,
    M_before: np.ndarray,
) -> dict[str, Any]:
    """Theoretical no-noise profile for one layer: Tinit/Textrema/Tfinal + distances."""

    M00, M01, M10, M11 = (
        M_before[0, 0],
        M_before[0, 1],
        M_before[1, 0],
        M_before[1, 1],
    )

    d_nom = float(max(0.0, nominal_thickness))

    n_steps = max(3, int(np.ceil(d_nom / 1.0)) + 1)

    d_grid = np.linspace(0.0, d_nom, n_steps, dtype=np.float64)

    # Un seul appel compile pour toute la grille, au lieu d'un par nanometre.
    # La boucle est passee du cote njit (compute_T_front_profile) : meme
    # arithmetique point par point, mais ~200 franchissements de frontiere
    # Python->njit economises par couche.
    t_grid = compute_T_front_profile(wl_nm, n_current, n_sub, M00, M01, M10, M11, d_grid)

    t_init = float(t_grid[0])

    t_final = float(t_grid[-1])

    extrema = _extract_local_extrema_points(d_grid, t_grid)

    dist_ps, dist_ns, dist_pe, dist_ne = calculate_extrema_distances(
        float(wl_nm), complex(n_current), complex(n_sub), d_nom, M_before
    )

    d_end_nearest = float(min(dist_pe, dist_ne))

    nearest_end_type = "between"

    nearest_curve_dist = d_end_nearest

    if extrema:
        nearest_ext = min(extrema, key=lambda e: abs(float(e.get("d_nm", 0.0)) - d_nom))

        nearest_curve_dist = float(abs(float(nearest_ext.get("d_nm", 0.0)) - d_nom))

        nearest_end_type = str(nearest_ext.get("type", "between")).lower()

    if nearest_end_type in {"min", "max"} and nearest_curve_dist <= 2.0:
        tfinal_class = f"near {nearest_end_type}"

    else:
        tfinal_class = "between"

    return {
        "Tinit": t_init,
        "Tfinal": t_final,
        "Textrema": extrema,
        "d_nom_nm": d_nom,
        "ext_prev_start": float(dist_ps),
        "ext_next_start": float(dist_ns),
        "ext_prev_end": float(dist_pe),
        "ext_next_end": float(dist_ne),
        "dist_prev_start": float(dist_ps),
        "dist_next_start": float(dist_ns),
        "dist_prev_end": float(dist_pe),
        "dist_next_end": float(dist_ne),
        "dist_end_nearest": d_end_nearest,
        "nearest_end_type": nearest_end_type,
        "nearest_end_dist_nm": nearest_curve_dist,
        "tfinal_class": tfinal_class,
        "extrema_count": int(len(extrema)),
    }

def _compute_strategy_symmetry_score_percent(
    theoretical_layer_profile: list[dict[str, Any]],
    window_ot: float,
) -> float:
    """

    Strategy-level symmetry score on [0, 100].

    Per layer, evaluate start/end local symmetry around extrema and keep the best

    (pseudo-symmetry included via the local score balance term), then average.

    """

    if not theoretical_layer_profile:
        return 0.0

    layer_scores: list[float] = []

    for prof in theoretical_layer_profile:
        try:
            s_start = _compute_local_extrema_symmetry_score(
                float(prof.get("ext_prev_start", prof.get("dist_prev_start", SYM_MISSING_DISTANCE))),
                float(prof.get("ext_next_start", prof.get("dist_next_start", SYM_MISSING_DISTANCE))),
                float(window_ot),
            )

            s_end = _compute_local_extrema_symmetry_score(
                float(prof.get("ext_prev_end", prof.get("dist_prev_end", SYM_MISSING_DISTANCE))),
                float(prof.get("ext_next_end", prof.get("dist_next_end", SYM_MISSING_DISTANCE))),
                float(window_ot),
            )

            layer_scores.append(max(float(s_start), float(s_end)))

        except (TypeError, ValueError) as exc:
            logging.getLogger("CERTUS").warning("Failed to compute symmetry score for layer: %s", exc)
            layer_scores.append(0.0)

    if not layer_scores:
        return 0.0

    return float(100.0 * _clamp01(float(np.mean(np.array(layer_scores, dtype=np.float64)))))
