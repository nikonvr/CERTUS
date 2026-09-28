from __future__ import annotations
from certus.utils.certus_re_math import re_substrate_cauchy_n_re_from_theta
import numpy as np
import pyqtgraph as pg


from certus.ui.certus_qt_widgets import (
    Qt,
)

from certus_physics import Layer, calc_spectrum_front_wrapper, calc_spectrum_full_exact_wrapper



from certus.ui.certus_ui import (
    CertusTheme,
)


from certus.utils.certus_re_helpers import (
    RE_SPLINE_NODE2_DEFAULT_NM,
    RE_SPLINE_N_KNOTS,
    re_interp_delta_knots_clamped,
    re_knots_wavelengths,
)
calc_spectrum_front = calc_spectrum_front_wrapper
calc_spectrum_full_exact = calc_spectrum_full_exact_wrapper


class CertusREPlotMixin:
    """CertusREPlotMixin for CERTUS_RE."""

    def _on_update_spectrum_y_scale_signal(self, *_args) -> None:

        self._update_spectrum_y_scale()

    def _plot_profile(
        self,
        ep: np.ndarray,
        stack: list[Layer],
    ):
        """Update n,k display in spectrum widget."""

        # ... logic ...

        """Refractive index profile (front side only  RE without rear coating)."""

        for plot_widget in self._get_plot_targets("profile", self.profile_plot):
            plot_widget.plotItem.clear()

            mats = self._get_materials()

            if "Substrate" not in mats:
                continue

            ns = mats["Substrate"].n4

            x, y = [0.0, 0.0], [ns, mats[stack[0].mat].n4] if stack else [ns, 1.0]

            if ep is not None and len(ep) > 0:
                cs = np.cumsum(ep)

                n_vals = [mats[l.mat].n4 for l in stack]

                # Protection against index out of bounds (oblique mode may have more thicknesses than layers)

                n_layers = min(len(ep) - 1, len(n_vals) - 1)

                for i in range(n_layers):
                    x.extend([cs[i], cs[i]])

                    y.extend([n_vals[i], n_vals[i + 1]])

                if n_vals:
                    x.extend([cs[-1], cs[-1], cs[-1] + max(50.0, 0.1 * cs[-1])])

                    y.extend([n_vals[-1], 1.0, 1.0])

            else:
                x, y = [0.0, 50.0], [ns, 1.0]

            plot_widget.plot(
                x,
                y,
                pen=pg.mkPen(CertusTheme.PRIMARY, width=2),
                fillLevel=0,
                brush=(30, 58, 138, 30),
            )

    def _plot_nk(self):
        """n(lambda) curves. If RE loaded: extended range; dashed = corrected Re (DeltaRe splines or drift %)."""

        mats = self._get_materials()

        cols = [
            CertusTheme.PRIMARY,
            CertusTheme.SECONDARY,
            CertusTheme.ACCENT,
            CertusTheme.SUCCESS,
            CertusTheme.WARNING,
            CertusTheme.ERROR,
        ]

        re_loaded = getattr(self, "_re_loaded", False)

        re_busy = getattr(self, "_re_mode_active", False)

        if re_loaded and getattr(self, "_re_tabular_H", None) is not None:
            wf = np.asarray(self._re_tabular_H.wls_nm, dtype=np.float64)

            if wf.size >= 2:
                w_dense = np.linspace(float(wf[0]), float(wf[-1]), max(400, int(wf.size) * 4))

                w = np.unique(np.concatenate([wf, w_dense]))

            elif wf.size == 1:
                w = np.linspace(max(200.0, wf[0] - 200), wf[0] + 2000.0, 300)

            else:
                w = np.linspace(380.0, 5500.0, 600)

        elif re_loaded:
            w = np.linspace(380.0, 5500.0, 600)

        else:
            w = np.linspace(380.0, 1000.0, 400)

        a_gui = float(getattr(self, "_re_opt_a_pct", 0.0)) if re_loaded else 0.0

        b_gui = float(getattr(self, "_re_opt_b_pct", 0.0)) if re_loaded else 0.0

        _nksp = RE_SPLINE_N_KNOTS

        if re_busy:
            dH_st = getattr(self, "_re_nk_preview_dH", None)

            dL_st = getattr(self, "_re_nk_preview_dL", None)

            _lam2_pv = getattr(self, "_re_nk_preview_lam2", None)

            sub012_pv = getattr(self, "_re_nk_preview_sub012", None)

        else:
            dH_st = getattr(self, "_re_spline_dH", None)

            dL_st = getattr(self, "_re_spline_dL", None)

            _lam2_pv = getattr(self, "_re_spline_lam2_nm", None)

            sub012_pv = None

        use_sp = (
            re_loaded
            and dH_st is not None
            and dL_st is not None
            and len(np.asarray(dH_st).ravel()) == _nksp
            and len(np.asarray(dL_st).ravel()) == _nksp
        )

        if use_sp:
            dh_arr = np.asarray(dH_st, dtype=np.float64).ravel()

            dl_arr = np.asarray(dL_st, dtype=np.float64).ravel()

            show_renk_corr = re_loaded and (
                np.max(np.abs(dh_arr)) > 1e-12
                or np.max(np.abs(dl_arr)) > 1e-12
                or (sub012_pv is not None and len(sub012_pv) == 3 and max(abs(float(x)) for x in sub012_pv) > 1e-12)
            )

        else:
            show_renk_corr = re_loaded and (abs(a_gui) > 1e-12 or abs(b_gui) > 1e-12)

        for plot_widget in self._get_plot_targets("nk", self.nk_plot):
            plot_widget.plotItem.clear()

            for i, (k, m) in enumerate(mats.items()):
                n_nominal = m.get_nk(w).real

                plot_widget.plot(
                    w,
                    n_nominal,
                    pen=pg.mkPen(cols[i % len(cols)], width=2),
                    name=k,
                )

            if show_renk_corr:
                if use_sp:
                    _lam2_pl = float(_lam2_pv) if _lam2_pv is not None else float(RE_SPLINE_NODE2_DEFAULT_NM)

                    _kw_pl = re_knots_wavelengths(_lam2_pl)

                    _es_nk = self._re_envelope_scale_from_gui()

                    dHv = re_interp_delta_knots_clamped(
                        _kw_pl,
                        np.asarray(dH_st, dtype=np.float64),
                        w,
                        envelope_scale=_es_nk,
                    )

                    dLv = re_interp_delta_knots_clamped(
                        _kw_pl,
                        np.asarray(dL_st, dtype=np.float64),
                        w,
                        envelope_scale=_es_nk,
                    )

                    for i, (k, m) in enumerate(mats.items()):
                        if k == "H":
                            n_corr = m.get_nk(w).real + dHv

                        elif k == "L":
                            n_corr = m.get_nk(w).real + dLv

                        elif k == "Substrate":
                            lr = float(self.l0_spin.value())

                            if sub012_pv is not None and len(sub012_pv) == 3:
                                ths = np.asarray(sub012_pv, dtype=np.float64)

                            else:
                                _sa = getattr(self, "_re_sub_cauchy_a0", None)

                                _s1 = getattr(self, "_re_sub_cauchy_a1", None)

                                _s2 = getattr(self, "_re_sub_cauchy_a2", None)

                                if _sa is None or _s1 is None or _s2 is None:
                                    continue

                                ths = np.array(
                                    [float(_sa), float(_s1), float(_s2)],
                                    dtype=np.float64,
                                )

                            n_corr = re_substrate_cauchy_n_re_from_theta(w, lr, ths)

                        else:
                            continue

                        pen = pg.mkPen(cols[i % len(cols)], width=2, style=Qt.PenStyle.DashLine)

                        plot_widget.plot(
                            w,
                            n_corr,
                            pen=pen,
                            name=f"{k} corrected",
                        )

                else:
                    a_pct = a_gui

                    b_pct = b_gui

                    lambda_ref = float(self.l0_spin.value())

                    wls_drift_denom = max(5200.0 - lambda_ref, 1.0)

                    t = np.clip((w - lambda_ref) / wls_drift_denom, 0.0, None)

                    drift_factor = t**3

                    for i, (k, m) in enumerate(mats.items()):
                        if k == "H":
                            mult = 1.0 + (a_pct / 100.0) * drift_factor

                        elif k == "L":
                            mult = 1.0 + (b_pct / 100.0) * drift_factor

                        else:
                            continue

                        n_corr = m.get_nk(w).real * mult

                        pen = pg.mkPen(cols[i % len(cols)], width=2, style=Qt.PenStyle.DashLine)

                        plot_widget.plot(
                            w,
                            n_corr,
                            pen=pen,
                            name=f"{k} corrected",
                        )

    def _re_clear_re_nk_preview(self) -> None:
        """Reset n(lambda) preview synchronized with the RE worker."""

        self._re_nk_preview_dH = None

        self._re_nk_preview_dL = None

        self._re_nk_preview_lam2 = None

        self._re_nk_preview_sub012 = None

    def _re_init_plot_factors(self, wls, spline_dH, spline_dL):

        mats = self._get_materials()

        lam_ref = float(self.l0_spin.value())

        drift_factor = np.clip((wls - lam_ref) / max(5200.0 - lam_ref, 1.0), 0.0, None) ** 3

        use_sp = (
            spline_dH is not None
            and spline_dL is not None
            and len(np.asarray(spline_dH).ravel()) == int(RE_SPLINE_N_KNOTS)
            and len(np.asarray(spline_dL).ravel()) == int(RE_SPLINE_N_KNOTS)
        )

        return mats, drift_factor, use_sp

    def _update_re_spectrum_title(self, rmse=None, suffix=""):
        """Update spectrum plot title with RE RMSE."""

        n_layers = self.front_table.rowCount()

        title = f"RE Spectrum ({n_layers} layers)"

        if rmse is not None and np.isfinite(rmse):
            title += f"  RMSE: {rmse:.6f}"

        if suffix:
            title += f" {suffix}"

        self.spectrum_plot.plotItem.setTitle(title, color=CertusTheme.PRIMARY, size="11pt")

    def _re_spline_lam2_nm_from_result(self, r: dict) -> float:

        _kw = r.get("re_knots_nm")

        if _kw is not None and len(_kw) > 1:
            return float(np.asarray(_kw, dtype=np.float64).ravel()[1])

        _lv = r.get("re_spline_lam_node2_nm")

        if _lv is not None:
            return float(_lv)

        return float(RE_SPLINE_NODE2_DEFAULT_NM)
