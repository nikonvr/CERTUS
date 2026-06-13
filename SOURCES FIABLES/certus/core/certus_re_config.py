from __future__ import annotations
import numpy as np
from dataclasses import dataclass, field
from typing import Any

RE_RESULT_LABEL_WITH_DRIFT = "Deltaln(lambda) trap + splines Re(H,L)"

# --- RE Worker DTOs and Physics Helpers ---

@dataclass
class REMseContext:
    _alpha_slot: Any
    _lref_arr: Any
    _re_env_on_wls: Any
    _re_state: Any
    ep0: Any
    is_H: Any
    is_L: Any
    lambda_ref: Any
    n_layers_count: Any
    n_layers_nominal: Any
    n_ref_nom_per_layer: Any
    n_sub_nominal: Any
    oblique_config_meta: Any
    re_env_s: Any
    var_idx: Any
    wls: Any
    yR_all_buf: np.ndarray = field(init=False)
    yT_all_buf: np.ndarray = field(init=False)
    dR_all_buf: np.ndarray = field(init=False)
    dT_all_buf: np.ndarray = field(init=False)
    grad_raw_buf: np.ndarray = field(init=False)

    def __post_init__(self):
        nloc = len(self.wls)
        nv = self.n_layers_count
        self.yR_all_buf = np.zeros(nloc, dtype=np.float64)
        self.yT_all_buf = np.zeros(nloc, dtype=np.float64)
        self.dR_all_buf = np.zeros((nloc, nv), dtype=np.float64)
        self.dT_all_buf = np.zeros((nloc, nv), dtype=np.float64)
        self.grad_raw_buf = np.zeros(nv, dtype=np.float64)


@dataclass
class REPhase2Context:
    _Phi_sub: Any
    _cb2_ref: Any
    _compute_qwot_rmse: Any
    _emit_re_prog: Any
    _emit_re_spectrum_live: Any
    _fd_1s: Any
    _fd_nw: Any
    _maxiter_p2b: Any
    _mse_grad_accumulate_ep: Any
    _n_joint_fd: Any
    _n_tab_sub: Any
    _nk: Any
    _p2_ki_slot: Any
    _p2_trf_log_tag: Any
    _p2fd_cu: Any
    _p2fd_lam: Any
    _p2fd_spl: Any
    _pct_p2a: Any
    _pct_p2b: Any
    _prefit_max: Any
    _re_state: Any
    _rmse_combined: Any
    _t_p2: Any
    _use_sub_c3: Any
    i0: Any
    i_cu: Any
    i_lam: Any
    n_layers_count: Any
    n_sp: Any
    pl: Any
    re_env_s: Any
    wls: Any
    wt_spectral: Any
    ep_p1: Any = None



@dataclass
class REWorkerRequest:
    """DTO boundary for RE worker payload."""

    cfg: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_legacy(cfg: dict[str, Any] | None) -> "REWorkerRequest":
        if not isinstance(cfg, dict):
            return REWorkerRequest(cfg={})
        return REWorkerRequest(cfg=dict(cfg))


@dataclass(frozen=True)
class REPhase1Result:
    """DTO boundary for one RE phase-1 candidate result."""

    label: str
    ep: np.ndarray
    a: float
    b: float
    f: float
    rmse: float
    rmse_qwot: float
    rmse_combined: float
    nfev: int
    success: bool

    def to_legacy_dict(self) -> dict[str, Any]:
        """Compatibility adapter for existing downstream consumers."""
        return {
            "label": self.label,
            "ep": np.asarray(self.ep, dtype=np.float64).flatten(),
            "a": float(self.a),
            "b": float(self.b),
            "f": float(self.f),
            "rmse": float(self.rmse),
            "rmse_qwot": float(self.rmse_qwot),
            "rmse_combined": float(self.rmse_combined),
            "nfev": int(self.nfev),
            "success": bool(self.success),
        }


@dataclass(frozen=True)
class REPhase2Result:
    """DTO boundary for one RE phase-2 candidate result."""

    label: str
    ep: np.ndarray
    a: float
    b: float
    f: float
    re_dh_knots: np.ndarray
    re_dl_knots: np.ndarray
    re_knots_nm: np.ndarray
    re_spline_lam_node2_nm: float
    rmse: float
    rmse_qwot: float
    rmse_combined: float
    nfev: int
    success: bool
    nfev_phase1: int
    nfev_phase2_prefit: int
    re_sub_cauchy_a0: float | None = None
    re_sub_cauchy_a1: float | None = None
    re_sub_cauchy_a2: float | None = None

    def to_legacy_dict(self) -> dict[str, Any]:
        """Compatibility adapter for existing downstream consumers."""
        return _re_phase23_result_to_legacy_dict(self)


@dataclass(frozen=True)
class REPhase3Result:
    """DTO boundary for one RE phase-3 refined result."""

    label: str
    ep: np.ndarray
    a: float
    b: float
    f: float
    re_dh_knots: np.ndarray
    re_dl_knots: np.ndarray
    re_knots_nm: np.ndarray
    re_spline_lam_node2_nm: float
    rmse: float
    rmse_qwot: float
    rmse_combined: float
    nfev: int
    success: bool
    nfev_phase1: int
    nfev_phase2_prefit: int
    re_sub_cauchy_a0: float | None = None
    re_sub_cauchy_a1: float | None = None
    re_sub_cauchy_a2: float | None = None

    def to_legacy_dict(self) -> dict[str, Any]:
        """Compatibility adapter for existing downstream consumers."""
        return _re_phase23_result_to_legacy_dict(self)


def _re_phase23_result_to_legacy_dict(result: Any) -> dict[str, Any]:
    """Shared legacy serializer for RE phase-2/phase-3 result DTOs."""
    out: dict[str, Any] = {
        "label": result.label,
        "ep": np.asarray(result.ep, dtype=np.float64).flatten(),
        "a": float(result.a),
        "b": float(result.b),
        "f": float(result.f),
        "re_dH_knots": np.asarray(result.re_dh_knots, dtype=np.float64).tolist(),
        "re_dL_knots": np.asarray(result.re_dl_knots, dtype=np.float64).tolist(),
        "re_knots_nm": np.asarray(result.re_knots_nm, dtype=np.float64).tolist(),
        "re_spline_lam_node2_nm": float(result.re_spline_lam_node2_nm),
        "rmse": float(result.rmse),
        "rmse_qwot": float(result.rmse_qwot),
        "rmse_combined": float(result.rmse_combined),
        "nfev": int(result.nfev),
        "success": bool(result.success),
        "nfev_phase1": int(result.nfev_phase1),
        "nfev_phase2_prefit": int(result.nfev_phase2_prefit),
    }
    if result.re_sub_cauchy_a0 is not None:
        out["re_sub_cauchy_a0"] = float(result.re_sub_cauchy_a0)
    if result.re_sub_cauchy_a1 is not None:
        out["re_sub_cauchy_a1"] = float(result.re_sub_cauchy_a1)
    if result.re_sub_cauchy_a2 is not None:
        out["re_sub_cauchy_a2"] = float(result.re_sub_cauchy_a2)
    return out


@dataclass(frozen=True)
class REPhase4Result:
    """DTO boundary for one RE phase-4 (beam/aperture) refined result."""

    label: str
    ep: np.ndarray
    a: float
    b: float
    f: float
    re_dh_knots: np.ndarray
    re_dl_knots: np.ndarray
    re_knots_nm: np.ndarray
    re_spline_lam_node2_nm: float
    rmse: float
    rmse_qwot: float
    rmse_combined: float
    nfev: int
    success: bool
    nfev_phase1: int
    nfev_phase2_prefit: int
    re_p4_aperture_deg: float
    re_p4_beam_ap_knots_nm: np.ndarray
    re_p4_beam_ap_knots_deg: np.ndarray
    re_sub_cauchy_a0: float | None = None
    re_sub_cauchy_a1: float | None = None
    re_sub_cauchy_a2: float | None = None

    @staticmethod
    def from_legacy_dict(payload: dict[str, Any]) -> "REPhase4Result":
        """Build a typed phase-4 result from existing legacy dict payload."""
        return REPhase4Result(
            label=str(payload.get("label", RE_RESULT_LABEL_WITH_DRIFT)),
            ep=np.asarray(payload.get("ep", []), dtype=np.float64).flatten(),
            a=float(payload.get("a", 0.0)),
            b=float(payload.get("b", 0.0)),
            f=float(payload.get("f", 0.0)),
            re_dh_knots=np.asarray(payload.get("re_dH_knots", []), dtype=np.float64).flatten(),
            re_dl_knots=np.asarray(payload.get("re_dL_knots", []), dtype=np.float64).flatten(),
            re_knots_nm=np.asarray(payload.get("re_knots_nm", []), dtype=np.float64).flatten(),
            re_spline_lam_node2_nm=float(payload.get("re_spline_lam_node2_nm", 0.0)),
            rmse=float(payload.get("rmse", 0.0)),
            rmse_qwot=float(payload.get("rmse_qwot", 0.0)),
            rmse_combined=float(payload.get("rmse_combined", payload.get("rmse", 0.0))),
            nfev=int(payload.get("nfev", 0)),
            success=bool(payload.get("success", False)),
            nfev_phase1=int(payload.get("nfev_phase1", 0)),
            nfev_phase2_prefit=int(payload.get("nfev_phase2_prefit", 0)),
            re_p4_aperture_deg=float(payload.get("re_p4_aperture_deg", 0.0)),
            re_p4_beam_ap_knots_nm=np.asarray(payload.get("re_p4_beam_ap_knots_nm", []), dtype=np.float64).flatten(),
            re_p4_beam_ap_knots_deg=np.asarray(payload.get("re_p4_beam_ap_knots_deg", []), dtype=np.float64).flatten(),
            re_sub_cauchy_a0=(
                float(payload["re_sub_cauchy_a0"]) if payload.get("re_sub_cauchy_a0") is not None else None
            ),
            re_sub_cauchy_a1=(
                float(payload["re_sub_cauchy_a1"]) if payload.get("re_sub_cauchy_a1") is not None else None
            ),
            re_sub_cauchy_a2=(
                float(payload["re_sub_cauchy_a2"]) if payload.get("re_sub_cauchy_a2") is not None else None
            ),
        )

    def to_legacy_dict(self) -> dict[str, Any]:
        """Compatibility adapter for existing downstream consumers."""
        out: dict[str, Any] = {
            "label": self.label,
            "ep": np.asarray(self.ep, dtype=np.float64).flatten(),
            "a": float(self.a),
            "b": float(self.b),
            "f": float(self.f),
            "re_dH_knots": np.asarray(self.re_dh_knots, dtype=np.float64).tolist(),
            "re_dL_knots": np.asarray(self.re_dl_knots, dtype=np.float64).tolist(),
            "re_knots_nm": np.asarray(self.re_knots_nm, dtype=np.float64).tolist(),
            "re_spline_lam_node2_nm": float(self.re_spline_lam_node2_nm),
            "rmse": float(self.rmse),
            "rmse_qwot": float(self.rmse_qwot),
            "rmse_combined": float(self.rmse_combined),
            "nfev": int(self.nfev),
            "success": bool(self.success),
            "nfev_phase1": int(self.nfev_phase1),
            "nfev_phase2_prefit": int(self.nfev_phase2_prefit),
            "re_p4_aperture_deg": float(self.re_p4_aperture_deg),
            "re_p4_beam_ap_knots_nm": np.asarray(self.re_p4_beam_ap_knots_nm, dtype=np.float64).tolist(),
            "re_p4_beam_ap_knots_deg": np.asarray(self.re_p4_beam_ap_knots_deg, dtype=np.float64).tolist(),
        }
        if self.re_sub_cauchy_a0 is not None:
            out["re_sub_cauchy_a0"] = float(self.re_sub_cauchy_a0)
        if self.re_sub_cauchy_a1 is not None:
            out["re_sub_cauchy_a1"] = float(self.re_sub_cauchy_a1)
        if self.re_sub_cauchy_a2 is not None:
            out["re_sub_cauchy_a2"] = float(self.re_sub_cauchy_a2)
        return out


def _result_dto_at(results: list[dict[str, Any]], idx: int) -> REPhase4Result | None:
    """Return typed DTO view for one result index."""
    if idx < 0 or idx >= len(results):
        return None
    return REPhase4Result.from_legacy_dict(results[idx])


def _top_result_dto(results: list[dict[str, Any]]) -> REPhase4Result | None:
    """Return the current top result as a typed DTO view."""
    return _result_dto_at(results, 0)


def _set_top_result_dto(results: list[dict[str, Any]], dto: REPhase4Result) -> None:
    """Set or initialize top result from typed DTO."""
    payload = dto.to_legacy_dict()
    if results:
        results[0] = payload
        return
    results.append(payload)


def _prepend_result_dto(results: list[dict[str, Any]], dto: REPhase4Result) -> None:
    """Insert one typed DTO result at front of ranking list."""
    results.insert(0, dto.to_legacy_dict())


def _replace_all_with_top_dto(results: list[dict[str, Any]], dto: REPhase4Result) -> None:
    """Replace ranking list with exactly one typed top result."""
    results[:] = [dto.to_legacy_dict()]


