# =============================================================================

# Threads Qt partages : CERTUS_DESIGN et CERTUS_RE (warmup, eval spectrale, tableau detache).

# =============================================================================

from __future__ import annotations


import logging

import time

import traceback

from dataclasses import dataclass, field
from typing import Any


import numpy as np

from PyQt6.QtCore import QThread, pyqtSignal

from PyQt6.QtWidgets import QDialog, QVBoxLayout


from certus.core.certus_core import CFG, NUMERICAL_FAULT_EXCEPTIONS, ensure_numpy_array, get_complex_dtype, get_float_dtype
from certus.utils.certus_progress_tracker import build_progress_snapshot, StepState

from certus_physics import NKCache, calc_rmse

from certus_physics import calc_spectrum_front as calc_spectrum_front_numba

from certus_physics import (
    calc_spectrum_full_oblique_exact,
    calc_spectrum_oblique_backside_vectorized,
    calc_spectrum_oblique_vectorized,
    get_nk_cauchy,
    calc_spectrum_front_wrapper,
    calc_spectrum_full_exact_wrapper,
)

from certus.ui.certus_ui import WorkerSignals, set_certus_window_icon


calc_spectrum_front = calc_spectrum_front_wrapper

calc_spectrum_full_exact = calc_spectrum_full_exact_wrapper


class WarmupWorker(QThread):
    """JIT compilation warmup thread"""

    finished = pyqtSignal()
    progress_snapshot = pyqtSignal(object)

    def run(self) -> None:

        try:
            _t0 = time.time()

            logging.info("[WARMUP] Starting JIT compilation...")
            snapshot = build_progress_snapshot(message='Warmup', sub_message='Starting JIT compilation', progress_ratio=0.0, display_ratio=0.0, eta_seconds=None, confidence=0.1, state=StepState.RUNNING, module='SPECTRAL', phase='WARMUP', is_indeterminate=True)
            self.progress_snapshot.emit(snapshot)

            wls_dumb = np.linspace(CFG.WL_DEFAULT_MIN, CFG.WL_DEFAULT_MAX, 20, dtype=np.float64)

            get_nk_cauchy(2.3, 2.3, wls_dumb)

            n_layers = np.ones((4, 20), dtype=np.complex128) * (2.3 + 0j)

            n_layers_T = np.ascontiguousarray(n_layers.T)

            d_layers = ensure_numpy_array([50.0, 100.0, 50.0, 100.0], dtype=np.float64)

            n_sub = np.ones(20, dtype=np.complex128) * (1.52 + 0j)

            logging.info("[WARMUP] Compiling calc_spectrum_front_numba...")

            calc_spectrum_front_numba(wls_dumb, d_layers, n_layers_T, n_sub)

            logging.info(f"[WARMUP] Front done in {(time.time() - _t0) * 1000:.0f}ms")

            logging.info("[WARMUP] Compiling calc_spectrum_oblique_vectorized (s-pol)...")

            _t1 = time.time()

            calc_spectrum_oblique_vectorized(wls_dumb, n_layers_T, d_layers, n_sub, 45.0, "s")

            logging.info(f"[WARMUP] Oblique s-pol done in {(time.time() - _t1) * 1000:.0f}ms")

            logging.info("[WARMUP] Compiling calc_spectrum_oblique_vectorized (p-pol)...")

            _t2 = time.time()

            calc_spectrum_oblique_vectorized(wls_dumb, n_layers_T, d_layers, n_sub, 45.0, "p")

            logging.info(f"[WARMUP] Oblique p-pol done in {(time.time() - _t2) * 1000:.0f}ms")

            logging.info(f"[WARMUP] Total warmup time: {(time.time() - _t0) * 1000:.0f}ms")
            self.progress_snapshot.emit(build_progress_snapshot(message='Warmup', sub_message='Completed', progress_ratio=1.0, display_ratio=1.0, eta_seconds=0.0, confidence=1.0, state=StepState.DONE, module='SPECTRAL', phase='WARMUP', is_indeterminate=False))

            self.finished.emit()

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            import traceback as _tb

            logging.error(f"[WARMUP] Error: {e}")

            _tb.print_exc()

            self.finished.emit()


class DetachedTableWindow(QDialog):
    """Detached window for layer table"""

    finished = pyqtSignal()

    def __init__(self, table, parent=None) -> None:

        super().__init__(parent)

        set_certus_window_icon(self)

        self.setWindowTitle("FRONT STRUCTURE (Detached)")

        self.resize(500, 600)

        self.layout = QVBoxLayout(self)

        self.table = table

        self.layout.addWidget(self.table)

    def closeEvent(self, event) -> None:

        self.finished.emit()

        event.accept()


def _resolve_substrate_key(mats: dict, explicit: str | None) -> str:

    if explicit:
        return explicit

    if "substrate" in mats:
        return "substrate"

    return "Substrate"


def _log_oblique_backside_mode(
    *,
    oblique_mode: bool,
    has_back_calc: bool,
    has_back_stack: bool,
    re_loaded: bool,
) -> None:
    """Emit the mode-selection trace for oblique/backside kernels."""
    if oblique_mode and has_back_calc and has_back_stack:
        logging.info("[DESIGN] Oblique+backside with back coating: using full oblique exact kernel.")
        return
    if oblique_mode and has_back_calc and re_loaded:
        logging.info("[RE-EVAL] Oblique+backside (substrate, no rear coating in RE).")
        return
    if oblique_mode and has_back_calc:
        logging.info("[DESIGN] Oblique+backside enabled (bare substrate): using oblique backside kernel.")


def _re_beam_eval_params(cfg: dict[str, Any]) -> tuple[bool, Any, Any, float]:
    """Extract RE phase-4 beam averaging parameters from worker config."""
    re_p4_disp = bool(cfg.get("re_p4_display_beam", False))
    ak_re = cfg.get("re_p4_ap_knots_deg")
    alk_re = cfg.get("re_p4_ap_knots_lam_nm")
    ap_re = float(cfg.get("re_beam_aperture_deg", 1.0))
    return re_p4_disp, ak_re, alk_re, ap_re


def _re_index_eval_params(
    cfg: dict[str, Any],
    stack: list[Any],
) -> tuple[float, np.ndarray, np.ndarray, float, float, float, Any, Any, Any, float, Any]:
    """Extract RE index-model parameters from worker config and stack."""
    l0 = float(cfg.get("l0", 500.0))
    is_H = np.array([l.mat == "H" for l in stack], dtype=bool)
    is_L = np.array([l.mat == "L" for l in stack], dtype=bool)
    a_b = float(cfg.get("a_pct", 0.0))
    b_b = float(cfg.get("b_pct", 0.0))
    f_b = float(cfg.get("f_pct", 0.0))
    sdh = cfg.get("spline_dH")
    sdl = cfg.get("spline_dL")
    lam2 = cfg.get("spline_lam2")
    re_env_s = float(cfg.get("re_envelope_scale", 1.0))
    s0 = cfg.get("re_sub_cauchy_a0")
    return l0, is_H, is_L, a_b, b_b, f_b, sdh, sdl, lam2, re_env_s, s0


def _group_valid_oblique_targets(oblique_tgts: list[Any]) -> dict[tuple[Any, Any, bool], list[Any]]:
    """Group valid oblique targets by (angle, pol, include_backside)."""
    unique_configs: dict[tuple[Any, Any, bool], list[Any]] = {}
    for tgt in oblique_tgts:
        if not tgt.valid():
            continue
        key = (tgt.angle, tgt.pol, bool(getattr(tgt, "include_backside", True)))
        if key not in unique_configs:
            unique_configs[key] = []
        unique_configs[key].append(tgt)
    return unique_configs


def _prepare_oblique_configs(
    oblique_tgts: list[Any],
    *,
    log_grouping: bool = True,
) -> dict[tuple[Any, Any, bool], list[Any]]:
    """Build grouped oblique configs and optionally log grouping summary."""
    if log_grouping:
        logging.info("[EVAL-WORKER] Oblique mode: grouping targets...")
    unique_configs = _group_valid_oblique_targets(oblique_tgts)
    if log_grouping:
        logging.info(f"[EVAL-WORKER] {len(unique_configs)} unique (angle, pol, include_backside) configs")
    return unique_configs


def _log_oblique_eval_start(*, phase: str, angle: Any, pol: Any, inc_back: bool) -> None:
    """Emit standardized oblique-evaluation start message."""
    logging.info(
        f"[EVAL-WORKER] Calculating {phase} spectrum for angle={angle}, pol={pol}, "
        f"back={'on' if inc_back else 'off'}..."
    )


def _log_oblique_eval_done(
    *,
    phase: str,
    angle: Any,
    pol: Any,
    inc_back: bool,
    n_lambda: int,
    elapsed_ms: float,
) -> None:
    """Emit standardized oblique-evaluation completion message."""
    logging.info(
        f"[EVAL-WORKER] {phase} oblique={angle} pol={pol} back={'on' if inc_back else 'off'}  "
        f"{int(n_lambda)} lambda en {float(elapsed_ms):.1f}ms"
    )


def _elapsed_ms_since(t0: float) -> float:
    """Return elapsed time in milliseconds from timestamp t0."""
    return (time.time() - float(t0)) * 1000.0


def _log_eval_worker_completion(worker_start: float) -> None:
    """Emit standardized EvalWorker completion timing log."""
    logging.info(f"[EVAL-WORKER] === EvalWorker complete in {_elapsed_ms_since(worker_start):.1f}ms ===")


def _log_eval_worker_start() -> None:
    """Emit standardized EvalWorker start log."""
    logging.info("[EVAL-WORKER] === EvalWorker.run() started ===")


def _log_eval_worker_state(
    *,
    oblique_mode: bool,
    oblique_tgts: list[Any],
    wls_vis: np.ndarray,
) -> None:
    """Emit worker initial state summary for observability."""
    logging.info(f"[EVAL-WORKER] oblique_mode={oblique_mode}, n_targets={len(oblique_tgts)}, n_wls_vis={len(wls_vis)}")


def _build_eval_worker_result(
    cfg: dict[str, Any],
    *,
    wls_vis: np.ndarray,
    ts_vis: np.ndarray,
    wls_optim: np.ndarray,
    ts_optim: np.ndarray,
    rmse: float | None,
    oblique_mode: bool,
    spectra_vis: dict[str, Any],
    spectra_optim: dict[str, Any],
    oblique_tgts: Any,
) -> EvalWorkerResult:
    """Build EvalWorkerResult DTO from runtime outputs."""
    return EvalWorkerResult.success(
        vis={"l": wls_vis, "Ts": ts_vis},
        optimization={"l": wls_optim, "Ts": ts_optim},
        rmse=rmse,
        ep=cfg["ep"],
        eval_generation_id=cfg.get("eval_generation_id"),
        ep_back=cfg.get("ep_back") if "ep_back" in cfg else None,
        oblique_mode=oblique_mode,
        spectra_vis=spectra_vis if oblique_mode else None,
        spectra_optim=spectra_optim if oblique_mode else None,
        oblique_tgts=oblique_tgts if oblique_mode else None,
    )


def _emit_eval_worker_success(signals: WorkerSignals, result_data: EvalWorkerResult) -> None:
    """Emit legacy success payload for EvalWorker."""
    signals.finished.emit(result_data.to_legacy_dict())


def _emit_eval_worker_error(signals: WorkerSignals, err: Exception) -> None:
    """Emit formatted error payload for EvalWorker and log details."""
    logging.error(f"[EVAL-WORKER] ERROR: {err}")
    tb = traceback.format_exc()
    logging.error(tb)
    signals.error.emit(tb)


def _compute_rmse_if_targets(ts_optim: np.ndarray, wls_optim: np.ndarray, tgts: Any) -> float | None:
    """Compute RMSE against targets for optimization spectrum."""
    rmse, _ = calc_rmse(ts_optim, wls_optim, tgts)
    return float(rmse)


def _init_optim_outputs() -> tuple[np.ndarray, float | None, dict[tuple[Any, Any, bool], dict[str, Any]]]:
    """Initialize OPT outputs before optional optimization-grid evaluation."""
    ts_optim = ensure_numpy_array([])
    rmse: float | None = None
    spectra_optim: dict[tuple[Any, Any, bool], dict[str, Any]] = {}
    return ts_optim, rmse, spectra_optim


def _build_optim_materials_and_substrate(
    mats: dict[str, Any],
    wls_optim: np.ndarray,
    substrate_key: str,
) -> tuple[dict[str, np.ndarray], np.ndarray]:
    """Build OPT material nk map and associated substrate array."""
    mats_optim = _build_material_nk_map(mats, wls_optim)
    n_sub_opt = _resolve_substrate_nk_from_map(mats_optim, substrate_key)
    return mats_optim, n_sub_opt


def _build_optim_stacks(
    *,
    mats_optim: dict[str, np.ndarray],
    stack: list[Any],
    n_sub_opt: np.ndarray,
    wls_optim: np.ndarray,
    complex_dtype: np.dtype,
    apply_re_index_fn: Any,
    stack_back: list[Any],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Build OPT front/back stack arrays and possibly adjusted substrate."""
    n_front_opt_T, n_sub_opt_adj = _build_front_stack_arrays(
        mats_optim,
        stack,
        n_sub_opt,
        wls_optim,
        complex_dtype,
        apply_re_index_fn,
    )
    n_back_opt_T = _build_back_stack_arrays(
        mats_optim,
        stack_back,
        len(wls_optim),
        complex_dtype,
    )
    return n_front_opt_T, n_sub_opt_adj, n_back_opt_T


def _build_sub_cauchy_theta(
    cfg: dict[str, Any],
    s0: Any,
    sdh: Any,
) -> tuple[float, float, float] | None:
    """Build optional substrate Cauchy theta tuple for RE index model."""
    if s0 is None or cfg.get("re_sub_cauchy_a1") is None or cfg.get("re_sub_cauchy_a2") is None or sdh is None:
        return None
    return (
        float(s0),
        float(cfg["re_sub_cauchy_a1"]),
        float(cfg["re_sub_cauchy_a2"]),
    )


def _pick_transmission_from_spectra_or_front(
    spectra: dict[tuple[Any, Any, bool], dict[str, Any]],
    wls: np.ndarray,
    n_front_T: np.ndarray,
    d_front: np.ndarray,
    n_sub: np.ndarray,
) -> np.ndarray:
    """Return first grouped transmission or fallback to front-spectrum transmission."""
    if spectra:
        first_key = list(spectra.keys())[0]
        return np.asarray(spectra[first_key]["T"])
    t_vals, _ = calc_spectrum_front(wls, n_front_T, d_front, n_sub)
    return np.asarray(t_vals)


def _build_back_stack_arrays(
    mats_map: dict[str, np.ndarray],
    stack_back: list[Any],
    wls_len: int,
    complex_dtype: np.dtype,
) -> np.ndarray:
    """Build transposed backside refractive-index stack array or empty shape."""
    if not (len(stack_back) > 0):
        return np.zeros((int(wls_len), 0), dtype=complex_dtype)
    return np.ascontiguousarray(np.array([mats_map[l.mat] for l in stack_back], dtype=complex_dtype).T)


def _build_back_thickness_array(
    cfg: dict[str, Any],
    *,
    has_back_stack: bool,
    float_dtype: np.dtype,
) -> np.ndarray:
    """Build backside thickness vector or empty fallback."""
    if has_back_stack:
        return np.ascontiguousarray(cfg["ep_back"], dtype=float_dtype)
    return np.zeros(0, dtype=float_dtype)


def _build_front_thickness_array(cfg: dict[str, Any], float_dtype: np.dtype) -> np.ndarray:
    """Build front-side thickness vector."""
    return np.ascontiguousarray(cfg["ep"], dtype=float_dtype)


def _resolve_substrate_nk_from_map(
    mats_map: dict[str, np.ndarray],
    substrate_key: str,
) -> np.ndarray:
    """Resolve substrate nk array from material map."""
    return np.ascontiguousarray(mats_map[substrate_key])


def _build_front_stack_arrays(
    mats_map: dict[str, np.ndarray],
    stack: list[Any],
    n_sub: np.ndarray,
    wls: np.ndarray,
    complex_dtype: np.dtype,
    apply_re_index_fn: Any,
) -> tuple[np.ndarray, np.ndarray]:
    """Build transposed front stack and possibly adjusted substrate array."""
    if stack:
        n_front = np.array([mats_map[l.mat] for l in stack], dtype=complex_dtype)
        n_front, n_sub = apply_re_index_fn(n_front, n_sub, wls)
        n_front_T = np.ascontiguousarray(n_front.T)
        return n_front_T, n_sub
    n_front_T = np.zeros((len(wls), 0), dtype=complex_dtype)
    return n_front_T, n_sub


def _build_material_nk_map(mats: dict[str, Any], wls: np.ndarray) -> dict[str, np.ndarray]:
    """Build spectral nk arrays for each material on provided wavelength grid."""
    return {
        k: (m.get_nk(wls) if getattr(m, "_is_tabular", False) else NKCache.get(k, m.n4, m.n7, wls))
        for k, m in mats.items()
    }


def _resolve_eval_wavelength_grids(cfg: dict[str, Any], float_dtype: np.dtype) -> tuple[np.ndarray, np.ndarray]:
    """Resolve VIS and OPT wavelength grids as contiguous arrays."""
    wls_vis = np.ascontiguousarray(cfg["wls_vis"], dtype=float_dtype)
    wls_optim = np.ascontiguousarray(cfg["wls_optim"], dtype=float_dtype)
    return wls_vis, wls_optim


def _resolve_eval_mode_flags(
    cfg: dict[str, Any],
) -> tuple[bool, list[Any], bool, bool, bool, list[Any], bool]:
    """Resolve evaluation mode flags and related payloads from config."""
    back_enabled = bool(cfg.get("back", False))
    use_coating = bool(cfg.get("use_back_coat", False))
    stack_back = cfg.get("stack_back", [])
    has_back_calc = bool(back_enabled)
    has_back_stack = bool(use_coating and len(stack_back) > 0)
    oblique_mode = bool(cfg.get("oblique_mode", False))
    oblique_tgts = cfg.get("oblique_tgts", [])
    re_loaded = bool(cfg.get("re_loaded", False))
    return back_enabled, stack_back, has_back_calc, has_back_stack, oblique_mode, oblique_tgts, re_loaded


def _transmission_non_oblique(
    *,
    wls: np.ndarray,
    n_front_T: np.ndarray,
    d_front: np.ndarray,
    n_sub: np.ndarray,
    n_back_T: np.ndarray,
    d_back: np.ndarray,
    back_enabled: bool,
) -> np.ndarray:
    """Compute non-oblique transmission with/without backside stack."""
    if back_enabled:
        _, tf, rf_prime, rb_prime, tb = calc_spectrum_full_exact(wls, n_front_T, d_front, n_sub, n_back_T, d_back)
        denom = np.maximum(1.0 - rf_prime * rb_prime, 1e-12)
        return np.asarray((tf * tb) / denom)
    t_vals, _ = calc_spectrum_front(wls, n_front_T, d_front, n_sub)
    return np.asarray(t_vals)


def _calc_oblique_selected_kernel(
    *,
    wls_arr: np.ndarray,
    n_front_T: np.ndarray,
    d_front_arr: np.ndarray,
    n_sub_arr: np.ndarray,
    angle: Any,
    pol: Any,
    has_back_calc: bool,
    has_back_stack: bool,
    n_back_T_arr: np.ndarray | None = None,
    d_back_arr: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Select oblique kernel variant according to backside configuration."""
    if has_back_calc and has_back_stack and n_back_T_arr is not None and d_back_arr is not None:
        return calc_spectrum_full_oblique_exact(
            wls_arr,
            d_front_arr,
            n_front_T,
            d_back_arr,
            n_back_T_arr,
            n_sub_arr,
            float(angle),
            str(pol).lower() == "s",
        )
    if has_back_calc and (not has_back_stack):
        return calc_spectrum_oblique_backside_vectorized(wls_arr, n_front_T, d_front_arr, n_sub_arr, angle, pol)
    return calc_spectrum_oblique_vectorized(wls_arr, n_front_T, d_front_arr, n_sub_arr, angle, pol)


def _should_use_re_phase4_average(
    *,
    re_p4_disp: bool,
    re_loaded: bool,
    ak_re: Any,
    alk_re: Any,
    angle: Any,
    has_back_stack: bool,
    n_back_T_arr: np.ndarray | None,
    d_back_arr: np.ndarray | None,
) -> bool:
    """Return True when RE phase-4 averaged oblique path should be used."""
    return bool(
        re_p4_disp
        and re_loaded
        and ak_re is not None
        and alk_re is not None
        and float(angle) >= 10.0
        and not (has_back_stack and n_back_T_arr is not None and d_back_arr is not None and d_back_arr.size > 0)
    )


def _normalize_beam_knots(ak_re: Any, alk_re: Any) -> tuple[np.ndarray, np.ndarray, int]:
    """Normalize beam-knot arrays and return common usable length."""
    ak = np.asarray(ak_re, dtype=np.float64).ravel()
    alk = np.asarray(alk_re, dtype=np.float64).ravel()
    nk = int(min(ak.size, alk.size))
    return ak, alk, nk


def _re_phase4_oblique_spectrum(
    *,
    wls_arr: np.ndarray,
    n_front_T: np.ndarray,
    d_front_arr: np.ndarray,
    n_sub_arr: np.ndarray,
    angle: Any,
    pol: Any,
    include_backside: bool,
    beam_aperture: float,
    ak: np.ndarray,
    alk: np.ndarray,
    nk: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute RE phase-4 averaged oblique spectrum."""
    from certus.utils.certus_re_helpers import _re_calc_spectrum_for_config

    return _re_calc_spectrum_for_config(
        wls_arr,
        n_front_T,
        d_front_arr,
        n_sub_arr,
        float(angle),
        str(pol),
        bool(include_backside),
        phase4_average=True,
        beam_aperture=beam_aperture,
        beam_aperture_knots_deg=ak[:nk],
        beam_aperture_knots_lam_nm=alk[:nk],
    )


@dataclass(frozen=True)
class EvalWorkerRequest:
    """DTO boundary for spectral eval worker payload."""

    cfg: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_legacy(cfg: dict[str, Any] | None) -> "EvalWorkerRequest":
        if not isinstance(cfg, dict):
            return EvalWorkerRequest(cfg={})
        return EvalWorkerRequest(cfg=dict(cfg))


@dataclass(frozen=True)
class EvalWorkerResult:
    """DTO boundary for spectral eval worker output payload."""

    vis: dict[str, Any]
    optimization: dict[str, Any]
    rmse: float | None
    ep: Any
    eval_generation_id: Any
    ep_back: Any | None = None
    oblique_mode: bool = False
    spectra_vis: dict[str, Any] | None = None
    spectra_optim: dict[str, Any] | None = None
    oblique_tgts: Any | None = None

    @staticmethod
    def success(
        *,
        vis: dict[str, Any],
        optimization: dict[str, Any],
        rmse: float | None,
        ep: Any,
        eval_generation_id: Any,
        ep_back: Any | None,
        oblique_mode: bool,
        spectra_vis: dict[str, Any] | None,
        spectra_optim: dict[str, Any] | None,
        oblique_tgts: Any | None,
    ) -> "EvalWorkerResult":
        return EvalWorkerResult(
            vis=vis,
            optimization=optimization,
            rmse=rmse,
            ep=ep,
            eval_generation_id=eval_generation_id,
            ep_back=ep_back,
            oblique_mode=bool(oblique_mode),
            spectra_vis=spectra_vis,
            spectra_optim=spectra_optim,
            oblique_tgts=oblique_tgts,
        )

    def to_legacy_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "vis": self.vis,
            "optimization": self.optimization,
            "rmse": self.rmse,
            "ep": self.ep,
            "eval_generation_id": self.eval_generation_id,
            "oblique_mode": bool(self.oblique_mode),
        }
        if self.ep_back is not None:
            out["ep_back"] = self.ep_back
        if self.oblique_mode:
            out["spectra_vis"] = self.spectra_vis if self.spectra_vis is not None else {}
            out["spectra_optim"] = self.spectra_optim if self.spectra_optim is not None else {}
            out["oblique_tgts"] = self.oblique_tgts if self.oblique_tgts is not None else []
        return out


class EvalWorker(QThread):
    """Spectral evaluation thread (Design + RE).

    ``cfg`` may include:

    - ``substrate_mat_key``: ``\"substrate\"`` (Design) or ``\"Substrate\"`` (RE); auto if omitted.

    - ``re_loaded``: if true, apply ``re_apply_re_index_model`` (import paresseux depuis ``certus_re_helpers``).

    - ``use_back_coat``, ``stack_back``, ``ep_back``: pile arriere (Design uniquement).

    """

    def __init__(self, cfg: dict[str, Any] | EvalWorkerRequest) -> None:

        super().__init__()

        self.request = cfg if isinstance(cfg, EvalWorkerRequest) else EvalWorkerRequest.from_legacy(cfg)

        # Keep legacy mutable cfg field for incremental migration in call sites.
        self.cfg = dict(self.request.cfg)

        self.signals = WorkerSignals()

    def run(self) -> Any:

        try:
            _worker_start = time.time()

            _log_eval_worker_start()

            float_dtype = get_float_dtype()

            complex_dtype = get_complex_dtype()

            wls_vis, wls_optim = _resolve_eval_wavelength_grids(self.cfg, float_dtype)

            mats = self.cfg["mats"]

            stack = self.cfg["stack"]

            substrate_key = _resolve_substrate_key(mats, self.cfg.get("substrate_mat_key"))

            (
                back_enabled,
                stack_back,
                has_back_calc,
                has_back_stack,
                oblique_mode,
                oblique_tgts,
                re_loaded,
            ) = _resolve_eval_mode_flags(self.cfg)

            mats_vis = _build_material_nk_map(mats, wls_vis)

            n_sub_vis = _resolve_substrate_nk_from_map(mats_vis, substrate_key)

            _log_oblique_backside_mode(
                oblique_mode=bool(oblique_mode),
                has_back_calc=bool(has_back_calc),
                has_back_stack=bool(has_back_stack),
                re_loaded=bool(re_loaded),
            )

            _log_eval_worker_state(
                oblique_mode=bool(oblique_mode),
                oblique_tgts=list(oblique_tgts),
                wls_vis=wls_vis,
            )

            _re_p4_disp, _ak_re, _alk_re, _ap_re = _re_beam_eval_params(self.cfg)

            def _oblique_spectrum_for_eval(
                wls_arr,
                n_front_T,
                d_front_arr,
                n_sub_arr,
                angle,
                pol,
                include_backside,
                n_back_T_arr,
                d_back_arr,
            ) -> Any:

                if _should_use_re_phase4_average(
                    re_p4_disp=bool(_re_p4_disp),
                    re_loaded=bool(re_loaded),
                    ak_re=_ak_re,
                    alk_re=_alk_re,
                    angle=angle,
                    has_back_stack=bool(has_back_stack),
                    n_back_T_arr=n_back_T_arr,
                    d_back_arr=d_back_arr,
                ):
                    ak, alk, _nk = _normalize_beam_knots(_ak_re, _alk_re)

                    if _nk >= 2:
                        return _re_phase4_oblique_spectrum(
                            wls_arr=wls_arr,
                            n_front_T=n_front_T,
                            d_front_arr=d_front_arr,
                            n_sub_arr=n_sub_arr,
                            angle=angle,
                            pol=pol,
                            include_backside=bool(include_backside),
                            beam_aperture=float(_ap_re),
                            ak=ak,
                            alk=alk,
                            nk=int(_nk),
                        )

                return _calc_oblique_selected_kernel(
                    wls_arr=wls_arr,
                    n_front_T=n_front_T,
                    d_front_arr=d_front_arr,
                    n_sub_arr=n_sub_arr,
                    angle=angle,
                    pol=pol,
                    has_back_calc=bool(has_back_calc),
                    has_back_stack=bool(has_back_stack),
                    n_back_T_arr=n_back_T_arr,
                    d_back_arr=d_back_arr,
                )

            def _apply_re_index_if_needed(n_front, n_sub, wls) -> Any:

                if not re_loaded or not stack:
                    return n_front, n_sub

                from certus.utils.certus_re_helpers import re_apply_re_index_model

                l0, is_H, is_L, a_b, b_b, f_b, sdh, sdl, lam2, re_env_s, _s0 = _re_index_eval_params(self.cfg, stack)

                _sub_theta = _build_sub_cauchy_theta(self.cfg, _s0, sdh)

                return re_apply_re_index_model(
                    n_front,
                    n_sub,
                    is_H=is_H,
                    is_L=is_L,
                    wls_nm=wls,
                    lambda_ref_nm=l0,
                    a_pct=a_b,
                    b_pct=b_b,
                    f_pct=f_b,
                    spline_dH=np.asarray(sdh, dtype=np.float64) if sdh is not None else None,
                    spline_dL=np.asarray(sdl, dtype=np.float64) if sdl is not None else None,
                    spline_lam_node2_nm=lam2,
                    re_envelope_scale=re_env_s,
                    sub_cauchy_theta=_sub_theta,
                )

            n_front_vis_T, n_sub_vis = _build_front_stack_arrays(
                mats_vis,
                stack,
                n_sub_vis,
                wls_vis,
                complex_dtype,
                _apply_re_index_if_needed,
            )

            d_front = _build_front_thickness_array(self.cfg, float_dtype)

            n_back_vis_T = _build_back_stack_arrays(
                mats_vis,
                stack_back,
                len(wls_vis),
                complex_dtype,
            )
            d_back = _build_back_thickness_array(
                self.cfg,
                has_back_stack=bool(has_back_stack),
                float_dtype=float_dtype,
            )

            unique_configs: dict[tuple[Any, Any, bool], list[Any]] = {}
            spectra_vis: dict[tuple[Any, Any, bool], dict[str, Any]] = {}
            if oblique_mode:
                unique_configs = _prepare_oblique_configs(oblique_tgts, log_grouping=True)

                import concurrent.futures
                
                def _eval_vis_oblique(k):
                    angle, pol, inc_back = k
                    _log_oblique_eval_start(phase="VIS", angle=angle, pol=pol, inc_back=bool(inc_back))
                    _t0 = time.time()
                    R_vis, T_vis = _oblique_spectrum_for_eval(
                        wls_vis, n_front_vis_T, d_front, n_sub_vis,
                        angle, pol, inc_back, n_back_vis_T, d_back
                    )
                    return k, R_vis, T_vis, _t0

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    futures = [executor.submit(_eval_vis_oblique, k) for k in unique_configs.keys()]
                    for f in concurrent.futures.as_completed(futures):
                        k, R_vis, T_vis, _t0 = f.result()
                        spectra_vis[k] = {"R": R_vis, "T": T_vis}
                        _log_oblique_eval_done(
                            phase="VIS", angle=k[0], pol=k[1], inc_back=bool(k[2]),
                            n_lambda=int(len(wls_vis)), elapsed_ms=_elapsed_ms_since(_t0)
                        )

                Ts_vis = _pick_transmission_from_spectra_or_front(
                    spectra_vis, wls_vis, n_front_vis_T, d_front, n_sub_vis
                )

                logging.info("[EVAL-WORKER] VIS spectra calculationation complete")

            else:
                Ts_vis = _transmission_non_oblique(
                    wls=wls_vis,
                    n_front_T=n_front_vis_T,
                    d_front=d_front,
                    n_sub=n_sub_vis,
                    n_back_T=n_back_vis_T,
                    d_back=d_back,
                    back_enabled=bool(back_enabled),
                )

            Ts_optim, rmse, spectra_optim = _init_optim_outputs()

            if wls_optim.size > 0:
                mats_optim, n_sub_opt = _build_optim_materials_and_substrate(mats, wls_optim, substrate_key)

                n_front_opt_T, n_sub_opt, n_back_opt_T = _build_optim_stacks(
                    mats_optim=mats_optim,
                    stack=stack,
                    n_sub_opt=n_sub_opt,
                    wls_optim=wls_optim,
                    complex_dtype=complex_dtype,
                    apply_re_index_fn=_apply_re_index_if_needed,
                    stack_back=stack_back,
                )

                if oblique_mode:
                    import concurrent.futures
                    
                    def _eval_opt_oblique(k):
                        angle, pol, inc_back = k
                        _log_oblique_eval_start(phase="OPT", angle=angle, pol=pol, inc_back=bool(inc_back))
                        _to0 = time.time()
                        R_opt, T_opt = _oblique_spectrum_for_eval(
                            wls_optim, n_front_opt_T, d_front, n_sub_opt,
                            angle, pol, inc_back, n_back_opt_T, d_back
                        )
                        return k, R_opt, T_opt, _to0
                    
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        futures = [executor.submit(_eval_opt_oblique, k) for k in unique_configs.keys()]
                        for f in concurrent.futures.as_completed(futures):
                            k, R_opt, T_opt, _to0 = f.result()
                            spectra_optim[k] = {"R": R_opt, "T": T_opt}
                            _log_oblique_eval_done(
                                phase="OPT", angle=k[0], pol=k[1], inc_back=bool(k[2]),
                                n_lambda=int(len(wls_optim)), elapsed_ms=_elapsed_ms_since(_to0)
                            )

                    Ts_optim = _pick_transmission_from_spectra_or_front(
                        spectra_optim, wls_optim, n_front_opt_T, d_front, n_sub_opt
                    )

                    rmse = None

                else:
                    Ts_optim = _transmission_non_oblique(
                        wls=wls_optim,
                        n_front_T=n_front_opt_T,
                        d_front=d_front,
                        n_sub=n_sub_opt,
                        n_back_T=n_back_opt_T,
                        d_back=d_back,
                        back_enabled=bool(back_enabled),
                    )

                    rmse = _compute_rmse_if_targets(Ts_optim, wls_optim, self.cfg["tgts"])

            result_data = _build_eval_worker_result(
                self.cfg,
                wls_vis=wls_vis,
                ts_vis=Ts_vis,
                wls_optim=wls_optim,
                ts_optim=Ts_optim,
                rmse=rmse,
                oblique_mode=bool(oblique_mode),
                spectra_vis=spectra_vis,
                spectra_optim=spectra_optim,
                oblique_tgts=oblique_tgts,
            )

            _log_eval_worker_completion(_worker_start)

            _emit_eval_worker_success(self.signals, result_data)

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            _emit_eval_worker_error(self.signals, e)
