from __future__ import annotations








from certus.core.certus_core import create_module_environment, NUMERICAL_FAULT_EXCEPTIONS


from certus.workers.certus_re_worker_utils import (
    re_objective_wls_weight_log_trap,
    re_ranking_combined_rmse,
)


# =============================================================================


# BOOTSTRAP - Centralized app initialization


# =============================================================================


env = create_module_environment(__file__, "CERTUS_RE")


script_dir = env["script_dir"]


# =============================================================================


# FURTHER IMPORTS


# =============================================================================


from certus.utils.certus_re_config import RE_GUI_DEFAULT_BEAM_APERTURE_DEG, RE_SPLINE_CORREC_KINDS

from certus.utils.certus_re_math import (
    Any,
    Dict,
    RE_SPLINE_KNOTS_NM,
    RE_SPLINE_NODE2_DEFAULT_NM,
    RE_SPLINE_N_KNOTS,
    dataclass,
    field,
    logging,
    np,
    re,
    re_apply_re_index_model,
    re_interp_delta_knots_clamped,
    re_knots_wavelengths,
    unicodedata,
)

from certus.utils.certus_re_math import (
    _re_p4_beam_knots_lam_nm_from_wls,
    _re_p4_sort_knot_pairs,
    _re_p4_chromatic_band_masks,
    _re_p4_band_ap_deg,
    _re_p4_ap_staircase_polyline,
    _re_p4_ap_band_intervals_str,
    _re_p4_effective_half_width_deg,
    _re_deadzone_excess_abs,
    _RE_FT_COL_NUM,
    _RE_FT_COL_MAT,
    _RE_FT_COL_N,
    _RE_FT_COL_QW,
    _RE_FT_COL_THICK,
    _re_envelope_pchip,
    _RE_BMAT_CACHE_MAXSIZE,
)


# =============================================================================


# RE factored helpers (F1 + F2)  single source of truth for spectrum dispatch


# and correc-tuple -> re_apply_re_index_model mapping.


# =============================================================================


def _re_apply_correc(
    n_layers_nominal: np.ndarray,
    n_sub_nominal: np.ndarray,
    *,
    is_H: np.ndarray,
    is_L: np.ndarray,
    wls: np.ndarray,
    lambda_ref: float,
    correc: tuple,
    re_env_s: float = 1.0,
    env_cache: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Dispatch a correc-tuple to `re_apply_re_index_model`.

    *correc* is either ``("pct", a, b, f)`` for legacy drift-percent model,

    or ``("spline", dH_knots, dL_knots, lam_node2_nm)`` for cubic-spline DeltaRe,

    or ``("spline_cached", dH_knots, dL_knots, lam_node2_nm, B_matrix, env_wls)``

    for zero-allocation vectorised B-spline mapping,

    or ``("spline_cached_sub3", ..., tk_w, a0, a1, a2)`` / ``("spline_sub3", ..., a0, a1, a2)``

    for phase 2b (Cauchy substrate + tube; see RE_SUB_CAUCHY_* constants).

    """

    if correc[0] == "pct":
        return re_apply_re_index_model(
            n_layers_nominal,
            n_sub_nominal,
            is_H=is_H,
            is_L=is_L,
            wls_nm=wls,
            lambda_ref_nm=lambda_ref,
            a_pct=float(correc[1]),
            b_pct=float(correc[2]),
            f_pct=float(correc[3]),
            spline_dH=None,
            spline_dL=None,
            re_envelope_scale=re_env_s,
        )

    # Spline variants

    dh = np.asarray(correc[1], dtype=np.float64).ravel()

    dl = np.asarray(correc[2], dtype=np.float64).ravel()

    lam_spl = float(correc[3]) if len(correc) > 3 else float(RE_SPLINE_NODE2_DEFAULT_NM)

    B_mat = None

    env_wls_cached = env_cache

    sub_c = None

    if correc[0] in ("spline_cached", "spline_cached_sub3"):
        B_mat = correc[4]

        env_wls_cached = correc[5]

    if correc[0] == "spline_cached_sub3":
        sub_c = (float(correc[7]), float(correc[8]), float(correc[9]))

    elif correc[0] == "spline_sub3":
        if len(correc) >= 8 and isinstance(correc[4], np.ndarray):
            sub_c = (float(correc[5]), float(correc[6]), float(correc[7]))

        else:
            sub_c = (float(correc[4]), float(correc[5]), float(correc[6]))

    return re_apply_re_index_model(
        n_layers_nominal,
        n_sub_nominal,
        is_H=is_H,
        is_L=is_L,
        wls_nm=wls,
        lambda_ref_nm=lambda_ref,
        a_pct=0.0,
        b_pct=0.0,
        f_pct=0.0,
        spline_dH=dh,
        spline_dL=dl,
        spline_lam_node2_nm=lam_spl,
        re_envelope_scale=re_env_s,
        re_envelope_at_wls=env_wls_cached,
        spline_basis_matrix=B_mat,
        sub_cauchy_theta=sub_c,
    )


def _re_correc_to_nk_preview_payload(correc: tuple) -> dict[str, Any]:
    """Extract DeltaRe (knots), lambda₂ and Cauchy substrate from *correc* for the live n(lambda) tab."""

    out: dict[str, Any] = {
        "re_nk_preview_dH": None,
        "re_nk_preview_dL": None,
        "re_nk_preview_lam2": None,
        "re_nk_preview_sub012": None,
    }

    if not correc:
        return out

    tag = correc[0]

    if tag == "pct":
        return out

    if tag not in (
        "spline",
        "spline_cached",
        "spline_sub3",
        "spline_cached_sub3",
    ):
        return out

    dh = np.asarray(correc[1], dtype=np.float64).ravel()

    dl = np.asarray(correc[2], dtype=np.float64).ravel()

    lam = float(correc[3]) if len(correc) > 3 else float(RE_SPLINE_NODE2_DEFAULT_NM)

    out["re_nk_preview_dH"] = dh.tolist()

    out["re_nk_preview_dL"] = dl.tolist()

    out["re_nk_preview_lam2"] = lam

    if tag == "spline_cached_sub3" and len(correc) >= 10:
        out["re_nk_preview_sub012"] = [
            float(correc[7]),
            float(correc[8]),
            float(correc[9]),
        ]

    elif tag == "spline_sub3":
        if len(correc) >= 8 and isinstance(correc[4], np.ndarray):
            out["re_nk_preview_sub012"] = [
                float(correc[5]),
                float(correc[6]),
                float(correc[7]),
            ]

        elif len(correc) >= 7:
            out["re_nk_preview_sub012"] = [
                float(correc[4]),
                float(correc[5]),
                float(correc[6]),
            ]

    return out


def _re_calc_spectrum_for_config(
    wls: np.ndarray,
    n_layers_T: np.ndarray,
    ep: np.ndarray,
    n_sub: np.ndarray,
    angle: float,
    pol: str,
    include_backside: bool,
    phase4_average: bool = False,
    beam_aperture: float = 1.0,
    beam_aperture_knots_deg: np.ndarray | None = None,
    beam_aperture_knots_lam_nm: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute (R, T) for one physical config (angle × pol × backside model).

    RE does not model a rear stack: plate with or without a substrate rear-face

    (Fresnel) model, never an explicit rear coating.

    * ``include_backside``  semi-infinite (front only) vs inconsistent plate,

    * ``pol``  ``"s"`` / ``"p"`` / ``"Avg"`` (mean of s and p).

     * Phase 4 (``phase4_average``) - for incidence >= 10 deg: average of two angles

      ``theta +/- h`` with ``h`` = effective half-width from total beam width ``ap`` (deg);

      ``h`` is reduced so ``theta +/- h`` stays inside (0, 90) deg. If ``beam_aperture_knots_*``

      are set, ``ap(lambda)`` is **stepwise constant** between lambda knots (midpoints between

      consecutive sorted lambda); the ap per knot are independent (no monotonicity enforced).

      The fast path groups lambda by band and takes the knot ap value at the **mean lambda** of the band.

    """

    def _one_w(wl_s: np.ndarray, nlay_s: np.ndarray, nsub_s: np.ndarray, is_s: bool, a: float):

        p = "s" if is_s else "p"

        if not include_backside:
            return calc_spectrum_oblique_vectorized(wl_s, nlay_s, ep, nsub_s, a, p)

        return calc_spectrum_oblique_backside_vectorized(wl_s, nlay_s, ep, nsub_s, a, p)

    def _one(is_s: bool, a: float) -> tuple[np.ndarray, np.ndarray]:

        return _one_w(wls, n_layers_T, n_sub, is_s, a)

    def _eval_angle_w(wl_s, nlay_s, nsub_s, a: float):

        pl = str(pol).lower()

        if pl == "avg":
            Rs, Ts = _one_w(wl_s, nlay_s, nsub_s, True, a)

            Rp, Tp = _one_w(wl_s, nlay_s, nsub_s, False, a)

            return (Rs + Rp) * 0.5, (Ts + Tp) * 0.5

        return _one_w(wl_s, nlay_s, nsub_s, pl == "s", a)

    def _eval_angle(a: float):

        return _eval_angle_w(wls, n_layers_T, n_sub, a)

    if phase4_average and angle >= 10.0:
        ak = None if beam_aperture_knots_deg is None else np.asarray(beam_aperture_knots_deg, dtype=np.float64).ravel()

        lk = (
            None
            if beam_aperture_knots_lam_nm is None
            else np.asarray(beam_aperture_knots_lam_nm, dtype=np.float64).ravel()
        )

        if ak is not None and lk is not None and ak.size >= 2 and lk.size >= 2 and ak.size == lk.size:
            n = int(wls.size)

            R_acc = np.zeros(n, dtype=np.float64)

            T_acc = np.zeros(n, dtype=np.float64)

            masks = _re_p4_chromatic_band_masks(wls, lk)

            for m in masks:
                if not np.any(m):
                    continue

                lam_c = float(np.mean(wls[m]))

                ap_b = _re_p4_band_ap_deg(lk, ak, lam_c)

                h = _re_p4_effective_half_width_deg(angle, ap_b)

                nl = n_layers_T[m, :]

                ns = n_sub[m]

                ws = wls[m]

                if h <= 0.0:
                    R0, T0 = _eval_angle_w(ws, nl, ns, angle)

                    R_acc[m] = R0

                    T_acc[m] = T0

                else:
                    R1, T1 = _eval_angle_w(ws, nl, ns, angle - h)

                    R2, T2 = _eval_angle_w(ws, nl, ns, angle + h)

                    R_acc[m] = 0.5 * (R1 + R2)

                    T_acc[m] = 0.5 * (T1 + T2)

            return R_acc, T_acc

        h = _re_p4_effective_half_width_deg(angle, beam_aperture)

        if h <= 0.0:
            return _eval_angle(angle)

        R1, T1 = _eval_angle(angle - h)

        R2, T2 = _eval_angle(angle + h)

        return 0.5 * (R1 + R2), 0.5 * (T1 + T2)

    return _eval_angle(angle)


def _re_p4_kwargs_from_opt_result(best_r: Dict, cfg: Dict) -> Dict[str, Any]:
    """If *best_r* contains phase-4 knots, returns kwargs to align theory/RMSE with the beam fit."""

    _ak = best_r.get("re_p4_beam_ap_knots_deg")

    _nm = best_r.get("re_p4_beam_ap_knots_nm")

    if _ak is None or _nm is None:
        return {}

    ak = np.asarray(_ak, dtype=np.float64).ravel()

    nm = np.asarray(_nm, dtype=np.float64).ravel()

    n = int(min(ak.size, nm.size))

    if n < 2:
        return {}

    ap = float(
        best_r.get(
            "re_p4_aperture_deg",
            cfg.get("re_beam_aperture_deg", RE_GUI_DEFAULT_BEAM_APERTURE_DEG),
        )
    )

    return {
        "phase4_average": True,
        "beam_aperture": ap,
        "beam_aperture_knots_deg": np.ascontiguousarray(ak[:n]),
        "beam_aperture_knots_lam_nm": np.ascontiguousarray(nm[:n]),
    }


def _re_oblique_config_groups(tgts: list) -> dict:

    from collections import defaultdict

    g: dict = defaultdict(list)

    for tgt in tgts:
        if not getattr(tgt, "on", True):
            continue

        g[(tgt.angle, tgt.pol, tgt.include_backside)].append(tgt)

    return g


def _re_rmse_oblique_weighted(
    ep: np.ndarray,
    n_layers_T: np.ndarray,
    n_sub: np.ndarray,
    wls: np.ndarray,
    tgts: list,
    *,
    phase4_average: bool = False,
    beam_aperture: float = 1.0,
    beam_aperture_knots_deg: np.ndarray | None = None,
    beam_aperture_knots_lam_nm: np.ndarray | None = None,
) -> float:
    """RE RMSE (Deltaln(lambda) trapezoidal weighting, same aggregation as the TRF least-squares objective)."""

    wt_lambda = re_objective_wls_weight_log_trap(wls)

    total_err = 0.0

    total_w = 0.0

    for (angle, pol, include_backside), tgt_list in _re_oblique_config_groups(tgts).items():
        R_c, T_c = _re_calc_spectrum_for_config(
            wls,
            n_layers_T,
            ep,
            n_sub,
            angle,
            pol,
            include_backside,
            phase4_average=phase4_average,
            beam_aperture=beam_aperture,
            beam_aperture_knots_deg=beam_aperture_knots_deg,
            beam_aperture_knots_lam_nm=beam_aperture_knots_lam_nm,
        )

        for tgt in tgt_list:
            mask = (wls >= tgt.lmin) & (wls <= tgt.lmax)

            pos = np.where(mask)[0]

            if pos.size == 0:
                continue

            tgt_val = (tgt.tmin + tgt.tmax) / 2.0

            vals = R_c[pos] if tgt.target_type == "R" else T_c[pos]

            wt = wt_lambda[pos]

            ws = float(tgt.w)

            wt_sum = float(np.sum(wt))

            wy = wt * vals

            wy2_sum = float(np.dot(wy, vals))

            wy_sum = float(np.sum(wy))

            w_tgt_sum = ws * tgt_val

            w_tgt2_sum = ws * tgt_val * tgt_val

            total_err += (ws * wy2_sum) - (2.0 * w_tgt_sum * wy_sum) + (w_tgt2_sum * wt_sum)

            total_w += ws * wt_sum

    if total_w <= 1e-18:
        return float("nan")

    return float(np.sqrt(total_err / total_w))


def _re_rmse_combined_spectral_qwot(rmse_spectral: float, rmse_qwot: float, alpha_qwot: float) -> float:
    """Combined RMSE matching REWorker: √(RMSE_sp2 + RMSE_QWOT2). =0 -> spectral only."""

    return re_ranking_combined_rmse(rmse_spectral, rmse_qwot, alpha_qwot)


def _re_sort_results_best_for_table_and_apply(results: list) -> None:
    """In-place sort: ``results[0]`` = best ``rmse_combined`` (user objective), with spectral RMSE as a tie-break."""

    if len(results) < 2:
        return

    results.sort(
        key=lambda r: (
            float(r.get("rmse_combined", r.get("rmse", float("inf")))),
            float(r.get("rmse", float("inf"))),
        )
    )


def _re_objective_variance_fractions(
    rmse_spectral: float, rmse_qwot: float, alpha_qwot: float
) -> tuple[float, float, float]:
    """Fractions of sp2 and QWOT2 in RMSE2 = sp2 + QWOT2 (same convention as the objective)."""

    sp = max(float(rmse_spectral), 0.0)

    qw = max(float(rmse_qwot), 0.0)

    a = max(float(alpha_qwot), 0.0)

    sp2 = sp * sp

    qw_t = a * qw * qw

    den = sp2 + qw_t

    if den < 1e-30:
        return (0.5, 0.5, 0.0)

    comb = re_ranking_combined_rmse(rmse_spectral, rmse_qwot, alpha_qwot)

    return (sp2 / den, qw_t / den, comb)


def _re_diagnostic_action_hints(
    frac_sp: float,
    frac_qw_weighted: float,
    rmse_sp: float,
    rmse_qw: float,
    alpha: float,
) -> list[str]:
    """Short hints to tune settings (, splines, Excel design) after a real run."""

    hints: list[str] = []

    if frac_qw_weighted > 0.55:
        hints.append(
            "Objective dominated by the QWOT term (weighted by ) -> increase QWOT weight, "
            "or review QWOT / lambda₀ in the Excel design sheet."
        )

    if frac_sp > 0.55:
        hints.append(
            "Objective dominated by spectral error (Deltaln(lambda) trap) -> adjust DeltaRe envelope, splines, "
            "thicknesses (phase 1 radius), or weighting / quality of measurement channels."
        )

    if rmse_sp < 0.03 and rmse_qw > 0.12 and frac_sp > 0.35:
        hints.append(
            "Spectrum already low but QWOT still high -> risk of spectral fit at the expense of "
            "optical thickness at lambda₀; strengthen  in phase 2b or check design consistency."
        )

    if alpha < 0.04 and rmse_qw > 0.1:
        hints.append(
            f"={alpha:g} is modest for RMSE_QWOT{rmse_qw:.3f} -> QWOT penalty may stay secondary "
            "in TRF (residual  √DeltaQ2)."
        )

    if not hints:
        hints.append(
            "Spectral and QWOT terms comparable in RMSE: refine according to metrology priority "
            "(spectrum vs QWOT anchoring)."
        )

    return hints


def _re_log_objective_diagnostic(
    tag: str,
    rmse_spectral: float,
    rmse_qwot: float,
    alpha_qwot: float,
) -> None:
    """Structured log: RMSE breakdown and hints (same log file as a reverse_sample.xlsx run)."""

    fs, fq, comb = _re_objective_variance_fractions(rmse_spectral, rmse_qwot, alpha_qwot)

    hints = _re_diagnostic_action_hints(fs, fq, float(rmse_spectral), float(rmse_qwot), float(alpha_qwot))

    logging.info(
        "RE diag [%s] RMSE_sp=%.6f | RMSE_QWOT=%.6f | =%.4f -> RMSE=%.6f | "
        "shares in RMSE2 (sp2 vs QWOT2): %.0f%% / %.0f%%",
        tag,
        float(rmse_spectral),
        float(rmse_qwot),
        float(alpha_qwot),
        comb,
        100.0 * fs,
        100.0 * fq,
    )

    for h in hints:
        logging.info("RE diag [%s] -> %s", tag, h)


def _parse_re_rmse_combined_from_progress_message(msg: str) -> float | None:
    """Reads RMSE_facade / RMSE_combined / RMSE(curr) from REWorker messages (backup if signal is delayed)."""

    if not msg:
        return None

    #  in RE f-strings is often U+2211 (n-ary summation), not Greek  U+03A3.

    for pat in (
        r"RMSE_facade\(curr\)=\s*([0-9]+(?:\.[0-9]*)?(?:[eE][+-]?\d+)?)",
        r"RMSE_facade=\s*([0-9]+(?:\.[0-9]*)?(?:[eE][+-]?\d+)?)",
        r"RMSE[\u2211\u03A3]=\s*([0-9]+(?:\.[0-9]*)?(?:[eE][+-]?\d+)?)",
        r"RMSE_combined=\s*([0-9]+(?:\.[0-9]*)?(?:[eE][+-]?\d+)?)",
        r"RMSE\(curr\)=\s*([0-9]+(?:\.[0-9]*)?(?:[eE][+-]?\d+)?)",
        r"(?<![\w(])RMSE=\s*([0-9]+(?:\.[0-9]*)?(?:[eE][+-]?\d+)?)",
    ):
        m = re.search(pat, msg)

        if m:
            try:
                x = float(m.group(1))

            except ValueError:
                continue

            if np.isfinite(x) and x >= 0.0:
                return x

    return None


def re_n_corr_at_lambda_ref(
    n_ref_nom_per_layer: np.ndarray,
    is_H: np.ndarray,
    is_L: np.ndarray,
    lref_arr: np.ndarray,
    re_envelope_scale: float,
    *,
    correc: tuple | None = None,
    spline_dH: np.ndarray | None = None,
    spline_dL: np.ndarray | None = None,
    spline_lam2_nm: float | None = None,
) -> np.ndarray:
    """Re(n) per layer at lambda_ref: tabulated + DeltaRe H/L - **unique** source for the QWOT term (TRF + RMSE).

    Priority: if ``correc`` is a spline tuple (worker), it takes precedence; otherwise ``spline_dH`` /

    ``spline_dL`` arrays (UI / export).

    """

    out = np.asarray(n_ref_nom_per_layer, dtype=np.float64).ravel().copy()

    _nk = int(RE_SPLINE_N_KNOTS)

    lr = np.asarray(lref_arr, dtype=np.float64).ravel()

    if lr.size == 0:
        lr = np.array([500.0], dtype=np.float64)

    esc = float(re_envelope_scale)

    iH = np.asarray(is_H, dtype=bool)

    iL = np.asarray(is_L, dtype=bool)

    if correc is not None and len(correc) > 0 and correc[0] in RE_SPLINE_CORREC_KINDS:
        dH = np.asarray(correc[1], dtype=np.float64).ravel()

        dL = np.asarray(correc[2], dtype=np.float64).ravel()

        lam2 = float(correc[3]) if len(correc) > 3 else float(RE_SPLINE_NODE2_DEFAULT_NM)

        kn = re_knots_wavelengths(lam2)

        dn_h = float(re_interp_delta_knots_clamped(kn, dH, lr, envelope_scale=esc)[0])

        dn_l = float(re_interp_delta_knots_clamped(kn, dL, lr, envelope_scale=esc)[0])

        out[iH] += dn_h

        out[iL] += dn_l

        return out

    if spline_dH is not None and spline_dL is not None:
        dh = np.asarray(spline_dH, dtype=np.float64).ravel()

        dl = np.asarray(spline_dL, dtype=np.float64).ravel()

        if dh.size == _nk and dl.size == _nk:
            lam2 = float(spline_lam2_nm) if spline_lam2_nm is not None else float(RE_SPLINE_NODE2_DEFAULT_NM)

            kn = re_knots_wavelengths(lam2)

            dn_h = float(re_interp_delta_knots_clamped(kn, dh, lr, envelope_scale=esc)[0])

            dn_l = float(re_interp_delta_knots_clamped(kn, dl, lr, envelope_scale=esc)[0])

            out[iH] += dn_h

            out[iL] += dn_l

    return out


def re_delta_qwot_per_layer(
    ep: np.ndarray,
    ep0: np.ndarray,
    n_ref_nom_per_layer: np.ndarray,
    is_H: np.ndarray,
    is_L: np.ndarray,
    lambda_ref: float,
    re_envelope_scale: float,
    lref_arr: np.ndarray,
    *,
    correc: tuple | None = None,
    spline_dH: np.ndarray | None = None,
    spline_dL: np.ndarray | None = None,
    spline_lam2_nm: float | None = None,
) -> np.ndarray:
    """Q_i = (4/lambda_ref)(n_corr_iep_i - n_tab_iep0_i) - identical to the TRF QWOT residual."""

    ep = np.asarray(ep, dtype=np.float64).ravel()

    ep0 = np.asarray(ep0, dtype=np.float64).ravel()

    nref = np.asarray(n_ref_nom_per_layer, dtype=np.float64).ravel()

    if ep.size != ep0.size or ep.size != nref.size or ep.size == 0:
        return np.zeros(0, dtype=np.float64)

    l0 = float(max(float(lambda_ref), 1e-9))

    kq = 4.0 / l0

    n_corr = re_n_corr_at_lambda_ref(
        nref,
        is_H,
        is_L,
        lref_arr,
        re_envelope_scale,
        correc=correc,
        spline_dH=spline_dH,
        spline_dL=spline_dL,
        spline_lam2_nm=spline_lam2_nm,
    )

    return kq * (n_corr * ep - nref * ep0)


def _re_qwot_rmse_abs_delta_at_l0(
    ep: np.ndarray,
    ep0: np.ndarray,
    stack: list,
    mats: dict,
    lambda_ref: float,
    is_H: np.ndarray,
    is_L: np.ndarray,
    *,
    spline_dH: np.ndarray | None,
    spline_dL: np.ndarray | None,
    spline_lam2_nm: float | None,
    re_envelope_scale: float,
    deadzone_abs: float = 0.0,
) -> float:
    """QWOT-related RMS at lambda₀: if deadzone_abs>0, RMS(max(0,|DeltaQ|)); else RMS(|DeltaQ|). DeltaQ = QQ_init."""

    ep = np.asarray(ep, dtype=np.float64).ravel()

    ep0 = np.asarray(ep0, dtype=np.float64).ravel()

    if ep.size != ep0.size or ep.size == 0:
        return 0.0

    n_lay = int(ep.size)

    l0 = float(max(float(lambda_ref), 1e-9))

    _lref = np.array([float(lambda_ref)], dtype=np.float64)

    n_ref_nom = np.array(
        [float(mats[stack[i].mat].get_nk(_lref).real[0]) for i in range(n_lay)],
        dtype=np.float64,
    )

    delta_q = re_delta_qwot_per_layer(
        ep,
        ep0,
        n_ref_nom,
        is_H,
        is_L,
        l0,
        float(re_envelope_scale),
        _lref,
        spline_dH=spline_dH,
        spline_dL=spline_dL,
        spline_lam2_nm=spline_lam2_nm,
    )

    if delta_q.size == 0:
        return 0.0

    ex = _re_deadzone_excess_abs(delta_q, float(deadzone_abs))

    return float(np.sqrt(np.mean(ex**2)))


def format_re_spline_knots_log(knot_wl: np.ndarray, dh: np.ndarray, dl: np.ndarray) -> str:

    parts = [
        f"lambda{float(knot_wl[i]):.0f}nm DeltaRe[H]={float(dh[i]):+.5f} DeltaRe[L]={float(dl[i]):+.5f}"
        for i in range(min(len(knot_wl), len(dh), len(dl)))
    ]

    return " | ".join(parts)


def re_drift_result_log_suffix(r: dict) -> str:
    """Concatenated optional drift fragments (leading space each) for one RE result dict row."""

    if r.get("re_dH_knots") is not None and r.get("re_dL_knots") is not None:
        try:
            kw = np.asarray(r.get("re_knots_nm", RE_SPLINE_KNOTS_NM), dtype=np.float64)

            dh = np.asarray(r["re_dH_knots"], dtype=np.float64)

            dl = np.asarray(r["re_dL_knots"], dtype=np.float64)

            _s = " " + format_re_spline_knots_log(kw, dh, dl)

            if r.get("re_sub_cauchy_a0") is not None:
                _s += (
                    f" | sub_Cauchy=({float(r['re_sub_cauchy_a0']):.5f},"
                    f"{float(r['re_sub_cauchy_a1']):.5f},{float(r['re_sub_cauchy_a2']):.5f})"
                )

            return _s

        except NUMERICAL_FAULT_EXCEPTIONS :
            pass

    parts: list[str] = []

    if "a" in r:
        parts.append(f" drift_Re[H]={r.get('a', 0):+.3f}%")

    if "b" in r:
        parts.append(f" drift_Re[L]={r.get('b', 0):+.3f}%")

    if "f" in r:
        parts.append(f" drift_Re[sub]={r.get('f', 0):+.3f}%")

    return "".join(parts)


# pyqtgraph configured in certus_ui, imported locally for use








# Conditional SVG Import


# =============================================================================


# IMPORTS MODULAR ARCHITECTURE


# =============================================================================


# Import Modular Architecture


# --- 1. CORE (Config, Constants, Utils) ---




# --- 4. DATA (IO, Reporting) ---




# --- 5. ERRORS (Validation, Messages) ---


# Direct import for warmup


# --- 2. PHYSICS (Models, TMM, Optimization) ---




from certus_physics import (
    calc_spectrum_oblique_backside_vectorized,
    calc_spectrum_oblique_vectorized,
)


# --- 3. UI (Theme, Widgets) ---








# =============================================================================


# TABULAR MATERIAL (Reverse Engineering  bypasses Cauchy model)


# =============================================================================


class TabularMaterial:
    """Material backed by tabulated n(\u03bb) data instead of the Cauchy 2-point model.

    Used exclusively for Reverse Engineering loads.  ``get_nk(wls)`` returns

    values by linear interpolation (constant extrapolation at boundaries).

    The ``n4`` attribute is set to n(\u03bb_ref) so that ``init_thickness`` converts

    QWOT values correctly for the actual working wavelength.

    """

    _is_tabular: bool = True

    def __init__(self, wls_nm: np.ndarray, n_arr: np.ndarray, k_arr: np.ndarray | None = None, l0_ref: float = 500.0):

        self.wls_nm = np.asarray(wls_nm, dtype=np.float64)

        self.n_arr = np.asarray(n_arr, dtype=np.float64)

        self.k_arr = np.zeros_like(self.n_arr) if k_arr is None else np.asarray(k_arr, dtype=np.float64)

        # n4 = n(\u03bb_ref): used by init_thickness for correct QWOT\u2192nm conversion

        self.n4 = float(np.interp(l0_ref, self.wls_nm, self.n_arr, left=self.n_arr[0], right=self.n_arr[-1]))

        self.n7 = self.n4  # kept for code that reads n7 (not used in RE calcs)

    def get_nk(self, wls: np.ndarray) -> np.ndarray:
        """Returns (n + ik) as a complex array via linear interpolation."""

        wls_f = np.asarray(wls, dtype=np.float64)

        n_i = np.interp(wls_f, self.wls_nm, self.n_arr, left=self.n_arr[0], right=self.n_arr[-1])

        k_i = np.interp(wls_f, self.wls_nm, self.k_arr, left=self.k_arr[0], right=self.k_arr[-1])

        return (n_i + 1j * k_i).astype(np.complex128)


# =============================================================================


# RE measurement column header parser (incidence, pol, R/T, backside)


# =============================================================================


def _re_ascii_fold_lower(s: str) -> str:
    """Lowercase without accents (mixed Excel FR/EN labels)."""

    if not s:
        return ""

    s = unicodedata.normalize("NFD", str(s))

    return "".join(c for c in s.lower() if unicodedata.category(c) != "Mn")


_re_no_back_tokens = frozenset(
    {
        "nobk",
        "no-bk",
        "noback",
        "nobackside",
        "no-backside",
        "nobs",
        "semisub",
        "semi",
        "inf",
        "infinite",
        "frontonly",
        "subinf",
        "semiinf",
        # Acronyms for 1 side / 2 sides (often 1f / 2f in exports)
        "1f",
        "1face",
        "1-face",
        "singleface",
        "1-face-only",
        # FR (single token or abbreviation without space)
        "sansarriere",
        "sansverso",
        "faceavant",
        "recto",
        "monoface",
    }
)


_re_with_back_tokens = frozenset(
    {
        "withback",
        "with-bk",
        "withbk",
        "wbk",
        "plate",
        "finite",
        "backside",
        "wback",
        "2f",
        "2face",
        "2faces",
        "2-face",
        "twoface",
        "twofaces",
        "rear",
        "doubleface",
        # FR ( verso = back / return side)
        "derriere",
        "facedos",
        "verso",
    }
)


@dataclass(frozen=True, slots=True)
class ParsedREColumn:
    """Metadata for a spectral column (RE measurement sheet)."""

    target_type: str  # 'R' or 'T'

    angle_deg: float

    pol: str  # 's', 'p', or 'Avg'

    include_backside: bool

    raw_header: str

    #: User-facing messages when interpretation relies on assumptions.

    interpretation_notes: tuple[str, ...] = field(default_factory=tuple)


def _re_header_normalize_for_tokens(raw: str) -> str:
    """Normalize before splitting column titles (mixed Excel FR/EN)."""

    s = _re_cell_str(raw)

    s = re.sub(r",\s*", " ", s)

    # Common FR -> tokens already handled by the parser

    s = re.sub(
        r"sans\s*[-_/]?\s*arri[eee]res?",
        " noBK ",
        s,
        flags=re.IGNORECASE,
    )

    s = re.sub(
        r"face\s*[-_/]?\s*avant(?:\s+seule)?",
        " noBK ",
        s,
        flags=re.IGNORECASE,
    )

    s = re.sub(
        r"avec\s*[-_/]?\s*arri[eee]res?",
        " withback ",
        s,
        flags=re.IGNORECASE,
    )

    s = re.sub(r"\bincidence\b", " aoi ", s, flags=re.IGNORECASE)

    s = re.sub(r"\bmoyenne\b", " Avg ", s, flags=re.IGNORECASE)

    s = re.sub(r"\bnon[\s-]*polaris", " unpol ", s, flags=re.IGNORECASE)

    # Detach 1f / 2f glued after a letter (e.g. ``Rs1f``, ``RnoBKs2f``)

    s = re.sub(r"(?<=[A-Za-z])(1f|2f)\b", r" \1 ", s, flags=re.IGNORECASE)

    return s


def _re_header_tokens(raw_stripped: str) -> list[str]:
    """Split an RE label into tokens (robust: - _ / space, parentheses)."""

    s = _re_header_normalize_for_tokens(raw_stripped)

    parts = [p for p in re.split(r"[\s\-_,/]+", s) if p]

    out: list[str] = []

    for p in parts:
        t = p.strip()

        if len(t) >= 2 and t[0] in "([{" and t[-1] in ")]}":
            t = t[1:-1].strip()

        if t:
            out.append(t)

    return out


def parse_re_column_header(raw: str | None) -> ParsedREColumn:
    """Infer R/T, angle (deg), polarization, and backside model from a column title.

    Accepts **French and/or English** labels (accents normalized), e.g.

    ``Reflection 45 s noBK``, ``Transmission AOI 30 p``,

    ``R-45-s-noBK``, ``T-30-P-BACK``, ``R45s1f``, legacy ``R`` / ``T``.

    * **noBK-type tokens** -> front side only (see ``_re_no_back_tokens``).

    * **with-back tokens** -> inconsistent plate (see ``_re_with_back_tokens``).

    * If both no-back and with-back hints appear, raises ``ValueError``.

    Ambiguous cases are recorded in ``interpretation_notes`` (for logs and optional

    dialog when loading Excel).

    """

    raw_header = "" if raw is None else str(raw).strip()

    if not raw_header:
        raise ValueError("measurement column header is empty")

    legacy_u = _re_ascii_fold_lower(raw_header).upper()

    if legacy_u == "R":
        return ParsedREColumn("R", 0.0, "s", True, raw_header, ())

    if legacy_u == "T":
        return ParsedREColumn("T", 0.0, "s", True, raw_header, ())

    tokens = _re_header_tokens(raw_header)

    if not tokens:
        raise ValueError(f"cannot parse measurement header: {raw_header!r}")

    notes: list[str] = []

    assumed_rt = False

    t0 = tokens[0].upper()

    t0_fold = _re_ascii_fold_lower(tokens[0])

    # Order: transmission (avoids ambiguous "T...") then reflection / R... (excluding "reference").

    if t0_fold.startswith("transm") or (
        t0.startswith("T")
        and not t0_fold.startswith("travail")
        and not t0_fold.startswith("titre")
        and not t0_fold.startswith("taux")
    ):
        target_type = "T"

        rest = tokens[1:]

    elif (
        t0_fold.startswith("refle")
        or t0_fold.startswith("reflex")
        or (t0.startswith("R") and not t0_fold.startswith("reference"))
    ):
        target_type = "R"

        rest = tokens[1:]

    else:
        raw_low = _re_ascii_fold_lower(raw_header)

        if any(_re_ascii_fold_lower(t).startswith("transm") for t in tokens) or (
            "transmission" in raw_low or "transmittance" in raw_low
        ):
            target_type = "T"

            rest = tokens[:]

        elif any(
            _re_ascii_fold_lower(t).startswith("refle") or _re_ascii_fold_lower(t).startswith("reflex") for t in tokens
        ) or ("reflection" in raw_low or "reflectance" in raw_low or "reflexion" in raw_low):
            target_type = "R"

            rest = tokens[:]

        else:
            target_type = "R"

            rest = tokens

            assumed_rt = True

            notes.append(
                "No R/T header or reflection/transmission keyword at the start of the label: "
                "the column is interpreted as **reflectance (R)**."
            )

            logging.warning(
                "RE measurement header %r: no leading R/T; assuming Reflectance (R).",
                raw_header,
            )

    angle_deg = 0.0

    pol = "s"

    no_back = False

    with_back = False

    unknown_tokens: list[str] = []

    for tok in rest:
        tl = _re_ascii_fold_lower(tok)

        if tl in _re_no_back_tokens or (tl.startswith("no") and tl.endswith("bk")):
            no_back = True

            continue

        if tl in _re_with_back_tokens or tl in ("back", "bk"):
            with_back = True

            continue

        if tl in ("s", "pols", "pol-s", "spol", "te"):
            pol = "s"

            continue

        if tl in ("p", "polp", "pol-p", "ppol", "tm"):
            pol = "p"

            continue

        if "avg" in tl or "unpol" in tl or tl == "amb" or "moyen" in tl:
            pol = "Avg"

            continue

        m_ang = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([sp]?)", tl, re.IGNORECASE)

        if m_ang:
            a = float(m_ang.group(1))

            if 0.0 <= a <= 90.0:
                angle_deg = a

            suf = (m_ang.group(2) or "").lower()

            if suf == "s":
                pol = "s"

            elif suf == "p":
                pol = "p"

            continue

        m_theta = re.match(r"(?:aoi|th(?:eta)?|deg|angle)\s*[\s_\-:]*(\d+(?:\.\d+)?)", tl, re.IGNORECASE)

        if m_theta:
            a = float(m_theta.group(1))

            if 0.0 <= a <= 90.0:
                angle_deg = a

            continue

        m_inc_fr = re.fullmatch(r"(?:i|inc|inci)(?:idence)?\s*[\s_\-:]*(\d+(?:\.\d+)?)", tl, re.IGNORECASE)

        if m_inc_fr:
            a = float(m_inc_fr.group(1))

            if 0.0 <= a <= 90.0:
                angle_deg = a

            continue

        if re.fullmatch(r"\d+(?:\.\d+)?", tl):
            a = float(tl)

            if 0.0 <= a <= 90.0:
                angle_deg = a

            continue

        unknown_tokens.append(tok)

    if unknown_tokens:
        notes.append(
            f"Unrecognized label segments (ignored by the parser): {', '.join(repr(t) for t in unknown_tokens)}."
        )

    if no_back and with_back:
        raise ValueError(f"RE header {raw_header!r}: conflicting backside hints (no back vs with back)")

    if no_back:
        include_backside = False

    elif with_back:
        include_backside = True

    else:
        include_backside = True

        if assumed_rt or unknown_tokens:
            notes.append(
                "No explicit rear-face marker (noBK, 1f, sans arriere, plate, 2f, back...): "
                "model **with** incoherent rear face on substrate (**default behaviour**)."
            )

    return ParsedREColumn(target_type, angle_deg, pol, include_backside, raw_header, tuple(notes))


# --- Robust Excel RE layout helpers (variable column order / count) -------------


_RE_DESIGN_LABEL_SKIP = frozenset(
    {
        "lambda",
        "l0",
        "wl",
        "wave",
        "wavelength",
        "longueur",
        "longueurdonde",
        "design",
        "sub",
        "substrate",
        "substrate",
        "ref",
        "lref",
        "nm",
        "qwot",
        "qwuot",
        "ot",
        "couche",
        "layers",
        "layer",
        "materiau",
        "materiaux",
        "thickness",
        "conception",
        "reference",
        "empilement",
        "pile",
        "multicouche",
    }
)


def _re_cell_str(cell) -> str:

    if cell is None:
        return ""

    s = str(cell).strip().replace("\u00a0", " ").replace("\u202f", " ")

    return " ".join(s.split())


def _re_header_is_wavelength_label(s: str) -> bool:

    s_clean = _re_cell_str(s)

    sl = s_clean.lower()

    fold = _re_ascii_fold_lower(s_clean)

    if "wavelength" in sl or "longueur" in sl or "lambda" in s_clean:
        return True

    if "longueur" in fold and "onde" in fold:
        return True

    t = sl.replace(" ", "").replace("(", "").replace(")", "")

    if not t:
        return False

    if any(
        k in t
        for k in (
            "wavelength",
            "longueurd'onde",
            "longueurdonde",
            "lambda",
            "lambda",
        )
    ):
        return True

    if t in ("wl", "wave", "lenm", "lnm"):
        return True

    if "nm" in t and not t.startswith("r") and not t.startswith("t-") and "r_" not in t[:3]:
        if "n_" in t or "n1" in t or "k_" in t:
            return False

        return True

    return False


def _re_header_looks_like_spectrum_title(s: str) -> bool:

    u = _re_ascii_fold_lower(_re_cell_str(s))

    if not u:
        return False

    if u in ("r", "t"):
        return True

    if u.startswith("r") or u.startswith("t"):
        return True

    if any(k in u for k in ("reflect", "reflex", "transmi", "transmission")):
        return True

    return False


def _re_parse_design_metadata_row(header: tuple) -> tuple[float, str]:
    """First row of ``design``: lambda_ref (nm) + substrate name, any column order."""

    import re as _re

    lambda_ref = 500.0

    for cell in header:
        if cell is None:
            continue

        if isinstance(cell, (int, float)):
            v = float(cell)

            if 200.0 <= v <= 200_000.0:
                lambda_ref = v

                break

        if isinstance(cell, str):
            m = _re.search(r"(\d+\.?\d*)", cell)

            if m:
                v = float(m.group(1))

                if 200.0 <= v <= 200_000.0:
                    lambda_ref = v

                    break

    substrate_name = ""

    for cell in header:
        if cell is None or isinstance(cell, (int, float)):
            continue

        s = _re_cell_str(cell)

        if not s:
            continue

        if "lambda" in s:
            continue

        sl = _re_ascii_fold_lower(s)

        if sl in _RE_DESIGN_LABEL_SKIP:
            continue

        if _re.fullmatch(r"\d+\.?\d*\s*(nm)?", sl):
            continue

        substrate_name = s

        break

    return lambda_ref, substrate_name


def _re_looks_like_layer_index_sequence(seq: list[float]) -> bool:
    """Reject columns that are 1,2,3... (layer row counters)."""

    if len(seq) < 3:
        return False

    arr = np.asarray(seq, dtype=np.float64)

    if not np.allclose(arr, np.round(arr), rtol=0.0, atol=1e-9):
        return False

    arr_i = np.round(arr).astype(int)

    if int(arr_i[0]) != 1:
        return False

    return bool(np.all(np.diff(arr_i) == 1))


def _re_qwot_cell_value(v) -> float | None:
    """Return *v* as QWOT if plausibly a quarter-wave fraction, else None."""

    try:
        fv = float(v)

    except (TypeError, ValueError):
        return None

    if fv <= 0.0 or fv > 1.0e6:
        return None

    return fv


def re_qwot_penalty_weight_from_preset(*, speed_preset: dict[str, Any], default: float) -> float:
    """Return the configured QWOT penalty weight from a speed preset."""
    try:
        return float(speed_preset["re_qwot_penalty_weight"])
    except (KeyError, TypeError, ValueError):
        return float(default)


def _re_row_left_qwot_run(row: tuple) -> list[float]:
    """Consecutive QWOT-like numbers from column 0 until None or invalid (one row)."""

    if not row:
        return []

    out: list[float] = []

    for j in range(len(row)):
        v = row[j]

        if v is None:
            break

        fv = _re_qwot_cell_value(v)

        if fv is None:
            break

        out.append(fv)

    return out


def _re_parse_design_qwot_rows(rows: list[tuple]) -> list[float]:
    """QWOT list below the metadata header.

    Supports **multi-column** rows (e.g. H and L on the same line) by flattening

    row-major, and **single-column** legacy (longest vertical run).

    """

    if len(rows) < 2:
        return []

    data_rows = [r for r in rows[1:] if r and any(c is not None for c in r)]

    if not data_rows:
        return []

    head = min(5, len(data_rows))

    multi = any(len(_re_row_left_qwot_run(r)) >= 2 for r in data_rows[:head])

    if multi:
        flat: list[float] = []

        for row in data_rows:
            flat.extend(_re_row_left_qwot_run(row))

        if flat and not _re_looks_like_layer_index_sequence(flat):
            return flat

    max_w = max((len(r) for r in rows if r), default=0)

    best_seq: list[float] = []

    for j in range(max_w):
        seq: list[float] = []

        for row in rows[1:]:
            if not row or len(row) <= j:
                break

            v = row[j]

            if v is None:
                break

            fv = _re_qwot_cell_value(v)

            if fv is None:
                break

            seq.append(fv)

        if _re_looks_like_layer_index_sequence(seq):
            continue

        if len(seq) > len(best_seq):
            best_seq = seq

    return best_seq


def _re_normalize_sheet_key(name: str) -> str:
    """Normalized key to match sheet names (FR accents ignored)."""

    return _re_ascii_fold_lower(_re_cell_str(name))


_RE_CANONICAL_SHEETS = ("measurement", "design", "index")


_RE_SHEET_SYNONYMS: dict[str, tuple[str, ...]] = {
    "measurement": (
        "measurement",
        "measurment",
        "measure",
        "measures",
        "mesure",
        "mesures",
        "spectrum",
        "spectres",
        "spectrum",
        "data",
        "re data",
        "data",
        "mesuree",
        "results",
    ),
    "design": (
        "design",
        "stack",
        "structure",
        "empilement",
        "conception",
        "pile",
        "multicouche",
    ),
    "index": (
        "index",
        "indices",
        "nk",
        "materials",
        "material clues",
        "clues",
        "materiaux",
        "materiaux",
        "indice",
        "optique",
    ),
}


def _re_resolve_re_workbook_sheets(sheetnames: list[str]) -> dict[str, str]:
    """Map canonical keys *measurement* / *design* / *index* to actual sheet titles."""

    norm_to_actual: dict[str, str] = {}

    for s in sheetnames:
        k = _re_normalize_sheet_key(s)

        if not k:
            continue

        norm_to_actual.setdefault(k, s)

    def resolve_one(canonical: str) -> str | None:

        for syn in _RE_SHEET_SYNONYMS.get(canonical, (canonical,)):
            sk = _re_normalize_sheet_key(syn)

            if sk and sk in norm_to_actual:
                return norm_to_actual[sk]

        for raw in sheetnames:
            rk = _re_normalize_sheet_key(raw).replace("_", " ")

            for syn in _RE_SHEET_SYNONYMS.get(canonical, (canonical,)):
                sk = _re_normalize_sheet_key(syn).replace("_", " ")

                if not sk:
                    continue

                pad = f" {rk} "

                if rk == sk or rk.startswith(sk + " ") or rk.endswith(" " + sk) or f" {sk} " in pad:
                    return raw

        return None

    out: dict[str, str] = {}

    for c in _RE_CANONICAL_SHEETS:
        r = resolve_one(c)

        if r:
            out[c] = r

    return out


def _re_index_split_header_and_data(rows: list[tuple]) -> tuple[tuple | None, list[tuple]]:
    """If row 0 looks like text headers, return (row0, data). Else (None, all)."""

    if not rows:
        return None, []

    r0 = rows[0]

    text_n = sum(1 for c in r0 if c is not None and isinstance(c, str) and _re_cell_str(c))

    num_n = sum(1 for c in r0 if isinstance(c, (int, float)))

    if text_n >= 2 and text_n >= num_n:
        return tuple(r0), list(rows[1:])

    return None, list(rows)


def _re_index_column_map(
    header: tuple | None, _max_cols: int
) -> tuple[int, int | None, int | None, int | None, int | None]:
    """Map wavelength + n1,k1,n2,k2 columns. None = missing column (use defaults).

    Priority:
    1. If header labels explicitly contain n_H/k_H and n_B|n_L/k_B|k_L prefixes,
       use name-based mapping so columns don't have to be in positional order.
    2. Fallback: positional order (col after wavelength = n1,k1,n2,k2).
    """

    if header is None:
        return 0, 1, 2, 3, 4

    # --- wavelength column (unchanged) ---
    wl = 0
    for i, c in enumerate(header):
        if c is not None and _re_header_is_wavelength_label(_re_cell_str(c)):
            wl = i
            break

    # --- name-based detection of H / L columns ---
    # Accept multiple conventions used in Excel exports:
    #   n_H / k_H / n_L / k_L
    #   n_high / k_high / n_low / k_low
    #   n_haut / k_haut / n_bas / k_bas
    #   n1 / k1 / n2 / k2
    col_nH = col_kH = col_nL = col_kL = None
    for i, c in enumerate(header):
        if i == wl or c is None:
            continue
        s = _re_cell_str(c).lower().replace(" ", "_").replace("-", "_")
        if s.startswith(("n_h", "n_high", "n_haut", "n1")):
            col_nH = i
        elif s.startswith(("k_h", "k_high", "k_haut", "k1")):
            col_kH = i
        elif s.startswith(("n_l", "n_low", "n_bas", "n_b", "n2")):
            col_nL = i
        elif s.startswith(("k_l", "k_low", "k_bas", "k_b", "k2")):
            col_kL = i

    # If we identified at least n_H and n_L by name, use name-based mapping
    if col_nH is not None and col_nL is not None:
        return wl, col_nH, col_kH, col_nL, col_kL

    # --- fallback: positional order ---
    rest = [i for i in range(len(header)) if i != wl and header[i] is not None and _re_cell_str(header[i])]
    rest.sort()

    if len(rest) >= 4:
        return wl, rest[0], rest[1], rest[2], rest[3]

    if len(rest) == 3:
        return wl, rest[0], rest[1], rest[2], None

    if len(rest) == 2:
        return wl, rest[0], None, rest[1], None

    if len(rest) == 1:
        return wl, rest[0], None, None, None

    return 0, 1, 2, 3, 4



def _re_find_measurement_wavelength_column(header: tuple, data_rows: list[tuple]) -> tuple[int, str | None]:
    """Find the lambda column; returns (index, user message if ambiguous, else None)."""

    if header:
        for i, h in enumerate(header):
            if h is not None and _re_header_is_wavelength_label(_re_cell_str(h)):
                return i, None

    n = len(data_rows)

    if n < 2:
        return 0, (
            "Few rows in the sheet: the wavelength column is assumed to be the **first column (A)**; check values (nm)."
        )

    max_c = max((len(r) for r in data_rows if r), default=0)

    best_i, best_score = 0, -1.0

    for j in range(max_c):
        vals: list[float] = []

        bad = False

        for r in data_rows:
            if not r or len(r) <= j:
                bad = True

                break

            v = r[j]

            if not isinstance(v, (int, float)):
                bad = True

                break

            vals.append(float(v))

        if bad or len(vals) < 3:
            continue

        med = float(np.median(vals))

        if not (80.0 < med < 55000.0):
            continue

        dif = np.diff(vals)

        inc_ratio = float(np.sum(dif >= 0.0)) / max(len(dif), 1)

        score = inc_ratio * len(vals)

        if score > best_score:
            best_score, best_i = score, j

    if best_score >= 0.55 * n:
        # Heuristic clear enough: no user alert (see business logs if needed).

        return best_i, None

    return 0, (
        "**lambda** column not discriminative enough: falling back to **column A**. "
        "Add a header such as 'wavelength (nm)' on the correct column if needed."
    )


def _re_measurement_values_are_percent(vals: list[float]) -> bool:

    arr = np.asarray(vals, dtype=np.float64)

    arr = arr[np.isfinite(arr)]

    if arr.size == 0:
        return True

    return float(np.nanmax(np.abs(arr))) > 1.25



def _re_trf_residual_rms(residual: np.ndarray | None) -> float:
    """RMS of the residual vector as minimized by least_squares: sqrt(mean(r_i^2))."""

    if residual is None:
        return float("nan")

    v = np.asarray(residual, dtype=np.float64).ravel()

    if v.size == 0:
        return 0.0

    return float(np.sqrt(np.mean(v * v)))


def _re_backside_bundle_fixed(ep_local, n_layers_sel, n_sub_sel, wls_sel, var_idx, angle, is_s_pol) -> Any:

    from certus_physics import compute_oblique_backside_bundle_analytic

    return compute_oblique_backside_bundle_analytic(
        ep_local, n_layers_sel, n_sub_sel, wls_sel, var_idx, angle, is_s_pol, None, None
    )


def _re_eval_angle_physics_for(
    sub, angle, pl, inc_back, ep_use, n_layers_all, n_sub_all, wls_all, pos_all, var_idx
) -> tuple:

    from certus_physics import compute_oblique_rt_and_grads_analytic

    if sub is None:
        wls_s = wls_all

        n_lay_s = n_layers_all

        n_sub_s = n_sub_all

    else:
        wls_s = wls_all[sub]

        n_lay_s = n_layers_all[sub, :]

        n_sub_s = n_sub_all[sub]

    if pl == "avg":
        if not inc_back:
            Rs, Ts, dRs, dTs = compute_oblique_rt_and_grads_analytic(
                ep_use, n_lay_s, n_sub_s, wls_s, var_idx, angle, True, False
            )

            Rp, Tp, dRp, dTp = compute_oblique_rt_and_grads_analytic(
                ep_use, n_lay_s, n_sub_s, wls_s, var_idx, angle, False, False
            )

            return 0.5 * (Rs + Rp), 0.5 * (dRs + dRp), 0.5 * (Ts + Tp), 0.5 * (dTs + dTp)

        else:
            yRs, dRs, yTs, dTs = _re_backside_bundle_fixed(ep_use, n_lay_s, n_sub_s, wls_s, var_idx, angle, True)

            yRp, dRp, yTp, dTp = _re_backside_bundle_fixed(ep_use, n_lay_s, n_sub_s, wls_s, var_idx, angle, False)

            return 0.5 * (yRs + yRp), 0.5 * (dRs + dRp), 0.5 * (yTs + yTp), 0.5 * (dTs + dTp)

    else:
        is_s_pol = pl != "p"

        if not inc_back:
            rR, rT, rdR, rdT = compute_oblique_rt_and_grads_analytic(
                ep_use, n_lay_s, n_sub_s, wls_s, var_idx, angle, is_s_pol, False
            )

            return rR, rdR, rT, rdT

        else:
            rR, rdR, rT, rdT = _re_backside_bundle_fixed(ep_use, n_lay_s, n_sub_s, wls_s, var_idx, angle, is_s_pol)

            return rR, rdR, rT, rdT
