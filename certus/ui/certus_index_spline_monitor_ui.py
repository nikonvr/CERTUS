from __future__ import annotations
from certus.ui.certus_index_spline_common import *

class LiveIndexMonitor(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        # Support mock parents safely
        parent_widget = parent if isinstance(parent, QWidget) else None
        super().__init__(parent_widget)

        self.setWindowTitle("Monitoring Indices (Live)")
        self.resize(550, 700)

        l = QVBoxLayout(self)
        h = QHBoxLayout()
        h.addWidget(QLabel("X Axis Unit:"))

        self.cb = QComboBox()
        self.cb.addItems(["Lambda (nm)", "Sigma (nm⁻1)", "Sigma2 (nm⁻2)"])

        def on_unit_change() -> None:
            if hasattr(self, "_last_data"):
                self.update_indices(*self._last_data)

        self.cb.currentIndexChanged.connect(on_unit_change)
        h.addWidget(self.cb)

        self._btn_copy_nk_2nm = create_styled_button("Copy lambda, n, k (2 nm step)", "secondary", parent=self)
        self._btn_copy_nk_2nm.setToolTip(
            "Clipboard: lambda (integer nm), n, k sorted by increasing lambda, interpolated on a 2 nm grid (TSV)."
        )
        self._btn_copy_nk_2nm.clicked.connect(self._copy_nk_clipboard_2nm)
        h.addWidget(self._btn_copy_nk_2nm)

        h.addStretch()
        l.addLayout(h)

        self.lbl_d = QLabel("d =  nm")
        self.lbl_d.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px;")
        l.addWidget(self.lbl_d)

        self.p_n = CertusScientificPlot(title="Index n")
        self.p_k = CertusScientificPlot(title="Index k  Log Scale")

        _apply_fixed_log_k_axis(self.p_k)

        l.addWidget(self.p_n)
        l.addWidget(self.p_k)

        apply_certus_theme(self)

    def _copy_nk_clipboard_2nm(self) -> None:
        if not hasattr(self, "_last_data") or self._last_data is None:
            QMessageBox.information(
                self,
                "Clipboard",
                "No n, k data (wait for live update).",
            )
            return

        lam_arr, n_arr, k_arr, _ = self._last_data
        txt = _live_monitor_nk_clipboard_tsv_2nm(lam_arr, n_arr, k_arr)
        if not txt:
            QMessageBox.information(
                self,
                "Clipboard",
                "No valid points for export.",
            )
            return

        cb = QApplication.clipboard()
        if cb is None:
            QMessageBox.warning(self, "Clipboard", "Clipboard unavailable.")
            return

        cb.setText(txt)

        prev = self._btn_copy_nk_2nm.text()
        self._btn_copy_nk_2nm.setText("Copied!")
        QTimer.singleShot(
            1500,
            lambda t=prev: self._btn_copy_nk_2nm.setText(t),
        )

    def update_indices(
        self, lam_arr: np.ndarray, n_arr: np.ndarray, k_arr: np.ndarray, d_nm: float | None = None
    ) -> None:
        self._last_data = (lam_arr, n_arr, k_arr, d_nm)
        mode = self.cb.currentIndex()

        if mode == 0:
            x, lbl = lam_arr, "lambda (nm)"
        elif mode == 1:
            x, lbl = 1.0 / lam_arr, "sigma (nm⁻1)"
        else:
            x, lbl = (1.0 / lam_arr) ** 2, "sigma2 (nm⁻2)"

        if d_nm is not None and np.isfinite(float(d_nm)):
            self.lbl_d.setText(f"d = {float(d_nm):.1f} nm")

        self.p_n.setLabel("bottom", lbl)
        self.p_k.setLabel("bottom", lbl)

        if "n" not in self.p_n._curves:
            self.p_n.add_curve(x, n_arr, "n", color=CertusTheme.PRIMARY, width=2, animate=False)
        else:
            self.p_n.update_curve("n", x, n_arr, animate=False)

        if "k" not in self.p_k._curves:
            self.p_k.add_curve(x, k_arr, "k", color=CertusTheme.DANGER, width=2, animate=False)
        else:
            self.p_k.update_curve("k", x, k_arr, animate=False)

        study_fn = getattr(self, "_study_lam_window_fn", None)
        if not callable(study_fn):
            self.p_n.autoRange()
            _apply_fixed_log_k_axis(self.p_k)
            return

        try:
            lo_s, hi_s = study_fn()
        except (TypeError, ValueError, RuntimeError):
            self.p_n.autoRange()
            _apply_fixed_log_k_axis(self.p_k)
            return

        if not (hi_s > lo_s and np.isfinite(lo_s) and np.isfinite(hi_s)):
            self.p_n.autoRange()
            _apply_fixed_log_k_axis(self.p_k)
            return

        pad_l = max((hi_s - lo_s) * 0.02, 1e-6)
        lam_f = np.asarray(lam_arr, dtype=np.float64).ravel()
        n_f = np.asarray(n_arr, dtype=np.float64).ravel()
        k_f = np.asarray(k_arr, dtype=np.float64).ravel()

        npt = min(lam_f.size, n_f.size, k_f.size)
        if npt <= 0:
            self.p_n.autoRange()
            _apply_fixed_log_k_axis(self.p_k)
            return

        lam_f, n_f, k_f = lam_f[:npt], n_f[:npt], k_f[:npt]
        mwin = np.isfinite(lam_f) & (lam_f >= lo_s) & (lam_f <= hi_s)
        if not np.any(mwin):
            mwin = np.isfinite(lam_f)

        if mode == 0:
            x_lo, x_hi = float(lo_s - pad_l), float(hi_s + pad_l)
        elif mode == 1:
            x_lo = 1.0 / float(hi_s + pad_l)
            x_hi = 1.0 / float(max(lo_s - pad_l, 1e-30))
        else:
            x_lo = (1.0 / float(hi_s + pad_l)) ** 2
            x_hi = (1.0 / float(max(lo_s - pad_l, 1e-30))) ** 2

        if x_hi < x_lo:
            x_lo, x_hi = x_hi, x_lo

        pad_x = max((x_hi - x_lo) * 0.02, 1e-24)
        x0, x1 = float(x_lo - pad_x), float(x_hi + pad_x)

        self.p_n.plotItem.setXRange(x0, x1, padding=0)
        self.p_k.plotItem.setXRange(x0, x1, padding=0)

        nn = n_f[mwin]
        nn = nn[np.isfinite(nn)]
        if nn.size > 0:
            n_lo, n_hi = float(np.min(nn)), float(np.max(nn))
            pr = max((n_hi - n_lo) * 0.07, 1e-6)
            self.p_n.plotItem.setYRange(n_lo - pr, n_hi + pr, padding=0)

        _apply_fixed_log_k_axis(self.p_k)

