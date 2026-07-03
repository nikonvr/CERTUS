from __future__ import annotations
from certus.ui.certus_index_spline_common import *

class CertusIndexSplineSpectrumUIMixin:
    """CertusIndexSplineSpectrumUIMixin."""

    def _persist_spectrum_fit_settings(self) -> None:
        """Saves step 3 to QSettings (read at next launch)."""

        if not hasattr(self, "chk_t"):
            return

        s = QSettings(_QS_SPLINE_ORG, _QS_SPLINE_APP)

        s.setValue(_QS_SPECTRUM_FIT_T, self.chk_t.isChecked())

        s.setValue(_QS_SPECTRUM_FIT_TREL, self.chk_trel.isChecked())

        s.setValue(_QS_SPECTRUM_FIT_R, self.chk_r.isChecked())

        s.setValue(_QS_SPECTRUM_WT, float(self.w_t.value()))

        s.setValue(_QS_SPECTRUM_WR, float(self.w_r.value()))

        s.setValue(_QS_NK_PROFILE_INTERP, "smooth")

    def _wire_spectrum_fit_settings_persistence(self) -> None:

        self.chk_t.toggled.connect(self._persist_spectrum_fit_settings)

        self.chk_trel.toggled.connect(self._persist_spectrum_fit_settings)

        self.chk_r.toggled.connect(self._persist_spectrum_fit_settings)

        self.w_t.valueChanged.connect(self._persist_spectrum_fit_settings)

        self.w_r.valueChanged.connect(self._persist_spectrum_fit_settings)

    def _spectrum_open_dialog_start_path(self) -> str:
        """Dernier file spectrum (pre-selection Qt) sinon last dossier suite, sinon script."""

        s = QSettings(_QS_SPLINE_ORG, _QS_SPLINE_APP)

        last_file = str(s.value(_QS_LAST_SPECTRUM, "") or "").strip()

        if last_file and Path(last_file).is_file():
            return last_file

        d = get_certus_last_dir()

        if d and Path(d).is_dir():
            return d

        return str(_SCRIPT_DIR)

    def _persist_last_spectrum_path(self, path: str) -> None:

        ap = str(Path(path).resolve(strict=False))

        self._last_spectrum_path = ap

        set_certus_last_dir(ap)

        QSettings(_QS_SPLINE_ORG, _QS_SPLINE_APP).setValue(_QS_LAST_SPECTRUM, ap)

    def _spectrum_clear_theory_probe(self) -> None:
        """Clears the n,k,T (R) grid aligned on the last model trace (spectrum context menu)."""
        self._spectrum_theory_probe_lam_nm = None
        self._spectrum_theory_probe_n = None
        self._spectrum_theory_probe_k = None
        self._spectrum_theory_probe_tt = None
        self._spectrum_theory_probe_rt = None
        self._spectrum_theory_probe_d_nm = None

    def _spectrum_x_axis_mode_current(self) -> str:
        cb = getattr(self, "cb_spectrum_xmode", None)
        if cb is None:
            return "lambda"
        d = cb.currentData()
        return str(d) if d is not None else "lambda"

    def _spectrum_view_abscissa_to_lambda_nm(self, x_view: float) -> float | None:
        """Inverse of _transform_spectrum_x: displayed abscissa -> lambda (nm)."""
        if not np.isfinite(x_view):
            return None
        mode = self._spectrum_x_axis_mode_current()
        xv = float(x_view)
        if mode == "lambda":
            return xv if xv > 0.0 else None
        if mode == "sigma":
            return (1.0 / xv) if xv > 0.0 else None
        if mode == "sigma2":
            return (1.0 / np.sqrt(xv)) if xv > 0.0 else None
        return xv if xv > 0.0 else None

    def _spectrum_theory_interp_at_lambda_nm(self, lam_nm_query: float) -> dict[str, Any]:
        """Linear interpolation of model quantities on the grid used for theoretical T/R."""

        lg0 = getattr(self, "_spectrum_theory_probe_lam_nm", None)

        def _missing_why() -> dict[str, Any]:
            return {"ok": False, "reason": "no_data"}

        if lg0 is None:
            return _missing_why()

        n0 = getattr(self, "_spectrum_theory_probe_n", None)

        k0 = getattr(self, "_spectrum_theory_probe_k", None)

        t0 = getattr(self, "_spectrum_theory_probe_tt", None)

        if n0 is None or k0 is None or t0 is None:
            return _missing_why()

        lg = np.asarray(lg0, dtype=np.float64).ravel()

        nn = np.asarray(n0, dtype=np.float64).ravel()

        kk = np.asarray(k0, dtype=np.float64).ravel()

        tt = np.asarray(t0, dtype=np.float64).ravel()

        rt_arr = getattr(self, "_spectrum_theory_probe_rt", None)

        rr = np.asarray(rt_arr, dtype=np.float64).ravel() if rt_arr is not None else None

        m = np.isfinite(lg) & np.isfinite(nn) & np.isfinite(kk) & np.isfinite(tt)

        if rr is not None and rr.shape == lg.shape:
            m = m & np.isfinite(rr)

        elif rr is not None:
            rr = None

        if not np.any(m):
            return {"ok": False, "reason": "no_finite_points"}

        lam_use = lg[m]

        order = np.argsort(lam_use, kind="mergesort")

        xs = lam_use[order]

        if xs.size < 1:
            return {"ok": False, "reason": "no_finite_points"}

        lo, hi = float(xs[0]), float(xs[-1])

        lam_q = float(lam_nm_query)

        span = hi - lo

        tol = max(1e-9 * span, 1e-12)

        if lam_q < lo - tol or lam_q > hi + tol:
            out: dict[str, Any] = {
                "ok": False,
                "reason": "outside",
                "lambda_lo_nm": lo,
                "lambda_hi_nm": hi,
                "lambda_nm": lam_q,
                "d_nm": getattr(self, "_spectrum_theory_probe_d_nm", float("nan")),
            }

            return out

        nn_s = nn[m][order]

        kk_s = kk[m][order]

        tt_s = tt[m][order]

        out_ok: dict[str, Any] = {
            "ok": True,
            "lambda_nm": lam_q,
            "n": float(np.interp(lam_q, xs, nn_s)),
            "k": float(np.interp(lam_q, xs, kk_s)),
            "t_model": float(np.interp(lam_q, xs, tt_s)),
            "d_nm": getattr(self, "_spectrum_theory_probe_d_nm", float("nan")),
        }

        if rr is not None:
            rr_use = rr[m][order]

            out_ok["r_model"] = float(np.interp(lam_q, xs, rr_use))

        else:
            out_ok["r_model"] = None

        return out_ok

    def _spectrum_probe_d_nm_crosshair_txt(self) -> str:
        d_nm = getattr(self, "_spectrum_theory_probe_d_nm", None)
        if d_nm is not None and np.isfinite(float(d_nm)):
            return f"{float(d_nm):.2f} nm"
        return "—"

    def _spectrum_T_crosshair_formatter(self, x_view: float, y_show: float | None, y_raw: float) -> str:
        """Spectrum tooltip: lambda, n, k, d (model grid) + tracked ordinate on the curve."""
        yt = (
            float(y_show)
            if y_show is not None and np.isfinite(float(y_show))
            else float(y_raw if np.isfinite(float(y_raw)) else float("nan"))
        )
        y_bit = f"y ≈ {yt:.6g}" if np.isfinite(yt) else "y = —"
        d_txt = self._spectrum_probe_d_nm_crosshair_txt()
        lam_hint = self._spectrum_view_abscissa_to_lambda_nm(float(x_view))
        if lam_hint is None:
            return f"x = {float(x_view):.5g}  |  {y_bit}  |  λ n k —  |  d = {d_txt}"

        lg0 = getattr(self, "_spectrum_theory_probe_lam_nm", None)
        if lg0 is None:
            return f"λ (indic.) = {float(lam_hint):.4f} nm  |  {y_bit}  |  n k: no model  |  d = {d_txt}"

        res = self._spectrum_theory_interp_at_lambda_nm(float(lam_hint))
        if not res.get("ok"):
            if str(res.get("reason", "")) == "outside":
                lq = float(res.get("lambda_nm", lam_hint))
                lo = float(res.get("lambda_lo_nm", float("nan")))
                hi = float(res.get("lambda_hi_nm", float("nan")))
                return f"λ = {lq:.4f} nm  (outside grid [{lo:.1f}–{hi:.1f}] nm)\nn = —    k = —    d = {d_txt}\n{y_bit}"
            return f"λ = {float(lam_hint):.4f} nm  |  n = —  k = —  |  d = {d_txt}  |  {y_bit}"

        ln = float(res["lambda_nm"])
        return f"λ = {ln:.4f} nm    n = {float(res['n']):.5f}    k = {float(res['k']):.4e}    d = {d_txt}\n{y_bit}"

    def _spectrum_plot_context_menu_augment(
        self,
        plot: Any,
        menu: Any,
        _widget_pos: Any,
        view_x: float,
        view_y: float,
    ) -> None:
        if plot is not getattr(self, "plot_T", None):
            return

        if getattr(self, "_spectrum_theory_probe_lam_nm", None) is None:
            return

        act_show = menu.addAction("Show n, k, T (model) at clicked point…")

        act_show.triggered.connect(lambda *_, vx=view_x, vy=view_y: self._spectrum_show_theory_probe_dialog(vx, vy))

        act_copy = menu.addAction("Copy λ, n, k, d, T (R) model at point — TSV")

        act_copy.triggered.connect(lambda *_, vx=view_x, vy=view_y: self._spectrum_copy_theory_probe_tsv(vx, vy))

    def _spectrum_show_theory_probe_dialog(self, view_x: float, view_y: float) -> None:

        lam = self._spectrum_view_abscissa_to_lambda_nm(view_x)

        if lam is None:
            QMessageBox.information(
                self,
                "Spectrum",
                "Invalid click abscissa (λ ≤ 0 or coordinate not convertible to wavelength).",
            )

            return

        res = self._spectrum_theory_interp_at_lambda_nm(float(lam))

        if not res.get("ok"):
            rsn = str(res.get("reason", ""))

            if rsn == "outside":
                d_o = res.get("d_nm")

                d_line = f"\nd displayed = {float(d_o):.4f} nm" if d_o is not None and np.isfinite(float(d_o)) else ""

                QMessageBox.information(
                    self,
                    "Spectrum",
                    (
                        f"λ = {res.get('lambda_nm', float('nan')):.4f} nm is outside model grid "
                        f"[{res.get('lambda_lo_nm', float('nan')):.4f} ; "
                        f"{res.get('lambda_hi_nm', float('nan')):.4f}] nm.\n"
                        "n, k, T values are interpolated only on this grid."
                        f"{d_line}"
                    ),
                )

            else:
                QMessageBox.information(
                    self,
                    "Spectrum",
                    "No n,k,T model grid available for this plot. Load a fit result or plot the model spectrum.",
                )

            return

        lines = [
            f"λ = {float(res['lambda_nm']):.6f} nm",
            f"n = {float(res['n']):.8f}",
            f"k = {float(res['k']):.6e}",
        ]

        d_nm = res.get("d_nm")

        if d_nm is not None and np.isfinite(float(d_nm)):
            lines.append(f"d = {float(d_nm):.4f} nm")

        else:
            lines.append("d = (undefined)")

        lines.append(f"T (model) = {float(res['t_model']):.8f}")
        rr = res.get("r_model")
        if rr is not None and np.isfinite(float(rr)):
            lines.append(f"R (model) = {float(rr):.8f}")

        xm = self._spectrum_x_axis_mode_current()

        lines.append("")

        lines.append(f"Abscissa mode : {xm} | x_view = {view_x:.8g} | y_view ≈ {view_y:.8g}")

        QMessageBox.information(self, "Model at point (spectrum)", "\n".join(lines))

    def _spectrum_copy_theory_probe_tsv(self, view_x: float, view_y: float) -> None:

        lam = self._spectrum_view_abscissa_to_lambda_nm(view_x)

        if lam is None:
            QMessageBox.information(
                self,
                "Spectrum",
                "Invalid click abscissa; nothing to copy.",
            )

            return

        res = self._spectrum_theory_interp_at_lambda_nm(float(lam))

        if not res.get("ok"):
            rsn = str(res.get("reason", ""))

            if rsn == "outside":
                QMessageBox.information(
                    self,
                    "Spectrum",
                    'λ outside model grid: copy cancelled (see "Display n, k...").',
                )

            else:
                QMessageBox.information(self, "Spectrum", "No model data to copy.")

            return

        d_cell = f"{float(res['d_nm']):.10g}" if res.get("d_nm") is not None and np.isfinite(float(res["d_nm"])) else ""

        hdr = "lambda_nm\tn\tk\td_nm\tt_model"

        row = f"{float(res['lambda_nm']):.10g}\t{float(res['n']):.10g}\t{float(res['k']):.10g}\t{d_cell}\t{float(res['t_model']):.10g}"

        rr = res.get("r_model")

        if rr is not None and np.isfinite(float(rr)):
            row += f"\t{float(rr):.10g}"

            hdr += "\tr_model"

        QApplication.clipboard().setText(hdr + "\n" + row + "\n")

        QMessageBox.information(self, "Spectrum", "A TSV line (header + values) was copied.")

    def _transform_spectrum_x(self, lam_nm: np.ndarray) -> tuple[np.ndarray, str]:

        mode = str(
            getattr(self, "cb_spectrum_xmode", None).currentData() if hasattr(self, "cb_spectrum_xmode") else "lambda"
        )

        lam = np.asarray(lam_nm, dtype=np.float64).ravel()

        if mode == "sigma":
            return 1.0 / np.maximum(lam, 1e-30), "sigma (nm?1)"

        if mode == "sigma2":
            s = 1.0 / np.maximum(lam, 1e-30)

            return s * s, "sigma2 (nm?2)"

        return lam, "lambda (nm)"

    def _apply_spectrum_x_axis_label(self, lbl: str) -> None:
        try:
            self.plot_T.setLabel("bottom", lbl)
        except (AttributeError, RuntimeError):
            try:
                self.plot_T.plotItem.setLabel("bottom", lbl)
            except (AttributeError, RuntimeError):
                logger.debug("_apply_spectrum_x_axis_label failed", exc_info=True)

    def _on_spectrum_x_mode_changed(self) -> None:

        if self._last_result is not None:
            self._plot_result(self._last_result, plot_source="abscisse_spectral")

        elif self.df is not None:
            self._plot_data_raw()

    def _format_spectrum_plot_title(self, r: dict) -> str:
        """Spectrum plot title: RMSE and thickness of the displayed snapshot + config summary."""

        rmse = float(r.get("rmse", float("nan")))

        d_nm = float(r.get("d_nm", float("nan")))

        rmse_s = f"{rmse:.6f}" if np.isfinite(rmse) else ""

        d_s = f"{d_nm:.2f} nm" if np.isfinite(d_nm) else ""

        rmse_lbl = "RMSE (bande lambda)" if r.get("rmse_fit_lambda_nm") is not None else "RMSE"

        bits: list[str] = []

        sk = r.get("sigma_knots")

        k_sig = int(np.asarray(sk, dtype=np.float64).size) if sk is not None else 0

        if k_sig > 0:
            bits.append(f"Ksigma={k_sig} ({k_sig - 1} seg.)")

        bits.append("interp sigma=cubic spline")

        if r.get("auto_knot_stages"):
            kb = r.get("auto_knots_K_best")

            if kb is not None:
                bits.append(f"auto-K (K*={int(kb)})")

            else:
                bits.append("auto-K")

        prof = str(self.cb_profilee.currentData() or "").strip() if hasattr(self, "cb_profilee") else ""

        if prof and prof != "fast":
            bits.append(f"profile={prof}")

        cfg_s = "  ".join(bits) if bits else ""

        return f"Spectrum  {rmse_lbl} {rmse_s}  d={d_s}  {cfg_s}"

    def _apply_spectrum_plot_title(self, r: dict | None) -> None:

        t = "Spectrum" if r is None else self._format_spectrum_plot_title(r)

        self.plot_T.plotItem.setTitle(t, color=CertusTheme.PRIMARY, size="11pt")

        self.plot_T._certus_init_title = t

    def _spectrum_plot_lambda_span_nm(self) -> tuple[float, float] | None:
        """lambda span of displayed spectrum (file first, else last result grid)."""

        if self.df is not None and "lambda" in self.df.columns:
            lam = ensure_lam_nm_array(self.df["lambda"].to_numpy(dtype=np.float64))

            lam = lam[np.isfinite(lam)]

            if lam.size:
                return float(np.min(lam)), float(np.max(lam))

        lr = getattr(self, "_last_result", None)

        if lr is not None and lr.get("lam_nm") is not None:
            lam = np.asarray(lr["lam_nm"], dtype=np.float64).ravel()

            lam = lam[np.isfinite(lam)]

            if lam.size:
                return float(np.min(lam)), float(np.max(lam))

        return None
