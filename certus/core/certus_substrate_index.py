#!/usr/bin/env python3


# -*- coding: utf-8 -*-


"""


CERTUS Substrate Index - Substrate refractive index determination only


"""


import functools
from pathlib import Path
from typing import Any
import re
import sys


import logging


import numpy as np


import pandas as pd










from certus.core.certus_substrate_sellmeier import (
    SELLMEIER_N_ACCEPT_LO, SELLMEIER_N_ACCEPT_HI, SELLMEIER_MIN_L_SEP_UM, SELLMEIER_L_SEP_SOFT_WEIGHT,
    SELLMEIER_DEFAULT_LOG_L1L2, SELLMEIER_2POLES_PARAM_BOUNDS, SELLMEIER_2POLES_LAM_FRAC_MAX, SELLMEIER_3TERM_C_FRAC_MAX, SELLMEIER_SEED_POINTS, SELLMEIER_MULTISTART_TRIALS, SELLMEIER_WEIGHT_MODE, _SUBSTRATE_PRIOR_HINTS,
    _sellmeier_2poles_jac,
    _sellmeier_param_reparam_helpers,
    _resolve_sellmeier_settings,
    _fit_model_sellmeier3poles,
    _sellmeier_l_separation_gap_um,
    _sellmeier_prior_coeffs_for_column,
    _sellmeier_build_candidates,
    _sellmeier_multistart_candidates,
    _sellmeier_compact_polynomial_seed,
    _sellmeier_polish_helpers,
    sellmeier_2poles_const_eval,
    _sellmeier_2poles_param_bounds,
    _sellmeier_3term_standard_eval,
    _sellmeier_residual_factory,
    _sellmeier_seed_from_compact_poly,
    _sellmeier_midpoint_seed,
    _sellmeier_initial_context,
    _sellmeier_weights_from_nm
)

from certus.core.certus_core import (
    NUMERICAL_FAULT_EXCEPTIONS,
    setup_module_logging,
    __version__,
    SELLMEIER_COEFFS_BY_ID,
    SUBSTRATES,
    CANONICAL_SUBSTRATE_LABELS,
    canonicalize_substrate_label,
    substrate_sellmeier_coeffs,
)
from certus.core.certus_substrate_helpers import filter_bare_substrate_columns, is_bare_substrate_column, norm_header, expand_substrate_abbrevs, unglue_substrate_nu
from certus.core.certus_metrology import ValidationStatus
from certus.utils.certus_services import SubstrateIndexRequest, SubstrateIndexService




from certus.utils.certus_spectral_preproc import dynamic_savgol_blend




logger = setup_module_logging("CERTUS_SUBSTRATE_INDEX")


def _substrate_index_norm_header(raw) -> str:

    return norm_header(raw)


def _substrate_index_expand_substrate_abbrevs(s: str) -> str:
    return expand_substrate_abbrevs(s)


def _substrate_index_unglue_substrate_nu(s: str) -> str:
    return unglue_substrate_nu(s)


# Exclusions: stack / target (including lab abbreviations)


_RE_SUBSTRATE_INDEX_EXCLUDE = re.compile(
    r"\b("
    r"filt|flt|filter|"
    r"multilayer|ml|hl|hlstack|stack|stk|layering|pile|"
    r"tgt|target|obj|objective|"
    r"design|dsg|qwot|qw\b|"
    r"theor|theoretical|theo\b|optimis|opti\b|reconst|simu|simulation|"
    r"sample|spc\b|specimen|lot\b|batch|"
    r"final|mes\s*filt"
    r")\b",
    re.IGNORECASE,
)


# Inclusions: bare substrate or equivalent (phrases + acronyms + EN)


_RE_SUBSTRATE_INDEX_INCLUDE = re.compile(
    r"("
    # Usual spectroscopic tags for bare substrate
    r"\brnu(?:\b|[\s\-_]*\d+[fsp]?|\d+[fsp]?)|"
    r"\btnu(?:\b|[\s\-_]*\d+[fsp]?|\d+[fsp]?)|"
    # substrate / sub ... nu
    r"substrate\s+nu\b|nu\s+substrate\b|nu\s+sub\b|"
    r"substrate\s+bare|sub\s+bare|sub\s+only|substrate\s+only|only\s+substrate|only\s+substrate|only\s+sub\b|"
    r"\bsub\s+nu\b|\bsub\s+nus\b|"
    # Concatenated still present or already unfolded
    r"substratnu\b|subnu\b|sbstnu\b|substnu\b|"
    # English
    r"\bbare\s+sub(strate)?\b|\bbaresub\b|"
    r"\b(blank|empty|void)\s+sub(strate)?\b|\bsub(strate)?\s+blank\b|"
    r"\buncoated\b|\bno\s*coating\b|"
    r"\bpolished\s+substrate\b|"
    # Without deposit / layer
    r"without\s*(layer|deposit|coat|coating|stack|layering)|"
    r"without[\s\-_/]*dep\b|"
    # Witness / reference substrate
    r"\b(ref|raw|empty|void)\s+sub(strate|strat)?\b|\bsub(strate)?\s+ref\b|"
    r"\b(witness|blank|empty|unstacked)\b|"
    # Explicit bare materials in some exports (including French synonyms for parsing compatibility)
    r"\b(sapphire|saphir|al2o3)\b|"
    # Acronyms / short tags
    r"\bsnu\b|\bsbn\b|\bbsub\b|"
    # bare isolated (not in tnu/rnu: non-alnum delimited)
    r"(?:^|[^a-z0-9])nu(?:s|es|e)?(?:[^a-z0-9]|$)"
    r")",
    re.IGNORECASE,
)


def _is_bare_substrate_spectrum_column(name) -> bool:
    return is_bare_substrate_column(name)


def _filter_dataframe_bare_substrate_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str], list[str]]:
    return filter_bare_substrate_columns(df)


def _classify_substrate_index_columns(columns) -> dict[str, list]:
    """Classifies measurement columns by n(lambda) calculation type."""

    groups = {
        "t_2f": [],
        "r_2f": [],
        "r45s_1f": [],
        "r45p_1f": [],
        "r45s_2f": [],
        "r45p_2f": [],
    }

    for col in columns:
        s = _substrate_index_norm_header(col)

        if not s:
            continue

        has_45s = "45s" in s or "45 s" in s

        has_45p = "45p" in s or "45 p" in s

        has_rnu = "rnu" in s

        has_tnu = "tnu" in s

        is_sapphire = bool(re.search(r"\b(sapphire|saphir|al2o3)\b", s))

        starts_r = bool(re.match(r"^\s*r\b", s))

        starts_t = bool(re.match(r"^\s*t\b", s))

        is_2f = bool(re.search(r"\b2\s*f\b|\b2\s*faces?\b|\b2faces?\b", s) or "2f" in s)

        if has_rnu and has_45s:
            groups["r45s_2f" if is_2f else "r45s_1f"].append(col)

            continue

        if has_rnu and has_45p:
            groups["r45p_2f" if is_2f else "r45p_1f"].append(col)

            continue

        # Other "45" columns are out of scope for this module.

        if "45" in s:
            continue

        if has_tnu and is_2f:
            groups["t_2f"].append(col)

            continue

        if has_rnu and is_2f:
            groups["r_2f"].append(col)

            continue

        # Fallback lab export: "R ... sapphire ..." / "T ... sapphire ..."

        # (bare substrate columns without explicit nu/rnu/tnu tag).

        if is_sapphire and not (has_45s or has_45p):
            if starts_t:
                groups["t_2f"].append(col)

                continue

            if starts_r:
                groups["r_2f"].append(col)

    return groups


# Order of n(lambda) models calculated together (bare substrate).


SUBSTRATE_INDEX_MODELS: tuple[tuple[str, str], ...] = (
    ("polynomial", "Polynomial"),
    ("sellmeier3poles", "Sellmeier 3-poles"),
    ("spline_adaptive", "Spline n (B-spline LSQ)"),
)


# Compact polynomial terms (fixed order for serialization / logs).


_POLY_COEFF_KEYS: tuple[str, ...] = ("a0", "a1", "a2", "a3", "a4", "a5", "a6")


_POLY_CANDIDATE_TERMS: tuple[tuple[str, ...], ...] = (
    ("a0", "a1", "a2", "a5"),
    ("a0", "a1", "a2", "a3", "a5"),
    ("a0", "a1", "a2", "a3", "a4", "a5"),
    ("a0", "a1", "a2", "a3", "a5", "a6"),
    ("a0", "a1", "a2", "a3", "a4", "a5", "a6"),
)


def _fit_compact_polynomial_model(
    wl_fit_nm: np.ndarray,
    n_fit: np.ndarray,
    wl_eval_nm: np.ndarray,
    *,
    rmse_target_compact: float = 1.5e-3,
) -> tuple[list[str], np.ndarray, np.ndarray, float] | None:
    """Fit polynomial compact via IRLS and return best candidate on wl_eval_nm."""

    wl_fit_nm = np.asarray(wl_fit_nm, dtype=np.float64)

    n_fit = np.asarray(n_fit, dtype=np.float64)

    wl_fit_um = np.maximum(wl_fit_nm / 1000.0, 1.0e-9)

    wl_eval_um = np.maximum(np.asarray(wl_eval_nm, dtype=np.float64) / 1000.0, 1.0e-9)

    w_fit = 1.0 / np.maximum(wl_fit_nm, 1.0)

    feat_fit = IndexCore._poly_compact_feature_dict(wl_fit_um)

    feat_eval = IndexCore._poly_compact_feature_dict(wl_eval_um)

    def _fit_terms(term_names: tuple[str, ...]) -> tuple[np.ndarray, np.ndarray, float]:

        phi = np.column_stack([feat_fit[t] for t in term_names])

        w = np.asarray(w_fit, dtype=np.float64)

        p_loc = np.zeros(len(term_names), dtype=np.float64)

        for _ in range(4):
            A = phi * w[:, None]

            b = n_fit * w

            p_loc, *_ = np.linalg.lstsq(A, b, rcond=None)

            r = n_fit - (phi @ p_loc)

            mad = float(np.median(np.abs(r - np.median(r))))

            s = max(1.4826 * mad, 1.0e-6)

            w_rob = 1.0 / np.sqrt(1.0 + (r / (2.5 * s)) ** 2)

            w = np.asarray(w_fit, dtype=np.float64) * w_rob

        rmse_loc = float(np.sqrt(np.mean((n_fit - (phi @ p_loc)) ** 2)))

        phi_eval = np.column_stack([feat_eval[t] for t in term_names])

        return p_loc, (phi_eval @ p_loc), rmse_loc

    best_choice = None

    best_rmse = float("inf")

    for terms in _POLY_CANDIDATE_TERMS:
        p_try, n_try, rmse_try = _fit_terms(terms)

        if rmse_try < best_rmse:
            best_rmse = rmse_try

            best_choice = (list(terms), p_try, n_try, rmse_try)

        if rmse_try <= float(rmse_target_compact):
            best_choice = (list(terms), p_try, n_try, rmse_try)

            break

    if best_choice is None:
        return None

    active_terms, p, n_out, rmse_c = best_choice

    if not np.all(np.isfinite(n_out)):
        return None

    return active_terms, np.asarray(p, dtype=np.float64), np.asarray(n_out, dtype=np.float64), float(rmse_c)


def _substrate_fit_engine_log_label(model_kind: str) -> str:
    """Short label for fit_sellmeier / get_smoothed_and_fits logs (ASCII, no UI accent)."""

    mk = str(model_kind).strip().lower()

    if mk == "sellmeier3poles":
        return "Sellmeier 3-poles (A free)"

    if mk == "spline_adaptive":
        return "Spline n (B-spline LSQ)"

    return "Polynomial"


# RMSE > best × this factor -> law considered bad (grayed out in table + plot).


SUBSTRATE_INDEX_RMSE_BAD_RATIO = 1.10


# Spline n (substrate, B-spline LSQ) : maximum number of lambda sites (fit window edges included).


# Reduce = smoother spline / fewer degrees of freedom (less close to noise).


SPLINE_INDEX_MAX_KNOTS = 5


# Knots merge: accept if RMSE_new <= ratio × current RMSE (larger = more aggressive merges, fewer sites).


SPLINE_INDEX_MERGE_RMSE_RATIO_MAX = 1.22


# Reduction stop: minimum number of lambda sites (edges included); 2 = single cubic segment on [lambda_min, lambda_max].


SPLINE_INDEX_MIN_KNOT_SITES = 2


# Sellmeier 3-poles : **physical** domain for optimization (least squares + light L-BFGS-B).


# Tightened bounds to physically realistic ranges for common optical substrates:


#   A   [0, 4]    (constant term of n2, typically ~13 for oxides, 35 for semi-cond.)


#   Bi  [0, 12]   (Sellmeier residuals, always positive for transparent materials)


#   Li : UV pole < lambda_min(fit) captured by _sellmeier_2poles_param_bounds


#         IR pole free up to 30 m (covers ZnSe, Ge, etc.)


# |LiLj| minimal : avoids quasi-identical poles (badly conditioned matrix).












# Optimisation Sellmeier : physical bounds -> Li linear direct (no log reparameterization).


# log-reparam disabled sufficiently tightened bounds








































MODEL_SELECT_MONO_WEIGHT = 0.04


MODEL_SELECT_PRIOR_WEIGHT = 0.35


































# Duplicated function _sellmeier_seed_from_compact_poly removed.












def _model_selection_score(
    *,
    rmse_fit: float,
    n_fit: np.ndarray,
    wl_nm: np.ndarray,
    fit_mask: np.ndarray,
    fit_meta: dict,
    col_name: str | None,
) -> float:

    if not np.isfinite(rmse_fit):
        return float("inf")

    score = float(rmse_fit)

    n_line = np.asarray(n_fit, dtype=np.float64)
    m = np.asarray(fit_mask, dtype=bool) & np.isfinite(n_line) & np.isfinite(wl_nm)

    src = str((fit_meta or {}).get("source") or "")
    is_sellmeier = "sellmeier" in src
    is_spline = src.startswith("analytic-bspline-lsq")

    if int(np.count_nonzero(m)) >= 3 and not is_sellmeier:
        n_seg = n_line[m]
        _cnt, frac = IndexCore._monotonic_violation_stats(n_seg)
        score += float(MODEL_SELECT_MONO_WEIGHT) * float(max(0.0, frac))

    if is_spline:
        # Penalize overly flexible spline fits a bit more to avoid fitting noise.
        n_seg = n_line[m]
        if int(np.count_nonzero(m)) >= 5:
            rough = float(np.mean(np.abs(np.diff(n_seg)))) if n_seg.size >= 2 else 0.0
            score += 0.01 * rough

    if "sellmeier" in src:
        prior = _sellmeier_prior_coeffs_for_column(col_name)
        if prior is not None and int(np.count_nonzero(m)) >= 8:
            n_seg = n_line[m]
            wl_um = np.asarray(wl_nm[m], dtype=np.float64) / 1000.0
            n_prior = _sellmeier_3term_standard_eval(np.asarray(prior, dtype=np.float64), wl_um)
            prior_rmse = float(np.sqrt(np.mean((n_seg - n_prior) ** 2)))
            score += float(MODEL_SELECT_PRIOR_WEIGHT) * prior_rmse

    return float(score)


def _rmse_is_best_fit(v: float, best_v: float) -> bool:

    return bool(np.isfinite(v) and np.isfinite(best_v) and abs(v - best_v) <= 1.0e-9 * max(1.0, abs(best_v)))


def _rmse_is_bad_vs_best(v: float, best_v: float) -> bool:

    if not np.isfinite(v):
        return True

    if not np.isfinite(best_v):
        return False

    if _rmse_is_best_fit(v, best_v):
        return False

    return bool(v > float(best_v) * SUBSTRATE_INDEX_RMSE_BAD_RATIO)


def _substrate_index_models_ordered_by_rmse(rms_by_label: dict[str, float]) -> list[tuple[str, str]]:
    """For a substrate column: order of laws by increasing RMSE (non-finite last; ties -> SUBSTRATE_INDEX_MODELS order)."""

    items = list(SUBSTRATE_INDEX_MODELS)

    def sort_key(idx: int) -> tuple:

        _mk, mlabel = items[idx]

        v = float(rms_by_label.get(mlabel, float("nan")))

        if np.isfinite(v):
            return (0, v, idx)

        return (1, 0.0, idx)

    return [items[i] for i in sorted(range(len(items)), key=sort_key)]


_MODEL_LABEL_TO_INDEX: dict[str, int] = {ml: j for j, (_, ml) in enumerate(SUBSTRATE_INDEX_MODELS)}


_N_SUBSTRATE_MODELS = len(SUBSTRATE_INDEX_MODELS)


def _rms_triplet(rms_by_label: dict[str, float]) -> list[float]:

    return [float(rms_by_label.get(ml, float("nan"))) for _, ml in SUBSTRATE_INDEX_MODELS]


def _best_finite_rmse_from_triplet(mv: list[float]) -> float:

    finite = [v for v in mv if np.isfinite(v)]

    return min(finite) if finite else float("nan")


def _bad_model_labels(rms_by_label: dict[str, float]) -> set[str]:

    mv = _rms_triplet(rms_by_label)

    best = _best_finite_rmse_from_triplet(mv)

    return {SUBSTRATE_INDEX_MODELS[j][1] for j in range(_N_SUBSTRATE_MODELS) if _rmse_is_bad_vs_best(mv[j], best)}


def _rank_models_by_selection_score(
    score_m: dict[str, float],
    rms_m: dict[str, float],
    by_model: dict[str, np.ndarray],
    fit_mask: np.ndarray,
) -> tuple[str, float, float, list[tuple[str, float]]]:
    """Return best label and ranked scores using score, RMSE, and complexity tie-breakers."""

    fit_mask = np.asarray(fit_mask, dtype=bool)
    candidates: list[tuple[str, float, float, int]] = []

    for _mk, mlabel in SUBSTRATE_INDEX_MODELS:
        sc = float(score_m.get(mlabel, float("inf")))
        rm = float(rms_m.get(mlabel, float("inf")))
        arr = by_model.get(mlabel)
        if arr is None:
            complexity = 999
        else:
            complexity = int(np.count_nonzero(np.isfinite(np.asarray(arr, dtype=np.float64)[fit_mask])))
        candidates.append((mlabel, sc, rm, complexity))

    ranked = sorted(
        candidates,
        key=lambda t: (
            not np.isfinite(t[1]),
            t[1],
            not np.isfinite(t[2]),
            t[2],
            t[3],
            t[0],
        ),
    )

    ranked_scores = [(lab, float(sc)) for lab, sc, _rm, _cx in ranked]
    best_lab, best_score, best_rmse, _cx = ranked[0]
    return best_lab, float(best_score), float(best_rmse), ranked_scores


def _fit_summary_line(
    col_name: str,
    best_lab: str,
    best_score: float,
    best_rmse: float,
    best_value_at_idx: float,
) -> str:
    """Compact human-readable summary for logs and debug trace."""

    return (
        f"Fit column done: {str(col_name)} | best={best_lab} | score={float(best_score):.6g} | "
        f"rmse_fit={float(best_rmse) if np.isfinite(best_rmse) else float('nan'):.6g} | "
        f"n@4500={float(best_value_at_idx):.6f}"
    )




def _prepare_substrate_index_input(df: pd.DataFrame) -> tuple[pd.DataFrame | None, np.ndarray | None, dict[str, list[str]] | None, float | None, float | None, list[str]]:
    """Validate input dataframe and extract wavelength + substrate groups."""

    warnings_list: list[str] = []
    if df is None or df.empty or len(df.columns) < 2:
        return None, None, None, None, None, ["empty dataframe"]

    x = np.asarray(pd.to_numeric(df.iloc[:, 0], errors="coerce").values, dtype=np.float64)
    m_x = np.isfinite(x)
    if int(np.count_nonzero(m_x)) < 5:
        return None, None, None, None, None, ["invalid wavelength column"]
    if not np.all(m_x):
        df = df.loc[m_x].reset_index(drop=True)
        x = np.asarray(pd.to_numeric(df.iloc[:, 0], errors="coerce").values, dtype=np.float64)
        warnings_list.append("non-finite wavelengths removed")

    groups = _classify_substrate_index_columns(df.columns[1:])
    if not any(groups.values()):
        return None, None, None, None, None, warnings_list + ["no matching bare-substrate columns"]

    # Ensure every retained spectral column matches the wavelength length.
    mismatched: list[str] = []
    for col in df.columns[1:]:
        y = np.asarray(pd.to_numeric(df[col], errors="coerce").values, dtype=np.float64)
        if y.size != x.size:
            mismatched.append(str(col))

    if mismatched:
        warnings_list.append(
            "length-mismatch columns: " + ", ".join(mismatched[:10]) + ("..." if len(mismatched) > 10 else "")
        )

    wl_min_fit, wl_max_fit = None, None
    if x.size >= 2:
        wl_min_fit = float(np.nanmin(x))
        wl_max_fit = float(np.nanmax(x))

    return df, x, groups, wl_min_fit, wl_max_fit, warnings_list


def _build_substrate_manifest(
    service: SubstrateIndexService,
    *,
    wl_min_fit: float,
    wl_max_fit: float,
    sellmeier_log_l1l2: bool,
    warnings_list: list[str],
    status_val: ValidationStatus,
    source_path: str,
    rmse_row: dict[str, dict[str, float]],
) -> dict | None:
    """Best-effort manifest creation for downstream export."""

    try:
        req = SubstrateIndexRequest(
            config={
                "wl_min_fit": float(wl_min_fit),
                "wl_max_fit": float(wl_max_fit),
                "sellmeier_log_l1l2": bool(sellmeier_log_l1l2),
            },
            source_paths=[p for p in (str(source_path or "").strip(),) if p],
            seed=12345,
            app_id="CERTUS_SUBSTRATE_INDEX",
            app_version=__version__,
            warnings=list(warnings_list),
            status=status_val,
        )
        return service.fit(req).manifest.to_dict()
    except NUMERICAL_FAULT_EXCEPTIONS as exc:
        logger.warning("SUBSTRATE manifest generation failed: %s", exc)
        return None


def _substrate_manifest_service(rmse_row: dict[str, dict[str, float]], wl_min_fit: float, wl_max_fit: float) -> SubstrateIndexService:
    """Create the thin service wrapper used for manifest generation."""

    return SubstrateIndexService(
        runner=lambda _cfg: {
            "rmse_row": rmse_row,
            "fit_window_nm": [float(wl_min_fit), float(wl_max_fit)],
        }
    )


def _synthesize_validation_status(n_fit_meta: dict[str, dict[str, dict]]) -> tuple[str, list[str]]:
    """Build a lightweight validation summary from fit metadata."""

    warn_list: list[str] = []
    for _by_model in n_fit_meta.values():
        for _model_name, _meta in _by_model.items():
            _src = str((_meta or {}).get("source") or "")
            if _src.startswith("skipped-"):
                warn_list.append(f"{_model_name}: fit skipped ({_src})")

    return ("WARNING_UNCERTAINTY_NOT_COMPUTED" if warn_list else "OK"), warn_list


def _finalize_substrate_run(
    *,
    wl_min_fit: float,
    wl_max_fit: float,
    rmse_row: dict[str, dict[str, float]],
    source_path: str,
    status_val: ValidationStatus,
    warnings_list: list[str],
    sellmeier_log_l1l2: bool,
) -> dict | None:
    """Create manifest in one place with explicit run settings."""

    svc = _substrate_manifest_service(rmse_row, wl_min_fit, wl_max_fit)
    return _build_substrate_manifest(
        svc,
        wl_min_fit=float(wl_min_fit),
        wl_max_fit=float(wl_max_fit),
        sellmeier_log_l1l2=bool(sellmeier_log_l1l2),
        warnings_list=list(warnings_list),
        status_val=status_val,
        source_path=source_path,
        rmse_row=rmse_row,
    )


def _align_xy_lengths(x: np.ndarray, y: np.ndarray, *, label: str = "") -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray(x, dtype=np.float64).reshape(-1)
    y = np.asarray(y, dtype=np.float64)
    if y.ndim == 1:
        y = y.reshape(1, -1)
    if y.ndim != 2:
        raise ValueError(f"{label}: expected 1D/2D spectral data, got shape={y.shape}")
    n = min(int(x.size), int(y.shape[-1]))
    if n < 5:
        raise ValueError(f"{label}: not enough aligned points (x={x.size}, y={y.shape[-1]})")
    if x.size != n or y.shape[-1] != n:
        logger.warning(
            "Aligning lengths for %s: x=%d y=%d -> %d",
            label or "spectrum",
            int(x.size),
            int(y.shape[-1]),
            n,
        )
    return x[:n], y[..., :n]


def _linear_extrap_exterior(
    out: np.ndarray,
    x: np.ndarray,
    lo: float,
    hi: float,
    y_lo: float,
    slope_lo: float,
    y_hi: float,
    slope_hi: float,
) -> None:
    """Completes `out` outside [lo,hi] by tangents at the edges (x already filtered internally by the caller)."""

    m_l = x < lo

    m_r = x > hi

    if np.any(m_l):
        xl = x[m_l]

        out[m_l] = y_lo + slope_lo * (xl - lo)

    if np.any(m_r):
        xr = x[m_r]

        out[m_r] = y_hi + slope_hi * (xr - hi)


def _index_spline_ensure_strictly_increasing(knot_lam_um: np.ndarray, min_gap: float = 1e-9) -> np.ndarray:

    out = np.asarray(knot_lam_um, dtype=np.float64).copy()

    for i in range(1, len(out)):
        if out[i] <= out[i - 1]:
            out[i] = out[i - 1] + min_gap

    return out


def _index_spline_merge_closest_knot_pair(knot_lam_um: np.ndarray, n_knot: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Reduces a knot by merging the closest consecutive pair in lambda (like IR / Phase 2.3)."""

    n = len(knot_lam_um)

    if n <= 2:
        return knot_lam_um.copy(), n_knot.copy()

    gaps = np.diff(knot_lam_um)

    i_merge = int(np.argmin(gaps))

    lam_new = np.concatenate(
        [
            knot_lam_um[:i_merge],
            [(knot_lam_um[i_merge] + knot_lam_um[i_merge + 1]) * 0.5],
            knot_lam_um[i_merge + 2 :],
        ]
    )

    n_new = np.concatenate(
        [
            n_knot[:i_merge],
            [(n_knot[i_merge] + n_knot[i_merge + 1]) * 0.5],
            n_knot[i_merge + 2 :],
        ]
    )

    return lam_new, n_new


def _index_eval_bspline_linear_extrap(spl, lo_um: float, hi_um: float, x_um: np.ndarray) -> np.ndarray:
    """Evaluates a scipy B-spline on [lo, hi]; outside range: tangents at edges (affine extension)."""

    from scipy.interpolate import BSpline

    if not isinstance(spl, BSpline):
        raise TypeError("expected scipy.interpolate.BSpline")

    x = np.asarray(x_um, dtype=np.float64)

    lo = float(min(lo_um, hi_um))

    hi = float(max(lo_um, hi_um))

    d1 = spl.derivative()

    out = np.empty(x.shape, dtype=np.float64)

    m = (x >= lo) & (x <= hi)

    if np.any(m):
        out[m] = spl(x[m])

    _linear_extrap_exterior(
        out,
        x,
        lo,
        hi,
        float(spl(lo)),
        float(d1(lo)),
        float(spl(hi)),
        float(d1(hi)),
    )

    return out


def _index_pack_bspline_lsq(spl, lo_um: float, hi_um: float) -> np.ndarray:
    """Serializes least squares B-spline: [4, k, lambdamin_nm, lambdamax_nm, nt, t_nm..., nc, c...]."""

    t_um = np.asarray(spl.t, dtype=np.float64).ravel()

    c = np.asarray(spl.c, dtype=np.float64).ravel()

    k = int(spl.k)

    t_nm = t_um * 1000.0

    head = np.asarray(
        [
            4.0,
            float(k),
            float(min(lo_um, hi_um) * 1000.0),
            float(max(lo_um, hi_um) * 1000.0),
            float(t_nm.size),
        ],
        dtype=np.float64,
    )

    nc_hdr = np.asarray([float(c.size)], dtype=np.float64)

    return np.concatenate([head, t_nm, nc_hdr, c], dtype=np.float64)


def _substrate_index_geom_fit_mask(wl_nm: np.ndarray, wl_min_fit: float, wl_max_fit: float) -> np.ndarray:
    """lambda in geometric interval [min,max] of fit spins (for UI: out-of-band graying)."""

    wl = np.asarray(wl_nm, dtype=np.float64)

    lo = float(min(wl_min_fit, wl_max_fit))

    hi = float(max(wl_min_fit, wl_max_fit))

    return np.isfinite(wl) & (wl >= lo) & (wl <= hi)










class IndexCore:
    @staticmethod
    def apply_dynamic_filtering(
        x: np.ndarray,
        y: np.ndarray,
        base_window: int,
        poly: int,
        heavy_window: int = 0,
    ) -> np.ndarray:

        return dynamic_savgol_blend(x, y, base_window, poly, heavy_window)

    @staticmethod
    def _fit_mask(wl_nm: np.ndarray, wl_min_fit: float, wl_max_fit: float) -> np.ndarray:

        wl = np.asarray(wl_nm, dtype=np.float64)

        lo = float(min(wl_min_fit, wl_max_fit))

        hi = float(max(wl_min_fit, wl_max_fit))

        m = (wl >= lo) & (wl <= hi)

        if int(np.count_nonzero(m)) < 5:
            return np.ones_like(wl, dtype=bool)

        return m

    @staticmethod
    def _fallback_monotonic_raw(
        wl_nm: np.ndarray,
        n_vals: np.ndarray,
        wl_min_fit: float,
        wl_max_fit: float,
    ) -> np.ndarray:

        wl = np.asarray(wl_nm, dtype=np.float64)

        n_fb = np.asarray(n_vals, dtype=np.float64).copy()

        fit_range_mask = IndexCore._fit_mask(wl, wl_min_fit, wl_max_fit)

        if int(np.count_nonzero(fit_range_mask)) >= 3:
            idx = np.where(fit_range_mask)[0]

            n_fb[idx] = np.minimum.accumulate(n_fb[idx])

        return n_fb

    @staticmethod
    def _monotonic_violation_stats(n_fit_range: np.ndarray) -> tuple[int, float]:

        dn = np.diff(np.asarray(n_fit_range, dtype=np.float64))

        pos_count = int(np.count_nonzero(dn > 2.0e-4))

        pos_frac = float(pos_count) / float(max(dn.size, 1))

        return pos_count, pos_frac

    @staticmethod
    def _clipboard_law_line_from_source(source: str, requested_model_kind: str) -> str:
        """Short text for clipboard: law actually used after fit."""

        s = str(source or "")

        req = str(requested_model_kind or "").strip().lower()

        if s == "skipped-insufficient-points":
            return "Law: fit not executed (less than 8 valid points in fit window)."

        if s.startswith("analytic-polynomial"):
            return (
                "Law (adjustment): n(lambda) = a0 + a1/lambda + a2/lambda2 + a3/lambda3 + a4/lambda4 + a5lambda + a6√lambda "
                "(lambda in m for evaluation; wavelengths in nm)."
            )

        if s == "analytic-sellmeier-3poles-A":
            return (
                "Law (adjustment): n2 = A + B1lambda2/(lambda2-L12) + B2lambda2/(lambda2-L22) + B3lambda2/(lambda2-L32) "
                "(lambda and Li in m; lambda_nm/1000 = lambda_m)."
            )

        if s == "analytic-sellmeier-3term-standard":
            return (
                "Law (adjustment): Standard Sellmeier n2 = 1 + (Bilambda2/(lambda2-Ci)) "
                "(lambda in m, Ci in m2; compatible with literature/catalogs)."
            )

        if str(source or "").startswith("analytic-bspline-lsq"):
            return (
                "Law (adjustment): Piecewise polynomial regression (cubic B-spline, 1/lambda weighted "
                f"least squares in nm); at most {SPLINE_INDEX_MAX_KNOTS} lambda sites (m), adaptive knots then "
                "reduction by merge; outside fit window: affine extension (edge slope)."
            )

        return f"Law: non-analytical output or rejection (source={s!r}); model requested in UI={req!r}."

    @staticmethod
    def _clipboard_coeffs_line_from_source(
        source: str,
        coeffs: np.ndarray | list | None,
        *,
        meta: dict | None = None,
    ) -> str:

        if coeffs is None:
            return "Coefficients: (unavailable - raw curve / analytical fit rejection)"

        c = np.asarray(coeffs, dtype=np.float64).ravel()

        s = str(source or "")

        if s == "analytic-sellmeier-3poles-A" and c.size >= 7:
            base = (
                f"Coefficients: A={c[0]:.9g} ; B1={c[1]:.9g} ; L1={c[2]:.9g} m ; "
                f"B2={c[3]:.9g} ; L2={c[4]:.9g} m ; "
                f"B3={c[5]:.9g} ; L3={c[6]:.9g} m"
            )

            if meta is not None and bool(meta.get("sellmeier_optim_log_l1l2")):
                ln1 = float(np.log(max(float(c[2]), 1.0e-300)))

                ln2 = float(np.log(max(float(c[4]), 1.0e-300)))

                ln3 = float(np.log(max(float(c[6]), 1.0e-300)))

                base += (
                    f"\n  (optimization. ui=ln(Li), nat.) ln(L1)={ln1:.9g} ; ln(L2)={ln2:.9g} ; ln(L3)={ln3:.9g} "
                    f"(equivalent log10: log10(L1)={ln1 / np.log(10.0):.9g} ; log10(L2)={ln2 / np.log(10.0):.9g} ; log10(L3)={ln3 / np.log(10.0):.9g})"
                )

            return base

        if s == "analytic-sellmeier-3term-standard" and c.size >= 6:
            return (
                f"Coefficients standard: B1={c[0]:.9g} ; C1={c[1]:.9g} m2 ; "
                f"B2={c[2]:.9g} ; C2={c[3]:.9g} m2 ; "
                f"B3={c[4]:.9g} ; C3={c[5]:.9g} m2"
            )

        if s.startswith("analytic-polynomial") and c.size >= 1:
            c7 = np.zeros(7, dtype=np.float64)

            c7[: min(7, c.size)] = c[: min(7, c.size)]

            parts = [f"{_POLY_COEFF_KEYS[i]}={c7[i]:.9g}" for i in range(7)]

            return "Coefficients: " + " ; ".join(parts)

        if str(source or "").startswith("analytic-bspline-lsq") and c.size >= 6:
            kdeg = int(round(float(c[1])))

            lo_nm, hi_nm = float(c[2]), float(c[3])

            nt = int(round(float(c[4])))

            min_nt = 2 * (kdeg + 1)  # minimal valid knot vector for a B-spline of degree k

            if nt < min_nt or kdeg < 0 or c.size < 5 + nt + 1:
                return f"Coefficients (B-spline LSQ, raw): {np.array2string(c, precision=9, separator=', ')}"

            nc_hdr = int(round(float(c[5 + nt])))

            if nc_hdr < 1 or c.size < 6 + nt + nc_hdr:
                return f"Coefficients (B-spline LSQ, raw): {np.array2string(c, precision=9, separator=', ')}"

            t_nm = c[5 : 5 + nt]

            coef_b = c[6 + nt : 6 + nt + nc_hdr]

            tk = np.array2string(t_nm, precision=4, separator=", ", max_line_width=220)

            cc = np.array2string(coef_b, precision=9, separator=", ", max_line_width=220)

            return (
                "B-spline coefficients (LSQ, scipy):\n"
                f"   degree k = {kdeg}\n"
                f"   fit window lambda (nm): [{lo_nm:.4f}, {hi_nm:.4f}]\n"
                f"   knot vector t (nm), n_t = {nt}: [{tk}]\n"
                f"   B-spline coefficients c, n_c = {nc_hdr}: [{cc}]"
            )

        return f"Coefficients (raw): {np.array2string(c, precision=9, separator=', ')}"

    @staticmethod
    def _poly_compact_feature_dict(wl_um: np.ndarray) -> dict[str, np.ndarray]:

        u = np.asarray(wl_um, dtype=np.float64)

        inv = 1.0 / np.maximum(u, 1.0e-9)

        return {
            "a0": np.ones_like(u, dtype=np.float64),
            "a1": inv,
            "a2": inv**2,
            "a3": inv**3,
            "a4": inv**4,
            "a5": u,
            "a6": np.sqrt(u),
        }



    @staticmethod
    def suggest_trimmed_fit_range(
        wl_nm: np.ndarray,
        residuals: np.ndarray,
        lo_init: float,
        hi_init: float,
        *,
        threshold: float = 0.04,
        edge_fraction: float = 0.15,
    ) -> tuple[float, float, bool]:
        """Detect noisy spectral edges from residuals and trim fit range.

        Returns (lo_nm, hi_nm, changed). If residuals near the high edge exceed
        `threshold`, shrinks hi_nm to exclude that noisy tail. Same for lo_nm.

        Args:
            wl_nm: wavelength array (nm), sorted ascending.
            residuals: per-wavelength residual array (same length).
            lo_init: initial low bound (nm).
            hi_init: initial high bound (nm).
            threshold: residual level above which an edge is considered noisy.
            edge_fraction: fraction of the range to inspect at each edge.
        """
        wl = np.asarray(wl_nm, dtype=np.float64)
        res = np.asarray(residuals, dtype=np.float64)

        lo = float(lo_init)
        hi = float(hi_init)
        span = hi - lo
        edge_band = span * edge_fraction

        # Inspect high edge
        m_hi = (wl >= (hi - edge_band)) & (wl <= hi)
        if np.any(m_hi) and np.nanmedian(res[m_hi]) > threshold:
            # Find the first wavelength from the left where residuals exceed threshold
            m_all = (wl >= lo) & (wl <= hi)
            wl_range = wl[m_all]
            res_range = res[m_all]
            # Walk from high end backwards to find clean edge
            for i in range(len(wl_range) - 1, 0, -1):
                if res_range[i] > threshold:
                    hi = float(wl_range[i - 1]) if i > 0 else float(wl_range[0])
                else:
                    break

        # Inspect low edge
        m_lo = (wl >= lo) & (wl <= (lo + edge_band))
        if np.any(m_lo) and np.nanmedian(res[m_lo]) > threshold:
            m_all = (wl >= lo) & (wl <= hi)
            wl_range = wl[m_all]
            res_range = res[m_all]
            for i in range(len(wl_range)):
                if res_range[i] > threshold:
                    lo = float(wl_range[i + 1]) if i < len(wl_range) - 1 else float(wl_range[-1])
                else:
                    break

        changed = (abs(lo - float(lo_init)) > 1.0) or (abs(hi - float(hi_init)) > 1.0)
        return lo, hi, changed

    @staticmethod
    def fit_sellmeier(
        n_data: np.ndarray,
        wl_nm: np.ndarray,
        wl_min_fit: float,
        wl_max_fit: float,
        valid_mask: np.ndarray | None = None,
        progress_cb=None,
        model_kind: str = "polynomial",
        *,
        return_meta: bool = False,
        sellmeier_timeout_s: float | None = None,
        sellmeier_de_maxiter: int = 300,
        sellmeier_de_popsize: int = 12,
        sellmeier_ls_max_nfev: int = 3000,
        sellmeier_log_l1l2: bool | None = None,
    ) -> np.ndarray | tuple[np.ndarray, dict]:

        wl = np.asarray(wl_nm, dtype=np.float64)

        n_vals = np.asarray(n_data, dtype=np.float64)

        mask = IndexCore._fit_mask(wl, wl_min_fit, wl_max_fit)

        if valid_mask is not None:
            mask &= np.asarray(valid_mask, dtype=bool)

        mask &= np.isfinite(wl) & np.isfinite(n_vals)

        model_kind = str(model_kind).strip().lower()

        model_label = _substrate_fit_engine_log_label(model_kind)

        wl_eval_min = float(np.nanmin(wl)) if wl.size else float("nan")

        wl_eval_max = float(np.nanmax(wl)) if wl.size else float("nan")

        logger.info(
            "event=index_fit_start model=%s wl_fit_lo_nm=%.1f wl_fit_hi_nm=%.1f points=%d/%d wl_eval_lo_nm=%.1f wl_eval_hi_nm=%.1f",
            model_label,
            float(min(wl_min_fit, wl_max_fit)),
            float(max(wl_min_fit, wl_max_fit)),
            int(np.count_nonzero(mask)),
            int(wl.size),
            wl_eval_min,
            wl_eval_max,
        )

        logger.info(
            "event=index_input_stats model=%s n_fit_min=%.6f n_fit_max=%.6f wl_min_nm=%.1f wl_max_nm=%.1f",
            model_label,
            float(np.nanmin(n_vals[mask])) if np.any(mask) else float("nan"),
            float(np.nanmax(n_vals[mask])) if np.any(mask) else float("nan"),
            float(np.nanmin(wl[mask])) if np.any(mask) else float("nan"),
            float(np.nanmax(wl[mask])) if np.any(mask) else float("nan"),
        )

        if model_kind == "sellmeier3poles":
            logger.info("event=index_fit_mode model=sellmeier3poles equation=sellmeier_3poles")

        elif model_kind == "spline_adaptive":
            logger.info("event=index_fit_mode model=spline_adaptive max_knots=%d basis=cubic_bspline", SPLINE_INDEX_MAX_KNOTS)

        else:
            logger.info("event=index_fit_mode model=polynomial equation=compact_7_term")

        if model_kind != "spline_adaptive":
            logger.info("event=index_units model=%s wavelength_unit=nm eval_unit=m", model_label)

        else:
            logger.info("event=index_units model=%s wavelength_unit=nm eval_extension=affine_edge_slope", model_label)

        def _fit_meta(
            source: str,
            coeffs: np.ndarray | None,
            requested_model_kind: str,
            **extra,
        ) -> dict:

            coeffs_list = None

            if coeffs is not None:
                coeffs_list = np.asarray(coeffs, dtype=np.float64).ravel().tolist()

            d = {
                "source": str(source),
                "coeffs": coeffs_list,
                "requested_model_kind": str(requested_model_kind),
            }

            for k, v in extra.items():
                if v is not None:
                    d[k] = v

            return d

        def _ret(n_out: np.ndarray, source: str, coeffs: np.ndarray | None, **meta_extra):

            out = np.asarray(n_out, dtype=np.float64)

            if return_meta:
                return out, _fit_meta(source, coeffs, model_kind, **meta_extra)

            return out

        def _ret_fallback_raw(source: str):

            n_fb = IndexCore._fallback_monotonic_raw(wl, n_vals, wl_min_fit, wl_max_fit)

            return _ret(n_fb, source, None)

        if int(np.count_nonzero(mask)) < 8:
            logger.warning("%s fit skipped: not enough valid points (%d).", model_label, int(np.count_nonzero(mask)))

            return _ret(n_vals.copy(), "skipped-insufficient-points", None)

        wl_fit_um = wl[mask] / 1000.0

        wl_fit_nm = wl[mask]

        n_fit = n_vals[mask]

        w_fit = 1.0 / np.maximum(wl_fit_nm, 1.0)

        if model_kind == "sellmeier3poles":
            res_n, res_src, res_coeffs, res_extra = _fit_model_sellmeier3poles(
                n_vals=n_vals, wl=wl, mask=mask, n_fit=n_fit, wl_fit_nm=wl_fit_nm, wl_fit_um=wl_fit_um,
                progress_cb=progress_cb, sellmeier_timeout_s=sellmeier_timeout_s,
                sellmeier_de_maxiter=sellmeier_de_maxiter, sellmeier_de_popsize=sellmeier_de_popsize,
                sellmeier_ls_max_nfev=sellmeier_ls_max_nfev, sellmeier_log_l1l2=sellmeier_log_l1l2,
            )
        elif model_kind == "spline_adaptive":
            res_n, res_src, res_coeffs, res_extra = IndexCore._fit_model_spline_adaptive(
                wl=wl, mask=mask, n_fit=n_fit, wl_fit_nm=wl_fit_nm, w_fit=w_fit, progress_cb=progress_cb
            )
        else:
            res_n, res_src, res_coeffs, res_extra = IndexCore._fit_model_polynomial(
                wl=wl, wl_min_fit=wl_min_fit, wl_max_fit=wl_max_fit, mask=mask, n_fit=n_fit, wl_fit_nm=wl_fit_nm, w_fit=w_fit
            )

        if res_n is None:
            return _ret_fallback_raw(res_src)
        return _ret(res_n, res_src, res_coeffs, **res_extra)



    @staticmethod
    def _fit_model_spline_adaptive(
        wl: np.ndarray,
        mask: np.ndarray,
        n_fit: np.ndarray,
        wl_fit_nm: np.ndarray,
        w_fit: np.ndarray,
        progress_cb,
    ) -> tuple[np.ndarray | None, str, np.ndarray | None, dict]:
        from scipy.interpolate import make_lsq_spline

        from scipy.optimize import minimize

        # Cubic B-spline = piecewise polynomials; weighted least squares on the fit grid.

        # Grid of \u03bb sites (fixed edges) + interior knot optimization + merge if RMSE OK.

        RMSE_RATIO_MAX = float(SPLINE_INDEX_MERGE_RMSE_RATIO_MAX)

        MIN_KNOT_DIST_UM = 0.05

        N_BOUND_LO, N_BOUND_HI = 1.35, 5.0

        BSPLINE_K = 3

        xf = np.asarray(wl_fit_nm, dtype=np.float64).copy()

        yf = np.asarray(n_fit, dtype=np.float64).copy()

        wf = np.asarray(w_fit, dtype=np.float64).copy()

        o = np.argsort(xf)

        xf, yf, wf = xf[o], yf[o], wf[o]

        if np.any(np.diff(xf) <= 0.0):
            ux, inv = np.unique(xf, return_inverse=True)

            sum_w = np.bincount(inv, weights=wf)

            sum_yw = np.bincount(inv, weights=yf * wf)

            xf = ux

            yf = sum_yw / np.maximum(sum_w, 1.0e-30)

            wf = sum_w

        npts = int(xf.size)

        wl_fit_um = xf / 1000.0

        lo_um = float(wl_fit_um[0])

        hi_um = float(wl_fit_um[-1])

        span_um = max(hi_um - lo_um, 1.0e-9)

        max_knots_by_gap = max(2, int(span_um / MIN_KNOT_DIST_UM) + 1)

        k_min_stop = min(int(SPLINE_INDEX_MIN_KNOT_SITES), int(max_knots_by_gap))

        k_min_stop = max(2, k_min_stop)

        num_knots = min(
            SPLINE_INDEX_MAX_KNOTS,
            max_knots_by_gap,
            max(3, npts // 24),
        )

        num_knots = max(num_knots, min(3, max_knots_by_gap))

        num_knots = min(num_knots, max_knots_by_gap)

        num_knots = min(num_knots, SPLINE_INDEX_MAX_KNOTS)

        try:
            if callable(progress_cb):
                progress_cb(1, 2)

            def _fit_bspline_lsq_wls(interior_um: np.ndarray):
                """Interior knots strictly in ]lo,hi[; cubic clamped at edges."""

                inter = np.asarray(interior_um, dtype=np.float64).ravel()

                inter = inter[(inter > lo_um) & (inter < hi_um)]

                inter = np.sort(inter)

                margin = max(0.5 * MIN_KNOT_DIST_UM, 1.0e-9)

                if inter.size > 0:
                    inter = np.clip(inter, lo_um + margin, hi_um - margin)

                    inter = _index_spline_ensure_strictly_increasing(
                        inter, min_gap=max(1e-9, 0.25 * MIN_KNOT_DIST_UM)
                    )

                    inter = inter[(inter > lo_um) & (inter < hi_um)]

                t_full = np.concatenate(
                    ([lo_um] * (BSPLINE_K + 1), inter, [hi_um] * (BSPLINE_K + 1)),
                    dtype=np.float64,
                )

                try:
                    spl = make_lsq_spline(wl_fit_um, yf, t_full, k=BSPLINE_K, w=wf, check_finite=True)

                except (ValueError, TypeError):
                    return None, float("nan")

                pred = spl(wl_fit_um)

                rmse_u = float(np.sqrt(np.mean((pred - yf) ** 2)))

                return spl, rmse_u

            def _optimize_bspline_interior_knots(
                knot_lam_um: np.ndarray,
                rmse_cur: float,
            ) -> tuple[np.ndarray, float]:
                """With fixed K sites, optimizes interior \u03bb to minimize B-spline LSQ RMSE."""

                k_loc = int(knot_lam_um.size)

                if k_loc <= 2:
                    return knot_lam_um.copy(), rmse_cur

                margin_i = max(0.5 * MIN_KNOT_DIST_UM, 1.0e-9)

                lo_b = lo_um + margin_i

                hi_b = hi_um - margin_i

                if hi_b <= lo_b + 1.0e-12:
                    return knot_lam_um.copy(), rmse_cur

                n_int = k_loc - 2

                x0 = np.clip(knot_lam_um[1:-1].copy(), lo_b, hi_b)

                def _obj(tv: np.ndarray) -> float:

                    ts = np.sort(np.clip(np.asarray(tv, dtype=np.float64), lo_b, hi_b))

                    knot_t = np.empty(k_loc, dtype=np.float64)

                    knot_t[0] = lo_um

                    knot_t[-1] = hi_um

                    knot_t[1:-1] = ts

                    knot_t = _index_spline_ensure_strictly_increasing(
                        knot_t, min_gap=max(1e-9, 0.1 * MIN_KNOT_DIST_UM)
                    )

                    knot_t[0] = lo_um

                    knot_t[-1] = hi_um

                    if np.any(np.diff(knot_t) < 0.5 * MIN_KNOT_DIST_UM):
                        return 1e6

                    _spl, rm = _fit_bspline_lsq_wls(knot_t[1:-1])

                    if _spl is None or not np.isfinite(rm):
                        return 1e6

                    return float(rm)

                try:
                    res = minimize(
                        _obj,
                        x0,
                        method="L-BFGS-B",
                        bounds=[(lo_b, hi_b)] * n_int,
                        options={"maxiter": 120, "ftol": 1e-14},
                    )

                    if np.isfinite(res.fun):
                        tv = np.sort(np.clip(np.asarray(res.x, dtype=np.float64), lo_b, hi_b))

                        knot_t = np.empty(k_loc, dtype=np.float64)

                        knot_t[0] = lo_um

                        knot_t[-1] = hi_um

                        knot_t[1:-1] = tv

                        knot_t = _index_spline_ensure_strictly_increasing(
                            knot_t, min_gap=max(1e-9, 0.1 * MIN_KNOT_DIST_UM)
                        )

                        knot_t[0] = lo_um

                        knot_t[-1] = hi_um

                        if not np.any(np.diff(knot_t) < 0.5 * MIN_KNOT_DIST_UM):
                            _spl2, rm2 = _fit_bspline_lsq_wls(knot_t[1:-1])

                            if _spl2 is not None and np.isfinite(rm2) and rm2 < rmse_cur - 1.0e-15:
                                logger.info(
                                    "B-spline spline: knot optimization \u2192 rmse_fit=%.6g (was %.6g).",
                                    rm2,
                                    rmse_cur,
                                )

                                return knot_t, rm2

                except (
                    ValueError,
                    TypeError,
                    RuntimeError,
                    AttributeError,
                    KeyError,
                    IndexError,
                    FileNotFoundError,
                ):
                    pass

                return knot_lam_um.copy(), rmse_cur

            knot_lam = np.linspace(lo_um, hi_um, num_knots, dtype=np.float64)

            knot_lam = _index_spline_ensure_strictly_increasing(knot_lam, min_gap=max(1e-9, 0.1 * MIN_KNOT_DIST_UM))

            knot_lam[0] = lo_um

            knot_lam[-1] = hi_um

            spl_best, best_rmse = _fit_bspline_lsq_wls(knot_lam[1:-1])

            if spl_best is None or not np.isfinite(best_rmse):
                raise ValueError("B-spline LSQ: echec fit initial")

            best_knot_lam = knot_lam.copy()

            best_n_knot = np.clip(np.interp(best_knot_lam, wl_fit_um, yf), N_BOUND_LO, N_BOUND_HI)

            best_knot_lam, best_rmse = _optimize_bspline_interior_knots(best_knot_lam, best_rmse)

            best_n_knot = np.clip(np.interp(best_knot_lam, wl_fit_um, yf), N_BOUND_LO, N_BOUND_HI)

            baseline_mse = float(best_rmse**2)

            while len(best_knot_lam) > k_min_stop:
                lam_try, n_try = _index_spline_merge_closest_knot_pair(best_knot_lam, best_n_knot)

                lam_try = _index_spline_ensure_strictly_increasing(lam_try, min_gap=1e-9)

                lam_try[0] = lo_um

                lam_try[-1] = hi_um

                if np.any(np.diff(lam_try) < 0.5 * MIN_KNOT_DIST_UM):
                    logger.info(
                        "B-spline spline: reduction stop (knot spacing < %.3f m).",
                        0.5 * MIN_KNOT_DIST_UM,
                    )

                    break

                spl_new, rmse_new = _fit_bspline_lsq_wls(lam_try[1:-1])

                if spl_new is None or not np.isfinite(rmse_new):
                    logger.info("B-spline spline: merge impossible (LSQ).")

                    break

                if (rmse_new**2) > (RMSE_RATIO_MAX**2) * baseline_mse:
                    logger.info(
                        "B-spline spline: merge rejected (RMSE %.6g, ref %.6g, max ratio %.2f). Keeping K=%d.",
                        rmse_new,
                        float(np.sqrt(baseline_mse)),
                        RMSE_RATIO_MAX,
                        len(best_knot_lam),
                    )

                    break

                best_knot_lam = lam_try

                best_n_knot = n_try

                best_rmse = rmse_new

                baseline_mse = float(best_rmse**2)

                logger.info(
                    "B-spline spline: reduction accepted \u2192 K=%d sites | rmse_fit=%.6g.",
                    len(best_knot_lam),
                    best_rmse,
                )

            best_knot_lam, best_rmse = _optimize_bspline_interior_knots(best_knot_lam, best_rmse)

            best_n_knot = np.clip(np.interp(best_knot_lam, wl_fit_um, yf), N_BOUND_LO, N_BOUND_HI)

            spl_final, best_rmse = _fit_bspline_lsq_wls(best_knot_lam[1:-1])

            if spl_final is None or not np.isfinite(best_rmse):
                raise ValueError("B-spline LSQ: echec fit final")

            wl_full_um = np.asarray(wl, dtype=np.float64) / 1000.0

            n_out_sp = _index_eval_bspline_linear_extrap(spl_final, lo_um, hi_um, wl_full_um)

            if callable(progress_cb):
                progress_cb(2, 2)

            if not np.all(np.isfinite(n_out_sp)):
                raise ValueError("non-finite B-spline output")

            n_coef = int(spl_final.c.size)

            k_sites = int(best_knot_lam.size)

            packed = _index_pack_bspline_lsq(spl_final, lo_um, hi_um)

            logger.info(
                "Spline n (B-spline LSQ): n_coef=%d | K_sites=%d | rmse_fit=%.6g | n_pts_fit=%d | lambda_fit=[%.4f,%.4f] m",
                n_coef,
                k_sites,
                best_rmse,
                npts,
                lo_um,
                hi_um,
            )

            n_eval = np.asarray(n_out_sp[mask], dtype=np.float64)

            if np.any((n_eval < 1.35) | (n_eval > 5.0)):
                logger.warning(
                    "Spline fit rejected: out-of-bounds n(lambda) in fit range -> fallback monotonic raw."
                )

                return None, "fallback-raw-spline-bounds", None, {}

            wrmse = float(np.sqrt(np.mean(((n_eval - n_fit) * w_fit) ** 2)))

            logger.info(
                "Spline fit stats: wrmse=%.6g | rmse=%.6g | n_range_fit=[%.6f, %.6f] | n@edges=[%.6f, %.6f]",
                wrmse,
                float(best_rmse),
                float(np.min(n_eval)),
                float(np.max(n_eval)),
                float(n_eval[0]),
                float(n_eval[-1]),
            )

            return n_out_sp, f"analytic-bspline-lsq-nc{n_coef}", packed, {}

        except (ValueError, RuntimeError, ArithmeticError) as ex:
            logger.warning("Spline fit failed: %s -> fallback to Polynomial.", str(ex))

        except NUMERICAL_FAULT_EXCEPTIONS :
            logger.exception("Spline fit unexpected failure -> fallback to Polynomial.")

    @staticmethod
    def _fit_model_polynomial(
        wl: np.ndarray,
        wl_min_fit: float,
        wl_max_fit: float,
        mask: np.ndarray,
        n_fit: np.ndarray,
        wl_fit_nm: np.ndarray,
        w_fit: np.ndarray,
    ) -> tuple[np.ndarray | None, str, np.ndarray | None, dict]:
        # Polynomial fit (requested): deterministic weighted IRLS + physical checks.

        rmse_target_compact = 1.5e-3

        fitted = _fit_compact_polynomial_model(
            wl_fit_nm,
            n_fit,
            wl,
            rmse_target_compact=rmse_target_compact,
        )

        if fitted is None:
            logger.warning("Polynomial fit failed: no candidate solution -> fallback monotonic raw.")

            return None, "fallback-raw-poly-no-candidate", None, {}

        active_terms, p, n_out, rmse_compact = fitted

        logger.info(
            "Polynomial model selection: terms=%s | n_vars=%d | rmse_fit=%.6g | target<=%.6g",
            ",".join(active_terms),
            int(len(active_terms)),
            float(rmse_compact),
            float(rmse_target_compact),
        )

        if not np.all(np.isfinite(n_out)):
            logger.warning("Polynomial output invalid: non-finite values, fallback monotonic raw.")

            return None, "fallback-raw-poly-nonfinite", None, {}

        fit_range_mask = IndexCore._fit_mask(wl, wl_min_fit, wl_max_fit)

        if int(np.count_nonzero(fit_range_mask)) >= 3:
            idx = np.where(fit_range_mask)[0]

            n_sub = np.asarray(n_out[idx], dtype=np.float64)

            pos_count, pos_frac = IndexCore._monotonic_violation_stats(n_sub)

            if (pos_count > 8) and (pos_frac > 0.03):
                logger.warning(
                    "Polynomial fit rejected: monotonic tolerance exceeded (count=%d frac=%.3f) -> fallback monotonic raw.",
                    int(pos_count),
                    float(pos_frac),
                )

                return None, "fallback-raw-poly-nonmonotonic", None, {}

        n_eval = np.asarray(n_out[mask], dtype=np.float64)

        if np.any((n_eval < 1.35) | (n_eval > 5.0)):
            logger.warning("Polynomial fit rejected: out-of-bounds n(lambda) in fit range -> fallback monotonic raw.")

            return None, "fallback-raw-poly-bounds", None, {}

        rmse_unweighted = float(np.sqrt(np.mean((n_eval - n_fit) ** 2)))

        wrmse = float(np.sqrt(np.mean(((n_eval - n_fit) * w_fit) ** 2)))

        if rmse_unweighted > 0.06:
            logger.warning(
                "Polynomial fit rejected: rmse %.6g > acceptance %.6g (wrmse=%.6g) -> fallback monotonic raw.",
                float(rmse_unweighted),
                float(0.06),
                float(wrmse),
            )

            return None, "fallback-raw-poly-rmse", None, {}

        r_fit = n_eval - n_fit

        i_worst = int(np.argmax(np.abs(r_fit)))

        logger.info(
            "Polynomial fit stats: wrmse=%.6g | rmse=%.6g | n_range_fit=[%.6f, %.6f] | n@edges=[%.6f, %.6f]",
            wrmse,
            rmse_unweighted,
            float(np.min(n_eval)),
            float(np.max(n_eval)),
            float(n_eval[0]),
            float(n_eval[-1]),
        )

        logger.info(
            "Residual stats: rmse=%.6g | mae=%.6g | maxabs=%.6g @ lambda=%.1fnm (pred=%.6f raw=%.6f)",
            rmse_unweighted,
            float(np.mean(np.abs(r_fit))),
            float(np.max(np.abs(r_fit))),
            float(wl_fit_nm[i_worst]),
            float(n_eval[i_worst]),
            float(n_fit[i_worst]),
        )

        coeff_map = {k: v for k, v in zip(active_terms, p)}

        p_full = np.asarray(
            [float(coeff_map.get(k, 0.0)) for k in _POLY_COEFF_KEYS],
            dtype=np.float64,
        )

        logger.info(
            "Polynomial coefficients accepted: a0=%.9g | a1=%.9g | a2=%.9g | a3=%.9g | a4=%.9g | a5=%.9g | a6=%.9g",
            *p_full.tolist(),
        )

        return n_out, f"analytic-polynomial-{len(active_terms)}", p_full, {}

    @staticmethod
    def get_smoothed_and_fits(
        n_raw: np.ndarray,
        wl_nm: np.ndarray,
        wl_min_fit: float,
        wl_max_fit: float,
        model_kind: str = "polynomial",
        progress_cb=None,
        *,
        log_preprocess: bool = True,
        sellmeier_timeout_s: float | None = None,
        sellmeier_de_maxiter: int = 300,
        sellmeier_ls_max_nfev: int = 3000,
        sellmeier_log_l1l2: bool | None = None,
    ):

        n_raw = np.asarray(n_raw, dtype=np.float64).ravel()

        wl = np.asarray(wl_nm, dtype=np.float64).ravel()

        lo = float(min(wl_min_fit, wl_max_fit))

        hi = float(max(wl_min_fit, wl_max_fit))

        fit_mask = IndexCore._fit_mask(wl, lo, hi) & np.isfinite(wl) & np.isfinite(n_raw)

        if log_preprocess:
            logger.info(
                "Curve preprocess: range=[%.1f, %.1f]nm | kept=%d/%d",
                lo,
                hi,
                int(np.count_nonzero(fit_mask)),
                int(wl.size),
            )

            if int(np.count_nonzero(fit_mask)) >= 2:
                wl_kept = wl[fit_mask]

                logger.info(
                    "Strict fit mask effective bounds: [%.1f, %.1f]nm",
                    float(np.min(wl_kept)),
                    float(np.max(wl_kept)),
                )

        fit_label = _substrate_fit_engine_log_label(model_kind)

        if log_preprocess:
            logger.info("Curve smoothing disabled: using raw n(lambda) directly before %s fit.", fit_label)

            logger.info(
                "Fit/eval policy: fit_only=[%.1f, %.1f]nm | index_eval_full=[%.1f, %.1f]nm",
                lo,
                hi,
                float(np.nanmin(wl)) if wl.size else float("nan"),
                float(np.nanmax(wl)) if wl.size else float("nan"),
            )

        else:
            logger.info("Additional model fit (%s) on same column / same mask.", fit_label)

        n_sell, fit_meta = IndexCore.fit_sellmeier(
            n_raw,
            wl,
            lo,
            hi,
            valid_mask=fit_mask,
            progress_cb=progress_cb,
            model_kind=model_kind,
            return_meta=True,
            sellmeier_timeout_s=sellmeier_timeout_s,
            sellmeier_de_maxiter=sellmeier_de_maxiter,
            sellmeier_ls_max_nfev=sellmeier_ls_max_nfev,
            sellmeier_log_l1l2=sellmeier_log_l1l2,
        )

        return n_raw, n_sell, fit_meta

    @staticmethod
    def to_fraction(y_clean: np.ndarray) -> np.ndarray:

        frac = y_clean / 100.0 if np.max(y_clean) > 2.0 else y_clean.copy()

        return np.clip(frac, 0.0001, 0.9999)

    @staticmethod
    def single_face_from_two_face(r_2f: np.ndarray) -> np.ndarray:

        return np.clip(r_2f / (2.0 - r_2f), 0.0001, 0.9999)

    @staticmethod
    def n_from_tnu2f(t_frac: np.ndarray) -> np.ndarray:

        return (1.0 + np.sqrt(1.0 - t_frac**2)) / t_frac

    @staticmethod
    def n_from_rnu2f(r_frac: np.ndarray) -> np.ndarray:

        disc = np.maximum(2.0 * r_frac - r_frac**2, 0.0)

        return (1.0 + np.sqrt(disc)) / (1.0 - r_frac)

    @staticmethod
    def enforce_normal_dispersion(wl_nm: np.ndarray, n_vals: np.ndarray) -> np.ndarray:
        """Enforce a physically plausible normal dispersion: n decreases with lambda."""

        wl = np.asarray(wl_nm, dtype=np.float64)

        n = np.asarray(n_vals, dtype=np.float64).copy()

        m = np.isfinite(wl) & np.isfinite(n)

        if int(np.count_nonzero(m)) < 3:
            return n

        idx = np.where(m)[0]

        # For increasing wavelength, enforce non-increasing index.

        n_sub = n[idx]

        n[idx] = np.minimum.accumulate(n_sub)

        return n

    @staticmethod
    def n_from_r45s_single_face(r_frac: np.ndarray) -> np.ndarray:

        term = (1.0 + np.sqrt(r_frac)) / (1.0 - np.sqrt(r_frac))

        return np.sqrt(0.5 * (1.0 + term**2))

    @staticmethod
    def n_from_r45p_single_face(r_frac: np.ndarray) -> np.ndarray:

        k = (1.0 - np.sqrt(r_frac)) / (1.0 + np.sqrt(r_frac))

        n2 = (1.0 + np.sqrt(np.maximum(0.0, 1.0 - k**2))) / (k**2 + 1e-9)

        return np.sqrt(np.maximum(1.0, n2))



