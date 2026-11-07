"""Explicit native resonance analysis/refinement; ordinary DESIGN runs stay unchanged."""
from __future__ import annotations

import logging
from threading import Event
from typing import Any

import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QCloseEvent

from certus.core.certus_design_resonances import (
    DesignResonanceInput,
    prepare_design_resonances,
    resonance_lower_bounds,
)
from certus.core.certus_design_worker_utils import optim_qwot_values_from_ep_stack
from certus.physics.design_resonances import (
    ResonanceAnalysis,
    ResonanceRefinement,
    ResonanceSettings,
    analyze_resonances,
    refine_resonances,
)
from certus.ui.certus_qt_widgets import (
    QAbstractItemView,
    QDialog,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSpinBox,
    Qt,
    QTableWidget,
    QTableWidgetItem,
    QThread,
    QVBoxLayout,
    QWidget,
)
from certus.utils.certus_ux import OBJ
from certus_physics import init_thickness


class _ResonanceWorker(QObject):
    progress = pyqtSignal(int, object)
    result = pyqtSignal(object)
    error = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, request: DesignResonanceInput, settings: ResonanceSettings,
                 floor_nm: float | np.ndarray, refine: bool) -> None:
        super().__init__()
        self.request, self.settings, self.floor_nm, self.refine = request, settings, floor_nm, refine
        self._stop = Event()

    def stop(self) -> None:
        self._stop.set()

    @pyqtSlot()
    def run(self) -> None:
        try:
            request = self.request
            if self.refine:
                result = refine_resonances(request.problem, request.thicknesses, settings=self.settings,
                                           variable_indices=request.variable_indices,
                                           lower_bounds=np.broadcast_to(self.floor_nm, request.thicknesses.shape).copy(),
                                           progress=self.progress.emit, cancelled=self._stop.is_set)
            else:
                analysis = analyze_resonances(request.problem, request.thicknesses, settings=self.settings)
                result = ResonanceRefinement(request.thicknesses.copy(), analysis, analysis, 0, (analysis,),
                                             cancelled=self._stop.is_set())
            self.result.emit(result)
        except (ValueError, RuntimeError, FloatingPointError, OverflowError, np.linalg.LinAlgError) as error:
            logging.exception("DESIGN resonance calculation failed")
            self.error.emit(str(error))
        finally:
            self.finished.emit()


class DesignResonanceDialog(QDialog):
    """A cancellable modal tool; refined thicknesses require an explicit Apply action."""

    def __init__(self, ui: Any) -> None:
        super().__init__(ui)
        self.ui = ui
        self._thread: QThread | None = None
        self._worker: _ResonanceWorker | None = None
        self._request: DesignResonanceInput | None = None
        self._result: ResonanceRefinement | None = None
        self._refining = False
        self._closing = False
        self.setWindowTitle("Hidden transmission resonances")
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.resize(900, 590)
        layout = QVBoxLayout(self)
        description = QLabel(
            "Detect narrow transmission resonances from complex wavelengths, verify their pole count, "
            "and optionally refine their real maxima. Normal incidence, constant lossless indices, no rear surface.\n"
            "This tool uses its own uniform wavelength grid with equal point weights; ordinary DESIGN scoring is unchanged.")
        description.setWordWrap(True)
        layout.addWidget(description)
        controls = QGridLayout()
        self.step = self._float(0.001, 50., 1., 3)
        self.rounds = QSpinBox()
        self.rounds.setRange(1, 200)
        self.rounds.setValue(40)
        self.burst = QSpinBox()
        self.burst.setRange(1, 300)
        self.burst.setValue(30)
        self.height = self._float(0., 100., 0.1, 3)
        self.width = self._float(0.000001, 10., 0.5, 6)
        self.floor = self._float(0.000001, 1e6, 5., 6)
        self.ot = self._float(0., 1e9, 0., 3)
        self.ot.setSpecialValueText("No extra OT limit")
        self.ot.setToolTip("An active OT cap from the design file remains enforced.")
        cap = getattr(ui, "_max_total_qwot", None)
        if isinstance(cap, (int, float)) and cap > 0:
            self.ot.setValue(float(cap) * float(ui.l0_spin.value()) / 4)
        entries = (("Grid step / offset (nm)", self.step), ("Refinement rounds", self.rounds),
                   ("Evaluations per burst", self.burst), ("Minimum peak error (%)", self.height),
                   ("Maximum pole width (nm)", self.width), ("Minimum physical layer (nm)", self.floor),
                   ("Maximum retained OT (nm)", self.ot))
        self._controls = [widget for _label, widget in entries]
        for i, (label, widget) in enumerate(entries):
            row, col = divmod(i, 3)
            field_label = QLabel(label)
            field_label.setBuddy(widget)
            widget.setAccessibleName(label)
            widget.setToolTip(label)
            controls.addWidget(field_label, 2 * row, col)
            controls.addWidget(widget, 2 * row + 1, col)
        layout.addLayout(controls)
        actions = QHBoxLayout()
        self.analyze_button = QPushButton("Analyze current design")
        self.refine_button = QPushButton("Refine real maxima")
        self.stop_button = QPushButton("Stop resonance calculation")
        self.stop_button.setEnabled(False)
        for button in (self.analyze_button, self.refine_button):
            button.setObjectName(OBJ.PRIMARY_BUTTON)
        self.analyze_button.clicked.connect(self._analyze)
        self.refine_button.clicked.connect(self._refine)
        self.stop_button.clicked.connect(self._stop)
        self.analyze_button.setToolTip("Locate resonances and verify the pole count without changing the design.")
        self.refine_button.setToolTip("Refine moving real maxima; applying the resulting design remains a separate action.")
        self.stop_button.setToolTip("Cancel this calculation without applying partly refined thicknesses.")
        for button in (self.analyze_button, self.refine_button, self.stop_button):
            actions.addWidget(button)
        layout.addLayout(actions)
        self.status = QLabel("Analyze first, or refine the current design. Fixed layers remain fixed.")
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.status)
        self.peaks = QTableWidget(0, 3)
        self.peaks.setHorizontalHeaderLabels(["Real maximum (nm)", "Pole-width estimate (nm)", "Peak error (%)"])
        self.peaks.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.peaks.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.peaks, 1)
        footer = QHBoxLayout()
        self.apply_button = QPushButton("Apply refined design")
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self._apply)
        self.apply_button.setToolTip("Apply the retained physical thicknesses, then request standard DESIGN evaluation.")
        close = QPushButton("Close resonance tool")
        close.clicked.connect(self.close)
        footer.addWidget(self.apply_button)
        footer.addStretch()
        footer.addWidget(close)
        layout.addLayout(footer)
        for widget in self._controls:
            widget.valueChanged.connect(self._invalidate)

    @staticmethod
    def _float(low: float, high: float, value: float, decimals: int) -> QDoubleSpinBox:
        widget = QDoubleSpinBox()
        widget.setDecimals(decimals)
        widget.setRange(low, high)
        widget.setValue(value)
        return widget

    def _analyze(self) -> None:
        self._start(False)

    def _refine(self) -> None:
        self._start(True)

    def _invalidate(self, *_args: Any) -> None:
        self._result = None
        self.apply_button.setEnabled(False)
        self.peaks.setRowCount(0)
        self.status.setText("Parameters changed. Run the analysis or refinement again.")

    def _file_ot_cap(self) -> float | None:
        cap = getattr(self.ui, "_max_total_qwot", None)
        if isinstance(cap, (float, int)) and not isinstance(cap, bool) and cap > 0:
            return float(cap) * float(self.ui.l0_spin.value()) / 4
        return None

    def _current_input(self) -> DesignResonanceInput:
        stack, mats = self.ui._get_front_stack(), self.ui._get_materials()
        d = self.ui.ep_current
        if d is None or len(d) != len(stack):
            d = np.asarray(init_thickness(stack, float(self.ui.l0_spin.value()), mats))
        return prepare_design_resonances(mats, stack, self.ui._get_tgts(), np.asarray(d),
                                         step_nm=float(self.step.value()), oblique=bool(self.ui.oblique_mode),
                                         backside=self.ui.back_check.isChecked() or self.ui.back_coat_check.isChecked())

    def _start(self, refine: bool) -> None:
        running = getattr(self.ui, "running_worker_count", lambda: 0)()
        if (self._thread is not None or getattr(self.ui, "_is_busy", False) or running
                or not getattr(self.ui, "_warmup_done", True)):
            self.status.setText("Wait for the current calculation to finish.")
            return
        try:
            self._request = self._current_input()
            ot_floor = getattr(self.ui, "_min_layer_ot_nm", None)
            optical = (float(ot_floor) if isinstance(ot_floor, (float, int)) and not isinstance(ot_floor, bool)
                       and ot_floor > 0 else None)
            floor = resonance_lower_bounds(self._request.problem, float(self.floor.value()), optical)
            caps = [limit for limit in (self.ot.value() or None, self._file_ot_cap()) if limit is not None]
            settings = ResonanceSettings(rounds=int(self.rounds.value()), burst=int(self.burst.value()),
                                         gamma_nm=float(self.step.value()), height_threshold=self.height.value() / 100,
                                         max_width_nm=float(self.width.value()), max_ot_nm=min(caps) if caps else None)
        except (ValueError, KeyError) as error:
            self.status.setText(str(error))
            return
        self._result, self._refining = None, refine
        self._worker = _ResonanceWorker(self._request, settings, floor, refine)
        self._thread = QThread(self)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._progress)
        self._worker.result.connect(self._received)
        self._worker.error.connect(self.status.setText)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._done)
        self._thread.finished.connect(self._thread.deleteLater)
        self._busy(True)
        self.status.setText("Localizing poles and checking their count...")
        self._thread.start()

    def _busy(self, busy: bool) -> None:
        for widget in (*self._controls, self.analyze_button, self.refine_button):
            widget.setEnabled(not busy)
        self.stop_button.setEnabled(busy)
        self.apply_button.setEnabled(not busy and self._refining and self._result is not None
                                     and not self._result.cancelled)

    def _show_analysis(self, analysis: ResonanceAnalysis) -> None:
        self.peaks.setRowCount(len(analysis.charged_peaks))
        for row, peak in enumerate(analysis.charged_peaks):
            values = (peak.peak_wavelength_nm, peak.width_nm, 100 * float(peak.height))
            for col, value in enumerate(values):
                self.peaks.setItem(row, col, QTableWidgetItem(f"{value:.9g}"))

    @pyqtSlot(int, object)
    def _progress(self, rnd: int, analysis: ResonanceAnalysis) -> None:
        self._show_analysis(analysis)
        self.status.setText(f"Round {rnd}/{self.rounds.value()}: reference-grid MF {100 * analysis.nominal_mf:.6g} %, "
                            f"charged MF {100 * analysis.charged_mf:.6g} %. Retained-state pole audit pending.")

    @pyqtSlot(object)
    def _received(self, result: ResonanceRefinement) -> None:
        self._result = result
        self._show_analysis(result.final)
        if result.cancelled:
            self.status.setText("Cancelled. The current design has not been changed.")
            return
        counts = "; ".join(f"{c.located}/{c.counted}" for c in result.final.counts)
        self.status.setText(f"Reference-grid MF: {100 * result.final.nominal_mf:.6g} %; "
                            f"charged MF: {100 * result.final.charged_mf:.6g} %. "
                            f"Located/counted by band: {counts}. "
                            + (f"Round {result.selected_round} retained. Apply to use this design." if self._refining
                               else "The current design is unchanged."))

    @pyqtSlot()
    def _done(self) -> None:
        self._thread, self._worker = None, None
        self._busy(False)
        if self._closing:
            self.close()

    def _stop(self) -> None:
        if self._worker is not None:
            self._worker.stop()
            self.status.setText("Stopping after the current numerical operation...")

    def _apply(self) -> None:
        if self._result is None or self._result.cancelled or self._request is None or self._thread is not None:
            return
        try:
            current = self._current_input()
            original = self._request
            if (current.materials != original.materials or current.problem.bands != original.problem.bands
                    or current.problem.substrate_index != original.problem.substrate_index
                    or not np.array_equal(current.problem.indices, original.problem.indices)
                    or not np.array_equal(current.thicknesses, original.thicknesses)
                    or not np.array_equal(current.variable_indices, original.variable_indices)):
                raise ValueError("The design or targets have changed. Repeat the resonance calculation before applying.")
            d = self._result.thicknesses
            cap = self._file_ot_cap()
            if cap is not None and float(d @ current.problem.indices.real) > cap:
                raise ValueError("The refined design exceeds the active file OT cap.")
            optical = getattr(self.ui, "_min_layer_ot_nm", None)
            if isinstance(optical, (float, int)) and optical > 0 and np.any(d * current.problem.indices.real < optical):
                raise ValueError("The refined design violates the active file minimum optical thickness.")
            qw = optim_qwot_values_from_ep_stack(d, self.ui._get_front_stack(), self.ui._get_materials(),
                                                float(self.ui.l0_spin.value()))
            self.ui._apply_qw_values_to_front_table(qw)
            self.ui._update_thickness_display()
            self.ui.ep_current = d.copy()
            self.ui._use_exact_ep = True
            self.ui._schedule_eval(True)
            self.apply_button.setEnabled(False)
            self.status.setText("Refined thicknesses applied. Standard DESIGN evaluation requested.")
            self.ui.log("Hidden-resonance refinement applied; standard scoring remains separate.", "SUCCESS")
        except (ValueError, KeyError) as error:
            self.status.setText(str(error))

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._thread is not None:
            self._closing = True
            self._stop()
            event.ignore()
            return
        super().closeEvent(event)

    def reject(self) -> None:
        if self._thread is not None:
            self._closing = True
            self._stop()
            return
        super().reject()


def build_resonance_tab(ui: Any) -> QWidget:
    """Add an explicit tool; creating the tab never changes the design or runs a calculation."""
    tab = QWidget()
    layout = QVBoxLayout(tab)
    label = QLabel("Find resonances hidden between grid wavelengths and refine their real maxima.\n"
                   "Initial scope: normal incidence, constant lossless indices, transmission targets, no rear surface.")
    label.setWordWrap(True)
    layout.addWidget(label)
    button = QPushButton("Open resonance analysis and refinement")
    button.setObjectName(OBJ.PRIMARY_BUTTON)
    button.setToolTip("Analyze the current front stack and optionally refine hidden transmission maxima.")

    def show() -> None:
        existing = getattr(ui, "resonance_dialog", None)
        if existing is not None:
            existing.raise_()
            existing.activateWindow()
            return
        dialog = DesignResonanceDialog(ui)
        ui.resonance_dialog = dialog
        def clear_dialog(_result: int) -> None:
            ui.resonance_dialog = None

        dialog.finished.connect(clear_dialog)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.show()

    button.clicked.connect(show)
    layout.addWidget(button)
    layout.addStretch()
    return tab
