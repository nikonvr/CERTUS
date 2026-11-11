from __future__ import annotations

from threading import Event
from typing import Any

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QFrame, QHBoxLayout, QMessageBox, QScrollArea, QVBoxLayout, QWidget

from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS
from certus.spline.certus_index_spline_corridor_contract import normalize_corridor_live_payload
from certus.ui.certus_index_spline_common import _worker_corridor_rmse_healer, logger
from certus.ui.certus_index_spline_corridor_interval import _CorridorIntervalMixin
from certus.ui.certus_index_spline_corridor_nk import _CorridorNkMixin
from certus.ui.certus_index_spline_corridor_rmse_view import _CorridorRmseViewMixin
from certus.ui.certus_index_spline_corridor_run import _CorridorRunMixin
from certus.ui.certus_ui import (
    CertusCard,
    CertusScientificPlot,
    CertusTheme,
    ExcelTableWidget,
    GenericWorker,
    create_styled_button,
    wrap_scientific_plot_with_toolbar,
)
from certus.utils.certus_atomic_io import atomic_open


class CertusIndexSplineCorridorUIMixin(_CorridorRunMixin, _CorridorRmseViewMixin, _CorridorIntervalMixin, _CorridorNkMixin):
    """CertusIndexSplineCorridorUIMixin."""

    def _launch_corridor_rmse_gap_heal(self, tasks: list[tuple[float, dict]]) -> None:
        """Starts the gap healing worker after the grid, outside the ``finished`` handler (prevents ``_cleanup_thread``)."""
        if self._worker is not None and self._worker.isRunning():
            if self.logger:
                self.logger.warning("GUI RMSE(d) gap heal skipped: a worker is already running.")
            return
        cfg = self._last_run_cfg
        if cfg is None:
            if self.logger:
                self.logger.warning("GUI RMSE(d) gap heal skipped: no optimization config.")
            return
        self._stop_event = Event()
        self._worker = GenericWorker(
            _worker_corridor_rmse_healer,
            cfg,
            tasks,
            self._stop_event,
        )
        self._worker.signals.finished.connect(self._on_worker_done)
        self._worker.signals.error.connect(self._on_worker_err)
        self._worker.signals.finished.connect(self._cleanup_thread)
        self._worker.signals.error.connect(self._cleanup_thread)
        self._worker_role = "rmse_heal"
        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self._set_corridor_grid_busy(True)
        self._worker.start()
