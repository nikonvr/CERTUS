"""DESIGN's "Compare" tab: distance between two designs and RMSE barrier along their aligned path.

The two designs are the current one and the Pareto records (one per layer count). The computations are in
``certus/core/certus_design_landscape.py`` (alignment, aligned path, string method) and ``BarrierWorker``; this module
only collects the designs, starts them and draws the results. Optical thicknesses use the real index of each material
at the reference wavelength of the Parameters section. Front face, normal incidence.
"""

from __future__ import annotations

import functools
import logging

import numpy as np
import pyqtgraph as pg

from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS
from certus.ui.certus_qt_widgets import (
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    Qt,
    QThread,
    QVBoxLayout,
    QWidget,
)
from certus.ui.certus_ui import CertusScientificPlot, CertusTheme
from certus.utils.certus_ux import OBJ

CURRENT = "current"


def build_compare_tab(ui) -> QWidget:
    """Build the tab and attach its widgets to ``ui`` (compare_*)."""
    tab = QWidget()
    lay = QVBoxLayout(tab)
    grid = QGridLayout()
    ui.compare_a_combo, ui.compare_b_combo = QComboBox(), QComboBox()
    for combo in (ui.compare_a_combo, ui.compare_b_combo):
        combo.setMinimumWidth(220)
    ui.compare_a_combo.setToolTip("Design A: the current design or a Pareto record (one per layer count).")
    ui.compare_b_combo.setToolTip("Design B: the current design or a Pareto record (one per layer count).")
    refresh = QPushButton("Refresh list")
    refresh.setToolTip("Reload the current design and the Pareto records into the two lists.")
    refresh.clicked.connect(functools.partial(refresh_design_lists, ui))
    grid.setContentsMargins(4, 4, 4, 0)
    grid.setVerticalSpacing(4)
    grid.addWidget(QLabel("A:"), 0, 0)
    grid.addWidget(ui.compare_a_combo, 0, 1)
    grid.addWidget(QLabel("B:"), 0, 2)
    grid.addWidget(ui.compare_b_combo, 0, 3)
    grid.addWidget(refresh, 0, 4)

    ui.compare_free_spin = QDoubleSpinBox()
    ui.compare_free_spin.setRange(0.0, 5000.0)
    ui.compare_free_spin.setDecimals(0)
    ui.compare_free_spin.setValue(0.0)
    ui.compare_free_spin.setToolTip(
        "Free ends (nm of optical thickness): an unmatched section at the substrate or at the air side costs\n"
        "nothing up to this length (e.g. an impedance-matching section). 0: distance between whole profiles.")
    ui.compare_iter_spin = QSpinBox()
    ui.compare_iter_spin.setRange(0, 100000)
    ui.compare_iter_spin.setValue(3000)
    ui.compare_iter_spin.setToolTip("Iterations of the string method (0: straight path only).")
    ui.compare_images_spin = QSpinBox()
    ui.compare_images_spin.setRange(3, 201)
    ui.compare_images_spin.setValue(33)
    ui.compare_images_spin.setToolTip("Images (designs) along the path.")
    params = QHBoxLayout()
    for label, widget in (("Free ends (nm OT):", ui.compare_free_spin), ("String iterations:", ui.compare_iter_spin),
                          ("Images:", ui.compare_images_spin)):
        params.addWidget(QLabel(label))
        params.addWidget(widget)
    params.addStretch()
    grid.addLayout(params, 1, 0, 1, 7)
    lay.setSpacing(4)
    lay.addLayout(grid)

    ui.compare_distance_btn = QPushButton("Distance")
    ui.compare_distance_btn.setObjectName(OBJ.PRIMARY_BUTTON)
    ui.compare_distance_btn.setToolTip(
        "Align the two designs (match, gap, merge of a needle; Needleman-Wunsch) and give the cost in nm of optical\n"
        "thickness and as a share of the mean total optical thickness. Instant.")
    ui.compare_distance_btn.clicked.connect(functools.partial(run_distance, ui))
    ui.compare_barrier_btn = QPushButton("Barrier")
    ui.compare_barrier_btn.setObjectName(OBJ.PRIMARY_BUTTON)
    ui.compare_barrier_btn.setToolTip(
        "RMSE along the aligned path from A to B: straight path, then relaxed by the string method (E, Ren,\n"
        "Vanden-Eijnden 2007). The highest RMSE on the string is an upper bound of the pass between the two designs.\n"
        "Click again to stop. Normal incidence, front face.")
    ui.compare_barrier_btn.clicked.connect(functools.partial(toggle_barrier, ui))
    grid.addWidget(ui.compare_distance_btn, 0, 5)
    grid.addWidget(ui.compare_barrier_btn, 0, 6)

    ui.compare_result_label = QLabel("Choose two designs, then Distance or Barrier.")
    ui.compare_result_label.setWordWrap(True)
    ui.compare_result_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    lay.addWidget(ui.compare_result_label)

    plots = QHBoxLayout()
    ui.compare_profile_plot = CertusScientificPlot(ui, "Index profiles (A, B)", "n", "optical thickness from the substrate (nm)")
    ui.compare_profile_plot.addLegend()
    ui.compare_profile_a = ui.compare_profile_plot.plot([], [], stepMode="center", pen=pg.mkPen(CertusTheme.PRIMARY, width=2),
                                                        name="A")
    ui.compare_profile_b = ui.compare_profile_plot.plot([], [], stepMode="center",
                                                        pen=pg.mkPen(CertusTheme.SECONDARY, width=2), name="B")
    ui.compare_path_plot = CertusScientificPlot(ui, "RMSE along the path A → B", "RMSE", "s (0 = A, 1 = B)")
    ui.compare_path_plot.showGrid(x=True, y=True)
    ui.compare_path_plot.addLegend()
    ui.compare_straight_curve = ui.compare_path_plot.plot(
        [], [], pen=pg.mkPen(CertusTheme.SECONDARY, width=1.5, style=Qt.PenStyle.DashLine), name="straight")
    ui.compare_string_curve = ui.compare_path_plot.plot([], [], pen=pg.mkPen(CertusTheme.ERROR, width=2), name="string")
    for plot in (ui.compare_profile_plot, ui.compare_path_plot):
        plot.setMinimumHeight(240)
        plots.addWidget(plot)
    lay.addLayout(plots, 1)
    ui.compare_thread = None
    return tab


def refresh_on_tab_shown(ui, tab, index: int) -> None:
    """Slot of the plot tabs' currentChanged: refresh the lists when the Compare tab is shown."""
    if ui.plot_tabs.widget(index) is tab:
        refresh_design_lists(ui)


def refresh_design_lists(ui, *_signal_args) -> None:
    """Fill both lists with the current design and the Pareto records, keeping the selections when possible."""
    items = []
    if getattr(ui, "last_result", None) and ui.last_result.get("ep") is not None:
        items.append(("Current design", CURRENT))
    for n, rec in sorted((getattr(ui, "pareto_history", {}) or {}).items()):
        if rec.get("ep_rmse") is not None and rec.get("table_rmse"):
            items.append((f"Pareto N={n} (RMSE {float(rec.get('best_rmse', np.nan)):.4g})", n))
    for k, combo in enumerate((ui.compare_a_combo, ui.compare_b_combo)):
        keep = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        for label, key in items:
            combo.addItem(label, key)
        idx = combo.findData(keep) if keep is not None else -1
        combo.setCurrentIndex(idx if idx >= 0 else min(k, combo.count() - 1))
        combo.blockSignals(False)


def _design(ui, key) -> tuple[list[str], np.ndarray]:
    """(materials, physical thicknesses) of the current design or of a Pareto record."""
    if key == CURRENT:
        return [layer.mat for layer in ui._get_front_stack()], np.asarray(ui.last_result["ep"], dtype=np.float64)
    rec = ui.pareto_history[key]
    return [row["mat"] for row in rec["table_rmse"]], np.asarray(rec["ep_rmse"], dtype=np.float64)


def _index_at_l0(ui):
    mats, l0 = ui._get_materials(), float(ui.l0_spin.value())
    cache: dict[str, float] = {}

    def n_of(m: str) -> float:
        if m not in cache:
            cache[m] = float(np.real(mats[m].get_nk(np.array([l0]))[0]))
        return cache[m]

    return n_of


def _selected(ui):
    from certus.core.certus_design_landscape import optical_layers

    ka, kb = ui.compare_a_combo.currentData(), ui.compare_b_combo.currentData()
    if ka is None or kb is None:
        ui.log("Compare: no design to compare (evaluate the design or run an optimization, then Refresh list).",
               "WARNING")
        return None
    n_of = _index_at_l0(ui)
    out = []
    for key in (ka, kb):
        mats, ep = _design(ui, key)
        out.append(optical_layers(mats, ep, np.array([n_of(m) for m in mats])))
    return out[0], out[1], n_of


def _draw_profiles(ui, a, b, n_of) -> None:
    for design, curve in ((a, ui.compare_profile_a), (b, ui.compare_profile_b)):
        edges = np.concatenate([[0.0], np.cumsum([t for _m, t in design])])
        curve.setData(edges, np.array([n_of(m) for m, _t in design]))


def run_distance(ui, *_signal_args) -> None:
    """Align the selected designs, show the distance and the index profiles."""
    from certus.core.certus_design_landscape import align_designs

    picked = _selected(ui)
    if picked is None:
        return
    a, b, n_of = picked
    try:
        al = align_designs(a, b, free_nm=float(ui.compare_free_spin.value()))
    except (*NUMERICAL_FAULT_EXCEPTIONS, KeyError) as e:
        ui.log(f"Compare: distance failed ({e}).", "ERROR")
        return
    kinds = {k: sum(1 for m in al.moves if m[0] == k) for k in ("match", "gap A", "gap B", "merge A", "merge B")}
    i0, j0 = al.start
    text = (f"Distance A–B: {al.cost_nm:.1f} nm of optical thickness, {100 * al.fraction:.1f} % of the mean total "
            f"optical thickness (A: {len(a)} layers, {sum(t for _m, t in a):.0f} nm; B: {len(b)} layers, "
            f"{sum(t for _m, t in b):.0f} nm). Moves: " + ", ".join(f"{k} {v}" for k, v in kinds.items() if v)
            + f". Cores aligned from layer {i0 + 1} of A and {j0 + 1} of B.")
    ui.compare_result_label.setText(text)
    ui.log(text, "INFO")
    _draw_profiles(ui, a, b, n_of)


def toggle_barrier(ui, *_signal_args) -> None:
    """Start the barrier computation, or stop it when it runs."""
    thread = getattr(ui, "compare_thread", None)
    if thread is not None:
        try:
            if thread.isRunning():
                thread.requestInterruption()
                ui.log("Compare: barrier stop requested (the string so far is kept).", "INFO")
                return
        except RuntimeError:
            logging.getLogger("CERTUS").debug("barrier thread already deleted", exc_info=True)
    run_barrier(ui)


def run_barrier(ui) -> None:
    """Start ``BarrierWorker`` on the aligned path of the selected designs."""
    from certus.core.certus_design_landscape import align_designs, aligned_path
    from certus.workers.certus_design_workers import BarrierWorker

    if getattr(ui, "oblique_mode", False):
        ui.log("Compare: the barrier is computed at normal incidence only.", "WARNING")
        return
    tgts = [t for t in ui._get_tgts() if t.valid()]
    if not tgts:
        ui.log("Compare: no valid target.", "WARNING")
        return
    picked = _selected(ui)
    if picked is None:
        return
    a, b, n_of = picked
    path = aligned_path(a, b, align_designs(a, b, free_nm=float(ui.compare_free_spin.value())), n_of)
    _draw_profiles(ui, a, b, n_of)
    cfg = {"mats": ui._get_materials(), "wls": np.asarray(ui._get_optim_wls(), dtype=np.float64), "tgts": tgts,
           "materials": list(path.materials), "ep_a": path.ep_a, "ep_b": path.ep_b,
           "images": ui.compare_images_spin.value(), "iterations": ui.compare_iter_spin.value()}
    ui.log(f"Compare: barrier on a path of {len(path.materials)} layers, {cfg['images']} images, "
           f"{cfg['iterations']} string iterations...", "INFO")
    ui.compare_barrier_btn.setText("Stop barrier")
    ui.compare_distance_btn.setEnabled(False)
    if hasattr(ui, "progress_widget"):
        ui.progress_widget.start(phase="BARRIER")
    ui.compare_worker = BarrierWorker(cfg)
    ui.compare_thread = QThread()
    ui.compare_worker.moveToThread(ui.compare_thread)
    ui.compare_thread.started.connect(ui.compare_worker.run)
    ui.compare_worker.signals.finished.connect(ui.compare_thread.quit)
    ui.compare_worker.signals.finished.connect(functools.partial(on_barrier_done, ui))
    ui.compare_worker.signals.finished.connect(ui.compare_worker.deleteLater)
    ui.compare_worker.signals.error.connect(ui.compare_thread.quit)
    ui.compare_worker.signals.error.connect(functools.partial(_barrier_idle, ui))
    ui.compare_worker.signals.error.connect(ui._on_error)
    ui.compare_worker.signals.error.connect(ui.compare_worker.deleteLater)
    ui.compare_thread.finished.connect(ui.compare_thread.deleteLater)
    ui.compare_thread.finished.connect(functools.partial(setattr, ui, "compare_thread", None))
    ui.compare_thread.start()


def _barrier_idle(ui, *_signal_args) -> None:
    ui.compare_barrier_btn.setText("Barrier")
    ui.compare_distance_btn.setEnabled(True)
    if hasattr(ui, "progress_widget"):
        ui.progress_widget.stop("Done")


def on_barrier_done(ui, d: dict) -> None:
    """Draw the RMSE along the straight path and the string, and report the barrier."""
    _barrier_idle(ui)
    if not d.get("ok"):
        return
    straight, string = np.asarray(d["rmse_straight"]), np.asarray(d["rmse_string"])
    ui.compare_straight_curve.setData(np.linspace(0.0, 1.0, straight.size), straight)
    ui.compare_string_curve.setData(np.linspace(0.0, 1.0, string.size), string)
    text = (f"RMSE A {d['rmse_a']:.4g}, B {d['rmse_b']:.4g}. Highest RMSE on the path: straight {straight.max():.4g}, "
            f"string {string.max():.4g} after {d['iterations']} iterations, so a barrier of at most "
            f"{d['barrier']:.4g} above the higher design; {d['local_minima']} local minima on the string, total "
            f"variation {d['total_variation']:.4g}. Upper bounds: one class of paths only.")
    ui.compare_result_label.setText(text)
    ui.log(text, "SUCCESS")
