from typing import Any
from certus.utils.certus_strat_context import StratContext, get_context
from certus.utils.certus_strat_service import APP_CONTEXT
from certus.core._certus_physics_impl import get_refractive_index, get_refractive_clues_vectorized
import certus.utils.certus_strat_service as _strat_service_module
from certus.utils.certus_strat_service import _validate_candidates_phase_a as _service_validate_candidates_phase_a
from certus.physics.certus_strat_kernels import validate_wavelengths_batch, update_run_states_kernel
import threading
_validate_phase_a_bridge_lock = threading.Lock()

def _validate_candidates_phase_a(*args, **kwargs) -> Any:
    """Compatibility bridge for tests monkeypatching STRAT kernel symbols.

    ``certus_strat_service._validate_candidates_phase_a`` resolves kernels from
    its own module globals. This wrapper mirrors legacy behavior by forwarding
    the kernel bindings from ``CERTUS_STRAT`` before dispatch.
    """
    with _validate_phase_a_bridge_lock:
        prev_validate = _strat_service_module.validate_wavelengths_batch
        prev_update = _strat_service_module.update_run_states_kernel
        _strat_service_module.validate_wavelengths_batch = validate_wavelengths_batch
        _strat_service_module.update_run_states_kernel = update_run_states_kernel
        try:
            return _service_validate_candidates_phase_a(*args, **kwargs)
        finally:
            _strat_service_module.validate_wavelengths_batch = prev_validate
            _strat_service_module.update_run_states_kernel = prev_update

# -----------------------------------------------------------------------------

# DYNAMICS METRIC - Single source of truth for candidate ranking

# -----------------------------------------------------------------------------

# Metric: peak-to-peak T(d) over layer growth (T_max - T_min).

# Must match compute_dynamics_kernel and all docstrings referring to "dynamics".

DYNAMICS_METRIC_NAME = "peak_to_peak"

# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------

# SYM STRATEGY SETTINGS - Local extrema symmetry preference

# -----------------------------------------------------------------------------

SYM_DEFAULT_EXTREMA_WINDOW_OT = 12.0

SYM_DEFAULT_WEIGHT = 0.35

SYM_DEFAULT_SAME_WL_BONUS = 0.15

SYM_DEFAULT_CONTINUITY_WEIGHT = 0.25

SYM_DEFAULT_SCORING_MODE = "post"

# -----------------------------------------------------------------------------
# MINIMUM SPECTRAL SEPARATION BETWEEN CANDIDATES OF THE SAME BLOCK (Phase B)
# -----------------------------------------------------------------------------
# DP only retains the `top_k` lowest-cost candidate wavelengths per block. Because
# cost is a smooth function of lambda, refining the grid spacing mechanically clusters
# candidates around the same local minimum.
#
# Minimum separation ensures candidate wavelengths represent genuinely different monitoring options.
# 10 nm default separation ensures candidates span distinct spectral regions.
DP_DEFAULT_MIN_WL_SEPARATION_NM = 10.0

SYM_DEFAULT_TIE_EPS_ABS = 1e-6

SYM_DEFAULT_TIE_EPS_REL = 1e-4

class _IdxWrapper:
    """Dict-like wrapper supporting both ``dict.get`` and ``list[idx]`` access."""

    __slots__ = ("obj",)

    def __init__(self, obj) -> None:
        self.obj = obj

    def __getitem__(self, k) -> Any:
        return self.obj.get(k) if hasattr(self.obj, "get") else self.obj[k]

    def __contains__(self, k) -> bool:
        if hasattr(self.obj, "__contains__"):
            return k in self.obj
        if hasattr(self.obj, "get"):
            return self.obj.get(k) is not None
        return False

# -----------------------------------------------------------------------------

# ROBUST INDEX RETRIEVAL - Uses StratContext for dependency injection

# -----------------------------------------------------------------------------

# Save references to original certus_physics functions

_original_get_refractive_index = get_refractive_index

_original_get_refractive_clues_vectorized = get_refractive_clues_vectorized

def set_robust_material_db(db) -> None:
    """

    Set the material database in the current context.

    Legacy wrapper for backward compatibility.

    Prefer using StratContext directly.

    """

    ctx = get_context()

    ctx.material_db = db

def smart_get_refractive_index(mat_id, wl, db_instance=None) -> Any:
    """Get refractive index using context-based dependency injection with robust fallback."""

    # 1. Explicit DB instance (Legacy)

    if db_instance is not None:
        return _original_get_refractive_index(mat_id, wl, db_instance)

    # 2. Context Strategy

    ctx = StratContext.get_current()

    if ctx is not None and ctx.material_db is not None:
        return ctx.material_db.get_refractive_index(mat_id, wl)

    # 3. Global Fallback (APP_CONTEXT) - Critical for maintaining state if context is empty

    # Check if context has it implicitly or fallback to global

    db_to_use = _resolve_materials_db_fallback(ctx)

    if db_to_use is not None:
        # Special handling for RobustMaterialDatabase if it requires direct call

        if type(db_to_use).__name__ == "RobustMaterialDatabase":
            return db_to_use.get_refractive_index(mat_id, wl)

        return _original_get_refractive_index(mat_id, wl, db_to_use)

    # 4. Final Fallback (No DB)

    return _original_get_refractive_index(mat_id, wl, None)

def smart_get_refractive_clues_vectorized(mat_id, wls, db_instance=None) -> Any:
    """Get vectorized clues using context-based dependency injection with robust fallback."""

    # 1. Explicit DB instance

    if db_instance is not None:
        return _original_get_refractive_clues_vectorized(mat_id, wls, db_instance)

    # 2. Context Strategy

    ctx = StratContext.get_current()

    if ctx is not None and ctx.material_db is not None:
        return ctx.material_db.get_refractive_clues_vectorized(mat_id, wls)

    # 3. Global Fallback

    db_to_use = _resolve_materials_db_fallback(ctx)

    if db_to_use is not None:
        if type(db_to_use).__name__ == "RobustMaterialDatabase":
            return db_to_use.get_refractive_clues_vectorized(mat_id, wls)

        return _original_get_refractive_clues_vectorized(mat_id, wls, db_to_use)

    # 4. Final Fallback

    return _original_get_refractive_clues_vectorized(mat_id, wls, None)

# Alias smart functions to replace imports

get_refractive_index = smart_get_refractive_index

get_refractive_clues_vectorized = smart_get_refractive_clues_vectorized


def _resolve_materials_db_fallback(ctx) -> Any:
    """Resolve the material database using the existing fallback order."""

    if ctx is not None and ctx.app_context.get("materials_db"):
        return ctx.app_context.get("materials_db")

    return APP_CONTEXT.get("materials_db")

