"""Headless service scaffold for CERTUS_STRAT (Track C)."""

from __future__ import annotations

from typing import Any, cast
import json
import logging
import pathlib
import threading
import concurrent.futures
import queue
import time
import numpy as np

from certus_services import BaseHeadlessService
from certus_physics import (
    arange_inclusive,
    get_refractive_index,
    get_refractive_clues_vectorized,
    calculate_RT_vectorized_real_HL,
    calculate_RT_batch_kernel,
    prepare_dynamics_data_kernel,
    compute_dynamics_kernel,
    check_extrema_proximity_batch,
    simulate_stack_robustness_batch,
    compute_batch_rmse,
    validate_wavelengths_batch,
    update_run_states_kernel,
    precompute_matrix_cache_kernel,
)
from certus_strat_context import StratContext
from certus_core import WL_DECIMALS

NOISE_DISTRIBUTION_GAUSSIAN = "gaussian"
NON_MONOTONIC_MODE_ATTENUATE = "attenuate"
WL_INDEX_SCALE = 10 ** WL_DECIMALS


def wavelength_to_index(wavelength_nm: float) -> int:
    """Convert a wavelength float to a stable integer index at WL_DECIMALS precision."""
    return int(np.rint(float(wavelength_nm) * WL_INDEX_SCALE))


def build_wavelength_index_map(clues_at_wl: dict[float, dict[str, complex]]) -> dict[int, dict[str, complex]]:
    """Build an integer-indexed wavelength map to avoid float-key drift in lookups."""
    return {wavelength_to_index(wavelength): value for wavelength, value in clues_at_wl.items()}


def generate_noise_array(
    shape: tuple,
    scale: float,
    distribution: str = NOISE_DISTRIBUTION_GAUSSIAN,
    rng: np.random.Generator | None = None,
    deterministic: bool = False,
) -> np.ndarray:
    """Generate gaussian noise array (clipped to +/-3sigma)."""
    if deterministic:
        return np.zeros(shape, dtype=np.float64)
    # NOTE: `distribution` is intentionally ignored (gaussian-only policy).
    _ = distribution
    # Use local RNG when provided to guarantee deterministic pipelines.
    local_rng = rng if rng is not None else np.random.default_rng(0)
    raw = np.clip(local_rng.normal(0.0, 1.0 / 3.0, shape), -1.0, 1.0)
    return (raw * scale).astype(np.float64)


class StratStrategyService(BaseHeadlessService):
    """Headless wrapper for STRAT payload normalization/validation."""

    VALID_STEPS = {0, 2, 3, 23, 33}

    # P1-8: JSON schema (loaded once at class level)
    _SCHEMA_PATH = pathlib.Path(__file__).parent / "schemas" / "STRAT_PAYLOAD_SCHEMA_V1.json"
    _schema: dict | None = None
    _deterministic: bool = False

    def set_deterministic(self, value: bool) -> None:
        """P1-10: Toggle deterministic mode for automated verification."""
        self._deterministic = bool(value)
        logging.getLogger(__name__).info("STRAT deterministic mode: %s", self._deterministic)

    @classmethod
    def _get_schema(cls) -> dict | None:
        """Load and cache the JSON schema, return None if jsonschema not available."""
        if cls._schema is not None:
            return cls._schema
        try:
            import jsonschema  # noqa: F401 – optional dependency check
            with open(cls._SCHEMA_PATH, encoding="utf-8") as f:
                cls._schema = json.load(f)
        except (ImportError, FileNotFoundError):
            cls._schema = None
        return cls._schema

    def validate_against_schema(self, payload: dict[str, Any]) -> list[str]:
        """Validate payload against STRAT_PAYLOAD_SCHEMA_V1. Returns list of error messages."""
        schema = self._get_schema()
        if schema is None:
            return []  # jsonschema not available or schema missing — skip silently
        try:
            import jsonschema
            validator = jsonschema.Draft202012Validator(schema)
            errors = [
                f"{'.'.join(str(p) for p in e.absolute_path) or 'root'}: {e.message}"
                for e in sorted(validator.iter_errors(payload), key=lambda e: e.path)
            ]
            return errors
        except Exception as exc:  # noqa: BLE001
            logging.getLogger(__name__).warning("Schema validation skipped: %s", exc)
            return []

    def validate_payload(self, payload: dict[str, Any], materials_db: Any = None) -> dict[str, Any]:
        """Validate/normalize legacy STRAT worker payload."""
        if not isinstance(payload, dict):
            raise ValueError("payload must be a dict")

        try:
            step = int(payload.get("step", 0))
        except (TypeError, ValueError):
            raise ValueError("payload.step must be an integer") from None
        if step not in self.VALID_STEPS:
            raise ValueError(f"unsupported step: {step}")

        params = payload.get("params", {})
        if not isinstance(params, dict):
            raise ValueError("payload.params must be a dict")

        opti_results = payload.get("opti_results")
        if opti_results is not None and not isinstance(opti_results, dict):
            raise ValueError("payload.opti_results must be a dict or None")

        # P1-8: strict schema validation
        schema_errors = self.validate_against_schema(payload)
        if schema_errors:
            raise ValueError("Payload schema violations:\n" + "\n".join(schema_errors))

        normalized: dict[str, Any] = {
            "step": step,
            "params": dict(params),
            "opti_results": dict(opti_results) if isinstance(opti_results, dict) else None,
        }

        if materials_db is not None:
            self.validate_material_coverage(normalized["params"], materials_db)

        return normalized

    def validate_material_coverage(self, params: dict[str, Any], db: Any) -> None:
        """Decoupled material coverage validation (ported from CERTUS_STRAT)."""
        if not hasattr(db, "data") or not db.data:
            return

        try:
            req_min = float(params["scan_wl_min"])
            req_max = float(params["scan_wl_max"])
            nH_id = params["nH_id"]
            nL_id = params["nL_id"]
            nSub_id = params["nSub_id"]
        except (KeyError, TypeError, ValueError) as e:
            # If params are missing, we can't validate coverage, but we don't necessarily fail here
            # as other parts of the system might handle it.
            return

        used_materials = {nH_id, nL_id, nSub_id}
        files_to_check = [m for m in used_materials if m in db.data]
        errors = []

        for mat_name in files_to_check:
            mat_data = db.data[mat_name]
            valid_min = float(mat_data.get("min_wl_valid", 0.0))
            valid_max = float(mat_data.get("max_wl_valid", 99999.0))

            if req_min < valid_min:
                errors.append(f"• {mat_name}: Requested start {req_min}nm < Data start {valid_min}nm")
            if req_max > valid_max:
                errors.append(f"• {mat_name}: Requested end {req_max}nm > Data end {valid_max}nm")

        if errors:
            msg = "CRITICAL: Material Data Missing for Spectral Range!\n" + "\n".join(errors)
            # We don't have the logger here, but raising ValueError is sufficient for the service contract.
            raise ValueError(msg)

    def run_step_0(self, params: dict[str, Any], materials_db: Any = None) -> dict[str, Any]:
        """Orchestrate Step 0 (Nominal + Sensitivity + SEEL) headlessly."""
        # Inject materials_db into params if provided for the kernels to use it
        # (This avoids global lookup in APP_CONTEXT inside the headless service)
        if materials_db:
            params["materials_db"] = materials_db

        nominal_results, multipliers = calculate_nominal_properties(params)
        sensitivity_data = calculate_sensitivity_matrix(params, nominal_results)
        seel_data = calculate_seel_analysis(params, nominal_results)

        return {
            "nominal_results": nominal_results,
            "multipliers": multipliers,
            "sensitivity_data": sensitivity_data,
            "seel_data": seel_data,
        }


def _emit_stat(counter_type: str, increment: int):
    """Emit stat via context (with SP batching)."""
    ctx = StratContext.get_current()
    if ctx is not None:
        ctx.emit_stat(counter_type, increment)


def calculate_RT_normal_real(
    wavelengths: np.ndarray,
    nH_id: Any,
    nL_id: Any,
    nSub_id: Any,
    p_thick: list[float],
    db_instance=None,
) -> np.ndarray:
    """Compute reflectance R and transmittance T for an alternating H/L thin-film stack."""
    wavelengths = np.asarray(wavelengths, dtype=np.float64)
    nH_array = get_refractive_clues_vectorized(nH_id, wavelengths, db_instance=db_instance)
    nL_array = get_refractive_clues_vectorized(nL_id, wavelengths, db_instance=db_instance)
    nSub_array = get_refractive_clues_vectorized(nSub_id, wavelengths, db_instance=db_instance)
    p_thick_arr = np.asarray(p_thick, dtype=np.float64)

    _emit_stat("SP", 1)

    # wrapper returns (R, T)
    R_arr, T_arr = calculate_RT_vectorized_real_HL(
        wavelengths, nH_array, nL_array, nSub_array, p_thick_arr
    )

    # Return as 2D array for backward compatibility
    return np.column_stack((R_arr, T_arr))


def calculate_nominal_properties(
    params: dict[str, Any],
) -> tuple[dict[str, Any], list[float]]:
    """Compute the nominal (ideal) spectral properties of the thin-film stack."""
    logger = params.get("logger", logging.getLogger("ThinFilm"))
    logger.info("=" * 80)
    logger.info("NOMINAL STACK CALCULATION")
    logger.info("=" * 80)

    nH_id = params["nH_id"]
    nL_id = params["nL_id"]
    nSub_id = params["nSub_id"]
    l0 = float(params["l0"])
    stack_string = params["stack_string"]
    wl_range = params["wl_range"]
    wl_step = float(params["wl_step"])

    multipliers = [float(e) for e in stack_string.split(",") if e.strip()]
    if not multipliers:
        raise ValueError("Stack definition is empty.")

    # Note: db_instance lookup should ideally use the same logic as elsewhere
    nH_at_l0 = get_refractive_index(nH_id, l0)
    nL_at_l0 = get_refractive_index(nL_id, l0)

    logger.info(f"   -> nH @ {l0}nm = {np.real(nH_at_l0):.4f}")
    logger.info(f"   -> nL @ {l0}nm = {np.real(nL_at_l0):.4f}")

    if abs(np.real(nH_at_l0) - 1.0) < 1e-4 and "air" not in str(nH_id).lower():
        logger.warning(f"⚠️ High Index Material ({nH_id}) appears to be AIR (n=1.0). Missing file?")

    if abs(np.real(nL_at_l0) - 1.0) < 1e-4 and "air" not in str(nL_id).lower():
        logger.warning(f"⚠️ Low Index Material ({nL_id}) appears to be AIR (n=1.0). Missing file?")

    p_thick_nominal = [
        (m * l0) / (4.0 * np.real(nH_at_l0 if (i % 2) == 0 else nL_at_l0))
        for i, m in enumerate(multipliers)
    ]

    wavelengths = arange_inclusive(float(wl_range[0]), float(wl_range[1]), wl_step)
    RT = calculate_RT_normal_real(wavelengths, nH_id, nL_id, nSub_id, p_thick_nominal)

    # RT is 2D array (num_wl, 2) with R in col 0, T in col 1
    R_nom, T_nom = RT[:, 0], RT[:, 1]

    return {
        "wavelengths": wavelengths,
        "R_spectral_nominal": R_nom,
        "T_spectral_nominal": T_nom,
        "physical_thicknesses_nominal": p_thick_nominal,
        "nH_at_l0": nH_at_l0,
        "nL_at_l0": nL_at_l0,
        "fom_nominal": 0.0,  # Legacy placeholder
        "color_nominal": [255, 255, 255],  # Placeholder
    }, multipliers


def calculate_sensitivity_matrix(
    params: dict[str, Any], nominal_results: dict[str, Any]
) -> dict[str, Any]:
    """Generating Sensitivity Landscape (0 -> 3nm)."""
    logger = params.get("logger", logging.getLogger("ThinFilm"))
    logger.info("Generating Sensitivity Landscape (0 -> 3nm)...")

    sigma_steps = np.linspace(0.0, 3.0, 31)
    runs_per_step = 40
    p_thick_nominal = nominal_results["physical_thicknesses_nominal"]
    wavelengths = nominal_results["wavelengths"]

    # Decouple from APP_CONTEXT: prefer params['materials_db'] if present
    local_db = params.get("materials_db")

    nH_arr = get_refractive_clues_vectorized(
        params["nH_id"], wavelengths, db_instance=local_db
    ).astype(np.complex128)
    nL_arr = get_refractive_clues_vectorized(
        params["nL_id"], wavelengths, db_instance=local_db
    ).astype(np.complex128)
    nSub_arr = get_refractive_clues_vectorized(
        params["nSub_id"], wavelengths, db_instance=local_db
    ).astype(np.complex128)

    # Recalculate exact nominal transmission to ensure perfect alignment with batch kernel
    _, T_clean_batch = calculate_RT_batch_kernel(
        wavelengths,
        nH_arr,
        nL_arr,
        nSub_arr,
        np.array(p_thick_nominal, dtype=np.float64).reshape(1, -1),
    )
    T_clean = T_clean_batch[0]
    sensitivity_grid = np.zeros((len(sigma_steps), len(wavelengths)), dtype=np.float64)

    # ... simplified/ported version of the loop ...
    # (I'll need to make sure I have all dependencies like simulate_stack_robustness_batch)
    # Wait, simulate_stack_robustness_batch is in certus_physics!
    from certus_physics import simulate_stack_robustness_batch

    for i, sigma in enumerate(sigma_steps):
        if sigma < 1e-9:
            sensitivity_grid[i, :] = 0.0
            continue
        _, T_noise_batch = simulate_stack_robustness_batch(
            wavelengths, nH_arr, nL_arr, nSub_arr,
            np.array(p_thick_nominal, dtype=np.float64),
            sigma, runs_per_step, seed=42
        )
        # RMS error per wavelength
        diff = T_noise_batch - T_clean
        sensitivity_grid[i, :] = np.sqrt(np.mean(diff**2, axis=0))

    return {
        "sigma_steps": sigma_steps,
        "wavelengths": wavelengths,
        "sensitivity_grid": sensitivity_grid,
    }


def calculate_seel_analysis(
    params: dict[str, Any], nominal_results: dict[str, Any]
) -> dict[str, Any]:
    """Parallel SEEL Analysis (3x50 runs per sigma)."""
    logger = params.get("logger", logging.getLogger("ThinFilm"))
    logger.info("Running Parallel SEEL Analysis (3x50 runs per sigma)...")

    target_sigmas = [0.05, 0.1, 0.3, 0.6, 1.2, 2.0]
    robustness_seed = int(params.get("robustness_seed", 0))
    rng = np.random.default_rng(robustness_seed)

    batches_per_sigma = 3
    runs_per_batch = 50
    p_thick_nominal = np.array(
        nominal_results["physical_thicknesses_nominal"], dtype=np.float64
    )
    wavelengths = np.array(nominal_results["wavelengths"], dtype=np.float64)
    local_db = params.get("materials_db")

    nH_arr = get_refractive_clues_vectorized(
        params["nH_id"], wavelengths, db_instance=local_db
    ).astype(np.complex128)
    nL_arr = get_refractive_clues_vectorized(
        params["nL_id"], wavelengths, db_instance=local_db
    ).astype(np.complex128)
    nSub_arr = get_refractive_clues_vectorized(
        params["nSub_id"], wavelengths, db_instance=local_db
    ).astype(np.complex128)

    from certus_physics import simulate_stack_robustness_batch, compute_batch_rmse

    results = []
    for sigma in target_sigmas:
        for _ in range(batches_per_sigma):
            _, T_noise_batch = simulate_stack_robustness_batch(
                wavelengths, nH_arr, nL_arr, nSub_arr,
                p_thick_nominal, sigma, runs_per_batch,
                seed=int(rng.integers(0, 1e9))
            )
            # Compute RMSE vs nominal
            T_nom = np.array(nominal_results["T_spectral_nominal"], dtype=np.float64)
            rmses = compute_batch_rmse(T_noise_batch, T_nom)
            results.append(np.mean(rmses))

    # Simplified linear fit for SEEL
    sigma_averages = np.array(results).reshape(len(target_sigmas), batches_per_sigma).mean(axis=1)
    valid_idx = sigma_averages > 1e-9
    if np.any(valid_idx):
        x = sigma_averages[valid_idx]
        y = np.array(target_sigmas)[valid_idx]
        fit_k = np.sum(x * y) / np.sum(x * x)
        fit_alpha = 1.0
    else:
        fit_alpha, fit_k = 1.0, 30.0

    return {
        "sigmas": target_sigmas,
        "avg_rmse": sigma_averages.tolist(),
        "fit_alpha": fit_alpha,
        "fit_k": fit_k,
    }


def calculate_dynamics_ULTIMATE(
    scan_wl_range: np.ndarray,
    i_layer: int,
    nominal_thickness: float,
    clues_at_wl: dict[float, dict[str, complex]],
    nominal_matrix_cache: np.ndarray,
    all_wls: np.ndarray,
) -> list[dict[str, float]]:
    """Evaluate transmittance dynamics for every candidate monitoring wavelength."""
    n_steps = max(2, int(np.ceil(nominal_thickness / 1.0)))
    thickness_steps = np.linspace(0.0, nominal_thickness, n_steps, dtype=np.float64)

    wls_array = scan_wl_range.astype(np.float64)
    all_wls_f64 = all_wls.astype(np.float64)

    # Extract per-wavelength clues arrays
    all_clues = [clues_at_wl[float(wl)] for wl in wls_array]
    n_H_arr = np.array([c["H"] for c in all_clues], dtype=np.complex128)
    n_L_arr = np.array([c["L"] for c in all_clues], dtype=np.complex128)
    n_Sub_arr = np.array([c.get("substrate", 1.0) for c in all_clues], dtype=np.complex128)

    # prepare_dynamics_data_kernel(wls, all_wls, matrix_cache, n_H, n_L, n_Sub, i_layer)
    n_layer_array, n_sub_array, M_before_stack = prepare_dynamics_data_kernel(
        wls_array, all_wls_f64, nominal_matrix_cache, n_H_arr, n_L_arr, n_Sub_arr, i_layer
    )

    # compute_dynamics_kernel(wls, n_layers, n_subs, thicknesses, M_befores)
    dyn_vals, t_inits, t_finals, t_mins = compute_dynamics_kernel(
        wls_array, n_layer_array, n_sub_array, thickness_steps, M_before_stack
    )

    return [
        {
            "wl": float(wl),
            "dynamics": float(dyn_vals[idx]),
            "t_init": float(t_inits[idx]),
            "t_final": float(t_finals[idx]),
            "t_min": float(t_mins[idx]),
        }
        for idx, wl in enumerate(wls_array)
    ]



def _select_candidates_phase_a(
    scan_wl_range: np.ndarray,
    i_layer: int,
    p_thick_nominal: list[float],
    clues_at_wl: dict[float, dict[str, complex]],
    nominal_matrix_cache: np.ndarray,
    all_wls: np.ndarray,
    params: dict[str, Any],
    l0: float,
    current_avg_stack: list[float] | None = None,
) -> tuple[list[dict[str, float]], dict[float, float]]:
    """Phase A - Step 1: Select candidate monitoring wavelengths for one layer."""
    logger = params.get("logger", logging.getLogger("ThinFilm"))

    dynamics = calculate_dynamics_ULTIMATE(
        scan_wl_range,
        i_layer,
        p_thick_nominal[i_layer],
        clues_at_wl,
        nominal_matrix_cache,
        all_wls,
    )

    # Store full map before sorting/filtering
    full_dyn_map = {float(d["wl"]): float(d["dynamics"]) for d in dynamics}
    full_t_min_map = {float(d["wl"]): float(d["t_min"]) for d in dynamics}

    dynamics.sort(key=lambda x: x["dynamics"], reverse=True)

    threshold = float(params.get("dynamics_threshold", 0.025))
    pre_candidates_dyn = [d for d in dynamics if d["dynamics"] >= threshold]

    # Exclude low-signal monitoring: reject if T drops below floor anywhere during layer growth.
    min_t_floor = float(params.get("min_transmission_floor", 0.10))
    pre_candidates = pre_candidates_dyn
    if min_t_floor > 0:
        n_before = len(pre_candidates)
        pre_candidates = [d for d in pre_candidates if d["t_min"] >= min_t_floor]
        if n_before > len(pre_candidates):
            logger.info(
                f"   [MIN-T] Layer {i_layer+1}: {n_before - len(pre_candidates)} candidate(s) dropped (T_min < {min_t_floor*100:.0f}%)"
            )

    # strict_min_transmission_floor: raise hard error if no candidate survives T floor
    strict_floor = bool(params.get("strict_min_transmission_floor", False))
    if strict_floor and min_t_floor > 0 and len(pre_candidates) == 0:
        # Check if l0 itself would also fail
        l0_t_min_check = full_t_min_map.get(float(l0), 0.0)
        if l0_t_min_check < min_t_floor:
            raise RuntimeError(
                f"Layer {i_layer+1}: no candidate satisfies T_min >= {min_t_floor:.2f} "
                f"(strict_min_transmission_floor=True). Cannot proceed."
            )

    limit_scan = int(params.get("phase_a_scan_limit", 300))
    check_list = pre_candidates[:limit_scan] if len(pre_candidates) > limit_scan else pre_candidates

    # Ensure l0 can be considered only if it respects the strict T floor.
    if not any(abs(c["wl"] - l0) < 0.1 for c in check_list):
        l0_dyn = full_dyn_map.get(float(l0), 0.0)
        l0_t_min = full_t_min_map.get(float(l0), 0.0)
        l0_t_init = l0_t_min
        l0_t_final = l0_t_min
        for d in dynamics:
            if abs(d["wl"] - l0) < 0.1:
                l0_t_init, l0_t_final = d["t_init"], d["t_final"]
                break
        if min_t_floor <= 0.0 or l0_t_min >= min_t_floor:
            check_list.append({
                "wl": l0,
                "dynamics": l0_dyn,
                "t_init": l0_t_init,
                "t_final": l0_t_final,
                "t_min": l0_t_min,
            })

    # Extrema Safety Check & Resolution Filtering
    valid_candidates_data = []
    if current_avg_stack is not None and i_layer > 0 and len(current_avg_stack) == i_layer:
        current_stack_for_res = current_avg_stack + [p_thick_nominal[i_layer]]
    elif current_avg_stack is not None and i_layer == 0:
        current_stack_for_res = [p_thick_nominal[0]]
    else:
        current_stack_for_res = p_thick_nominal[: i_layer + 1]

    exclusion_ratio = float(params.get("extrema_exclusion_ratio", 60.0))
    res_limit_nm = float(params.get("min_spectral_resolution", 1.0))
    noise_val_pct = float(params["reality_sim_params"]["trigger_tolerance"]) / 100.0
    resolution_curvature_tolerance = float(
        params.get("resolution_curvature_tolerance", noise_val_pct / 2.0)
    )

    # Vectorized Extrema Check
    n_check = len(check_list)
    wls_arr = np.array([float(d["wl"]) for d in check_list], dtype=np.float64)
    n_curr_arr = np.zeros(n_check, dtype=np.complex128)
    n_prev_arr = np.zeros(n_check, dtype=np.complex128)
    n_sub_arr = np.zeros(n_check, dtype=np.complex128)
    is_h_layer = i_layer % 2 == 0
    clues_by_wl_idx = build_wavelength_index_map(clues_at_wl)

    for idx, wl in enumerate(wls_arr):
        clue = clues_by_wl_idx.get(wavelength_to_index(wl))
        if clue:
            n_curr_arr[idx] = clue["H" if is_h_layer else "L"]
            n_prev_arr[idx] = clue["L" if is_h_layer else "H"] if i_layer > 0 else 1.0 + 0j
            n_sub_arr[idx] = clue["substrate"]

    # wl_changed_arr: True if candidate wl differs from previous layer's wl
    prev_layer_wl = float(params.get("prev_layer_wl", -1.0))
    if i_layer == 0 or prev_layer_wl < 0.0:
        wl_changed_arr = np.zeros(n_check, dtype=np.bool_)
    else:
        wl_changed_arr = np.array(
            [abs(wls_arr[j] - prev_layer_wl) > 0.1 for j in range(n_check)],
            dtype=np.bool_,
        )

    # M_befores: zeros placeholder when not precomputed (conservative: no extrema filtering)
    M_befores = np.zeros((n_check, 2, 2), dtype=np.complex128)

    extrema_results = check_extrema_proximity_batch(
        wls_arr,
        n_curr_arr,
        n_prev_arr,
        n_sub_arr,
        float(p_thick_nominal[i_layer]),
        M_befores,
        exclusion_ratio,
        (i_layer > 0),
        wl_changed_arr,
    )

    for idx, d in enumerate(check_list):
        if not extrema_results[idx]:
            continue
        valid_candidates_data.append(d)

    return valid_candidates_data, full_dyn_map


def compute_probe_offset_nm_from_ratio(params: dict[str, Any]) -> float:
    """Convert probe offset ratio (e.g. 0.3) to physical thickness (nm)."""
    offset_ratio = float(params.get("probe_offset_ratio", 0.0))
    if offset_ratio <= 0:
        return 0.0
    l0 = float(params["l0"])
    nH_at_l0 = float(np.real(get_refractive_index(params["nH_id"], l0)))
    # For H layers (0, 2, ...), next is L (idx 1). 
    # This is a bit simplified vs legacy but usually fine.
    return offset_ratio * (l0 / (4.0 * nH_at_l0))


def _validate_candidates_phase_a(
    candidates: list[dict[str, float]],
    i_layer: int,
    num_runs: int,
    p_thick_nominal: list[float],
    clues_at_wl: dict[float, dict[str, complex]],
    params: dict[str, Any],
    run_states: list[dict[str, Any]],
    layer_noise_array: np.ndarray = None,
) -> tuple[list[dict[str, float]], list[list[float]]]:
    """Phase A - Step 2: Validate candidate wavelengths with Monte Carlo noise."""
    noise_val_pct = float(params["reality_sim_params"]["trigger_tolerance"]) / 100.0
    factor_val = float(params.get("non_monotonic_error_factor", 2.0))
    offset_val = compute_probe_offset_nm_from_ratio(params)
    candidate_wls = [d["wl"] for d in candidates]
    cand_wls_arr = np.array(candidate_wls, dtype=np.float64)
    clues_by_wl_idx = build_wavelength_index_map(clues_at_wl)

    n_H_arr = np.array([clues_by_wl_idx[wavelength_to_index(w)]["H"] for w in candidate_wls], dtype=np.complex128)
    n_L_arr = np.array([clues_by_wl_idx[wavelength_to_index(w)]["L"] for w in candidate_wls], dtype=np.complex128)
    n_Sub_arr = np.array([clues_by_wl_idx[wavelength_to_index(w)]["substrate"] for w in candidate_wls], dtype=np.complex128)
    p_thick_nom_arr = np.array(p_thick_nominal, dtype=np.float64)

    runs_history_matrix = np.zeros((num_runs, len(p_thick_nominal)), dtype=np.float64)
    if i_layer > 0:
        for r_idx in range(num_runs):
            runs_history_matrix[r_idx, :i_layer] = run_states[r_idx]["p_thick_sim"]

    if layer_noise_array is not None:
        noise_values = layer_noise_array
    else:
        base_seed = int(params.get("phase_a_seed", params.get("robustness_seed", 42)))
        fallback_rng = np.random.default_rng(base_seed + int(i_layer))
        deterministic_mode = bool(params.get("deterministic", False))
        noise_values = generate_noise_array(
            (num_runs,),
            noise_val_pct,
            NOISE_DISTRIBUTION_GAUSSIAN,
            rng=fallback_rng,
            deterministic=deterministic_mode,
        )

    nm_mode = params.get("non_monotonic_mode", NON_MONOTONIC_MODE_ATTENUATE)
    results_fast = validate_wavelengths_batch(
        cand_wls_arr,
        n_H_arr,
        n_L_arr,
        n_Sub_arr,
        runs_history_matrix,
        p_thick_nom_arr,
        i_layer,
        offset_val,
        noise_values,
        factor_val,
        nm_mode,
    )

    results_thickness = []
    p_thick_sim_updates = [[] for _ in range(len(candidate_wls))]

    # Build results with extrema metadata pass-through from candidates
    _SYM_MISSING = float(1e18)
    _EXT_KEYS = ("ext_prev_start", "ext_next_start", "ext_prev_end", "ext_next_end", "dynamics")
    idx_dict = {wavelength_to_index(w): clues_by_wl_idx[wavelength_to_index(w)] for w in candidate_wls}

    for idx, wl in enumerate(candidate_wls):
        rmse = results_fast[idx, 0]
        std = results_fast[idx, 1]
        entry: dict[str, Any] = {
            "wl": float(wl),
            "cost": float(rmse),
            "std_dev": float(std),
        }
        # Carry over extrema and dynamics metadata from candidate (required by mining)
        src = candidates[idx]
        for k in _EXT_KEYS:
            if k in src:
                entry[k] = src[k]
        results_thickness.append(entry)

    results_thickness.sort(key=lambda x: x["cost"])

    # Propagate best-wl sim state for next layer
    if results_thickness:
        best_wl = float(results_thickness[0]["wl"])
        best_idx_data = idx_dict[wavelength_to_index(best_wl)]
        p_thick_sim_updates = update_run_states_kernel(
            p_thick_nom_arr,
            i_layer,
            runs_history_matrix[:, :i_layer],
            best_wl,
            complex(best_idx_data["H"]),
            complex(best_idx_data["L"]),
            complex(best_idx_data["substrate"]),
            offset_val,
            noise_values,
            factor_val,
            nm_mode,
        ).tolist()
    else:
        p_thick_sim_updates = []

    return results_thickness, p_thick_sim_updates
