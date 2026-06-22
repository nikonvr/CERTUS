# from typing import *  # Unused
import numpy as np
import logging
from certus.core.certus_core import Any, NUMERICAL_FAULT_EXCEPTIONS

from certus.spline.certus_corridor_config import (
    ProfileCorridorConfig,
    SplineOptConfig,
    _LOG_PREFIX,
)
from certus.spline.certus_corridor_utils import quick_pwlnk_refit_result_dict

log = logging.getLogger('CERTUS')

def _bootstrap_single_replicate(
    cfg_b: SplineOptConfig,
    base_result: dict,
    *,
    pconf: ProfileCorridorConfig,
    qref: int,
    lam: np.ndarray,
    log_run_1based: int | None = None,
) -> dict[str, Any]:
    """Run profiling + quick refit for one draw (cfg_b); structured return for aggregation."""

    lam = np.asarray(lam, dtype=np.float64).ravel()

    out: dict[str, Any] = {"status": "exception", "nvalid": 0}

    try:
        base_for: dict[str, Any] = base_result

        if int(qref) > 0:
            br = quick_pwlnk_refit_result_dict(cfg_b, base_result, maxfun=int(qref))

            if br is not None:
                base_for = br

        from certus.spline.spline_profile_corridors import compute_profiled_corridors_by_d
        extra = compute_profiled_corridors_by_d(cfg_b, base_for, pconf=pconf, log_coaching=False)

    except NUMERICAL_FAULT_EXCEPTIONS:
        if log_run_1based is not None:
            log.exception("%s [BOOT] failed run=%d", _LOG_PREFIX, int(log_run_1based))

        else:
            log.exception("%s [BOOT] internal run failed", _LOG_PREFIX)

        return out

    d_int = extra.get("profile_d_interval_nm", None)

    out["nvalid"] = int(np.asarray(extra.get("profile_d_values_nm", [])).size)

    if not (isinstance(d_int, (tuple, list)) and len(d_int) == 2):
        out["status"] = "bad_interval"

        return out

    try:
        dlo = float(d_int[0])

        dhi = float(d_int[1])

    except TypeError, ValueError:
        out["status"] = "bad_interval"

        return out

    n_lo = np.asarray(extra.get("corridor_n_lo", []), dtype=np.float64).ravel()

    n_hi = np.asarray(extra.get("corridor_n_hi", []), dtype=np.float64).ravel()

    k_lo = np.asarray(extra.get("corridor_k_lo", []), dtype=np.float64).ravel()

    k_hi = np.asarray(extra.get("corridor_k_hi", []), dtype=np.float64).ravel()

    if not (n_lo.size == lam.size == n_hi.size == k_lo.size == k_hi.size):
        out["status"] = "shape"

        return out

    out["status"] = "ok"

    out["dlo"] = dlo

    out["dhi"] = dhi

    out["n_lo"] = n_lo

    out["n_hi"] = n_hi

    out["k_lo"] = k_lo

    out["k_hi"] = k_hi

    return out
def _bootstrap_pool_entry(payload: tuple[Any, ...]) -> tuple[int, dict[str, Any]]:
    """ProcessPoolExecutor entry point (picklable, module level)."""

    b, cfg_b, base_result, pconf, qref, lam = payload

    r = _bootstrap_single_replicate(
        cfg_b,
        base_result,
        pconf=pconf,
        qref=int(qref),
        lam=lam,
        log_run_1based=int(b) + 1,
    )

    return int(b), r
def _resample_residuals_block(e: np.ndarray, block_len: int, rng: np.random.Generator) -> np.ndarray:
    """Moving-block bootstrap resample of residuals (wrap-around)."""

    ee = np.asarray(e, dtype=np.float64).ravel()
    n = int(ee.size)
    if n == 0:
        return ee.copy()
    L = int(max(1, min(block_len, n)))
    if L == 1:
        idx = rng.integers(0, n, size=n, endpoint=False)
        return ee[idx]
    n_blocks = int(np.ceil(n / L))
    starts = rng.integers(0, n, size=n_blocks, endpoint=False)
    out = np.empty(n_blocks * L, dtype=np.float64)
    pos = 0
    for s in starts:
        j = (s + np.arange(L)) % n
        out[pos : pos + L] = ee[j]
        pos += L
    return out[:n]