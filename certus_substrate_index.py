#!/usr/bin/env python3


# -*- coding: utf-8 -*-


"""


CERTUS Substrate Index - Substrate refractive index determination only


"""


import functools
from pathlib import Path


import re


import sys


import logging


import unicodedata


import numpy as np


import pandas as pd


import pyqtgraph as pg


from PyQt6.QtCore import Qt, QSettings


from PyQt6.QtGui import QFont, QColor, QBrush


from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QLabel,
    QFrame,
    QMessageBox,
    QCheckBox,
    QDialog,
    QTableWidgetItem,
    QHeaderView,
    QDoubleSpinBox,
    QSpinBox,
    QTextEdit,
)


from certus_core import (
    NUMERICAL_FAULT_EXCEPTIONS,
    setup_module_logging,
    __version__,
    SELLMEIER_COEFFS_BY_ID,
    SUBSTRATES,
    CANONICAL_SUBSTRATE_LABELS,
    canonicalize_substrate_label,
    substrate_sellmeier_coeffs,
)
from certus_metrology import ValidationStatus
from certus_services import SubstrateIndexRequest, SubstrateIndexService


from certus_measurement_excel_ui import open_measurement_excel_interactive


from certus_spectral_preproc import dynamic_savgol_blend


from certus_ui import (
    CertusTheme,
    CertusLogPanel,
    EnhancedProgressWidget,
    attach_excel_clipboard_context_menu,
    CertusScientificPlot,
    wrap_scientific_plot_with_toolbar,
    init_certus_app,
    create_styled_button,
    create_styled_label,
    set_certus_window_icon,
    create_header_logo_widget,
    ExcelTableWidget,
)


logger = setup_module_logging("CERTUS_SUBSTRATE_INDEX")


def _substrate_index_norm_header(raw) -> str:

    s = str(raw).strip().lower()

    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

    s = s.replace("œ", "oe").replace("æ", "ae")

    # Usual Excel / lab separators -> spaces (robust to pasted or heterogeneous shortcuts)

    s = re.sub(r"[_\-\./\\+|,:;]+", " ", s)

    s = re.sub(r"\s+", " ", s).strip()

    return s


def _substrate_index_expand_substrate_abbrevs(s: str) -> str:
    """Replaces common FR/EN abbreviations with canonical forms for the bare test."""

    # Order: long / specific forms first

    repl: tuple[tuple[str, str], ...] = (
        (r"\bsubstrate\b", "substrate"),
        (r"\bsubstrat\b", "substrate"),
        (r"\bsubstn\b", "substrate nu"),  # substn, subst-n
        (r"\bsbstn\b", "substrate nu"),
        (r"\bsubstnu\b", "substrate nu"),
        (r"\bsbstnu\b", "substrate nu"),
        (r"\bsnu\b", "substrate nu"),  # acronyme  substrate nu
        (r"\bsubst\b", "substrate"),
        (r"\bsbst\b", "substrate"),
        (r"\bsubstr\b", "substrate"),
        (r"\bsubs\b", "substrate"),  # subs = substrate (lab usage)
        (r"\bsub\b", "sub"),  # keep short; combines with nu elsewhere
        (r"\buncoated\b", "uncoated"),
        (r"\buncoat\b", "uncoated"),
        (r"\bnocoat\b", "no coating"),
        (r"\bno\s*coat\b", "no coating"),
        (r"\bwo\s*coat\b", "no coating"),
        (r"\bw/o\s*coat\b", "no coating"),
        (r"\btemoin\b", "witness"),
        (r"\bwitness\b", "witness"),
        (r"\bblk\b", "blank"),
        (r"\bref\b", "ref"),
    )

    out = s

    for pat, to in repl:
        out = re.sub(pat, to, out, flags=re.IGNORECASE)

    out = re.sub(r"\s+", " ", out).strip()

    return out


def _substrate_index_unglue_substrate_nu(s: str) -> str:
    """Unglues concatenated variants like substratnu, subnu, baresub, etc."""

    out = s

    out = re.sub(
        r"(substrate|sub|sbst|subst|substr|bare|blank|uncoated)(nu|nus|nue)\b",
        r"\1 \2",
        out,
        flags=re.IGNORECASE,
    )

    out = re.sub(
        r"\b(bare|blank|ref|raw|empty|void)(sub|substrate|substrate)\b",
        r"\1 \2",
        out,
        flags=re.IGNORECASE,
    )

    out = re.sub(r"\s+", " ", out).strip()

    return out


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
    """True if header indicates a bare substrate measurement (not a filter / stack)."""

    s0 = _substrate_index_norm_header(name)

    if not s0:
        return False

    s1 = _substrate_index_unglue_substrate_nu(s0)

    s2 = _substrate_index_expand_substrate_abbrevs(s1)

    s3 = _substrate_index_unglue_substrate_nu(s2)

    # Stack / target priority

    if _RE_SUBSTRATE_INDEX_EXCLUDE.search(s3):
        return False

    return bool(_RE_SUBSTRATE_INDEX_INCLUDE.search(s3))


def _filter_dataframe_bare_substrate_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str], list[str]]:
    """Keeps lambda + spectral columns marked bare substrate; returns (df, kept, ignoreds)."""

    if df is None or df.empty or len(df.columns) < 2:
        return df, [], []

    col_names = list(df.columns)

    wl = col_names[0]

    # Lab exports: 1st column may be "Unnamed", with lambda in another column.

    for c in col_names:
        s = _substrate_index_norm_header(c)

        if not re.search(r"\b(wavelength|lambda|longueur\s*d\s*onde|wl)\b", s):
            continue

        vals = pd.to_numeric(df[c], errors="coerce")

        if int(np.count_nonzero(np.isfinite(vals.values))) >= 3:
            wl = c

            break

    kept_cols: list = [wl]

    kept_spec: list[str] = []

    dropped: list[str] = []

    for col in col_names:
        if col == wl:
            continue

        cstr = str(col)

        if _is_bare_substrate_spectrum_column(col):
            kept_cols.append(col)

            kept_spec.append(cstr)

        else:
            dropped.append(cstr)

    return df[kept_cols].copy(), kept_spec, dropped


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


SELLMEIER_N_ACCEPT_LO = 1.05


SELLMEIER_N_ACCEPT_HI = 6.5


SELLMEIER_MIN_L_SEP_UM = 0.01  # m minimal spacing between Li poles (was 0.004)


SELLMEIER_L_SEP_SOFT_WEIGHT = 2.0e5  # soft residue weight on minimal Li separation


# Optimisation Sellmeier : physical bounds -> Li linear direct (no log reparameterization).


# log-reparam disabled sufficiently tightened bounds


SELLMEIER_DEFAULT_LOG_L1L2 = False  # log-reparam disabled  bounds sufficiently tightened


SELLMEIER_2POLES_PARAM_BOUNDS: tuple[tuple[float, float], ...] = (
    (0.0, 4.0),  # A constant term >= 0 ; standard substrates: A < 3
    (0.0, 12.0),  # B1 UV oscillator; positive for transparents
    (1.0e-3, 1.0),  # L1 m UV pole; effective ceiling via _sellmeier_2poles_param_bounds
    (0.0, 12.0),  # B2
    (1.0e-3, 30.0),  # L2 m can be UV or short IR
    (0.0, 12.0),  # B3
    (1.0e-3, 30.0),  # L3 m typically IR pole
)


SELLMEIER_2POLES_LAM_FRAC_MAX = 0.97


SELLMEIER_3TERM_C_FRAC_MAX = 0.995


# Light multistart: with physical bounds and good seeding, 2 candidates are enough.


SELLMEIER_SEED_POINTS = 5  # grid points for polynomial seed (was 9)


SELLMEIER_MULTISTART_TRIALS = 2  # additional random jitters (was 8)


SELLMEIER_WEIGHT_MODE = "uniform"  # uniform: no UV bias (was inv_sqrt_lambda)


# Selection of best model (beyond raw RMSE).


# score = rmse + w_mono*frac_viol_mono + w_prior*rmse_prior_sellmeier


MODEL_SELECT_MONO_WEIGHT = 0.04


MODEL_SELECT_PRIOR_WEIGHT = 0.35


# Catalog prior (standard Sellmeier 3-term from certus_core), by column name heuristic.


_SUBSTRATE_PRIOR_HINTS: tuple[tuple[re.Pattern[str], int], ...] = (
    (re.compile(r"\b(sapphire|saphir|al2o3)\b", re.IGNORECASE), 3),
    (re.compile(r"\b(n[\s\-_]*bk7|bk7)\b", re.IGNORECASE), 1),
    (re.compile(r"\b(sio2|silice|silica|quartz)\b", re.IGNORECASE), 0),
    (re.compile(r"\b(d263t|d263)\b", re.IGNORECASE), 2),
    (re.compile(r"\b(b270i|b270)\b", re.IGNORECASE), 4),
)


def _sellmeier_2poles_param_bounds(lam_min_um: float) -> list[tuple[float, float]]:
    """Box (A, B1, L1, B2, L2, B3, L3).

    L1 remains UV side (below lambda_min) for stability; L2/L3 are free (up to 40 m)

    for capture IR/Cauchy curvature without forcing all poles to UV.

    """

    cap_uv = max(1.0e-9, float(lam_min_um) * float(SELLMEIER_2POLES_LAM_FRAC_MAX))

    l_hi_uv = min(40.0, cap_uv)

    l_hi_ir = 40.0

    a_lo, a_hi = float(SELLMEIER_2POLES_PARAM_BOUNDS[0][0]), float(SELLMEIER_2POLES_PARAM_BOUNDS[0][1])

    b_lo, b_hi = float(SELLMEIER_2POLES_PARAM_BOUNDS[1][0]), float(SELLMEIER_2POLES_PARAM_BOUNDS[1][1])

    l_lo = float(SELLMEIER_2POLES_PARAM_BOUNDS[2][0])

    return [
        (a_lo, a_hi),
        (b_lo, b_hi),
        (l_lo, float(l_hi_uv)),
        (b_lo, b_hi),
        (l_lo, float(l_hi_ir)),
        (b_lo, b_hi),
        (l_lo, float(l_hi_ir)),
    ]


def _sellmeier_l_separation_gap_um(p: np.ndarray) -> float:
    """Missing part for min(|LiLj|) >= SELLMEIER_MIN_L_SEP_UM (m)."""

    pp = np.asarray(p, dtype=np.float64).ravel()

    lvals = []

    for i in (2, 4, 6):
        if i < pp.size:
            lvals.append(float(pp[i]))

    if len(lvals) < 2:
        return 0.0

    larr = np.sort(np.asarray(lvals, dtype=np.float64))

    min_sep = float(np.min(np.diff(larr)))

    return max(0.0, float(SELLMEIER_MIN_L_SEP_UM) - min_sep)


def _sellmeier_weights_from_nm(wl_nm: np.ndarray, mode: str) -> np.ndarray:

    wl = np.maximum(np.asarray(wl_nm, dtype=np.float64), 1.0)

    m = str(mode or "").strip().lower()

    if m == "uniform":
        return np.ones_like(wl, dtype=np.float64)

    if m == "inv_lambda":
        return 1.0 / wl

    # default robust compromise: less UV domination than 1/lambda

    return 1.0 / np.sqrt(wl)


def _sellmeier_param_reparam_helpers(
    bounds: list[tuple[float, float]],
    log_l1l2: bool,
) -> tuple[list[tuple[float, float]], Any, Any, np.ndarray, np.ndarray]:
    bounds_q: list[tuple[float, float]] = [(float(b[0]), float(b[1])) for b in bounds]
    if log_l1l2:
        _ll0 = float(max(bounds[2][0], 1.0e-30))
        _ll1 = float(bounds[2][1])
        _ln_lo = float(np.log(_ll0))
        _ln_hi = float(np.log(_ll1))
        bounds_q[2] = (_ln_lo, _ln_hi)
        bounds_q[4] = (_ln_lo, _ln_hi)
        bounds_q[6] = (_ln_lo, _ln_hi)

    def _p_from_q(q: np.ndarray) -> np.ndarray:
        q = np.asarray(q, dtype=np.float64).ravel()
        if not log_l1l2:
            return q.copy()
        p = q.copy()
        p[2] = float(np.exp(np.minimum(q[2], 700.0)))
        p[4] = float(np.exp(np.minimum(q[4], 700.0)))
        p[6] = float(np.exp(np.minimum(q[6], 700.0)))
        return p

    def _q_from_p(p: np.ndarray) -> np.ndarray:
        p = np.asarray(p, dtype=np.float64).ravel()
        if not log_l1l2:
            return p.copy()
        q = p.copy()
        q[2] = float(np.log(max(float(p[2]), 1.0e-300)))
        q[4] = float(np.log(max(float(p[4]), 1.0e-300)))
        q[6] = float(np.log(max(float(p[6]), 1.0e-300)))
        return q

    return bounds_q, _p_from_q, _q_from_p, np.asarray([b[0] for b in bounds], dtype=np.float64), np.asarray([b[1] for b in bounds], dtype=np.float64)


def _sellmeier_residual_factory(p_from_q, wl_fit_um: np.ndarray, n_fit: np.ndarray, w_fit_sell: np.ndarray, n_lo_acc: float, n_hi_acc: float):
    def _residuals(p: np.ndarray, x_um: np.ndarray, y_n: np.ndarray, w_nm_inv: np.ndarray) -> np.ndarray:
        pred = IndexCore.sellmeier_2poles_const_eval(p, x_um)
        return (pred - y_n) * w_nm_inv * 1000.0

    def _mse_full_q(q: np.ndarray) -> float:
        p = p_from_q(q)
        pred = IndexCore.sellmeier_2poles_const_eval(p, wl_fit_um)
        if not np.all(np.isfinite(pred)):
            return 1.0e30
        if np.any((pred < n_lo_acc) | (pred > n_hi_acc)):
            vio = float(np.mean(np.maximum(n_lo_acc - pred, 0.0) ** 2 + np.maximum(pred - n_hi_acc, 0.0) ** 2))
            return 1.0e12 + 1.0e9 * vio
        r = _residuals(p, wl_fit_um, n_fit, w_fit_sell)
        mse = float(np.dot(r, r))
        g = _sellmeier_l_separation_gap_um(p)
        if g > 0.0:
            mse += 5.0e7 * (g * g)
        return mse

    return _residuals, _mse_full_q


def _sellmeier_seed_from_compact_poly(
    wl: np.ndarray,
    wl_fit_nm: np.ndarray,
    n_vals: np.ndarray,
    mask: np.ndarray,
    p_from_q,
    q_mid: np.ndarray,
    ls_bounds_q: tuple[list[float], list[float]],
) -> tuple[str, np.ndarray]:
    from scipy.optimize import least_squares
    seed_desc = "centre box (q)"
    q0 = q_mid
    poly_seed = IndexCore._sellmeier_compact_polynomial_seed(wl, n_vals, mask)
    if poly_seed is not None:
        active_terms, p_poly, _ = poly_seed
        lo_nm = float(np.min(wl_fit_nm))
        hi_nm = float(np.max(wl_fit_nm))
        n_seed_pts = int(max(7, SELLMEIER_SEED_POINTS))
        seed_nm = np.linspace(lo_nm, hi_nm, n_seed_pts, dtype=np.float64)
        seed_um = seed_nm / 1000.0
        feat_s = IndexCore._poly_compact_feature_dict(seed_um)
        phi_s = np.column_stack([feat_s[t] for t in active_terms])
        n_tar = (phi_s @ p_poly).astype(np.float64, copy=False)

        def _res5_q(qv: np.ndarray) -> np.ndarray:
            pv = p_from_q(qv)
            r = IndexCore.sellmeier_2poles_const_eval(pv, seed_um) - n_tar
            g = _sellmeier_l_separation_gap_um(pv)
            return np.append(
                r,
                float(SELLMEIER_L_SEP_SOFT_WEIGHT) * 0.02 * g,
            )

        r5 = least_squares(
            _res5_q,
            q_mid,
            bounds=ls_bounds_q,
            loss="linear",
            max_nfev=2500,
            ftol=1.0e-12,
            xtol=1.0e-12,
            gtol=1.0e-12,
        )
        q0 = np.clip(np.asarray(r5.x, dtype=np.float64), ls_bounds_q[0], ls_bounds_q[1])
        seed_desc = (
            "compact polynomial + LS "
            f"{int(seed_nm.size)} points (lambda_nm={np.array2string(seed_nm, precision=1, separator=', ')})"
        )
    return seed_desc, q0


def _sellmeier_multistart_candidates(q0: np.ndarray, _p_from_q, _q_from_p, bounds, ls_bounds_q, n_trials: int) -> list[np.ndarray]:
    rng = np.random.default_rng(12345)
    q_candidates: list[np.ndarray] = [np.asarray(q0, dtype=np.float64)]
    p_base = _p_from_q(q0)
    l3_grid = (0.1, 0.5, 2.0, 8.0)
    for l3_try in l3_grid:
        p_try = np.asarray(p_base, dtype=np.float64).copy()
        p_try[6] = float(np.clip(l3_try, bounds[6][0], bounds[6][1]))
        q_try = _q_from_p(p_try)
        q_try = np.clip(q_try, ls_bounds_q[0], ls_bounds_q[1])
        q_candidates.append(np.asarray(q_try, dtype=np.float64))
    for _ in range(max(0, int(n_trials) - 1)):
        jit = rng.uniform(-0.15, 0.15, size=q0.shape)
        jit[6] = float(rng.uniform(-0.5, 0.5))
        qj = np.asarray(q0 + jit, dtype=np.float64)
        qj = np.clip(qj, ls_bounds_q[0], ls_bounds_q[1])
        q_candidates.append(qj)
    return q_candidates


def _sellmeier_polish_helpers(_p_from_q, wl_fit_um: np.ndarray, n_fit: np.ndarray, w_fit_sell: np.ndarray, log_l1l2: bool):
    def _residuals_polish_q(qv: np.ndarray) -> np.ndarray:
        pv = _p_from_q(qv)
        r = _residuals(pv, wl_fit_um, n_fit, w_fit_sell)
        g = _sellmeier_l_separation_gap_um(pv)
        return np.append(r, float(SELLMEIER_L_SEP_SOFT_WEIGHT) * g)

    def _jac_polish_q(qv: np.ndarray) -> np.ndarray:
        """Analytical Jacobian of polish residual (extended with separation constraint)."""
        pv = _p_from_q(qv)
        J_main = _sellmeier_2poles_jac(pv, wl_fit_um, w_fit_sell, scale=1000.0)
        J_sep = np.zeros((1, 7), dtype=np.float64)
        _L_vals = np.array([pv[2], pv[4], pv[6]], dtype=np.float64)
        _orig_idx = np.array([2, 4, 6])
        _sort_ord = np.argsort(_L_vals)
        _L_s = _L_vals[_sort_ord]
        _diffs = _L_s[1:] - _L_s[:-1]
        _i_min = int(np.argmin(_diffs))
        _gap = float(SELLMEIER_MIN_L_SEP_UM) - float(_diffs[_i_min])
        if _gap > 0.0:
            _pidx_lo = int(_orig_idx[int(_sort_ord[_i_min])])
            _pidx_hi = int(_orig_idx[int(_sort_ord[_i_min + 1])])
            _sc_lo = float(pv[_pidx_lo]) if log_l1l2 else 1.0
            _sc_hi = float(pv[_pidx_hi]) if log_l1l2 else 1.0
            J_sep[0, _pidx_lo] = float(SELLMEIER_L_SEP_SOFT_WEIGHT) * _sc_lo
            J_sep[0, _pidx_hi] = -float(SELLMEIER_L_SEP_SOFT_WEIGHT) * _sc_hi
        return np.vstack([J_main, J_sep])

    return _residuals_polish_q, _jac_polish_q


# Duplicated function _sellmeier_seed_from_compact_poly removed.


def _sellmeier_build_candidates(q0: np.ndarray, p_from_q, _q_from_p, bounds, ls_bounds_q, n_trials: int, rng) -> list[np.ndarray]:
    q_candidates: list[np.ndarray] = [np.asarray(q0, dtype=np.float64)]
    p_base = p_from_q(q0)
    l3_grid = (0.1, 0.5, 2.0, 8.0)
    for l3_try in l3_grid:
        p_try = np.asarray(p_base, dtype=np.float64).copy()
        p_try[6] = float(np.clip(l3_try, bounds[6][0], bounds[6][1]))
        q_try = _q_from_p(p_try)
        q_try = np.clip(q_try, ls_bounds_q[0], ls_bounds_q[1])
        q_candidates.append(np.asarray(q_try, dtype=np.float64))
    for _ in range(n_trials - 1):
        jit = rng.uniform(-0.15, 0.15, size=q0.shape)
        jit[6] = float(rng.uniform(-0.5, 0.5))
        qj = np.asarray(q0 + jit, dtype=np.float64)
        qj = np.clip(qj, ls_bounds_q[0], ls_bounds_q[1])
        q_candidates.append(qj)
    return q_candidates


def _sellmeier_polish_helpers(p_from_q, wl_fit_um: np.ndarray, n_fit: np.ndarray, w_fit_sell: np.ndarray, log_l1l2: bool):
    def _residuals_polish_q(qv: np.ndarray) -> np.ndarray:
        pv = p_from_q(qv)
        r = _sellmeier_residual_factory(p_from_q, wl_fit_um, n_fit, w_fit_sell, -np.inf, np.inf)[0](pv, wl_fit_um, n_fit, w_fit_sell)
        g = _sellmeier_l_separation_gap_um(pv)
        return np.append(r, float(SELLMEIER_L_SEP_SOFT_WEIGHT) * g)

    def _jac_polish_q(qv: np.ndarray) -> np.ndarray:
        pv = p_from_q(qv)
        J_main = _sellmeier_2poles_jac(pv, wl_fit_um, w_fit_sell, scale=1000.0)
        J_sep = np.zeros((1, 7), dtype=np.float64)
        _L_vals = np.array([pv[2], pv[4], pv[6]], dtype=np.float64)
        _orig_idx = np.array([2, 4, 6])
        _sort_ord = np.argsort(_L_vals)
        _L_s = _L_vals[_sort_ord]
        _diffs = _L_s[1:] - _L_s[:-1]
        _i_min = int(np.argmin(_diffs))
        _gap = float(SELLMEIER_MIN_L_SEP_UM) - float(_diffs[_i_min])
        if _gap > 0.0:
            _pidx_lo = int(_orig_idx[int(_sort_ord[_i_min])])
            _pidx_hi = int(_orig_idx[int(_sort_ord[_i_min + 1])])
            _sc_lo = float(pv[_pidx_lo]) if log_l1l2 else 1.0
            _sc_hi = float(pv[_pidx_hi]) if log_l1l2 else 1.0
            J_sep[0, _pidx_lo] = float(SELLMEIER_L_SEP_SOFT_WEIGHT) * _sc_lo
            J_sep[0, _pidx_hi] = -float(SELLMEIER_L_SEP_SOFT_WEIGHT) * _sc_hi
        return np.vstack([J_main, J_sep])

    return _residuals_polish_q, _jac_polish_q


def _sellmeier_2poles_jac(
    p: np.ndarray,
    x_um: np.ndarray,
    w: np.ndarray,
    scale: float = 1000.0,
) -> np.ndarray:
    """Analytical Jacobian of _residuals(p, x_um, n_data, w) with respect to p.

    Residue : r_i = (n_pred_i - n_data_i) * w_i * scale

    n2 = A + B1*lambda2/(lambda2-L12) + B2*lambda2/(lambda2-L22) + B3*lambda2/(lambda2-L32)

    n  = sqrt(max(n2, 0))

    Analytical derivatives :

        n2/A  = 1

        n2/Bk = lambda2/(lambda2-Lk2)

        n2/Lk = 2BkLklambda2/(lambda2-Lk2)2

        n/p   = (1/(2n)) * n2/p   (with anti-division-by-0 threshold)

    """

    p = np.asarray(p, dtype=np.float64).ravel()

    x = np.asarray(x_um, dtype=np.float64)

    w = np.asarray(w, dtype=np.float64)

    A, B1, L1, B2, L2, B3, L3 = p

    lam2 = x * x

    d1 = np.maximum(lam2 - L1 * L1, 1.0e-15)

    d2 = np.maximum(lam2 - L2 * L2, 1.0e-15)

    d3 = np.maximum(lam2 - L3 * L3, 1.0e-15)

    t1 = lam2 / d1

    t2 = lam2 / d2

    t3 = lam2 / d3

    n2 = A + B1 * t1 + B2 * t2 + B3 * t3

    n = np.sqrt(np.maximum(n2, 0.0))

    # dn/dn2 = 1/(2n) ; threshold 1e-9 to avoid division by zero

    inv2n = np.where(n > 1.0e-9, 1.0 / (2.0 * n), 0.0)

    # Common factor : w * scale * dn/dn2

    c = w * scale * inv2n

    J = np.empty((len(x), 7), dtype=np.float64)

    J[:, 0] = c * 1.0  # r/A

    J[:, 1] = c * t1  # r/B1

    J[:, 2] = c * (2.0 * B1 * L1 * lam2 / (d1 * d1))  # r/L1

    J[:, 3] = c * t2  # r/B2

    J[:, 4] = c * (2.0 * B2 * L2 * lam2 / (d2 * d2))  # r/L2

    J[:, 5] = c * t3  # r/B3

    J[:, 6] = c * (2.0 * B3 * L3 * lam2 / (d3 * d3))  # r/L3

    return J


def _sellmeier_3term_standard_eval(coeffs: np.ndarray, wl_um: np.ndarray) -> np.ndarray:
    """Sellmeier standard: n2 = 1 + (Bi*lambda2/(lambda2-Ci)), lambda in m."""

    p = np.asarray(coeffs, dtype=np.float64).ravel()

    wl = np.maximum(np.asarray(wl_um, dtype=np.float64), 1.0e-9)

    lam2 = wl * wl

    B1, C1, B2, C2, B3, C3 = p

    d1 = lam2 - C1

    d2 = lam2 - C2

    d3 = lam2 - C3

    d1 = np.where(np.abs(d1) < 1.0e-15, np.sign(d1) * 1.0e-15 + (d1 == 0.0) * 1.0e-15, d1)

    d2 = np.where(np.abs(d2) < 1.0e-15, np.sign(d2) * 1.0e-15 + (d2 == 0.0) * 1.0e-15, d2)

    d3 = np.where(np.abs(d3) < 1.0e-15, np.sign(d3) * 1.0e-15 + (d3 == 0.0) * 1.0e-15, d3)

    n2 = 1.0 + (B1 * lam2) / d1 + (B2 * lam2) / d2 + (B3 * lam2) / d3

    return np.sqrt(np.maximum(n2, 0.0))


def _sellmeier_prior_coeffs_for_column(col_name: str | None) -> tuple[float, ...] | None:

    s = _substrate_index_norm_header(col_name or "")

    for pat, mat_id in _SUBSTRATE_PRIOR_HINTS:
        if pat.search(s):
            c = SELLMEIER_COEFFS_BY_ID.get(int(mat_id))

            if c is not None and len(c) == 6:
                return tuple(float(v) for v in c)

    canon = canonicalize_substrate_label(col_name)
    if canon is not None:
        c = substrate_sellmeier_coeffs(canon)
        if c is not None and len(c) == 6:
            return tuple(float(v) for v in c)

    return None


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

    # Sellmeier should not be penalized by a decrease constraint here.

    src = str((fit_meta or {}).get("source") or "")

    is_sellmeier = "sellmeier" in src

    if int(np.count_nonzero(m)) >= 3 and not is_sellmeier:
        n_seg = n_line[m]

        _cnt, frac = IndexCore._monotonic_violation_stats(n_seg)

        score += float(MODEL_SELECT_MONO_WEIGHT) * float(max(0.0, frac))

    else:
        n_seg = n_line[m]

    if "sellmeier" in src:
        prior = _sellmeier_prior_coeffs_for_column(col_name)

        if prior is not None and int(np.count_nonzero(m)) >= 8:
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


def _add_pg_fit_band_outside_shading(
    plot_widget: pg.PlotWidget,
    fit_lo_nm: float,
    fit_hi_nm: float,
    x_min_nm: float,
    x_max_nm: float,
) -> None:
    """Semi-opaque vertical bands for lambda outside [fit_lo, fit_hi] (data between x_min and x_max)."""

    lo = float(min(fit_lo_nm, fit_hi_nm))

    hi = float(max(fit_lo_nm, fit_hi_nm))

    w0 = float(min(x_min_nm, x_max_nm))

    w1 = float(max(x_min_nm, x_max_nm))

    if not np.isfinite([lo, hi, w0, w1]).all() or w1 <= w0:
        return

    plot_item = plot_widget.plotItem

    brush = pg.mkBrush(88, 90, 98, 62)

    z_back = -40

    if w0 < lo:
        e = min(lo, w1)

        if e > w0:
            r = pg.LinearRegionItem([w0, e], movable=False, brush=brush, pen=pg.mkPen(None))

            r.setZValue(z_back)

            plot_item.addItem(r)

    if hi < w1:
        s = max(hi, w0)

        if w1 > s:
            r = pg.LinearRegionItem([s, w1], movable=False, brush=brush, pen=pg.mkPen(None))

            r.setZValue(z_back)

            plot_item.addItem(r)


def _nan_split_band_y(
    y,
    fit_mask: np.ndarray | None,
) -> tuple[np.ndarray | None, np.ndarray]:
    """If mask: (y out-of-band with internal NaN, y in-band). Otherwise: (None, y)."""

    y_arr = np.asarray(y, dtype=np.float64)

    if fit_mask is None:
        return None, y_arr

    return np.where(~fit_mask, y_arr, np.nan), np.where(fit_mask, y_arr, np.nan)


def _pg_plot_xy_split_band(
    plot_widget: pg.PlotWidget,
    wl,
    y,
    fit_mask: np.ndarray | None,
    pen_inside,
    pen_outside,
    **plot_kw,
):
    """Plot y(lambda); if fit_mask provided, out-of-band segment in gray then in-band segment."""

    y_out, y_in = _nan_split_band_y(y, fit_mask)

    if y_out is None:
        return plot_widget.plot(wl, y_in, pen=pen_inside, **plot_kw)

    plot_widget.plot(wl, y_out, pen=pen_outside)

    return plot_widget.plot(wl, y_in, pen=pen_inside, **plot_kw)


def _pg_plot_scatter_split_band(
    plot_widget: pg.PlotWidget,
    wl,
    y,
    fit_mask: np.ndarray | None,
    symbol_pen_inside,
    symbol_pen_outside,
    *,
    symbol: str = "x",
    symbol_size: float = 5.0,
    name: str | None = None,
):
    """Scatter y(lambda) with symbols; fit out-of-band in gray if mask provided."""

    y_out, y_in = _nan_split_band_y(y, fit_mask)

    kw = {"pen": None, "symbol": symbol, "symbolSize": symbol_size}

    if y_out is None:
        return plot_widget.plot(wl, y_in, symbolPen=symbol_pen_inside, name=name, **kw)

    plot_widget.plot(wl, y_out, symbolPen=symbol_pen_outside, **kw)

    return plot_widget.plot(wl, y_in, symbolPen=symbol_pen_inside, name=name, **kw)


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
    def _sellmeier_compact_polynomial_seed(
        wl: np.ndarray,
        n_vals: np.ndarray,
        mask: np.ndarray,
    ) -> tuple[list[str], np.ndarray, np.ndarray] | None:
        """

        Same compact polynomial model selection as the main branch (weighted IRLS).

        Returns (active terms, p, n_poly on all `wl`) to seed Sellmeier; no RMSE/mono rejection here.

        """

        wl_fit_nm = np.asarray(wl[mask], dtype=np.float64)

        n_fit = np.asarray(n_vals[mask], dtype=np.float64)

        fitted = _fit_compact_polynomial_model(
            wl_fit_nm,
            n_fit,
            np.asarray(wl, dtype=np.float64),
            rmse_target_compact=1.5e-3,
        )

        if fitted is None:
            return None

        active_terms, p, n_out, _rmse_c = fitted

        return active_terms, np.asarray(p, dtype=np.float64), np.asarray(n_out, dtype=np.float64)

    @staticmethod
    def sellmeier_2poles_const_eval(params: np.ndarray, wl_um: np.ndarray) -> np.ndarray:
        """n2 = A + (Bi*lambda2/(lambda2-Li2)) (i=1..3), with lambda in m."""

        p = np.asarray(params, dtype=np.float64).ravel()

        wl = np.maximum(np.asarray(wl_um, dtype=np.float64), 1.0e-9)

        lam2 = wl**2

        A, B1, L1, B2, L2, B3, L3 = p

        # Under constraint L < lambda_min(fit), den > 0; floor only for numerical anti-0 (not 1e-9 which

        # produced ~1e9 terms when lambda2-L2<0 with L out of UV).

        den1 = np.maximum(lam2 - (L1**2), 1.0e-15)

        den2 = np.maximum(lam2 - (L2**2), 1.0e-15)

        den3 = np.maximum(lam2 - (L3**2), 1.0e-15)

        n2 = A + (B1 * lam2) / den1 + (B2 * lam2) / den2 + (B3 * lam2) / den3

        # No clip on n2 towards acceptance band: it produced n=1.05 everywhere (n2<0) while

        # passing band tests. 1e-9 floor gave n~3e-5. Here: n2<=0 -> n=0 -> out-of-band.

        return np.sqrt(np.maximum(np.asarray(n2, dtype=np.float64), 0.0))

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
            res_n, res_src, res_coeffs, res_extra = IndexCore._fit_model_sellmeier3poles(
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
    def _fit_model_sellmeier3poles(
        n_vals: np.ndarray,
        wl: np.ndarray,
        mask: np.ndarray,
        n_fit: np.ndarray,
        wl_fit_nm: np.ndarray,
        wl_fit_um: np.ndarray,
        progress_cb,
        sellmeier_timeout_s: float | None,
        sellmeier_de_maxiter: int,
        sellmeier_de_popsize: int,
        sellmeier_ls_max_nfev: int,
        sellmeier_log_l1l2: bool | None,
    ) -> tuple[np.ndarray | None, str, np.ndarray | None, dict]:
        from scipy.optimize import least_squares, minimize

        import time

        log_l1l2 = bool(SELLMEIER_DEFAULT_LOG_L1L2 if sellmeier_log_l1l2 is None else sellmeier_log_l1l2)

        lam_min_um = float(np.min(wl_fit_um))

        bounds = _sellmeier_2poles_param_bounds(lam_min_um)

        logger.info(
            "Sellmeier 3-poles: math domain A[%.1f,%.1f] B[%.0f,%.0f] L[%.1e,%.4f] m "
            "(lambda_min fit=%.4f m; L_max=min(40,%.2f×lambda_min) for lambda2-L2>0 in window).",
            bounds[0][0],
            bounds[0][1],
            bounds[1][0],
            bounds[1][1],
            bounds[2][0],
            bounds[2][1],
            lam_min_um,
            float(SELLMEIER_2POLES_LAM_FRAC_MAX),
        )

        logger.info(
            "Sellmeier: optimization on %s.",
            "ui=ln(Li) (Li=exp(ui), L1/L2/L3 reparam.)" if log_l1l2 else "native parameters Li (linear)",
        )

        logger.info(
            "Sellmeier: weights=%s | seed_points=%d | multistart=%d",
            str(SELLMEIER_WEIGHT_MODE),
            int(max(7, SELLMEIER_SEED_POINTS)),
            int(max(1, SELLMEIER_MULTISTART_TRIALS)),
        )

        ls_max_nfev = int(max(100, sellmeier_ls_max_nfev))

        timeout_s = None if sellmeier_timeout_s is None else float(max(0.0, sellmeier_timeout_s))

        t0 = time.monotonic()

        lbfgs_maxiter = int(max(80, sellmeier_de_maxiter * 4 + sellmeier_de_popsize * 8))

        w_fit_sell = _sellmeier_weights_from_nm(wl_fit_nm, SELLMEIER_WEIGHT_MODE)

        def _p_from_q(q: np.ndarray) -> np.ndarray:

            q = np.asarray(q, dtype=np.float64).ravel()

            if not log_l1l2:
                return q.copy()

            p = q.copy()

            p[2] = float(np.exp(np.minimum(q[2], 700.0)))

            p[4] = float(np.exp(np.minimum(q[4], 700.0)))

            p[6] = float(np.exp(np.minimum(q[6], 700.0)))

            return p

        def _q_from_p(p: np.ndarray) -> np.ndarray:

            p = np.asarray(p, dtype=np.float64).ravel()

            if not log_l1l2:
                return p.copy()

            q = p.copy()

            q[2] = float(np.log(max(float(p[2]), 1.0e-300)))

            q[4] = float(np.log(max(float(p[4]), 1.0e-300)))

            q[6] = float(np.log(max(float(p[6]), 1.0e-300)))

            return q

        bounds_q, _p_from_q, _q_from_p, _b_lo, _b_hi = _sellmeier_param_reparam_helpers(bounds, log_l1l2)
        n_lo_acc = float(SELLMEIER_N_ACCEPT_LO)
        n_hi_acc = float(SELLMEIER_N_ACCEPT_HI)
        _residuals, _mse_full_q = _sellmeier_residual_factory(_p_from_q, wl_fit_um, n_fit, w_fit_sell, n_lo_acc, n_hi_acc)

        ls_bounds_lin = ([b[0] for b in bounds], [b[1] for b in bounds])

        ls_bounds_q = ([b[0] for b in bounds_q], [b[1] for b in bounds_q])

        p_mid = np.array(
            [
                0.5 * (bounds[0][0] + bounds[0][1]),
                0.5 * (bounds[1][0] + bounds[1][1]),
                0.5 * (bounds[2][0] + bounds[2][1]),
                0.5 * (bounds[3][0] + bounds[3][1]),
                0.5 * (bounds[4][0] + bounds[4][1]),
                0.5 * (bounds[5][0] + bounds[5][1]),
                0.5 * (bounds[6][0] + bounds[6][1]),
            ],
            dtype=np.float64,
        )

        _l_lo1, _l_hi1 = float(bounds[2][0]), float(bounds[2][1])

        _span1 = max(_l_hi1 - _l_lo1, 1.0e-15)

        p_mid[2] = float(_l_lo1 + 0.35 * _span1)

        _l_lo2, _l_hi2 = float(bounds[4][0]), float(bounds[4][1])

        _l_lo3, _l_hi3 = float(bounds[6][0]), float(bounds[6][1])

        p_mid[4] = float(np.clip(max(0.35, 1.6 * lam_min_um), _l_lo2, _l_hi2))

        p_mid[6] = float(np.clip(max(1.2, 4.0 * lam_min_um), _l_lo3, _l_hi3))

        _sep_need = float(SELLMEIER_MIN_L_SEP_UM)

        _ls = np.sort(np.asarray([p_mid[2], p_mid[4], p_mid[6]], dtype=np.float64))

        if float(np.min(np.diff(_ls))) < _sep_need:
            _mid = 0.5 * (_l_lo1 + _l_hi1)

            p_mid[2] = float(max(_l_lo1, _mid - 1.1 * _sep_need))

            p_mid[4] = float(np.clip(max(0.35, 1.6 * lam_min_um), _l_lo2, _l_hi2))

            p_mid[6] = float(np.clip(max(1.2, 4.0 * lam_min_um), _l_lo3, _l_hi3))

        p_mid = np.clip(p_mid, ls_bounds_lin[0], ls_bounds_lin[1])

        q_mid = _q_from_p(p_mid)

        q_mid = np.clip(q_mid, ls_bounds_q[0], ls_bounds_q[1])

        q0 = np.asarray(q_mid, dtype=np.float64, order="C")

        try:
            if callable(progress_cb):
                progress_cb(1, 2)

            seed_desc, q0_seed = _sellmeier_seed_from_compact_poly(wl, wl_fit_nm, n_vals, mask, _p_from_q, q_mid, ls_bounds_q)
            q0 = np.clip(np.asarray(q0_seed, dtype=np.float64), ls_bounds_q[0], ls_bounds_q[1])
            logger.info("Sellmeier 3-poles: seed %s.", seed_desc)
            run_lbfgs = timeout_s is None or timeout_s <= 0.0 or (time.monotonic() - t0) < max(0.5, timeout_s - 0.3)

            if run_lbfgs:
                rng = np.random.default_rng(12345)

                q_candidates: list[np.ndarray] = [np.asarray(q0, dtype=np.float64)]

                # Reduced L3 structured grid (IR pole): 4 values covering UV-short/IR.
                p_base = _p_from_q(q0)
                l3_grid = (0.1, 0.5, 2.0, 8.0)

                for l3_try in l3_grid:
                    p_try = np.asarray(p_base, dtype=np.float64).copy()
                    p_try[6] = float(np.clip(l3_try, bounds[6][0], bounds[6][1]))
                    q_try = _q_from_p(p_try)
                    q_try = np.clip(q_try, ls_bounds_q[0], ls_bounds_q[1])
                    q_candidates.append(np.asarray(q_try, dtype=np.float64))

                n_trials = int(max(1, SELLMEIER_MULTISTART_TRIALS))

                for _ in range(n_trials - 1):
                    jit = rng.uniform(-0.15, 0.15, size=q0.shape)
                    jit[6] = float(rng.uniform(-0.5, 0.5))
                    qj = np.asarray(q0 + jit, dtype=np.float64)
                    qj = np.clip(qj, ls_bounds_q[0], ls_bounds_q[1])
                    q_candidates.append(qj)

                best_q = np.asarray(q0, dtype=np.float64)
                best_f = float("inf")

                for qi in q_candidates:
                    if timeout_s is not None and timeout_s > 0.0 and (time.monotonic() - t0) >= timeout_s:
                        break

                    rb = minimize(
                        _mse_full_q,
                        qi,
                        method="L-BFGS-B",
                        bounds=bounds_q,
                        options={"maxiter": int(lbfgs_maxiter), "ftol": 1.0e-14, "gtol": 1.0e-10},
                    )

                    q_try = np.asarray(rb.x, dtype=np.float64)
                    f_try = float(_mse_full_q(q_try))

                    if f_try < best_f:
                        best_f = f_try
                        best_q = q_try

                q_lbfgs = np.asarray(best_q, dtype=np.float64)

            else:
                logger.warning("Sellmeier 3-poles: timeout before L-BFGS-B - seed alone.")
                q_lbfgs = np.asarray(q0, dtype=np.float64)

            def _residuals_polish_q(qv: np.ndarray) -> np.ndarray:
                pv = _p_from_q(qv)
                r = _residuals(pv, wl_fit_um, n_fit, w_fit_sell)
                g = _sellmeier_l_separation_gap_um(pv)
                return np.append(r, float(SELLMEIER_L_SEP_SOFT_WEIGHT) * g)

            def _jac_polish_q(qv: np.ndarray) -> np.ndarray:
                pv = _p_from_q(qv)
                J_main = _sellmeier_2poles_jac(pv, wl_fit_um, w_fit_sell, scale=1000.0)
                J_sep = np.zeros((1, 7), dtype=np.float64)
                _L_vals = np.array([pv[2], pv[4], pv[6]], dtype=np.float64)
                _orig_idx = np.array([2, 4, 6])
                _sort_ord = np.argsort(_L_vals)
                _L_s = _L_vals[_sort_ord]
                _diffs = _L_s[1:] - _L_s[:-1]
                _i_min = int(np.argmin(_diffs))
                _gap = float(SELLMEIER_MIN_L_SEP_UM) - float(_diffs[_i_min])
                if _gap > 0.0:
                    _pidx_lo = int(_orig_idx[int(_sort_ord[_i_min])])
                    _pidx_hi = int(_orig_idx[int(_sort_ord[_i_min + 1])])
                    _sc_lo = float(pv[_pidx_lo]) if log_l1l2 else 1.0
                    _sc_hi = float(pv[_pidx_hi]) if log_l1l2 else 1.0
                    J_sep[0, _pidx_lo] = float(SELLMEIER_L_SEP_SOFT_WEIGHT) * _sc_lo
                    J_sep[0, _pidx_hi] = -float(SELLMEIER_L_SEP_SOFT_WEIGHT) * _sc_hi
                return np.vstack([J_main, J_sep])

            res_pol = least_squares(
                _residuals_polish_q,
                q_lbfgs,
                jac=_jac_polish_q,
                bounds=ls_bounds_q,
                loss="linear",
                f_scale=1.0,
                max_nfev=ls_max_nfev,
            )

            q_sell = np.asarray(res_pol.x, dtype=np.float64)

            p_sell = _p_from_q(q_sell)

            p_lbfgs = _p_from_q(q_lbfgs)

            # Removal of redundant unweighted polish (canceled pass 1 corrections).

            # The weighted pass with analytical Jacobian is sufficient.

            if callable(progress_cb):
                progress_cb(2, 2)

            wl_full_um = np.asarray(wl / 1000.0, dtype=np.float64)

            def _sellmeier_n_in_accept_band(p: np.ndarray) -> bool:

                n_line = IndexCore.sellmeier_2poles_const_eval(p, wl_full_um)

                if not np.all(np.isfinite(n_line)):
                    return False

                ne = np.asarray(n_line[mask], dtype=np.float64)

                return bool(np.all(ne >= n_lo_acc) and np.all(ne <= n_hi_acc))

            def _accept_stats(p: np.ndarray) -> tuple[bool, float, float, float]:
                n_line = IndexCore.sellmeier_2poles_const_eval(p, wl_full_um)
                if not np.all(np.isfinite(n_line)):
                    return False, float("nan"), float("nan"), float("nan")
                ne = np.asarray(n_line[mask], dtype=np.float64)
                nmin = float(np.nanmin(ne)) if ne.size else float("nan")
                nmax = float(np.nanmax(ne)) if ne.size else float("nan")
                viol = float(np.max(np.maximum(n_lo_acc - ne, 0.0) + np.maximum(ne - n_hi_acc, 0.0))) if ne.size else float("inf")
                ok = bool(np.all(ne >= n_lo_acc) and np.all(ne <= n_hi_acc))
                return ok, nmin, nmax, viol

            ok_sell, sell_min, sell_max, sell_viol = _accept_stats(p_sell)
            ok_lbfgs, lbfgs_min, lbfgs_max, lbfgs_viol = _accept_stats(p_lbfgs)
            if not ok_sell and ok_lbfgs:
                logger.info(
                    "Sellmeier 3-poles: polish candidate out of band n[%.2f,%.2f] (min=%.6f max=%.6f viol=%.3g); keeping L-BFGS-B (min=%.6f max=%.6f viol=%.3g).",
                    n_lo_acc,
                    n_hi_acc,
                    sell_min,
                    sell_max,
                    sell_viol,
                    lbfgs_min,
                    lbfgs_max,
                    lbfgs_viol,
                )
                p_sell = np.asarray(p_lbfgs, dtype=np.float64)
                ok_sell = ok_lbfgs
                sell_min, sell_max, sell_viol = lbfgs_min, lbfgs_max, lbfgs_viol

            if not ok_sell:
                logger.warning(
                    "Sellmeier 3-poles fit out of band but kept for competitiveness: n[%.2f, %.2f] -> min=%.6f max=%.6f viol=%.3g",
                    n_lo_acc,
                    n_hi_acc,
                    sell_min,
                    sell_max,
                    sell_viol,
                )

            n_out_sell = IndexCore.sellmeier_2poles_const_eval(p_sell, wl_full_um)
            if not np.all(np.isfinite(n_out_sell)):
                raise ValueError("non-finite output")
            n_eval = np.asarray(n_out_sell[mask], dtype=np.float64)

            rmse_unweighted = float(np.sqrt(np.mean((n_eval - n_fit) ** 2)))

            wrmse = float(np.sqrt(np.mean(((n_eval - n_fit) * w_fit_sell) ** 2)))

            logger.info(
                "Sellmeier 3-poles fit stats: wrmse=%.6g | rmse=%.6g | n_range_fit=[%.6f, %.6f] | n@edges=[%.6f, %.6f]",
                wrmse,
                rmse_unweighted,
                float(np.min(n_eval)),
                float(np.max(n_eval)),
                float(n_eval[0]),
                float(n_eval[-1]),
            )

            logger.info(
                "Sellmeier coefficients accepted: A=%.9g | B1=%.9g | L1=%.9g m | B2=%.9g | L2=%.9g m | B3=%.9g | L3=%.9g m",
                float(p_sell[0]),
                float(p_sell[1]),
                float(p_sell[2]),
                float(p_sell[3]),
                float(p_sell[4]),
                float(p_sell[5]),
                float(p_sell[6]),
            )

            if log_l1l2:
                _ln1 = float(np.log(max(float(p_sell[2]), 1.0e-300)))

                _ln2 = float(np.log(max(float(p_sell[4]), 1.0e-300)))

                _ln3 = float(np.log(max(float(p_sell[6]), 1.0e-300)))

                _lg10 = float(np.log(10.0))

                logger.info(
                    "Sellmeier (reparam. ln L): u1=ln(L1)=%.9g | u2=ln(L2)=%.9g | u3=ln(L3)=%.9g "
                    "| log10(L1)=%.9g | log10(L2)=%.9g | log10(L3)=%.9g",
                    _ln1,
                    _ln2,
                    _ln3,
                    _ln1 / _lg10,
                    _ln2 / _lg10,
                    _ln3 / _lg10,
                )

            # 3-term standard variant (n2=1+Bi*λ2/(λ2-Ci)) for literature/catalog compatibility.
            c_hi = max(1.0e-15, (lam_min_um * float(SELLMEIER_3TERM_C_FRAC_MAX)) ** 2)
            b_bounds = (-200.0, 200.0)
            c_bounds = (1.0e-15, c_hi)
            std_bounds = (
                [b_bounds[0], c_bounds[0], b_bounds[0], c_bounds[0], b_bounds[0], c_bounds[0]],
                [b_bounds[1], c_bounds[1], b_bounds[1], c_bounds[1], b_bounds[1], c_bounds[1]],
            )

            def _std_seed_from_2p(p2: np.ndarray) -> np.ndarray:
                p2 = np.asarray(p2, dtype=np.float64)
                seed = np.asarray(
                    [
                        p2[1],
                        min(c_hi, max(1.0e-15, p2[2] ** 2)),
                        p2[3],
                        min(c_hi, max(1.0e-15, p2[4] ** 2)),
                        p2[5],
                        min(c_hi, max(1.0e-15, p2[6] ** 2)),
                    ],
                    dtype=np.float64,
                )
                return np.clip(seed, std_bounds[0], std_bounds[1])

            def _std_residuals(p_std: np.ndarray) -> np.ndarray:
                pred = _sellmeier_3term_standard_eval(p_std, wl_fit_um)
                r = (pred - n_fit) * w_fit_sell * 1000.0
                return np.asarray(r, dtype=np.float64)

            candidates: list[tuple[str, np.ndarray, np.ndarray, float, dict]] = []
            candidates.append(
                (
                    "analytic-sellmeier-3poles-A",
                    np.asarray(p_sell, dtype=np.float64),
                    np.asarray(n_out_sell, dtype=np.float64),
                    float(wrmse),
                    {"sellmeier_optim_log_l1l2": log_l1l2},
                )
            )

            try:
                p0_std = _std_seed_from_2p(p_sell)
                res_std = least_squares(
                    _std_residuals,
                    p0_std,
                    bounds=std_bounds,
                    loss="linear",
                    max_nfev=max(1200, int(ls_max_nfev)),
                )
                p_std = np.asarray(res_std.x, dtype=np.float64)
                n_out_std = _sellmeier_3term_standard_eval(p_std, wl_full_um)
                n_std_fit = np.asarray(n_out_std[mask], dtype=np.float64)

                if np.all(np.isfinite(n_std_fit)) and np.all((n_std_fit >= n_lo_acc) & (n_std_fit <= n_hi_acc)):
                    wrmse_std = float(np.sqrt(np.mean(((n_std_fit - n_fit) * w_fit_sell) ** 2)))
                    candidates.append(
                        (
                            "analytic-sellmeier-3term-standard",
                            p_std,
                            np.asarray(n_out_std, dtype=np.float64),
                            wrmse_std,
                            {},
                        )
                    )
                    logger.info(
                        "Sellmeier standard 3-term candidate: wrmse=%.6g | rmse=%.6g",
                        wrmse_std,
                        float(np.sqrt(np.mean((n_std_fit - n_fit) ** 2))),
                    )
            except NUMERICAL_FAULT_EXCEPTIONS:
                logger.info("Sellmeier standard 3-term: fit unavailable, keeping 3-poles variant.")

            best_src, best_coeffs, best_curve, _best_wrmse, best_extra = min(
                candidates,
                key=lambda t: float(t[3]),
            )

            if best_src != "analytic-sellmeier-3poles-A":
                logger.info(
                    "Sellmeier selection: variante standard 3-termes retenue (plus proche, wrmse=%.6g).",
                    float(_best_wrmse),
                )

            return (
                np.asarray(best_curve, dtype=np.float64),
                best_src,
                np.asarray(best_coeffs, dtype=np.float64),
                best_extra,
            )

        except (ValueError, RuntimeError, ArithmeticError) as ex:
            logger.warning("Sellmeier 3-poles fit failed: %s -> fallback to Polynomial.", str(ex))
            return None, "fallback-raw-sell2p-error", None, {}

        except NUMERICAL_FAULT_EXCEPTIONS:
            logger.exception("Sellmeier 3-poles fit unexpected failure -> fallback to Polynomial.")
            return None, "fallback-raw-sell2p-exception", None, {}

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

        n_raw = np.asarray(n_raw, dtype=np.float64)

        wl = np.asarray(wl_nm, dtype=np.float64)

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


class IndexTableDialog(QDialog):
    def __init__(
        self,
        wl,
        n_results_raw,
        n_results_by_model: dict[str, dict[str, np.ndarray]],
        rmse_row: dict[str, dict[str, float]],
        *,
        fit_meta_by_key: dict[str, dict[str, dict]] | None = None,
        fit_wl_lo: float | None = None,
        fit_wl_hi: float | None = None,
        spectral_wl_lo: float | None = None,
        spectral_wl_hi: float | None = None,
    ):

        super().__init__()

        self.setWindowTitle("Substrate Refractive Index (n)")

        self.resize(1100, 820)

        self.setStyleSheet(f"background-color: {CertusTheme.BACKGROUND}; color: {CertusTheme.TEXT_MAIN};")

        layout = QVBoxLayout(self)

        layout.addWidget(
            create_styled_label(
                "Refractive index: 3 laws compared (RMSE on 1st row; "
                "by series, law columns sorted by increasing RMSE, left \u2192 right)",
                style="subtitle",
            )
        )

        self.chk_only_cauchy = QCheckBox("Hide Raw points")

        self.chk_only_cauchy.setChecked(False)

        self.chk_only_cauchy.stateChanged.connect(self.toggle_raw_plots)

        layout.addWidget(self.chk_only_cauchy)

        if fit_wl_lo is not None and fit_wl_hi is not None:
            _lo_d = float(min(fit_wl_lo, fit_wl_hi))

            _hi_d = float(max(fit_wl_lo, fit_wl_hi))

            _hint = QLabel(
                f"Table rows and plot bands: grayed if \u03bb out of fit window "
                f"[{_lo_d:.1f}, {_hi_d:.1f}] nm (extrapolation / out-of-fit)."
            )

            _hint.setWordWrap(True)

            _hint.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px;")

            layout.addWidget(_hint)

        self.raw_items = []

        bad_model: dict[str, set[str]] = {bk: _bad_model_labels(rmse_row.get(bk, {})) for bk in n_results_raw.keys()}

        self.plot = CertusScientificPlot(title="Refractive index vs Wavelength")

        self.plot.setMinimumHeight(400)

        self.plot.addLegend(offset=(10, 10))

        self.plot.showGrid(x=True, y=True, alpha=0.3)

        self.plot.setLabel("bottom", "Wavelength (nm)")

        self.plot.setLabel("left", "Index (n)")

        wl_plot = np.asarray(wl, dtype=np.float64)

        fit_mask_plot = None

        if fit_wl_lo is not None and fit_wl_hi is not None:
            fit_mask_plot = _substrate_index_geom_fit_mask(wl_plot, float(fit_wl_lo), float(fit_wl_hi))

        colors = [CertusTheme.BRAND_DESIGN, CertusTheme.WARNING, "#9b59b6", "#34495e"]

        _fit_pen_styles = [
            (2.4, Qt.PenStyle.SolidLine),
            (2.0, Qt.PenStyle.DashLine),
            (2.0, Qt.PenStyle.DotLine),
        ]

        for i, key in enumerate(n_results_raw.keys()):
            y_raw = n_results_raw[key]

            c = pg.mkColor(colors[i % len(colors)])

            c_raw = pg.mkColor(c)

            c_raw.setAlpha(150)

            raw_item = _pg_plot_scatter_split_band(
                self.plot,
                wl,
                y_raw,
                fit_mask_plot,
                pg.mkPen(color=c_raw, width=1.5),
                pg.mkPen(color=CertusTheme.TEXT_SUB, width=1.2),
                name=f"{key} (Raw)",
            )

            self.raw_items.append(raw_item)

            bym = n_results_by_model.get(key, {})

            for pi, (_mk, mlabel) in enumerate(SUBSTRATE_INDEX_MODELS):
                arr = bym.get(mlabel)

                if arr is None:
                    continue

                if mlabel in bad_model.get(key, set()):
                    pc = pg.mkColor(CertusTheme.TEXT_SUB)

                    pc.setAlpha(160)

                else:
                    pc = pg.mkColor(c)

                    pc.setAlpha(220)

                pw, pst = _fit_pen_styles[pi % 3]

                _pg_plot_xy_split_band(
                    self.plot,
                    wl,
                    arr,
                    fit_mask_plot,
                    pg.mkPen(color=pc, width=pw, style=pst),
                    pg.mkPen(
                        color=CertusTheme.TEXT_SUB,
                        width=max(1.2, pw - 0.5),
                        style=pst,
                    ),
                    name=f"{key} ({mlabel})",
                )

        if fit_wl_lo is not None and fit_wl_hi is not None and wl_plot.size:
            _wmn = float(np.nanmin(wl_plot))

            _wmx = float(np.nanmax(wl_plot))

            if np.isfinite(_wmn) and np.isfinite(_wmx) and _wmx > _wmn:
                _add_pg_fit_band_outside_shading(self.plot, float(fit_wl_lo), float(fit_wl_hi), _wmn, _wmx)

        vb = self.plot.getViewBox()

        vb.enableAutoRange(axis=pg.ViewBox.XYAxes, enable=True)

        self.plot.autoRange()

        attach_excel_clipboard_context_menu(self.plot)

        layout.addWidget(wrap_scientific_plot_with_toolbar(self, self.plot))

        self.wl = wl

        self.n_results_by_model = n_results_by_model

        self.n_results_raw = n_results_raw

        self.rmse_row = rmse_row

        self.fit_meta_by_key = fit_meta_by_key if fit_meta_by_key is not None else {}

        self.fit_wl_lo = fit_wl_lo

        self.fit_wl_hi = fit_wl_hi

        self.spectral_wl_lo = spectral_wl_lo

        self.spectral_wl_hi = spectral_wl_hi

        self._models_order_by_bk: dict[str, list[tuple[str, str]]] = {
            bk: _substrate_index_models_ordered_by_rmse(rmse_row.get(bk, {})) for bk in n_results_raw.keys()
        }

        col_names = ["lambda (nm)"]

        for bk in self.n_results_raw.keys():
            col_names.append(f"{bk} (Raw)")

            for _mk, mlabel in self._models_order_by_bk[bk]:
                col_names.append(f"{bk} ({mlabel})")

        bad_column = [False] * len(col_names)

        _ci = 1

        for _bk in self.n_results_raw.keys():
            bad_column[_ci] = False

            _ci += 1

            rms_b = self.rmse_row.get(_bk, {})

            _mv = _rms_triplet(rms_b)

            _best = _best_finite_rmse_from_triplet(_mv)

            for _mk, mlabel in self._models_order_by_bk[_bk]:
                _j = _MODEL_LABEL_TO_INDEX[mlabel]

                bad_column[_ci] = _rmse_is_bad_vs_best(_mv[_j], _best)

                _ci += 1

        table = ExcelTableWidget()

        n_data_rows = len(wl)

        table.setRowCount(1 + n_data_rows)

        table.setColumnCount(len(col_names))

        table.setHorizontalHeaderLabels(col_names)

        _hh = table.horizontalHeader()

        for _c in range(len(col_names)):
            _hh.setSectionResizeMode(_c, QHeaderView.ResizeMode.Interactive)

        _hh.setMinimumSectionSize(52)

        _hh.setStretchLastSection(False)

        self.table = table

        rmse_font = QFont()

        rmse_font.setBold(True)

        rmse_font.setPointSize(max(rmse_font.pointSize(), 11))

        _col_base_raw: dict[str, int] = {}

        _ix_hdr = 1

        for _bk in self.n_results_raw.keys():
            _col_base_raw[_bk] = _ix_hdr

            _ix_hdr += 1 + _N_SUBSTRATE_MODELS

        it0 = QTableWidgetItem("RMSE (fit window)")

        it0.setFont(rmse_font)

        it0.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        it0.setBackground(QBrush(QColor(CertusTheme.SURFACE)))

        table.setItem(0, 0, it0)

        for bk in self.n_results_raw.keys():
            base = _col_base_raw[bk]

            rms = self.rmse_row.get(bk, {})

            model_vals = _rms_triplet(rms)

            best_v = _best_finite_rmse_from_triplet(model_vals)

            ir = QTableWidgetItem("")

            ir.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            ir.setFont(rmse_font)

            ir.setBackground(QBrush(QColor(CertusTheme.SURFACE)))

            table.setItem(0, base, ir)

            for j, (_mk, mlabel) in enumerate(self._models_order_by_bk[bk]):
                v = float(rms.get(mlabel, float("nan")))

                txt = f"{v:.6f}" if np.isfinite(v) else ""

                cell = QTableWidgetItem(txt)

                cell.setFont(rmse_font)

                cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                cell.setBackground(QBrush(QColor(CertusTheme.SURFACE)))

                if _rmse_is_best_fit(v, best_v):
                    cell.setForeground(QBrush(QColor(CertusTheme.SUCCESS)))

                elif _rmse_is_bad_vs_best(v, best_v):
                    cell.setForeground(QBrush(QColor(CertusTheme.TEXT_SUB)))

                else:
                    cell.setForeground(QBrush(QColor(CertusTheme.TEXT_MAIN)))

                table.setItem(0, base + 1 + j, cell)

        wl_arr = np.asarray(wl, dtype=np.float64)

        row_outside_fit_brush = QBrush(QColor(CertusTheme.BORDER))

        if self.fit_wl_lo is not None and self.fit_wl_hi is not None:
            m_band_geom = _substrate_index_geom_fit_mask(wl_arr, float(self.fit_wl_lo), float(self.fit_wl_hi))

            finite_n_any = np.zeros(len(wl_arr), dtype=bool)

            for arr in self.n_results_raw.values():
                finite_n_any |= np.isfinite(np.asarray(arr, dtype=np.float64))

            bold_wl_row = m_band_geom & np.isfinite(wl_arr) & finite_n_any

            outside_fit_row = (~m_band_geom) & np.isfinite(wl_arr) & finite_n_any

        else:
            bold_wl_row = np.zeros(len(wl), dtype=bool)

            outside_fit_row = np.zeros(len(wl), dtype=bool)

        for i in range(n_data_rows):
            r = 1 + i

            row_vals = [f"{wl[i]:.1f}"]

            for bk in self.n_results_raw.keys():
                row_vals.append(f"{self.n_results_raw[bk][i]:.4f}")

                bym = self.n_results_by_model.get(bk, {})

                for _mk, mlabel in self._models_order_by_bk[bk]:
                    arr = bym.get(mlabel)

                    row_vals.append(f"{arr[i]:.4f}" if arr is not None else "")

            for j, txt in enumerate(row_vals):
                it = QTableWidgetItem(txt)

                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                if bool(outside_fit_row[i]):
                    it.setBackground(row_outside_fit_brush)

                    it.setForeground(QBrush(QColor(CertusTheme.TEXT_SUB)))

                elif j > 0 and j < len(bad_column) and bad_column[j]:
                    it.setForeground(QBrush(QColor(CertusTheme.TEXT_SUB)))

                if j == 0 and bool(bold_wl_row[i]):
                    fnt = QFont(it.font())

                    fnt.setBold(True)

                    it.setFont(fnt)

                table.setItem(r, j, it)

        layout.addWidget(table)

        btn_row = QHBoxLayout()

        btn_params = create_styled_button("Law parameters (Poly., Sellmeier, Spline)", variant="secondary")

        btn_params.clicked.connect(self.show_model_params_dialog)

        btn_copy = create_styled_button(" Copy to Clipboard", variant="primary")

        btn_copy.clicked.connect(functools.partial(self.copy_to_clipboard, col_names))

        btn_row.addWidget(btn_params)

        btn_row.addStretch()

        btn_row.addWidget(btn_copy)

        layout.addLayout(btn_row)

    def toggle_raw_plots(self, state):

        visible = state == Qt.CheckState.Unchecked.value

        for item in self.raw_items:
            item.setVisible(visible)

    def copy_to_clipboard(self, col_names):

        header_lines: list[str] = [
            "CERTUS Substrate Index: 3 laws comparison (Polynomial, Sellmeier 3-poles, Spline n B-spline LSQ).",
            "RMSE (unweighted) calculated on fit window, vs raw n.",
        ]

        if self.fit_wl_lo is not None and self.fit_wl_hi is not None:
            header_lines.append(
                f"Fit zone (data): \u03bb = [{float(self.fit_wl_lo):.1f}, {float(self.fit_wl_hi):.1f}] nm"
            )

        if self.spectral_wl_lo is not None and self.spectral_wl_hi is not None:
            header_lines.append(
                f"n(\u03bb) evaluated on full measured band: \u03bb = [{float(self.spectral_wl_lo):.1f}, {float(self.spectral_wl_hi):.1f}] nm"
            )

        header_lines.append("")

        for bk in self.n_results_raw.keys():
            header_lines.append(f"=== {bk} ===")

            rms = self.rmse_row.get(bk, {})

            for _mk, mlabel in self._models_order_by_bk[bk]:
                v = rms.get(mlabel, float("nan"))

                header_lines.append(f"RMSE {mlabel}: {v:.6g}" if np.isfinite(v) else f"RMSE {mlabel}: ")

            meta_block = self.fit_meta_by_key.get(bk, {})

            for _mk, mlabel in self._models_order_by_bk[bk]:
                meta = meta_block.get(mlabel, {})

                src = str(meta.get("source", "unknown"))

                header_lines.append(f"--- {mlabel} ---")

                header_lines.append(IndexCore._clipboard_law_line_from_source(src, _mk))

                header_lines.append(IndexCore._clipboard_coeffs_line_from_source(src, meta.get("coeffs"), meta=meta))

                header_lines.append(f"internal source: {src}")

            header_lines.append("")

        header_lines.append("=== Table (TSV) ===")

        text = "\n".join(header_lines) + "\n"

        text += "\t".join(col_names) + "\n"

        row0 = [col_names[0]]

        for bk in self.n_results_raw.keys():
            row0.append("")

            rms = self.rmse_row.get(bk, {})

            for _mk, mlabel in self._models_order_by_bk[bk]:
                v = rms.get(mlabel, float("nan"))

                row0.append(f"{v:.6f}" if np.isfinite(v) else "")

        text += "\t".join(row0) + "\n"

        for i in range(len(self.wl)):
            row = [f"{self.wl[i]:.1f}"]

            for bk in self.n_results_raw.keys():
                row.append(f"{self.n_results_raw[bk][i]:.4f}")

                bym = self.n_results_by_model.get(bk, {})

                for _mk, mlabel in self._models_order_by_bk[bk]:
                    arr = bym.get(mlabel)

                    row.append(f"{arr[i]:.4f}" if arr is not None else "")

            text += "\t".join(row) + "\n"

        QApplication.clipboard().setText(text)

        QMessageBox.information(self, "Copied", "Table + RMSE + laws/coefficients copied to clipboard.")

    def show_model_params_dialog(self):

        lines: list[str] = [
            "CERTUS Substrate Index: analytical law parameters",
            "",
        ]

        def _bk_best_rmse_sort_key(bk: str) -> tuple:

            best = _best_finite_rmse_from_triplet(_rms_triplet(self.rmse_row.get(bk, {})))

            if not np.isfinite(best):
                return (1, float("inf"), str(bk))

            return (0, best, str(bk))

        bks_dialog_order = sorted(self.n_results_raw.keys(), key=_bk_best_rmse_sort_key)

        for bk in bks_dialog_order:
            lines.append(f"=== {bk} ===")

            meta_block = self.fit_meta_by_key.get(bk, {})

            rms_b = self.rmse_row.get(bk, {})

            for rank, (_mk, mlabel) in enumerate(self._models_order_by_bk[bk]):
                meta = meta_block.get(mlabel, {})

                src = str(meta.get("source", "unknown"))

                coeffs = meta.get("coeffs")

                req_mk = str(meta.get("requested_model_kind", _mk))

                rmse_v = rms_b.get(mlabel, float("nan"))

                best_tag = "  best RMSE (this series)" if rank == 0 and np.isfinite(rmse_v) else ""

                lines.append(f"[{mlabel}]{best_tag}")

                lines.append(
                    f"RMSE (fit vs raw n, fit window): {float(rmse_v):.6g}"
                    if np.isfinite(rmse_v)
                    else "RMSE (fit vs raw n, fit window): "
                )

                lines.append(IndexCore._clipboard_law_line_from_source(src, req_mk))

                lines.append(f"internal source: {src}")

                lines.append(IndexCore._clipboard_coeffs_line_from_source(src, coeffs, meta=meta))

                lines.append("")

            lines.append("")

        text = "\n".join(lines).strip() + "\n"

        dlg = QDialog(self)

        dlg.setWindowTitle("Law parameters")

        dlg.resize(980, 620)

        dlg.setStyleSheet(f"background-color: {CertusTheme.BACKGROUND}; color: {CertusTheme.TEXT_MAIN};")

        layout = QVBoxLayout(dlg)

        info = QLabel(
            f"<span style='color:{CertusTheme.TEXT_SUB};font-size:11px;'>"
            "RMSE (unweighted, vs raw n on fit window), description and coefficients. "
            "Series (blocks === ... ===): from minimal best RMSE to worst, top of window. "
            "In each series: laws from best to worst RMSE (like table columns).</span>"
        )

        info.setWordWrap(True)

        layout.addWidget(info)

        txt = QTextEdit()

        txt.setReadOnly(True)

        txt.setText(text)

        layout.addWidget(txt)

        brow = QHBoxLayout()

        btn_copy = create_styled_button(" Copy", variant="secondary")

        btn_copy.clicked.connect(functools.partial(QApplication.clipboard().setText, text))

        btn_close = create_styled_button("Close", variant="primary")

        btn_close.clicked.connect(dlg.accept)

        brow.addWidget(btn_copy)

        brow.addStretch()

        brow.addWidget(btn_close)

        layout.addLayout(brow)

        dlg.exec()


class SubstrateIndexGUI(QMainWindow):
    def __init__(self):

        super().__init__()

        self.setWindowTitle(f"CERTUS SUBSTRATE INDEX v{__version__}")

        self.resize(1200, 750)

        self.setStyleSheet(f"background-color: {CertusTheme.BACKGROUND};")

        set_certus_window_icon(self)

        self.df: pd.DataFrame | None = None

        self.settings = QSettings("CERTUS_SUITE", "SubstrateIndex")

        self.last_dir = self.settings.value("last_dir", "")

        self.current_window = 15

        self.current_poly = 2

        self.current_heavy = 25
        self.validation_status = "OK"
        self.validation_warnings: list[str] = []
        self.last_run_manifest: dict[str, object] | None = None

        self._setup_ui()
        self._attach_ui_log_handler()

    def export_substrate_datasheet(self) -> None:
        """P1-11: Export versioned substrate datasheet (JSON)."""
        if self.last_run_manifest is None:
            QMessageBox.warning(self, "Export", "No result available. Run a Sellmeier fit first.")
            return

        from PyQt6.QtWidgets import QFileDialog
        import json
        from datetime import datetime

        default_fn = f"Substrate_Datasheet_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        path, _ = QFileDialog.getSaveFileName(self, "Export Datasheet", default_fn, "JSON Files (*.json)")
        if not path:
            return

        # Prepare payload from manifest
        payload = {
            "metadata": {
                "instrument": "CERTUS SUBSTRATE INDEX",
                "version": __version__,
                "export_date": datetime.now().isoformat(),
                "status": self.validation_status,
            },
            "substrate": {
                "source_file": self.last_run_manifest.get("source_file"),
                "file_hash": self.last_run_manifest.get("file_hash"),
                "sellmeier_coeffs": self.last_run_manifest.get("sellmeier_coeffs"),
                "fit_rmse": self.last_run_manifest.get("rmse"),
                "lambda_range_nm": self.last_run_manifest.get("lambda_range_nm"),
            },
        }

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=4)
            self.log(f"Datasheet exported to {Path(path).name}", "SUCCESS")
        except (OSError, TypeError, ValueError) as e:
            self.log(f"Export failed: {e}", "ERROR")
            QMessageBox.critical(self, "Export Error", str(e))

    class _UILogHandler(logging.Handler):
        def __init__(self, append_fn):

            super().__init__(level=logging.INFO)

            self._append_fn = append_fn

            self.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", "%H:%M:%S"))

        def emit(self, record: logging.LogRecord) -> None:

            try:
                self._append_fn(self.format(record))

            except NUMERICAL_FAULT_EXCEPTIONS :
                pass

    def _attach_ui_log_handler(self) -> None:

        if not hasattr(self, "log_panel") or self.log_panel is None:
            return

        underlying_logger = getattr(logger, "logger", logger)
        for h in underlying_logger.handlers:
            if isinstance(h, SubstrateIndexGUI._UILogHandler):
                return

        h = SubstrateIndexGUI._UILogHandler(self.log_panel.log_text.append)

        h.setLevel(logging.INFO)

        underlying_logger.addHandler(h)

        self.log("UI log bridge attached (INFO+).", "INFO")

    def log(self, message: str, level: str = "INFO") -> None:

        level_u = str(level).upper().strip()

        _map = {
            "DEBUG": logger.debug,
            "INFO": logger.info,
            "WARNING": logger.warning,
            "ERROR": logger.error,
            "SUCCESS": logger.info,
        }

        _map.get(level_u, logger.info)(message)

    def _set_busy(self, busy: bool) -> None:

        if hasattr(self, "btn_load"):
            self.btn_load.setEnabled(not busy)

        if hasattr(self, "btn_calc_n"):
            self.btn_calc_n.setEnabled((not busy) and (self.df is not None))
        if hasattr(self, "btn_export_datasheet"):
            self.btn_export_datasheet.setEnabled((not busy) and (self.last_run_manifest is not None))

    def _get_fit_range_from_ui(self) -> tuple[float, float]:

        lo = float(self.fit_lmin_spin.value())

        hi = float(self.fit_lmax_spin.value())

        lo, hi = (min(lo, hi), max(lo, hi))

        if self.df is not None and not self.df.empty:
            wl = np.asarray(
                pd.to_numeric(self.df.iloc[:, 0], errors="coerce").values,
                dtype=np.float64,
            )

            m = np.isfinite(wl)

            if int(np.count_nonzero(m)) >= 2:
                wmin = float(np.min(wl[m]))

                wmax = float(np.max(wl[m]))

                lo = max(lo, wmin)

                hi = min(hi, wmax)

        if hi < lo:
            lo, hi = hi, lo

        return lo, hi

    def _on_fit_range_changed(self):

        if self.df is None:
            return

        # Immediately redraws preview to update out-of-fit shading.

        self.preview_plot()

    def _on_fit_range_spin_changed(self, *_args) -> None:

        self._on_fit_range_changed()

    def _apply_full_auto_sellmeier_mode(self) -> None:
        """Full auto mode: hides/disables manual Sellmeier settings."""

        auto_on = bool(self.sell_auto_chk.isChecked()) if hasattr(self, "sell_auto_chk") else True

        controls = [
            getattr(self, "sell_timeout_lbl", None),
            getattr(self, "sell_timeout_spin", None),
            getattr(self, "sell_de_lbl", None),
            getattr(self, "sell_de_iter_spin", None),
            getattr(self, "sell_ls_lbl", None),
            getattr(self, "sell_ls_nfev_spin", None),
        ]

        for w in controls:
            if w is None:
                continue

            w.setVisible(not auto_on)

            w.setEnabled(not auto_on)

    def _on_sell_auto_state_changed(self, *_args) -> None:

        self._apply_full_auto_sellmeier_mode()

    def _setup_ui(self):

        central_widget = QWidget()

        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)

        layout.setContentsMargins(0, 0, 0, 0)

        header = create_header_logo_widget(
            "CERTUS SUBSTRATE INDEX",
            "Index from spectral measurements",
            logo_width=200,
            module_name="CERTUS_SUBSTRATE_INDEX",
        )

        layout.addWidget(header)

        content = QWidget()

        c_layout = QVBoxLayout(content)

        c_layout.setContentsMargins(
            CertusTheme.SPACING_XL, CertusTheme.SPACING_XL, CertusTheme.SPACING_XL, CertusTheme.SPACING_XL
        )

        tools = QFrame()

        tools.setStyleSheet(
            f"background-color: {CertusTheme.SURFACE}; border-radius: {CertusTheme.RADIUS_LG}px; border: 1px solid {CertusTheme.BORDER};"
        )

        row = QHBoxLayout(tools)

        row.setContentsMargins(
            CertusTheme.SPACING_MD, CertusTheme.SPACING_MD, CertusTheme.SPACING_MD, CertusTheme.SPACING_MD
        )

        self.btn_load = create_styled_button("Load Data (.xlsx/.xls)", variant="primary")

        self.btn_load.clicked.connect(self.load_file)

        row.addWidget(QLabel("lambda min fit (nm):"))

        self.fit_lmin_spin = QDoubleSpinBox()

        self.fit_lmin_spin.setRange(100.0, 20000.0)

        self.fit_lmin_spin.setDecimals(1)

        self.fit_lmin_spin.setSingleStep(50.0)

        self.fit_lmin_spin.setValue(400.0)

        self.fit_lmin_spin.valueChanged.connect(self._on_fit_range_spin_changed)

        row.addWidget(self.fit_lmin_spin)

        row.addSpacing(8)

        row.addWidget(QLabel("lambda max fit (nm):"))

        self.fit_lmax_spin = QDoubleSpinBox()

        self.fit_lmax_spin.setRange(100.0, 20000.0)

        self.fit_lmax_spin.setDecimals(1)

        self.fit_lmax_spin.setSingleStep(50.0)

        self.fit_lmax_spin.setValue(5000.0)

        self.fit_lmax_spin.valueChanged.connect(self._on_fit_range_spin_changed)

        row.addWidget(self.fit_lmax_spin)

        row.addSpacing(12)

        self.sell_auto_chk = QCheckBox("Sellmeier full auto")

        self.sell_auto_chk.setChecked(True)

        self.sell_auto_chk.setToolTip("Active: automatic internal Sellmeier parameters.")

        self.sell_auto_chk.stateChanged.connect(self._on_sell_auto_state_changed)

        row.addWidget(self.sell_auto_chk)

        row.addSpacing(10)

        self.sell_timeout_lbl = QLabel("Sellmeier budget (s):")

        row.addWidget(self.sell_timeout_lbl)

        self.sell_timeout_spin = QDoubleSpinBox()

        self.sell_timeout_spin.setRange(0.0, 120.0)

        self.sell_timeout_spin.setDecimals(1)

        self.sell_timeout_spin.setSingleStep(1.0)

        self.sell_timeout_spin.setValue(8.0)

        self.sell_timeout_spin.setToolTip("0 = unlimited. Time limit for Sellmeier global optimization.")

        row.addWidget(self.sell_timeout_spin)

        row.addSpacing(8)

        self.sell_de_lbl = QLabel("Sellmeier DE iters:")

        row.addWidget(self.sell_de_lbl)

        self.sell_de_iter_spin = QSpinBox()

        self.sell_de_iter_spin.setRange(10, 2000)

        self.sell_de_iter_spin.setSingleStep(25)

        self.sell_de_iter_spin.setValue(300)

        self.sell_de_iter_spin.setToolTip("Max L-BFGS-B iterations (Sellmeier, global phase).")

        row.addWidget(self.sell_de_iter_spin)

        row.addSpacing(8)

        self.sell_ls_lbl = QLabel("Sellmeier LS nfev:")

        row.addWidget(self.sell_ls_lbl)

        self.sell_ls_nfev_spin = QSpinBox()

        self.sell_ls_nfev_spin.setRange(100, 50000)

        self.sell_ls_nfev_spin.setSingleStep(100)

        self.sell_ls_nfev_spin.setValue(3000)

        self.sell_ls_nfev_spin.setToolTip("Max evaluations for least_squares (polish after L-BFGS-B, Sellmeier).")

        row.addWidget(self.sell_ls_nfev_spin)

        row.addSpacing(8)

        self.sell_log_l_chk = QCheckBox("Sellmeier L1,L2 en ln (optimization.)")

        self.sell_log_l_chk.setChecked(bool(SELLMEIER_DEFAULT_LOG_L1L2))

        self.sell_log_l_chk.setToolTip(
            "If checked: optimization on ui=ln(Li) then Li=exp(ui) (log bounds). Otherwise: Li directly."
        )

        row.addWidget(self.sell_log_l_chk)

        row.addSpacing(12)

        row.addWidget(
            QLabel(
                f"<span style='color:{CertusTheme.TEXT_SUB};font-size:11px;'>"
                "Systematic calculation of <b>3</b> laws (Polynomial, Sellmeier, Spline) to compare RMSE (1st row).</span>"
            )
        )

        self.btn_calc_n = create_styled_button("Calc Substrate Index (3 laws)", variant="secondary")

        self.btn_calc_n.clicked.connect(self.calculate_index)

        self.btn_calc_n.setEnabled(False)

        self.btn_export_datasheet = create_styled_button("Export Datasheet (JSON)", variant="outline")
        self.btn_export_datasheet.setToolTip("Export substrate Sellmeier coefficients and metadata to JSON.")
        self.btn_export_datasheet.clicked.connect(self.export_substrate_datasheet)
        self.btn_export_datasheet.setEnabled(False)

        row.addWidget(self.btn_load)
        row.addWidget(self.btn_export_datasheet)

        row.addSpacing(20)

        row.addStretch()

        row.addWidget(self.btn_calc_n)

        c_layout.addWidget(tools)

        hint = QLabel(
            f"<span style='color:{CertusTheme.TEXT_SUB};font-size:11px;'>"
            "Only spectral columns whose <b>name</b> indicates a <b>bare substrate</b> "
            "(e.g. <i>substrate nu</i>, <i>sbst nu</i>, <i>SNU</i>, <i>BSUB</i>, <i>bare sub</i>, "
            "<i>no-coat</i>, <i>sans_dep</i>, <i>nu</i> isolated...) are loaded; "
            "filter / stack / target / design (including abbreviations) are ignored."
            "</span>"
        )

        hint.setWordWrap(True)

        c_layout.addWidget(hint)

        self.plot_widget = CertusScientificPlot(title="Spectra")

        self.plot_widget.addLegend(offset=(10, 10))

        self.plot_widget.showGrid(x=True, y=True, alpha=0.2)

        self.plot_widget.setLabel("bottom", "Wavelength (nm)")

        self.plot_widget.setLabel("left", "Amplitude")

        attach_excel_clipboard_context_menu(self.plot_widget)

        c_layout.addWidget(wrap_scientific_plot_with_toolbar(self, self.plot_widget))

        self.log_panel = CertusLogPanel(title="LOGS", visible=True, height=170)

        c_layout.addWidget(self.log_panel)

        layout.addWidget(content)

        self.progress_widget = EnhancedProgressWidget()

        if hasattr(self.progress_widget, "canceled"):
            self.progress_widget.canceled.connect(lambda: self.log("Cancellation requested by user...", "WARNING"))

        self.statusBar().addPermanentWidget(self.progress_widget)

        self._apply_full_auto_sellmeier_mode()

    def _is_cancel_requested(self) -> bool:

        return bool(
            hasattr(self, "progress_widget")
            and hasattr(self.progress_widget, "is_canceled")
            and self.progress_widget.is_canceled()
        )

    def load_file(self):

        self.progress_widget.start()

        self.progress_widget.set_time_budget(8.0)

        self.progress_widget.update(1, 1, phase="Load workbook")

        self.log("Loading measurement workbook...", "INFO")

        try:
            result = open_measurement_excel_interactive(
                self,
                start_dir=self.last_dir or "",
                caption="Open Data",
                round_wavelength_decimals=None,
            )

            if result is None:
                self.progress_widget.stop("Cancelled")

                return

            raw_df, path, self.last_dir = result
            self._last_loaded_measurement_path = str(path or "")

            self.settings.setValue("last_dir", self.last_dir)

            self.df, kept_spec, dropped_spec = _filter_dataframe_bare_substrate_columns(raw_df)

            if dropped_spec:
                logger.info(
                    "Substrate index: ignored columns (no bare substrate indicator in the name): %s",
                    "; ".join(dropped_spec[:40]) + ("; ..." if len(dropped_spec) > 40 else ""),
                )

            if not kept_spec:
                self.df = None

                self.btn_calc_n.setEnabled(False)

                QMessageBox.warning(
                    self,
                    "Bare substrate: no columns retained",
                    "No spectral column name indicates a **bare substrate** "
                    "(e.g. substrate nu, sbst nu, SNU, BSUB, bare sub, nocoat, sans_dep, "
                    "nu sub, empty sub, isolated word 'nu', etc.).\n\n"
                    "Filter or stack measurements are intentionally ignored.\n\n"
                    f"Columns present but excluded ({len(dropped_spec)}): "
                    + (", ".join(dropped_spec[:12]) + ("..." if len(dropped_spec) > 12 else "")),
                )

                self.progress_widget.stop("No bare-substrate columns")

                return

            self.btn_calc_n.setEnabled(True)

            # Measurement sheet imposes absolute lambda bounds; UI window stays inside these limits.

            wl_all = np.asarray(pd.to_numeric(self.df.iloc[:, 0], errors="coerce").values, dtype=np.float64)

            m_w = np.isfinite(wl_all)

            if int(np.count_nonzero(m_w)) >= 2:
                wmin = float(np.min(wl_all[m_w]))

                wmax = float(np.max(wl_all[m_w]))

                self.fit_lmin_spin.setRange(wmin, wmax)

                self.fit_lmax_spin.setRange(wmin, wmax)

                self.fit_lmin_spin.setValue(wmin)

                self.fit_lmax_spin.setValue(wmax)

            self.log(
                f"Substrate index: {Path(path).name}  "
                f"{len(kept_spec)} bare substrate column(s), {len(dropped_spec)} ignored.",
                "INFO",
            )

            logger.info(
                "Substrate index: loading %s  %d bare substrate column(s), %d ignored.",
                Path(path).name,
                len(kept_spec),
                len(dropped_spec),
            )

            self.progress_widget.update(1, 1, phase="Preview")

            self.preview_plot()

            self.progress_widget.stop("Loaded")

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            logger.error("Failed to load measurement sheet: %s", e)

            QMessageBox.critical(self, "Error", f"Failed to load measurement sheet:\n{e}")

            self.log(f"Load error: {e}", "ERROR")

            self.progress_widget.stop("Load failed")

    def preview_plot(self):

        if self.df is None:
            return

        self.plot_widget.clear()

        x = np.asarray(pd.to_numeric(self.df.iloc[:, 0], errors="coerce").values, dtype=np.float64)

        m_x = np.isfinite(x)

        if int(np.count_nonzero(m_x)) < 5:
            logger.warning("Substrate index preview: wavelength column has insufficient finite points.")

            return

        x = x[m_x]

        wmin, wmax = float(np.min(x)), float(np.max(x))

        lo_f, hi_f = self._get_fit_range_from_ui()

        if wmax > wmin:
            _add_pg_fit_band_outside_shading(self.plot_widget, lo_f, hi_f, wmin, wmax)

        fit_mask = _substrate_index_geom_fit_mask(x, lo_f, hi_f)

        y_raw = np.asarray(self.df.iloc[:, 1:].values, dtype=np.float64).T[:, m_x]

        y_clean = IndexCore.apply_dynamic_filtering(
            x, y_raw, self.current_window, self.current_poly, self.current_heavy
        )

        for i, col in enumerate(self.df.columns[1:]):
            color = [CertusTheme.BRAND_DESIGN, CertusTheme.BRAND_INDEX, CertusTheme.SUCCESS, CertusTheme.WARNING][i % 4]

            _pg_plot_xy_split_band(
                self.plot_widget,
                x,
                y_clean[i],
                fit_mask,
                pg.mkPen(color=color, width=2),
                pg.mkPen(color=CertusTheme.TEXT_SUB, width=1.6),
                name=str(col),
            )

        self.plot_widget.getViewBox().enableAutoRange(axis=pg.ViewBox.XYAxes, enable=True)

        self.plot_widget.autoRange()

    def _get_clean_fraction_column(self, x: np.ndarray, col_name) -> np.ndarray:

        y_raw = np.asarray(pd.to_numeric(self.df[col_name], errors="coerce").values, dtype=np.float64)

        m = np.isfinite(x) & np.isfinite(y_raw)

        if int(np.count_nonzero(m)) < 5:
            raise ValueError(f"Not enough finite points in column: {col_name}")

        if not np.all(m):
            y_raw = np.interp(x, x[m], y_raw[m])

        y_clean = IndexCore.apply_dynamic_filtering(
            x, y_raw, self.current_window, self.current_poly, self.current_heavy
        )

        return IndexCore.to_fraction(y_clean)

    def _compute_n_results(
        self,
        x: np.ndarray,
        groups: dict[str, list],
        wl_min_fit: float,
        wl_max_fit: float,
        *,
        sellmeier_timeout_s: float | None = None,
        sellmeier_de_maxiter: int = 300,
        sellmeier_ls_max_nfev: int = 3000,
        sellmeier_log_l1l2: bool | None = None,
    ) -> tuple[
        dict[str, np.ndarray],
        dict[str, dict[str, np.ndarray]],
        dict[str, dict[str, float]],
        dict[str, dict[str, dict]],
    ]:

        n_results_raw: dict[str, np.ndarray] = {}

        n_results_by_model: dict[str, dict[str, np.ndarray]] = {}

        rmse_row: dict[str, dict[str, float]] = {}

        n_fit_meta: dict[str, dict[str, dict]] = {}

        total_cols = sum(len(v) for v in groups.values())

        total_steps = max(total_cols * _N_SUBSTRATE_MODELS, 1)

        done_steps = 0

        col_idx = 0

        xa = np.asarray(x, dtype=np.float64)

        m_rmse_geom = IndexCore._fit_mask(xa, wl_min_fit, wl_max_fit) & np.isfinite(xa)

        def add_result(col_name, n_vals):

            nonlocal done_steps, col_idx

            if self._is_cancel_requested():
                raise RuntimeError("Calculation cancelled by user.")

            col_idx += 1

            if hasattr(self, "progress_widget"):
                self.progress_widget.update(
                    done_steps,
                    total_steps,
                    phase=f"Columns {col_idx}/{max(total_cols, 1)}",
                    extra_info=str(col_name),
                )

            n_raw_base = np.asarray(n_vals, dtype=np.float64)

            logger.info(
                "Fit column %d/%d: %s | n_raw_range=[%.6f, %.6f]",
                col_idx,
                max(total_cols, 1),
                str(col_name),
                float(np.nanmin(n_raw_base)),
                float(np.nanmax(n_raw_base)),
            )

            _i_min = int(np.argmin(n_raw_base))

            _i_max = int(np.argmax(n_raw_base))

            logger.info(
                "Column anchors: lambda@n_min=%.1fnm lambda@n_max=%.1fnm",
                float(xa[_i_min]),
                float(xa[_i_max]),
            )

            out_key = f"n ({col_name})"

            n_results_raw[out_key] = n_raw_base

            by_model: dict[str, np.ndarray] = {}

            rms_m: dict[str, float] = {}

            meta_m: dict[str, dict] = {}

            m_rmse_mask = m_rmse_geom & np.isfinite(n_raw_base)

            for mk, mlabel in SUBSTRATE_INDEX_MODELS:
                if self._is_cancel_requested():
                    raise RuntimeError("Calculation cancelled by user.")

                done_steps += 1

                if hasattr(self, "progress_widget"):
                    self.progress_widget.update(
                        done_steps,
                        total_steps,
                        phase=f"Fit {done_steps}/{total_steps}",
                        extra_info=f"{col_name}  {mlabel}",
                    )

                log_pre = mk == SUBSTRATE_INDEX_MODELS[0][0]

                _, n_fit, fit_meta = IndexCore.get_smoothed_and_fits(
                    n_raw_base,
                    xa,
                    wl_min_fit,
                    wl_max_fit,
                    model_kind=mk,
                    log_preprocess=log_pre,
                    sellmeier_timeout_s=sellmeier_timeout_s,
                    sellmeier_de_maxiter=sellmeier_de_maxiter,
                    sellmeier_ls_max_nfev=sellmeier_ls_max_nfev,
                    sellmeier_log_l1l2=sellmeier_log_l1l2,
                    progress_cb=None,
                )

                n_fit = np.asarray(n_fit, dtype=np.float64)

                by_model[mlabel] = n_fit

                if np.any(m_rmse_mask):
                    d = n_fit[m_rmse_mask] - n_raw_base[m_rmse_mask]

                    rmse_vs_raw = float(np.sqrt(np.mean(d * d)))

                else:
                    rmse_vs_raw = float("nan")

                meta_m[mlabel] = dict(fit_meta)

                src = str(fit_meta.get("source") or "")

                # Analytical rejection \u2192 raw monotonic curve: may coincide with n_raw (e.g. R after

                # enforce_normal_dispersion), hence RMSE=0; this score is not used to elect the best.

                if src.startswith("fallback-raw") or src == "skipped-insufficient-points":
                    rms_m[mlabel] = float("inf")

                    logger.info(
                        "Model %s | %s | RMSE(vs raw)=%.6g | source=%s - not eligible for best RMSE",
                        str(col_name),
                        mlabel,
                        rmse_vs_raw if np.isfinite(rmse_vs_raw) else float("nan"),
                        src,
                    )

                else:
                    rms_m[mlabel] = rmse_vs_raw if np.isfinite(rmse_vs_raw) else float("nan")

                    logger.info(
                        "Model %s | %s | RMSE(fit)=%.6g",
                        str(col_name),
                        mlabel,
                        float(rms_m[mlabel]) if np.isfinite(rms_m[mlabel]) else float("nan"),
                    )

            n_results_by_model[out_key] = by_model

            rmse_row[out_key] = rms_m

            n_fit_meta[out_key] = meta_m

            i_edge = int(np.argmin(np.abs(xa - 4500.0)))

            score_m: dict[str, float] = {}

            for _mk, _ml in SUBSTRATE_INDEX_MODELS:
                arr = by_model.get(_ml)

                if arr is None:
                    score_m[_ml] = float("inf")

                    continue

                score_m[_ml] = _model_selection_score(
                    rmse_fit=float(rms_m.get(_ml, float("nan"))),
                    n_fit=np.asarray(arr, dtype=np.float64),
                    wl_nm=xa,
                    fit_mask=m_rmse_mask,
                    fit_meta=meta_m.get(_ml, {}),
                    col_name=str(col_name),
                )

            best_lab = min(
                SUBSTRATE_INDEX_MODELS,
                key=lambda t: float(score_m.get(t[1], float("inf"))),
            )[1]

            n_best = by_model.get(best_lab, n_raw_base)

            _r = np.asarray(n_best, dtype=np.float64) - np.asarray(n_raw_base, dtype=np.float64)

            logger.info(
                "Fit column done: %s | best score=%s | score=%.6g | n@4500%.6f | rmse_fit(best)=%.6g",
                str(col_name),
                best_lab,
                float(score_m.get(best_lab, float("nan"))),
                float(n_best[i_edge]) if i_edge < len(n_best) else float("nan"),
                float(np.sqrt(np.mean((_r[m_rmse_mask]) ** 2))) if np.any(m_rmse_mask) else float("nan"),
            )

        for c in groups["t_2f"]:
            add_result(c, IndexCore.n_from_tnu2f(self._get_clean_fraction_column(x, c)))

        for c in groups["r_2f"]:
            n_r2f = IndexCore.n_from_rnu2f(self._get_clean_fraction_column(x, c))

            # R2f can exhibit high-lambda branch artifacts; stabilize before analytic fitting.

            n_r2f = IndexCore.enforce_normal_dispersion(x, n_r2f)

            add_result(c, n_r2f)

        for c in groups["r45s_1f"]:
            add_result(c, IndexCore.n_from_r45s_single_face(self._get_clean_fraction_column(x, c)))

        for c in groups["r45s_2f"]:
            add_result(
                c,
                IndexCore.n_from_r45s_single_face(
                    IndexCore.single_face_from_two_face(self._get_clean_fraction_column(x, c))
                ),
            )

        for c in groups["r45p_1f"]:
            add_result(c, IndexCore.n_from_r45p_single_face(self._get_clean_fraction_column(x, c)))

        for c in groups["r45p_2f"]:
            add_result(
                c,
                IndexCore.n_from_r45p_single_face(
                    IndexCore.single_face_from_two_face(self._get_clean_fraction_column(x, c))
                ),
            )

        return n_results_raw, n_results_by_model, rmse_row, n_fit_meta

    def calculate_index(self):

        if self.df is None:
            return

        self._set_busy(True)

        self.progress_widget.start()

        if hasattr(self.progress_widget, "enable_cancel"):
            self.progress_widget.enable_cancel(True)

        self.progress_widget.set_time_budget(25.0)

        self.progress_widget.update(1, 1, phase="Prepare data")

        self.log("Substrate index calculation started.", "INFO")

        try:
            x = np.asarray(pd.to_numeric(self.df.iloc[:, 0], errors="coerce").values, dtype=np.float64)

            m_x = np.isfinite(x)

            if int(np.count_nonzero(m_x)) < 5:
                QMessageBox.warning(self, "Wavelength column", "Invalid \u03bb column (not enough numerical points).")

                self.progress_widget.stop("Invalid wavelength column")

                return

            if not np.all(m_x):
                self.df = self.df.loc[m_x].reset_index(drop=True)

                x = np.asarray(pd.to_numeric(self.df.iloc[:, 0], errors="coerce").values, dtype=np.float64)

            wl_min_fit, wl_max_fit = self._get_fit_range_from_ui()

            if wl_min_fit >= wl_max_fit:
                QMessageBox.warning(self, "Fit range", "\u03bb min fit must be strictly less than \u03bb max fit.")

                self.progress_widget.stop("Invalid fit range")

                return

            groups = _classify_substrate_index_columns(self.df.columns[1:])

            if not any(groups.values()):
                QMessageBox.warning(self, "Column Not Found", "Could not locate expected columns.")

                self.progress_widget.stop("No matching columns")

                return

            if bool(self.sell_auto_chk.isChecked()):
                sell_timeout_cfg = 8.0

                sell_de_maxiter = 300

                sell_ls_max_nfev = 3000

                logger.info(
                    "Sellmeier full auto: budget=%.1fs | max iters L-BFGS-B=%d | polish LS nfev=%d",
                    float(sell_timeout_cfg),
                    int(sell_de_maxiter),
                    int(sell_ls_max_nfev),
                )

            else:
                sell_timeout_s = float(self.sell_timeout_spin.value())

                sell_timeout_cfg = None if sell_timeout_s <= 0.0 else sell_timeout_s

                sell_de_maxiter = int(self.sell_de_iter_spin.value())

                sell_ls_max_nfev = int(self.sell_ls_nfev_spin.value())

            sell_log_l1l2 = (
                bool(self.sell_log_l_chk.isChecked()) if hasattr(self, "sell_log_l_chk") else SELLMEIER_DEFAULT_LOG_L1L2
            )

            logger.info(
                "Sellmeier reparam. L1/L2/L3: %s",
                "ui=ln(Li) (optimization.)" if sell_log_l1l2 else "Li lineaire (natif)",
            )

            self.progress_widget.update(1, 1, phase="Fit 3 laws (toutes colonnes)")

            n_results_raw, n_results_by_model, rmse_row, n_fit_meta = self._compute_n_results(
                x,
                groups,
                wl_min_fit,
                wl_max_fit,
                sellmeier_timeout_s=sell_timeout_cfg,
                sellmeier_de_maxiter=sell_de_maxiter,
                sellmeier_ls_max_nfev=sell_ls_max_nfev,
                sellmeier_log_l1l2=sell_log_l1l2,
            )
            try:
                warn_list: list[str] = []
                for _by_model in n_fit_meta.values():
                    for _model_name, _meta in _by_model.items():
                        _src = str((_meta or {}).get("source") or "")
                        if _src.startswith("skipped-"):
                            warn_list.append(f"{_model_name}: fit skipped ({_src})")
                self.validation_warnings = warn_list
                self.validation_status = "WARNING_UNCERTAINTY_NOT_COMPUTED" if warn_list else "OK"
            except NUMERICAL_FAULT_EXCEPTIONS as exc:
                logger.warning("SUBSTRATE validation status synthesis failed: %s", exc)
                self.validation_status = "OK"
                self.validation_warnings = []
            try:
                status_val = ValidationStatus(str(self.validation_status))
            except ValueError:
                status_val = ValidationStatus.OK
            try:
                svc = SubstrateIndexService(
                    runner=lambda _cfg: {
                        "rmse_row": rmse_row,
                        "fit_window_nm": [float(wl_min_fit), float(wl_max_fit)],
                    }
                )
                req = SubstrateIndexRequest(
                    config={
                        "wl_min_fit": float(wl_min_fit),
                        "wl_max_fit": float(wl_max_fit),
                        "sellmeier_log_l1l2": bool(sell_log_l1l2),
                    },
                    source_paths=[
                        p for p in (str(getattr(self, "_last_loaded_measurement_path", "") or "").strip(),) if p
                    ],
                    seed=12345,
                    app_id="CERTUS_SUBSTRATE_INDEX",
                    app_version=__version__,
                    warnings=list(self.validation_warnings),
                    status=status_val,
                )
                self.last_run_manifest = svc.fit(req).manifest.to_dict()
            except NUMERICAL_FAULT_EXCEPTIONS as exc:
                logger.warning("SUBSTRATE manifest generation failed: %s", exc)
                self.last_run_manifest = None

            spec_lo = float(np.nanmin(x)) if x.size else float("nan")

            spec_hi = float(np.nanmax(x)) if x.size else float("nan")

            dialog = IndexTableDialog(
                x,
                n_results_raw,
                n_results_by_model,
                rmse_row,
                fit_meta_by_key=n_fit_meta,
                fit_wl_lo=float(wl_min_fit),
                fit_wl_hi=float(wl_max_fit),
                spectral_wl_lo=spec_lo,
                spectral_wl_hi=spec_hi,
            )

            self.progress_widget.update(1, 1, phase="Results")

            dialog.exec()

            self.log(
                f"Substrate index done on \u03bb=[{wl_min_fit:.0f},{wl_max_fit:.0f}] nm.",
                "SUCCESS",
            )

            self.progress_widget.stop("Done")

        except RuntimeError as ex:
            if "cancelled" in str(ex).lower():
                self.log("Calculation cancelled by user.", "WARNING")

                self.progress_widget.stop("Stopped by user")

                return

            raise

        except NUMERICAL_FAULT_EXCEPTIONS as ex:
            self.log(f"Calculation error: {ex}", "ERROR")

            self.progress_widget.stop("Failed")

            raise

        finally:
            if hasattr(self.progress_widget, "enable_cancel"):
                self.progress_widget.enable_cancel(False)

            self._set_busy(False)


def main():

    app = init_certus_app("CERTUS_SUBSTRATE_INDEX")

    window = SubstrateIndexGUI()

    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
