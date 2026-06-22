"""Headless service scaffold for CERTUS_STRAT (Track C)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
import json
import logging
import pathlib
from dataclasses import dataclass

import numpy as np

from certus.utils.certus_services import BaseHeadlessService
import certus_physics
from certus_physics import (
    arange_inclusive,
    get_refractive_index,
    get_refractive_clues_vectorized,
    calculate_RT_vectorized_real_HL,
    calculate_RT_batch_kernel,
    prepare_dynamics_data_kernel,
    compute_dynamics_kernel,
    check_extrema_proximity_batch,
    validate_wavelengths_batch,
    update_run_states_kernel,
    calculate_detailed_growth,
)
from certus.utils.certus_strat_context import StratContext
from certus.core.certus_core import WL_DECIMALS
from certus.workers.certus_strat_workers_dto import StratParamsDTO, StratOptiResultsDTO

NOISE_DISTRIBUTION_GAUSSIAN = "gaussian"
NON_MONOTONIC_MODE_ATTENUATE = "attenuate"
WL_INDEX_SCALE = 10**WL_DECIMALS

try:
    from certus.core.certus_strat_core import APP_CONTEXT as _APP_CONTEXT
except ImportError:
    try:
        from certus.core.certus_strat_config import APP_CONTEXT as _APP_CONTEXT
    except ImportError:
        _APP_CONTEXT = {"materials_db": None}

APP_CONTEXT = _APP_CONTEXT


class _PhysicsBridge:
    """Internal bridge that resolves kernels from module globals, enabling test monkeypatching."""

    @staticmethod
    def arange_inclusive(start: float, stop: float, step: float) -> np.ndarray:
        return arange_inclusive(start, stop, step)

    @staticmethod
    def get_refractive_index(mat_id: Any, wl: float, db_instance: Any = None) -> Any:
        return get_refractive_index(mat_id, wl, db_instance=db_instance)

    @staticmethod
    def get_refractive_clues_vectorized(mat_id: Any, wls: np.ndarray, db_instance: Any = None) -> Any:
        return get_refractive_clues_vectorized(mat_id, wls, db_instance=db_instance)

    @staticmethod
    def calculate_rt_hl(
        wavelengths: np.ndarray,
        nH: np.ndarray,
        nL: np.ndarray,
        nSub: np.ndarray,
        thicknesses: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        return calculate_RT_vectorized_real_HL(wavelengths, nH, nL, nSub, thicknesses)

    @staticmethod
    def calculate_rt_batch(
        wavelengths: np.ndarray,
        nH: np.ndarray,
        nL: np.ndarray,
        nSub: np.ndarray,
        thicknesses: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        return calculate_RT_batch_kernel(wavelengths, nH, nL, nSub, thicknesses)

    @staticmethod
    def prepare_dynamics_data(
        wls: np.ndarray,
        all_wls: np.ndarray,
        matrix_cache: np.ndarray,
        nH: np.ndarray,
        nL: np.ndarray,
        nSub: np.ndarray,
        i_layer: int,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        return prepare_dynamics_data_kernel(wls, all_wls, matrix_cache, nH, nL, nSub, i_layer)

    @staticmethod
    def compute_dynamics(
        wls: np.ndarray,
        n_layers: np.ndarray,
        n_subs: np.ndarray,
        thicknesses: np.ndarray,
        M_befores: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        return compute_dynamics_kernel(wls, n_layers, n_subs, thicknesses, M_befores)

    @staticmethod
    def check_extrema_proximity(
        wls: np.ndarray,
        n_curr: np.ndarray,
        n_prev: np.ndarray,
        n_sub: np.ndarray,
        thickness: float,
        M_befores: np.ndarray,
        exclusion_ratio: float,
        is_not_first_layer: bool,
        wl_changed: np.ndarray,
    ) -> np.ndarray:
        return check_extrema_proximity_batch(
            wls, n_curr, n_prev, n_sub, thickness, M_befores, exclusion_ratio, is_not_first_layer, wl_changed
        )

    @staticmethod
    def validate_wavelengths(
        wls: np.ndarray,
        nH: np.ndarray,
        nL: np.ndarray,
        nSub: np.ndarray,
        history: np.ndarray,
        nominal_thicknesses: np.ndarray,
        i_layer: int,
        offset: float,
        noise: np.ndarray,
        error_factor: float,
        mode: str,
    ) -> np.ndarray:
        return validate_wavelengths_batch(
            wls, nH, nL, nSub, history, nominal_thicknesses, i_layer, offset, noise, error_factor, mode
        )

    @staticmethod
    def update_run_states(
        nominal_thicknesses: np.ndarray,
        i_layer: int,
        history: np.ndarray,
        best_wl: float,
        nH: complex,
        nL: complex,
        nSub: complex,
        offset: float,
        noise: np.ndarray,
        error_factor: float,
        mode: str,
    ) -> np.ndarray:
        return update_run_states_kernel(
            nominal_thicknesses, i_layer, history, best_wl, nH, nL, nSub, offset, noise, error_factor, mode
        )

    @staticmethod
    def calculate_detailed_growth(
        num_layers: int,
        p_thick_arr: np.ndarray,
        layer_wls: np.ndarray,
        nH_arr: np.ndarray,
        nL_arr: np.ndarray,
        nSub_arr: np.ndarray,
        steps_per_layer: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        return calculate_detailed_growth(
            num_layers,
            p_thick_arr,
            layer_wls,
            nH_arr,
            nL_arr,
            nSub_arr,
            steps_per_layer,
        )



def wavelength_to_index(wavelength_nm: float) -> int:
    """Convert a wavelength float to a stable integer index at WL_DECIMALS precision."""
    return int(np.rint(float(wavelength_nm) * WL_INDEX_SCALE))


def build_wavelength_index_map(clues_at_wl: dict[float, dict[str, complex]]) -> dict[int, dict[str, complex]]:
    """Build an integer-indexed wavelength map to avoid float-key drift in lookups."""
    return {wavelength_to_index(wavelength): value for wavelength, value in clues_at_wl.items()}


@dataclass(frozen=True)
class StratPayloadParts:
    """Validated legacy STRAT payload pieces before normalization."""

    step: int
    params: StratParamsDTO
    opti_results: StratOptiResultsDTO | None


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
    _ = distribution
    local_rng = rng if rng is not None else np.random.default_rng(0)
    raw = np.clip(local_rng.normal(0.0, 1.0 / 3.0, shape), -1.0, 1.0)
    return (raw * scale).astype(np.float64)


class StratStrategyService(BaseHeadlessService):
    """Headless wrapper for STRAT payload normalization/validation."""

    def __init__(self, runner=lambda config: config) -> None:
        super().__init__(runner)

    VALID_STEPS = {0, 2, 3, 23, 33}

    _SCHEMA_PATH = pathlib.Path(__file__).resolve().parents[2] / "schemas" / "STRAT_PAYLOAD_SCHEMA_V1.json"
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
            import jsonschema  # noqa: F401

            with open(cls._SCHEMA_PATH, encoding="utf-8") as f:
                cls._schema = json.load(f)
        except (ImportError, FileNotFoundError) as exc:
            logging.getLogger(__name__).debug("STRAT payload schema unavailable: %s", exc)
            cls._schema = None
        return cls._schema

    def validate_against_schema(self, payload: Mapping[str, Any]) -> list[str]:
        """Validate payload against STRAT_PAYLOAD_SCHEMA_V1. Returns list of error messages."""
        schema = self._get_schema()
        if schema is None:
            logging.getLogger(__name__).debug("STRAT schema validation skipped: schema unavailable")
            return []
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

    def _validate_payload_shape(self, payload: Mapping[str, Any]) -> StratPayloadParts:
        """Validate the legacy STRAT payload shape before domain-specific checks."""
        try:
            step = int(payload.get("step", 0))
        except (TypeError, ValueError):
            raise ValueError("payload.step must be an integer") from None
        if step not in self.VALID_STEPS:
            raise ValueError(f"unsupported step: {step}")

        if "params" not in payload:
            raise ValueError("payload.params must be a dict")

        params_raw = payload["params"]
        if not isinstance(params_raw, dict) and not isinstance(params_raw, StratParamsDTO):
            raise ValueError("payload.params must be a dict")

        opti_results_raw = payload.get("opti_results")
        if opti_results_raw is not None and not isinstance(opti_results_raw, dict) and not isinstance(opti_results_raw, StratOptiResultsDTO):
            raise ValueError("payload.opti_results must be a dict or None")

        try:
            params = StratParamsDTO.model_validate(params_raw)
        except Exception as exc:
            raise ValueError(f"Invalid params payload structure: {exc}") from exc

        opti_results = None
        if opti_results_raw is not None:
            try:
                opti_results = StratOptiResultsDTO.model_validate(opti_results_raw)
            except Exception as exc:
                raise ValueError(f"Invalid opti_results payload structure: {exc}") from exc

        return StratPayloadParts(step=step, params=params, opti_results=opti_results)

    def _clean_payload_for_schema(self, val: Any) -> Any:
        if hasattr(val, "model_dump"):
            return self._clean_payload_for_schema(val.model_dump(exclude_none=True))
        if isinstance(val, Mapping):
            return {str(k): self._clean_payload_for_schema(v) for k, v in val.items() if v is not None}
        if isinstance(val, (list, tuple)):
            return [self._clean_payload_for_schema(v) for v in val]
        if isinstance(val, (int, float, str, bool)) or val is None:
            return val
        return str(val)

    def _validate_structural(self, payload: Mapping[str, Any]) -> StratPayloadParts:
        """Phase 1: Structural validation (JSON schema + type shape checks)."""
        if not isinstance(payload, Mapping):
            raise ValueError("payload must be a mapping")

        # Strict JSON schema validation (with rich-object clean conversion)
        clean_payload = self._clean_payload_for_schema(payload)
        schema_errors = self.validate_against_schema(clean_payload)
        if schema_errors:
            raise ValueError("Payload schema violations:\n" + "\n".join(schema_errors))

        # DTO schema and model structure checks
        return self._validate_payload_shape(payload)

    def _validate_domain(self, parts: StratPayloadParts, materials_db: Any = None) -> None:
        """Phase 2: Domain/Business rule validation (wavelength ranges, material bounds)."""
        params = parts.params
        
        # Verify scan limits consistency
        try:
            req_min = float(params.scan_wl_min)
            req_max = float(params.scan_wl_max)
            if req_min > req_max:
                logging.getLogger(__name__).warning(
                    "Domain validation: scan_wl_min > scan_wl_max, will be swapped dynamically."
                )
        except (AttributeError, TypeError, ValueError):
            pass

        # Verify material databases coverage if database is provided
        if materials_db is not None:
            self.validate_material_coverage(parts.params, materials_db)

    def _normalize(self, parts: StratPayloadParts) -> dict[str, Any]:
        """Phase 3: Normalization of validated payload into final contract dictionary."""
        return {
            "step": parts.step,
            "params": parts.params,
            "opti_results": parts.opti_results,
        }

    def validate_payload(self, payload: Mapping[str, Any], materials_db: Any = None) -> dict[str, Any]:
        """Validate/normalize legacy STRAT worker payload."""
        parts = self._validate_structural(payload)
        self._validate_domain(parts, materials_db)
        return self._normalize(parts)

    def validate_material_coverage(self, params: dict[str, Any] | StratParamsDTO, db: Any) -> None:
        """Validate spectral coverage, but degrade gracefully when material metadata is incomplete.

        The legacy workflow should not hard-fail on a single narrow material if the
        requested range can still be evaluated with the available refractive data.
        We keep a warning-level diagnostic and only raise when *all* relevant materials
        are outside the requested range or when no usable coverage metadata exists.
        """
        if not hasattr(db, "data") or not db.data:
            return

        try:
            req_min = float(params["scan_wl_min"])
            req_max = float(params["scan_wl_max"])
            nH_id = params["nH_id"]
            nL_id = params["nL_id"]
            nSub_id = params["nSub_id"]
        except (KeyError, TypeError, ValueError):
            return

        if req_min > req_max:
            req_min, req_max = req_max, req_min
            logging.getLogger(__name__).warning(
                "STRAT requested wavelength range was inverted; values were swapped to preserve validity.")

        used_materials = {nH_id, nL_id, nSub_id}
        files_to_check = [m for m in used_materials if m in db.data]
        if not files_to_check:
            return

        errors = []
        covered_any = False

        for mat_name in files_to_check:
            mat_data = db.data[mat_name]
            valid_min = float(mat_data.get("min_wl_valid", mat_data["wl"][0] if "wl" in mat_data and len(mat_data["wl"]) > 0 else float("nan")))
            valid_max = float(mat_data.get("max_wl_valid", mat_data["wl"][-1] if "wl" in mat_data and len(mat_data["wl"]) > 0 else float("nan")))

            has_bounds = np.isfinite(valid_min) and np.isfinite(valid_max) and valid_min < valid_max
            overlaps = has_bounds and not (req_max < valid_min or req_min > valid_max)
            covered_any = covered_any or overlaps

            if not has_bounds:
                errors.append(f"• {mat_name}: coverage metadata unavailable")
                continue

            if req_min < valid_min:
                errors.append(f"• {mat_name}: Requested start {req_min}nm < Data start {valid_min}nm")
            if req_max > valid_max:
                errors.append(f"• {mat_name}: Requested end {req_max}nm > Data end {valid_max}nm")

        if errors and not covered_any:
            msg = "CRITICAL: Material Data Missing for Spectral Range!\n" + "\n".join(errors)
            raise ValueError(msg)

        if errors:
            logging.getLogger(__name__).warning(
                "Material coverage mismatch detected but workflow allowed to continue: %s",
                " | ".join(errors),
            )

    def run_step_0(self, params: dict[str, Any], materials_db: Any = None) -> dict[str, Any]:
        """Orchestrate Step 0 (Nominal + Sensitivity + SEEL) headlessly.

        Step 0 evaluates the ideal design performance, deposition sensitivities
        and SEEL (Spectral Error Envelope Limit).
        """
        logger = logging.getLogger(__name__)
        logger.info("Initializing Headless Step 0 execution...")

        # Setup local context parameters if needed
        local_params = dict(params)
        if materials_db is not None:
            local_params["materials_db"] = materials_db

        # Context-isolated execution path
        nominal_results, multipliers = calculate_nominal_properties(local_params)
        sensitivity_data = calculate_sensitivity_matrix(local_params, nominal_results)
        seel_data = calculate_seel_analysis(local_params, nominal_results)

        logger.info("Step 0 computations successfully completed.")
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
    nH_array = _PhysicsBridge.get_refractive_clues_vectorized(nH_id, wavelengths, db_instance=db_instance)
    nL_array = _PhysicsBridge.get_refractive_clues_vectorized(nL_id, wavelengths, db_instance=db_instance)
    nSub_array = _PhysicsBridge.get_refractive_clues_vectorized(nSub_id, wavelengths, db_instance=db_instance)
    p_thick_arr = np.asarray(p_thick, dtype=np.float64)

    _emit_stat("SP", 1)

    # wrapper returns (R, T)
    R_arr, T_arr = _PhysicsBridge.calculate_rt_hl(wavelengths, nH_array, nL_array, nSub_array, p_thick_arr)

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

    # Retrieve the database instance from params
    db_instance = params.get("materials_db") or params.get("materials_db_instance")

    nH_at_l0 = _PhysicsBridge.get_refractive_index(nH_id, l0, db_instance=db_instance)
    nL_at_l0 = _PhysicsBridge.get_refractive_index(nL_id, l0, db_instance=db_instance)

    logger.info(f"   -> nH @ {l0}nm = {np.real(nH_at_l0):.4f}")
    logger.info(f"   -> nL @ {l0}nm = {np.real(nL_at_l0):.4f}")

    if abs(np.real(nH_at_l0) - 1.0) < 1e-4 and "air" not in str(nH_id).lower():
        logger.warning(f"⚠️ High Index Material ({nH_id}) appears to be AIR (n=1.0). Missing file?")

    if abs(np.real(nL_at_l0) - 1.0) < 1e-4 and "air" not in str(nL_id).lower():
        logger.warning(f"⚠️ Low Index Material ({nL_id}) appears to be AIR (n=1.0). Missing file?")

    p_thick_nominal = [
        (m * l0) / (4.0 * np.real(nH_at_l0 if (i % 2) == 0 else nL_at_l0)) for i, m in enumerate(multipliers)
    ]

    wavelengths = _PhysicsBridge.arange_inclusive(float(wl_range[0]), float(wl_range[1]), wl_step)
    RT = calculate_RT_normal_real(wavelengths, nH_id, nL_id, nSub_id, p_thick_nominal, db_instance=db_instance)

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



def calculate_sensitivity_matrix(params: dict[str, Any], nominal_results: dict[str, Any]) -> dict[str, Any]:
    """Generating Sensitivity Landscape (0 -> 3nm)."""
    logger = params.get("logger", logging.getLogger("ThinFilm"))
    logger.info("Generating Sensitivity Landscape (0 -> 3nm)...")

    base_seed = int(params.get("phase_a_seed", params.get("robustness_seed", 42)))
    rng = np.random.default_rng(base_seed)

    sigma_steps = np.linspace(0.0, 3.0, 31)
    runs_per_step = 40
    p_thick_nominal = nominal_results["physical_thicknesses_nominal"]
    wavelengths = nominal_results["wavelengths"]
    local_db = params.get("materials_db") or params.get("materials_db_instance") or APP_CONTEXT.get("materials_db")

    nH_arr = _PhysicsBridge.get_refractive_clues_vectorized(params["nH_id"], wavelengths, db_instance=local_db).astype(np.complex128)
    nL_arr = _PhysicsBridge.get_refractive_clues_vectorized(params["nL_id"], wavelengths, db_instance=local_db).astype(np.complex128)
    nSub_arr = _PhysicsBridge.get_refractive_clues_vectorized(params["nSub_id"], wavelengths, db_instance=local_db).astype(np.complex128)

    _, T_clean_batch = _PhysicsBridge.calculate_rt_batch(
        wavelengths,
        nH_arr,
        nL_arr,
        nSub_arr,
        np.array(p_thick_nominal, dtype=np.float64).reshape(1, -1),
    )
    T_clean = T_clean_batch[0]

    sensitivity_grid = np.zeros((len(sigma_steps), len(wavelengths)), dtype=np.float64)
    envelopes: dict[float, dict[str, np.ndarray]] = {}
    valid_sigmas = [float(s) for s in sigma_steps if s > 0.0]
    total_runs = len(valid_sigmas) * runs_per_step
    _emit_stat("SP", total_runs)

    # Match OLD: generate all Monte-Carlo batches then compute percentile envelopes.
    p_bulk = np.zeros((len(valid_sigmas), runs_per_step, len(p_thick_nominal)), dtype=np.float64)
    p_thick_arr = np.array(p_thick_nominal, dtype=np.float64)
    for idx, sigma in enumerate(valid_sigmas):
        noise = generate_noise_array((runs_per_step, len(p_thick_nominal)), scale=sigma, rng=rng)
        p_bulk[idx] = np.maximum(0.0, p_thick_arr + noise)

    p_flat = p_bulk.reshape(total_runs, -1)
    _, batch_T_flat = _PhysicsBridge.calculate_rt_batch(wavelengths, nH_arr, nL_arr, nSub_arr, p_flat)
    batch_T_bulk = batch_T_flat.reshape((len(valid_sigmas), runs_per_step, len(wavelengths)))

    bulk_idx = 0
    for i, sigma in enumerate(sigma_steps):
        if sigma == 0:
            continue
        batch_T = batch_T_bulk[bulk_idx]
        bulk_idx += 1
        delta_matrix = np.abs(batch_T - T_clean)
        sensitivity_grid[i, :] = np.mean(delta_matrix, axis=0)
        if np.isclose(sigma, 0.5) or np.isclose(sigma, 1.0) or np.isclose(sigma, 2.0):
            envelopes[float(sigma)] = {
                "p5": np.percentile(batch_T, 5, axis=0),
                "p95": np.percentile(batch_T, 95, axis=0),
                "p1": np.percentile(batch_T, 1, axis=0),
                "p99": np.percentile(batch_T, 99, axis=0),
            }

    return {
        "sigmas": sigma_steps,
        "wavelengths": wavelengths,
        "grid": sensitivity_grid,
        "envelopes": envelopes,
        "T_nominal": T_clean,
    }


def calculate_seel_analysis(params: dict[str, Any], nominal_results: dict[str, Any]) -> dict[str, Any]:
    """Parallel SEEL Analysis (3x50 runs per sigma)."""
    logger = params.get("logger", logging.getLogger("ThinFilm"))
    logger.info("Running Parallel SEEL Analysis (3x50 runs per sigma)...")

    base_seed = int(params.get("phase_a_seed", params.get("robustness_seed", 42)))
    rng = np.random.default_rng(base_seed)

    target_sigmas = [0.05, 0.1, 0.3, 0.6, 1.2, 2.0]
    batches_per_sigma = 3
    runs_per_batch = 50
    p_thick_nominal = np.array(nominal_results["physical_thicknesses_nominal"], dtype=np.float64)
    wavelengths = np.array(nominal_results["wavelengths"], dtype=np.float64)
    local_db = params.get("materials_db") or params.get("materials_db_instance") or APP_CONTEXT.get("materials_db")

    nH_arr = _PhysicsBridge.get_refractive_clues_vectorized(params["nH_id"], wavelengths, db_instance=local_db).astype(np.complex128)
    nL_arr = _PhysicsBridge.get_refractive_clues_vectorized(params["nL_id"], wavelengths, db_instance=local_db).astype(np.complex128)
    nSub_arr = _PhysicsBridge.get_refractive_clues_vectorized(params["nSub_id"], wavelengths, db_instance=local_db).astype(np.complex128)

    total_runs = len(target_sigmas) * batches_per_sigma * runs_per_batch
    _emit_stat("SP", total_runs)

    _, T_clean_batch = _PhysicsBridge.calculate_rt_batch(
        wavelengths, nH_arr, nL_arr, nSub_arr, p_thick_nominal.reshape(1, -1)
    )
    T_clean = T_clean_batch[0]

    p_bulk = np.zeros((len(target_sigmas), batches_per_sigma, runs_per_batch, len(p_thick_nominal)), dtype=np.float64)
    for i, sigma in enumerate(target_sigmas):
        for b in range(batches_per_sigma):
            noise = generate_noise_array((runs_per_batch, len(p_thick_nominal)), scale=sigma, rng=rng)
            p_bulk[i, b] = np.maximum(0.0, p_thick_nominal + noise)

    p_flat = p_bulk.reshape(total_runs, -1)
    _, batch_T_flat = _PhysicsBridge.calculate_rt_batch(wavelengths, nH_arr, nL_arr, nSub_arr, p_flat)
    batch_T_bulk = batch_T_flat.reshape((len(target_sigmas), batches_per_sigma, runs_per_batch, len(wavelengths)))

    results = []
    all_rmses_per_sigma = [[] for _ in target_sigmas]
    for i in range(len(target_sigmas)):
        for b in range(batches_per_sigma):
            T_batch = batch_T_bulk[i, b]
            mse_batch = np.mean((T_batch - T_clean) ** 2, axis=1)
            current_batch_rmses = np.sqrt(mse_batch)
            results.append(float(np.mean(current_batch_rmses)))
            all_rmses_per_sigma[i].extend(current_batch_rmses.tolist())

    rmse_p95_per_sigma = []
    rmse_p99_per_sigma = []
    for i in range(len(target_sigmas)):
        arr = np.array(all_rmses_per_sigma[i], dtype=np.float64)
        rmse_p95_per_sigma.append(float(np.percentile(arr, 95)) if len(arr) > 0 else 0.0)
        rmse_p99_per_sigma.append(float(np.percentile(arr, 99)) if len(arr) > 0 else 0.0)

    sigma_averages = []
    sigma_values = []
    expanded_sigmas = []
    expanded_rmses = []
    res_idx = 0
    for sigma in target_sigmas:
        batch_means = []
        for _b in range(batches_per_sigma):
            avg_batch = results[res_idx]
            expanded_sigmas.append(sigma)
            expanded_rmses.append(avg_batch)
            batch_means.append(avg_batch)
            res_idx += 1
        sigma_averages.append(np.mean(batch_means))
        sigma_values.append(sigma)

    valid_idx = np.array(sigma_averages) > 1e-9
    if np.any(valid_idx):
        x = np.array(sigma_averages)[valid_idx]
        y = np.array(sigma_values)[valid_idx]
        fit_k = np.sum(x * y) / np.sum(x * x)
        fit_alpha = 1.0
    else:
        fit_alpha, fit_k = 1.0, 30.0


    return {
        "sigmas": expanded_sigmas,
        "avg_rmse": expanded_rmses,
        "rmse_p95_per_sigma": rmse_p95_per_sigma,
        "rmse_p99_per_sigma": rmse_p99_per_sigma,
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
    """Evaluate transmittance dynamics for every candidate monitoring wavelength.

    The returned ``dynamics`` value is the peak-to-peak transmission variation
    (``T_max - T_min``) over the layer growth interval. When values collapse to
    zero across many wavelengths, the issue is usually upstream (flat signal,
    wrong units, or overly aggressive clipping / thresholds), so we emit
    additional diagnostics to make that visible in logs.
    """
    logger = logging.getLogger("ThinFilm")
    n_steps = max(2, int(np.ceil(nominal_thickness / 1.0)))
    thickness_steps = np.linspace(0.0, nominal_thickness, n_steps, dtype=np.float64)

    wls_array = scan_wl_range.astype(np.float64)
    all_wls_f64 = all_wls.astype(np.float64)

    # Extract per-wavelength clues arrays using rounded integer keys to avoid float drift.
    clues_by_wl_idx = build_wavelength_index_map(clues_at_wl)
    all_clues = []
    missing_wls = []
    for wl in wls_array:
        clue = clues_by_wl_idx.get(wavelength_to_index(wl))
        if clue is None:
            missing_wls.append(float(wl))
            continue
        all_clues.append(clue)
    if missing_wls:
        raise KeyError(
            f"Missing refractive clues for {len(missing_wls)} wavelength(s); "
            f"examples={missing_wls[:5]}"
        )
    n_H_arr = np.array([c["H"] for c in all_clues], dtype=np.complex128)
    n_L_arr = np.array([c["L"] for c in all_clues], dtype=np.complex128)
    n_Sub_arr = np.array([c.get("substrate", 1.0) for c in all_clues], dtype=np.complex128)

    # _PhysicsBridge.prepare_dynamics_data(wls, all_wls, matrix_cache, n_H, n_L, n_Sub, i_layer)
    n_layer_array, n_sub_array, M_before_stack = _PhysicsBridge.prepare_dynamics_data(
        wls_array, all_wls_f64, nominal_matrix_cache, n_H_arr, n_L_arr, n_Sub_arr, i_layer
    )

    # _PhysicsBridge.compute_dynamics(wls, n_layers, n_subs, thicknesses, M_befores)
    dyn_vals, t_inits, t_finals, t_mins = _PhysicsBridge.compute_dynamics(
        wls_array, n_layer_array, n_sub_array, thickness_steps, M_before_stack
    )

    dyn_vals = np.asarray(dyn_vals, dtype=np.float64)
    t_inits = np.asarray(t_inits, dtype=np.float64)
    t_finals = np.asarray(t_finals, dtype=np.float64)
    t_mins = np.asarray(t_mins, dtype=np.float64)

    # Diagnostic guardrail: expose suspiciously flat layers in scientific notation.
    dyn_min = float(np.nanmin(dyn_vals)) if dyn_vals.size else float("nan")
    dyn_max = float(np.nanmax(dyn_vals)) if dyn_vals.size else float("nan")
    dyn_std = float(np.nanstd(dyn_vals)) if dyn_vals.size else float("nan")
    if dyn_vals.size and (np.isclose(dyn_max, 0.0, atol=1e-12) or np.isclose(dyn_std, 0.0, atol=1e-12)):
        logger.warning(
            "[DYNAMICS] Layer %d suspiciously flat: min=%.12e max=%.12e std=%.12e thickness=%.3f nm samples=%d",
            i_layer + 1,
            dyn_min,
            dyn_max,
            dyn_std,
            float(nominal_thickness),
            int(dyn_vals.size),
        )
        if dyn_vals.size:
            probe_idx = int(np.nanargmax(dyn_vals))
            logger.warning(
                "[DYNAMICS] Layer %d probe wl=%.3f nm Tinit=%.12e Tfinal=%.12e Tmin=%.12e Dyn=%.12e",
                i_layer + 1,
                float(wls_array[probe_idx]),
                float(t_inits[probe_idx]),
                float(t_finals[probe_idx]),
                float(t_mins[probe_idx]),
                float(dyn_vals[probe_idx]),
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
                f"   [MIN-T] Layer {i_layer + 1}: {n_before - len(pre_candidates)} candidate(s) dropped (T_min below {min_t_floor * 100:.0f}%)"
            )

    # strict_min_transmission_floor: raise hard error if no candidate survives T floor
    strict_floor = bool(params.get("strict_min_transmission_floor", False))
    if strict_floor and min_t_floor > 0 and len(pre_candidates) == 0:
        # Check if l0 itself would also fail
        l0_t_min_check = full_t_min_map.get(float(l0), 0.0)
        if l0_t_min_check < min_t_floor:
            raise RuntimeError(
                f"Layer {i_layer + 1}: no candidate satisfies T_min >= {min_t_floor:.2f} "
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
            check_list.append(
                {
                    "wl": l0,
                    "dynamics": l0_dyn,
                    "t_init": l0_t_init,
                    "t_final": l0_t_final,
                    "t_min": l0_t_min,
                }
            )

    # Extrema Safety Check & Resolution Filtering
    valid_candidates_data = []
    exclusion_ratio = float(params.get("extrema_exclusion_ratio", 60.0))


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

    extrema_results = _PhysicsBridge.check_extrema_proximity(
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
    """Convert probe offset ratio to physical thickness (nm), using legacy STRAT logic."""
    tolerance_nm = params.get("thickness_tolerance_nm")
    if tolerance_nm is not None:
        return float(tolerance_nm)

    l0 = float(params.get("l0", 1500.0))
    nH_id = params.get("nH_id", 2.3)
    nL_id = params.get("nL_id", 1.45)
    try:
        nH_at_l0 = _PhysicsBridge.get_refractive_index(nH_id, l0)
        nL_at_l0 = _PhysicsBridge.get_refractive_index(nL_id, l0)
        n_avg_at_l0 = np.real((nH_at_l0 + nL_at_l0) / 2.0)
    except (ValueError, TypeError, KeyError):
        n_avg_at_l0 = 1.5
    probe_ratio = float(params.get("sim_thickness_probe_offset_ratio", 80.0))
    if n_avg_at_l0 > 1e-6 and probe_ratio > 1e-6:
        return float(l0 / n_avg_at_l0 / probe_ratio)
    return 5.0


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
    n_Sub_arr = np.array(
        [clues_by_wl_idx[wavelength_to_index(w)]["substrate"] for w in candidate_wls], dtype=np.complex128
    )
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
    results_fast = _PhysicsBridge.validate_wavelengths(
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
        p_thick_sim_updates = _PhysicsBridge.update_run_states(
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



def select_best_strat_result(strategies_results: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the best finite-ranked strategy result.

    The list is usually pre-sorted, but older or partially populated payloads may
    keep placeholder zeros at the top. We therefore prefer the first finite,
    strictly positive score while preserving the existing ranking order.
    """
    if not strategies_results:
        return None

    score_keys = ("robustness_score", "rmse_p95", "rmse_mean", "rmse", "final_rmse")
    for item in strategies_results:
        if not isinstance(item, dict):
            continue
        for key in score_keys:
            value = item.get(key)
            if value is None:
                continue
            try:
                score = float(value)
            except (TypeError, ValueError):
                continue
            if np.isfinite(score) and score > 0:
                return item

    return strategies_results[0]


def extract_best_rmse(strategies_results: list[dict[str, Any]]) -> float:
    """Extract the best finite RMSE score from the strategies results."""
    best_item = select_best_strat_result(strategies_results)
    if not best_item:
        return 0.0

    score_keys = ("robustness_score", "rmse_p95", "rmse_mean", "rmse", "final_rmse")
    for key in score_keys:
        val = best_item.get(key)
        if val is None:
            continue
        try:
            fval = float(val)
        except (TypeError, ValueError):
            continue
        if np.isfinite(fval):
            if 0.0 <= fval < 1e-7:
                from certus.utils.errors import PhysicsConvergenceError
                raise PhysicsConvergenceError(
                    f"RMSE calculation resulted in abnormally low/null value: {fval} (< 1e-7). "
                    "This is physically impossible for a noisy real deposition signal and suggests a convergence failure."
                )
            if fval > 0.0:
                return fval
    return 0.0


def rebuild_visualization_context(params: dict[str, Any], logger: Any = None) -> dict[str, Any]:
    """Rebuild a minimal context (clues, matrix cache, wavelengths, nominal properties)
    from StratParamsDTO or a raw params dictionary.
    """
    from certus.core.certus_strat_core import precompute_clues_and_matrices

    nominal_results, _ = calculate_nominal_properties(params)
    p_thick_nominal = nominal_results["physical_thicknesses_nominal"]
    clues_at_wl, nominal_matrix_cache, all_wls = precompute_clues_and_matrices(
        params, p_thick_nominal, logger
    )
    return {
        "p_thick_nominal": p_thick_nominal,
        "clues_at_wl": clues_at_wl,
        "nominal_matrix_cache": nominal_matrix_cache,
        "all_wls": all_wls,
    }


def simulate_detailed_growth_for_ui(
    strategy_result: dict[str, Any],
    opti_results: dict[str, Any],
    params: dict[str, Any],
) -> dict[str, Any]:
    """Simulate detailed growth on the fly for UI plot visualization.
    Encapsulates the physics and index validation logic.
    """
    if "detailed_growth_data" in strategy_result:
        return strategy_result["detailed_growth_data"]

    strategy = strategy_result["strategy"]
    block_list = strategy.get("blocks", [])
    p_thick_arr = np.array(opti_results["p_thick_nominal"], dtype=np.float64)
    num_layers = len(p_thick_arr)
    layer_wls = np.zeros(num_layers, dtype=np.float64)

    nH_arr = np.zeros(num_layers, dtype=np.complex128)
    nL_arr = np.zeros(num_layers, dtype=np.complex128)
    nSub_arr = np.zeros(num_layers, dtype=np.complex128)

    clues_db = opti_results["clues_at_wl"]

    try:
        first_wl = list(clues_db.keys())[0]
        _nSub_fallback = complex(clues_db[first_wl].get("substrate", 1.52))
    except (IndexError, AttributeError, KeyError):
        _nSub_fallback = complex(1.52)

    nH_id = params.get("nH_r", 2.3)
    nL_id = params.get("nL_r", 1.45)
    nSub_id = params.get("nSub_custom", 1.73)

    for block in block_list:
        wl = float(block["wavelength"])
        try:
            idx_data = clues_db[wl]
        except KeyError:
            n_h = complex(params.get("nH_r", 2.3)) if isinstance(nH_id, float) else complex(2.3)
            n_l = complex(params.get("nL_r", 1.45)) if isinstance(nL_id, float) else complex(1.45)
            n_sub = complex(params.get("nSub_custom", 1.73)) if isinstance(nSub_id, float) else complex(1.73)
            idx_data = {"H": n_h, "L": n_l, "substrate": n_sub}

        for layer_idx in range(block["start"], block["end"]):
            if layer_idx < num_layers:
                layer_wls[layer_idx] = wl
                nH_arr[layer_idx] = idx_data.get("H", complex(2.3))
                nL_arr[layer_idx] = idx_data.get("L", complex(1.45))
                n_sub_val = complex(idx_data.get("substrate", _nSub_fallback))
                if n_sub_val.real < 1.001:
                    n_sub_val = _nSub_fallback
                nSub_arr[layer_idx] = n_sub_val

    steps_per_layer = np.full(num_layers, 50, dtype=np.int32)
    x_pts, y_pts, bounds = _PhysicsBridge.calculate_detailed_growth(
        num_layers,
        p_thick_arr,
        layer_wls,
        nH_arr,
        nL_arr,
        nSub_arr,
        steps_per_layer,
    )
    return {
        "x": x_pts.tolist() if hasattr(x_pts, "tolist") else x_pts,
        "y": y_pts.tolist() if hasattr(y_pts, "tolist") else y_pts,
        "boundaries": bounds.tolist() if hasattr(bounds, "tolist") else bounds,
    }


def simulate_spectral_distribution_for_ui(
    strategy_result: dict[str, Any],
    opti_results: dict[str, Any],
    params: dict[str, Any],
) -> dict[str, Any] | None:
    """Simulate spectral distribution curves (T_nom, mean, p5, p95) for visual plotting."""
    db_instance = params.get("materials_db_instance") or params.get("materials_db") or APP_CONTEXT.get("materials_db")
    assert db_instance is not None, (
        "CERTUS-STRAT-E-DB-MISSING: Materials database instance is completely missing from params and APP_CONTEXT. "
        "Verify that the worker thread correctly serializes/deserializes the materials database or that "
        "APP_CONTEXT['materials_db'] is initialized on startup."
    )

    results_list = strategy_result.get("results_per_noise", [])
    target_res = None
    for res in results_list:
        if abs(res.get("noise_level", 0) - 2.0) < 0.1:
            target_res = res
            break
    if not target_res and results_list:
        target_res = results_list[0]
    if not target_res:
        return None

    thicknesses_all = target_res.get("thicknesses_all", [])
    p_thick_nominal = opti_results.get("p_thick_nominal")
    if not thicknesses_all or p_thick_nominal is None:
        return None

    wls = np.arange(380.0, 1000.0, 2.0, dtype=np.float64)
    nH_id = params.get("nH_r", 2.3)
    nL_id = params.get("nL_r", 1.45)
    nSub_id = params.get("nSub_custom", 1.73)

    nH_arr = _PhysicsBridge.get_refractive_clues_vectorized(nH_id, wls, db_instance).astype(np.complex128)
    nL_arr = _PhysicsBridge.get_refractive_clues_vectorized(nL_id, wls, db_instance).astype(np.complex128)
    nSub_arr = _PhysicsBridge.get_refractive_clues_vectorized(nSub_id, wls, db_instance).astype(np.complex128)

    _, T_clean_batch = _PhysicsBridge.calculate_rt_batch(
        wls,
        nH_arr,
        nL_arr,
        nSub_arr,
        np.array(p_thick_nominal, dtype=np.float64).reshape(1, -1),
    )
    T_nom = T_clean_batch[0]

    T_sim_list = []
    for p_sim in thicknesses_all:
        if len(p_sim) == len(p_thick_nominal):
            p_arr = np.array(p_sim, dtype=np.float64).reshape(1, -1)
            _, T_val_batch = _PhysicsBridge.calculate_rt_batch(wls, nH_arr, nL_arr, nSub_arr, p_arr)
            T_sim_list.append(T_val_batch[0])

    if not T_sim_list:
        return None

    arr_sim = np.array(T_sim_list)
    mean = np.mean(arr_sim, axis=0)
    p5 = np.percentile(arr_sim, 5, axis=0)
    p95 = np.percentile(arr_sim, 95, axis=0)

    return {
        "wls": wls.tolist(),
        "T_nom": T_nom.tolist(),
        "mean": mean.tolist(),
        "p5": p5.tolist(),
        "p95": p95.tolist(),
    }


