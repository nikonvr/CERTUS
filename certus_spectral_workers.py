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


from certus_core import CFG, ensure_numpy_array, get_complex_dtype, get_float_dtype

from certus_physics import NKCache, calc_rmse

from certus_physics import calc_spectrum_front as calc_spectrum_front_numba

from certus_physics import (

    calc_spectrum_front_wrapper,

    calc_spectrum_full_exact_wrapper,

    calc_spectrum_full_oblique_exact,

    calc_spectrum_oblique_backside_vectorized,

    calc_spectrum_oblique_vectorized,

    get_nk_cauchy,

)

from certus_ui import WorkerSignals, set_certus_window_icon


calc_spectrum_front = calc_spectrum_front_wrapper

calc_spectrum_full_exact = calc_spectrum_full_exact_wrapper


class WarmupWorker(QThread):

    """JIT compilation warmup thread"""

    finished = pyqtSignal()

    def run(self):

        try:

            _t0 = time.time()

            logging.info("[WARMUP] Starting JIT compilation...")

            wls_dumb = np.linspace(CFG.WL_DEFAULT_MIN, CFG.WL_DEFAULT_MAX, 20, dtype=np.float64)

            get_nk_cauchy(2.3, 2.3, wls_dumb)

            n_layers = np.ones((4, 20), dtype=np.complex128) * (2.3 + 0j)

            n_layers_T = np.ascontiguousarray(n_layers.T)

            d_layers = ensure_numpy_array([50.0, 100.0, 50.0, 100.0], dtype=np.float64)

            n_sub = np.ones(20, dtype=np.complex128) * (1.52 + 0j)

            logging.info("[WARMUP] Compiling calc_spectrum_front_numba...")

            calc_spectrum_front_numba(wls_dumb, d_layers, n_layers_T, n_sub)

            logging.info(f"[WARMUP] Front done in {(time.time()-_t0)*1000:.0f}ms")

            logging.info("[WARMUP] Compiling calc_spectrum_oblique_vectorized (s-pol)...")

            _t1 = time.time()

            calc_spectrum_oblique_vectorized(wls_dumb, n_layers_T, d_layers, n_sub, 45.0, "s")

            logging.info(f"[WARMUP] Oblique s-pol done in {(time.time()-_t1)*1000:.0f}ms")

            logging.info("[WARMUP] Compiling calc_spectrum_oblique_vectorized (p-pol)...")

            _t2 = time.time()

            calc_spectrum_oblique_vectorized(wls_dumb, n_layers_T, d_layers, n_sub, 45.0, "p")

            logging.info(f"[WARMUP] Oblique p-pol done in {(time.time()-_t2)*1000:.0f}ms")

            logging.info(f"[WARMUP] Total warmup time: {(time.time()-_t0)*1000:.0f}ms")

            self.finished.emit()

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError) as e:

            import traceback as _tb

            logging.error(f"[WARMUP] Error: {e}")

            _tb.print_exc()

            self.finished.emit()


class DetachedTableWindow(QDialog):

    """Detached window for layer table"""

    finished = pyqtSignal()

    def __init__(self, table, parent=None):

        super().__init__(parent)

        set_certus_window_icon(self)

        self.setWindowTitle("FRONT STRUCTURE (Detached)")

        self.resize(500, 600)

        self.layout = QVBoxLayout(self)

        self.table = table

        self.layout.addWidget(self.table)

    def closeEvent(self, event):

        self.finished.emit()

        event.accept()


def _resolve_substrate_key(mats: dict, explicit: str | None) -> str:

    if explicit:

        return explicit

    if "substrate" in mats:

        return "substrate"

    return "Substrate"


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

    def __init__(self, cfg: dict[str, Any] | EvalWorkerRequest):

        super().__init__()

        self.request = cfg if isinstance(cfg, EvalWorkerRequest) else EvalWorkerRequest.from_legacy(cfg)

        # Keep legacy mutable cfg field for incremental migration in call sites.
        self.cfg = dict(self.request.cfg)

        self.signals = WorkerSignals()

    def run(self):

        try:

            _worker_start = time.time()

            logging.info("[EVAL-WORKER] === EvalWorker.run() started ===")

            float_dtype = get_float_dtype()

            complex_dtype = get_complex_dtype()

            wls_vis = np.ascontiguousarray(self.cfg["wls_vis"], dtype=float_dtype)

            wls_optim = np.ascontiguousarray(self.cfg["wls_optim"], dtype=float_dtype)

            mats = self.cfg["mats"]

            stack = self.cfg["stack"]

            substrate_key = _resolve_substrate_key(mats, self.cfg.get("substrate_mat_key"))

            back_enabled = self.cfg.get("back", False)

            use_coating = self.cfg.get("use_back_coat", False)

            stack_back = self.cfg.get("stack_back", [])

            has_back_calc = back_enabled

            has_back_stack = use_coating and len(stack_back) > 0

            oblique_mode = self.cfg.get("oblique_mode", False)

            oblique_tgts = self.cfg.get("oblique_tgts", [])

            re_loaded = bool(self.cfg.get("re_loaded", False))

            mats_vis = {

                k: (

                    m.get_nk(wls_vis)

                    if getattr(m, "_is_tabular", False)

                    else NKCache.get(k, m.n4, m.n7, wls_vis)

                )

                for k, m in mats.items()

            }

            n_sub_vis = np.ascontiguousarray(mats_vis[substrate_key])

            if oblique_mode and has_back_calc and has_back_stack:

                logging.info(

                    "[DESIGN] Oblique+backside with back coating: using full oblique exact kernel."

                )

            elif oblique_mode and has_back_calc and re_loaded:

                logging.info(

                    "[RE-EVAL] Oblique+backside (substrate, no rear coating in RE)."

                )

            elif oblique_mode and has_back_calc:

                logging.info(

                    "[DESIGN] Oblique+backside enabled (bare substrate): using oblique backside kernel."

                )

            logging.info(

                f"[EVAL-WORKER] oblique_mode={oblique_mode}, n_targets={len(oblique_tgts)}, "

                f"n_wls_vis={len(wls_vis)}"

            )

            def _calc_oblique_selected(

                wls_arr,

                n_front_T,

                d_front_arr,

                n_sub_arr,

                angle,

                pol,

                n_back_T_arr=None,

                d_back_arr=None,

            ):

                if (

                    has_back_calc

                    and has_back_stack

                    and n_back_T_arr is not None

                    and d_back_arr is not None

                ):

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

                    return calc_spectrum_oblique_backside_vectorized(

                        wls_arr, n_front_T, d_front_arr, n_sub_arr, angle, pol

                    )

                return calc_spectrum_oblique_vectorized(

                    wls_arr, n_front_T, d_front_arr, n_sub_arr, angle, pol

                )

            _re_p4_disp = bool(self.cfg.get("re_p4_display_beam", False))

            _ak_re = self.cfg.get("re_p4_ap_knots_deg")

            _alk_re = self.cfg.get("re_p4_ap_knots_lam_nm")

            _ap_re = float(self.cfg.get("re_beam_aperture_deg", 1.0))

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

            ):

                if (

                    _re_p4_disp

                    and re_loaded

                    and _ak_re is not None

                    and _alk_re is not None

                    and float(angle) >= 10.0

                    and not (

                        has_back_stack

                        and n_back_T_arr is not None

                        and d_back_arr is not None

                        and d_back_arr.size > 0

                    )

                ):

                    ak = np.asarray(_ak_re, dtype=np.float64).ravel()

                    alk = np.asarray(_alk_re, dtype=np.float64).ravel()

                    _nk = int(min(ak.size, alk.size))

                    if _nk >= 2:

                        from certus_re_helpers import _re_calc_spectrum_for_config

                        return _re_calc_spectrum_for_config(

                            wls_arr,

                            n_front_T,

                            d_front_arr,

                            n_sub_arr,

                            float(angle),

                            str(pol),

                            bool(include_backside),

                            phase4_average=True,

                            beam_aperture=_ap_re,

                            beam_aperture_knots_deg=ak[:_nk],

                            beam_aperture_knots_lam_nm=alk[:_nk],

                        )

                return _calc_oblique_selected(

                    wls_arr,

                    n_front_T,

                    d_front_arr,

                    n_sub_arr,

                    angle,

                    pol,

                    n_back_T_arr,

                    d_back_arr,

                )

            def _apply_re_index_if_needed(n_front, n_sub, wls):

                if not re_loaded or not stack:

                    return n_front, n_sub

                from certus_re_helpers import re_apply_re_index_model

                l0 = float(self.cfg.get("l0", 500.0))

                is_H = np.array([l.mat == "H" for l in stack], dtype=bool)

                is_L = np.array([l.mat == "L" for l in stack], dtype=bool)

                a_b = float(self.cfg.get("a_pct", 0.0))

                b_b = float(self.cfg.get("b_pct", 0.0))

                f_b = float(self.cfg.get("f_pct", 0.0))

                sdh, sdl, lam2 = (

                    self.cfg.get("spline_dH"),

                    self.cfg.get("spline_dL"),

                    self.cfg.get("spline_lam2"),

                )

                re_env_s = float(self.cfg.get("re_envelope_scale", 1.0))

                _s0 = self.cfg.get("re_sub_cauchy_a0")

                _sub_theta = (

                    (

                        float(_s0),

                        float(self.cfg["re_sub_cauchy_a1"]),

                        float(self.cfg["re_sub_cauchy_a2"]),

                    )

                    if _s0 is not None

                    and self.cfg.get("re_sub_cauchy_a1") is not None

                    and self.cfg.get("re_sub_cauchy_a2") is not None

                    and sdh is not None

                    else None

                )

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

            if stack:

                n_front_vis = np.array([mats_vis[l.mat] for l in stack], dtype=complex_dtype)

                n_front_vis, n_sub_vis = _apply_re_index_if_needed(

                    n_front_vis, n_sub_vis, wls_vis

                )

                n_front_vis_T = np.ascontiguousarray(n_front_vis.T)

            else:

                n_front_vis_T = np.zeros((len(wls_vis), 0), dtype=complex_dtype)

            d_front = np.ascontiguousarray(self.cfg["ep"], dtype=float_dtype)

            if has_back_stack:

                n_back_vis_T = np.ascontiguousarray(

                    np.array([mats_vis[l.mat] for l in stack_back], dtype=complex_dtype).T

                )

                d_back = np.ascontiguousarray(self.cfg["ep_back"], dtype=float_dtype)

            else:

                n_back_vis_T = np.zeros((len(wls_vis), 0), dtype=complex_dtype)

                d_back = np.zeros(0, dtype=float_dtype)

            if oblique_mode:

                logging.info("[EVAL-WORKER] Oblique mode: grouping targets...")

                unique_configs: dict = {}

                for tgt in oblique_tgts:

                    if not tgt.valid():

                        continue

                    key = (tgt.angle, tgt.pol, bool(getattr(tgt, "include_backside", True)))

                    if key not in unique_configs:

                        unique_configs[key] = []

                    unique_configs[key].append(tgt)

                logging.info(

                    f"[EVAL-WORKER] {len(unique_configs)} unique (angle, pol, include_backside) configs"

                )

                spectra_vis = {}

                for (angle, pol, inc_back), _ in unique_configs.items():

                    logging.info(

                        f"[EVAL-WORKER] Calculating VIS spectrum for angle={angle}, pol={pol}, "

                        f"back={'on' if inc_back else 'off'}..."

                    )

                    _t0 = time.time()

                    R_vis, T_vis = _oblique_spectrum_for_eval(

                        wls_vis,

                        n_front_vis_T,

                        d_front,

                        n_sub_vis,

                        angle,

                        pol,

                        inc_back,

                        n_back_vis_T,

                        d_back,

                    )

                    spectra_vis[(angle, pol, inc_back)] = {"R": R_vis, "T": T_vis}

                    logging.info(

                        f"[EVAL-WORKER] VIS spectrum done in {(time.time()-_t0)*1000:.1f}ms"

                    )

                if spectra_vis:

                    first_key = list(spectra_vis.keys())[0]

                    Ts_vis = spectra_vis[first_key]["T"]

                else:

                    Ts_vis, _ = calc_spectrum_front(wls_vis, n_front_vis_T, d_front, n_sub_vis)

                logging.info("[EVAL-WORKER] VIS spectra calculationation complete")

            else:

                if back_enabled:

                    _, Tf, Rf_prime, Rb_prime, Tb = calc_spectrum_full_exact(

                        wls_vis, n_front_vis_T, d_front, n_sub_vis, n_back_vis_T, d_back

                    )

                    denom = np.maximum(1.0 - Rf_prime * Rb_prime, 1e-12)

                    Ts_vis = (Tf * Tb) / denom

                else:

                    Ts_vis, _ = calc_spectrum_front(wls_vis, n_front_vis_T, d_front, n_sub_vis)

            Ts_optim = ensure_numpy_array([])

            rmse = None

            spectra_optim = {}

            if wls_optim.size > 0:

                mats_optim = {

                    k: (

                        m.get_nk(wls_optim)

                        if getattr(m, "_is_tabular", False)

                        else NKCache.get(k, m.n4, m.n7, wls_optim)

                    )

                    for k, m in mats.items()

                }

                n_sub_opt = np.ascontiguousarray(mats_optim[substrate_key])

                if stack:

                    n_front_opt = np.array(

                        [mats_optim[l.mat] for l in stack], dtype=complex_dtype

                    )

                    n_front_opt, n_sub_opt = _apply_re_index_if_needed(

                        n_front_opt, n_sub_opt, wls_optim

                    )

                    n_front_opt_T = np.ascontiguousarray(n_front_opt.T)

                else:

                    n_front_opt_T = np.zeros((len(wls_optim), 0), dtype=complex_dtype)

                if has_back_stack:

                    n_back_opt_T = np.ascontiguousarray(

                        np.array([mats_optim[l.mat] for l in stack_back], dtype=complex_dtype).T

                    )

                else:

                    n_back_opt_T = np.zeros((len(wls_optim), 0), dtype=complex_dtype)

                if oblique_mode:

                    unique_configs = {}

                    for tgt in oblique_tgts:

                        if not tgt.valid():

                            continue

                        key = (tgt.angle, tgt.pol, bool(getattr(tgt, "include_backside", True)))

                        if key not in unique_configs:

                            unique_configs[key] = []

                        unique_configs[key].append(tgt)

                    for (angle, pol, inc_back), _ in unique_configs.items():

                        _to0 = time.time()

                        R_opt, T_opt = _oblique_spectrum_for_eval(

                            wls_optim,

                            n_front_opt_T,

                            d_front,

                            n_sub_opt,

                            angle,

                            pol,

                            inc_back,

                            n_back_opt_T,

                            d_back,

                        )

                        spectra_optim[(angle, pol, inc_back)] = {"R": R_opt, "T": T_opt}

                        logging.info(

                            f"[EVAL-WORKER] OPT oblique ={angle} pol={pol} back={'on' if inc_back else 'off'}  "

                            f"{len(wls_optim)} lambda en {(time.time()-_to0)*1000:.1f}ms"

                        )

                    if spectra_optim:

                        first_key = list(spectra_optim.keys())[0]

                        Ts_optim = spectra_optim[first_key]["T"]

                    else:

                        Ts_optim, _ = calc_spectrum_front(

                            wls_optim, n_front_opt_T, d_front, n_sub_opt

                        )

                    rmse = None

                else:

                    if back_enabled:

                        Rf, Tf, Rf_prime, Rb_prime, Tb = calc_spectrum_full_exact(

                            wls_optim,

                            n_front_opt_T,

                            d_front,

                            n_sub_opt,

                            n_back_opt_T,

                            d_back,

                        )

                        denom = np.maximum(1.0 - Rf_prime * Rb_prime, 1e-12)

                        Ts_optim = (Tf * Tb) / denom

                    else:

                        Ts_optim, _ = calc_spectrum_front(

                            wls_optim, n_front_opt_T, d_front, n_sub_opt

                        )

                    rmse, _ = calc_rmse(Ts_optim, wls_optim, self.cfg["tgts"])

            result_data = EvalWorkerResult.success(
                vis={"l": wls_vis, "Ts": Ts_vis},
                optimization={"l": wls_optim, "Ts": Ts_optim},
                rmse=rmse,
                ep=self.cfg["ep"],
                eval_generation_id=self.cfg.get("eval_generation_id"),
                ep_back=self.cfg.get("ep_back") if "ep_back" in self.cfg else None,
                oblique_mode=oblique_mode,
                spectra_vis=spectra_vis if oblique_mode else None,
                spectra_optim=spectra_optim if oblique_mode else None,
                oblique_tgts=oblique_tgts if oblique_mode else None,
            )

            logging.info(

                f"[EVAL-WORKER] === EvalWorker complete in {(time.time()-_worker_start)*1000:.1f}ms ==="

            )

            self.signals.finished.emit(result_data.to_legacy_dict())

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError) as e:

            logging.error(f"[EVAL-WORKER] ERROR: {e}")

            logging.error(traceback.format_exc())

            self.signals.error.emit(traceback.format_exc())
