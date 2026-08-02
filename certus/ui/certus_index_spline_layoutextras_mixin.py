from __future__ import annotations
from certus.ui.certus_index_spline_common import *
from certus.ui.certus_index_spline_common import _apply_fixed_log_k_axis

class CertusIndexSplineLayoutExtrasMixin:
    """CertusIndexSplineLayoutExtrasMixin."""

    def _build_controls_basic_panel(self) -> QWidget:
        """Steps 2 to 4: substrate / thickness, spectral targets, mesh and optimizer."""
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(2, 2, 2, 2)
        v.setSpacing(6)
        gst = self._control_group_box_style()
        hint = QLabel("Order: 2 → 3 → 4")
        hint.setWordWrap(False)
        hint.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px;")
        v.addWidget(hint)
        self._build_basic_step2_substrate_thickness(v, gst)
        self._build_basic_step3_spectral_targets(v, gst)
        self._build_basic_step4_mesh_optimizer(v, gst)
        return w

    def _build_tab_indices(self) -> QWidget:
        # Empty page for context_stack synchronization
        self._add_context_page(
            self._create_empty_context_widget("Standard refractive index plots.\nNo specific settings for this tab.")
        )

        panel = QWidget()
        lay = QVBoxLayout(panel)

        lay.setContentsMargins(0, 0, 0, 0)

        self.plot_n = CertusScientificPlot(title="n(lambda)", y_label="n", x_label="lambda (nm)")

        self.plot_n.showGrid(x=True, y=True, alpha=0.25)

        self.plot_k = CertusScientificPlot(title="k(lambda)", y_label="k", x_label="lambda (nm)")

        self.plot_k.showGrid(x=True, y=True, alpha=0.25)

        _apply_fixed_log_k_axis(self.plot_k)
        self.plot_k._certus_crosshair_label_fn = self._k_crosshair_formatter

        spl = QSplitter(Qt.Orientation.Vertical)

        spl.addWidget(wrap_scientific_plot_with_toolbar(self, self.plot_n))

        spl.addWidget(wrap_scientific_plot_with_toolbar(self, self.plot_k))

        spl.setStretchFactor(0, 1)

        spl.setStretchFactor(1, 1)

        lay.addWidget(spl, 1)

        return panel

    def _build_tab_log(self) -> QWidget:

        w = QWidget()

        lay = QVBoxLayout(w)

        lay.setContentsMargins(12, 12, 12, 12)

        info = QLabel(
            "The detailed stream (local stages, K stages, polish, continuous laws) appears in the "
            "<b>OPTIMIZATION LOG</b> panel under the plots. "
            "Use <b>Copy Logs</b> on that panel to copy all text."
        )

        info.setWordWrap(True)

        info.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px;")

        lay.addWidget(info)

        lay.addStretch(1)

        return w

    def _build_tab_why(self) -> QWidget:

        panel = QWidget()

        grid = QGridLayout(panel)

        grid.setSpacing(16)

        grid.setContentsMargins(24, 24, 24, 24)

        intro = QLabel(
            "<b>CERTUS-INDEX-SPLINE.</b> Global fit of "
            "<i>n(lambda)</i>, <i>k(lambda)</i> as piecewise-linear in sigma=1/lambda (ln k at knots), "
            "with <b>local L-BFGS-B</b> polish. Advanced mode: catalog of continuous laws "
            "on normalized <i>u</i> and 19-D re-optimization if spectral RMSE improves."
        )

        intro.setWordWrap(True)

        intro.setStyleSheet(f"color: {CertusTheme.TEXT_SUB}; font-size: 11px;")

        grid.addWidget(intro, 0, 0, 1, 2)

        cards = [
            ("Local L-BFGS-B", "Local optimization with tunable budgets.", ""),
            ("Spectral weights Deltaln lambda", "RMSE weighted trapezoidal rule on ln lambda grid (no cap).", ""),
            ("Auto-K and adaptive mesh", "K growth or SMART-style sigma insertions; warm start.", ""),
            ("Continuous laws (advanced)", "Rank n(u), ln k(u) families then optimize d + 18 parameters.", ""),
        ]

        for i, (title, desc, icon) in enumerate(cards):
            grid.addWidget(FlashyCard(title, desc, icon=icon), 1 + i // 2, i % 2)

        return panel
