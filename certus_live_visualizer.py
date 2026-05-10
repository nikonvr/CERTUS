"""CERTUS Live Optimization Visualizer
====================================

Real-time visualization of spectral fit and n,k clues during optimization.
Provides live updates every N evaluations with interactive plots.

Author: CERTUS Suite
Version: 1.0"""

import io
import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

# Import CERTUS components


@dataclass
class LiveUpdateData:
    """Data structure for live visualization updates"""

    iteration: int
    n_evaluations: int
    current_rmse: float
    best_rmse: float
    best_params: np.ndarray
    wavelengths: np.ndarray
    target_T: np.ndarray
    target_R: np.ndarray
    calculated_T: np.ndarray
    calculated_R: np.ndarray
    n_spectrum: np.ndarray
    k_spectrum: np.ndarray
    thickness: float


class LiveOptimizationVisualizer(QObject):
    """
    Real-time visualization widget for optimization progress.

    Updates spectral fit and n,k curves every N evaluations.
    """

    # Signals
    update_requested = pyqtSignal(LiveUpdateData)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger("CERTUS.LiveVisualizer")

        # Configuration
        self.update_interval = 1000  # Update every 1000 evaluations
        self.last_update_evals = 0

        # Data storage
        self.current_data: Optional[LiveUpdateData] = None
        self.wavelengths: Optional[np.ndarray] = None
        self.target_T: Optional[np.ndarray] = None
        self.target_R: Optional[np.ndarray] = None

        # UI components
        self.setup_ui()

        # Connect signals
        self.update_requested.connect(self.update_plots)

    def _on_copy_excel_clicked(self) -> None:
        tsv = self._build_tsv_for_excel()
        parent = self.main_widget.window()
        if not tsv:
            QMessageBox.warning(
                parent,
                "Export",
                "No live data to copy (wait for an update or load targets).",
            )
            return
        QApplication.clipboard().setText(tsv)
        QMessageBox.information(
            parent,
            "Export",
            "Data copied to clipboard (TSV).",
        )

    def _build_tsv_for_excel(self) -> Optional[str]:
        """TSV aligned on wavelength grid + convergence columns (NaN padding)."""
        d = self.current_data
        if d is None:
            if self.wavelengths is None or self.target_T is None:
                return None
            wl = np.asarray(self.wavelengths, dtype=float).ravel()
            n = wl.size
            tt = np.asarray(self.target_T, dtype=float).ravel()[:n]
            if self.target_R is None:
                tr = np.full(n, np.nan)
            else:
                tr = np.asarray(self.target_R, dtype=float).ravel()
                if tr.size < n:
                    tr = np.pad(tr, (0, n - tr.size), constant_values=np.nan)
                else:
                    tr = tr[:n]
            cols = {
                "wavelength_nm": wl,
                "target_T": tt,
                "target_R": tr,
                "calc_T": np.full(n, np.nan),
                "calc_R": np.full(n, np.nan),
                "n": np.full(n, np.nan),
                "k": np.full(n, np.nan),
            }
        else:
            wl = np.asarray(d.wavelengths, dtype=float).ravel()
            n = int(wl.size)

            def _col(arr) -> np.ndarray:
                a = np.asarray(arr, dtype=float).ravel()
                if a.size >= n:
                    return a[:n].copy()
                out = np.full(n, np.nan)
                out[: a.size] = a
                return out

            cols = {
                "wavelength_nm": wl,
                "target_T": _col(d.target_T),
                "target_R": _col(d.target_R),
                "calc_T": _col(d.calculated_T),
                "calc_R": _col(d.calculated_R),
                "n": _col(d.n_spectrum),
                "k": _col(d.k_spectrum),
            }
        ce = np.asarray(self.convergence_evals, dtype=float)
        cr = np.asarray(self.convergence_rmse, dtype=float)
        m = max(n, ce.size, cr.size)
        for k in list(cols.keys()):
            v = cols[k]
            if v.size < m:
                cols[k] = np.pad(v, (0, m - v.size), constant_values=np.nan)
        cols["convergence_eval"] = np.pad(ce, (0, m - ce.size), constant_values=np.nan)
        cols["convergence_rmse"] = np.pad(cr, (0, m - cr.size), constant_values=np.nan)
        df = pd.DataFrame(cols)
        buf = io.StringIO()
        df.to_csv(buf, sep="\t", index=False, lineterminator="\n")
        return buf.getvalue()

    def setup_ui(self):
        """Setup the visualization UI"""
        # Create main widget
        self.main_widget = QWidget()
        self.layout = QVBoxLayout(self.main_widget)

        # Status label + copie Excel
        head = QHBoxLayout()
        self.status_label = QLabel("Waiting for optimization data...")
        head.addWidget(self.status_label, stretch=1)
        self._btn_copy_excel = QPushButton("Copy data (Excel)")
        self._btn_copy_excel.setToolTip("TSV: spectrum, n/k, convergence (last update)")
        self._btn_copy_excel.clicked.connect(self._on_copy_excel_clicked)
        head.addWidget(self._btn_copy_excel)
        self.layout.addLayout(head)

        # Create matplotlib figure
        self.figure = Figure(figsize=(14, 10))
        self.canvas = FigureCanvas(self.figure)
        self.layout.addWidget(self.canvas)

        # Create subplots
        self.ax_spectral = self.figure.add_subplot(2, 2, 1)
        self.ax_n = self.figure.add_subplot(2, 2, 3)
        self.ax_k = self.figure.add_subplot(2, 2, 4)
        self.ax_convergence = self.figure.add_subplot(2, 2, 2)

        # Initial setup
        self.setup_initial_plots()

        self.figure.tight_layout()

    def setup_initial_plots(self):
        """Setup initial empty plots"""
        # Spectral fit plot
        self.ax_spectral.set_xlabel("Wavelength (nm)")
        self.ax_spectral.set_ylabel("T / R")
        self.ax_spectral.set_title("Spectral Fit")
        self.ax_spectral.grid(True, alpha=0.3)
        self.ax_spectral.legend(["Target T", "Target R", "Calc T", "Calc R"])

        # n spectrum plot
        self.ax_n.set_xlabel("Wavelength (nm)")
        self.ax_n.set_ylabel("n")
        self.ax_n.set_title("Refractive Index n")
        self.ax_n.grid(True, alpha=0.3)

        # k spectrum plot
        self.ax_k.set_xlabel("Wavelength (nm)")
        self.ax_k.set_ylabel("k")
        self.ax_k.set_title("Extinction Coefficient k")
        self.ax_k.grid(True, alpha=0.3)

        # Convergence plot
        self.ax_convergence.set_xlabel("Evaluations")
        self.ax_convergence.set_ylabel("RMSE")
        self.ax_convergence.set_title("Convergence")
        self.ax_convergence.grid(True, alpha=0.3)

        # Initialize convergence data
        self.convergence_evals = []
        self.convergence_rmse = []

    def set_target_data(self, wavelengths: np.ndarray, target_T: np.ndarray, target_R: np.ndarray):
        """Set the target spectral data"""
        self.wavelengths = wavelengths
        self.target_T = target_T
        self.target_R = target_R

        # Update initial plots with target data
        self.ax_spectral.clear()
        self.ax_spectral.plot(wavelengths, target_T, "b-", alpha=0.7, label="Target T")
        self.ax_spectral.plot(wavelengths, target_R, "r-", alpha=0.7, label="Target R")
        self.ax_spectral.set_xlabel("Wavelength (nm)")
        self.ax_spectral.set_ylabel("T / R")
        self.ax_spectral.set_title("Spectral Fit")
        self.ax_spectral.grid(True, alpha=0.3)
        self.ax_spectral.legend()

        self.canvas.draw()

    def request_update(
        self,
        iteration: int,
        n_evaluations: int,
        current_rmse: float,
        best_rmse: float,
        thickness: float,
        wavelengths: np.ndarray,
        n_calc: np.ndarray,
        k_calc: np.ndarray,
        T_calc: np.ndarray,
        R_calc: np.ndarray,
    ):
        """Request a visualization update with pre-calculated spectra"""
        if self.wavelengths is None:
            return

        # Throttle: only update every update_interval evaluations
        if n_evaluations - self.last_update_evals < self.update_interval:
            return
        self.last_update_evals = n_evaluations

        update_data = LiveUpdateData(
            iteration=iteration,
            n_evaluations=n_evaluations,
            current_rmse=current_rmse,
            best_rmse=best_rmse,
            best_params=np.array([thickness]),
            wavelengths=wavelengths,
            target_T=self.target_T,
            target_R=self.target_R,
            calculated_T=T_calc,
            calculated_R=R_calc,
            n_spectrum=n_calc,
            k_spectrum=k_calc,
            thickness=thickness,
        )

        self.update_requested.emit(update_data)

    def update_plots(self, data: LiveUpdateData):
        """Update all plots with new data"""
        try:
            # Store current data
            self.current_data = data

            # Update status
            self.status_label.setText(
                f"Iteration: {data.iteration} | "
                f"Evaluations: {data.n_evaluations} | "
                f"RMSE: {data.best_rmse:.6f} | "
                f"Thickness: {data.thickness:.2f} nm"
            )

            # Clear and update spectral fit plot
            self.ax_spectral.clear()
            self.ax_spectral.plot(data.wavelengths, data.target_T, "b-", alpha=0.7, label="Target T")
            self.ax_spectral.plot(data.wavelengths, data.target_R, "r-", alpha=0.7, label="Target R")
            self.ax_spectral.plot(
                data.wavelengths,
                data.calculated_T,
                "b--",
                linewidth=2,
                label="Calc T",
            )
            self.ax_spectral.plot(
                data.wavelengths,
                data.calculated_R,
                "r--",
                linewidth=2,
                label="Calc R",
            )
            self.ax_spectral.set_xlabel("Wavelength (nm)")
            self.ax_spectral.set_ylabel("T / R")
            self.ax_spectral.set_title("Spectral Fit")
            self.ax_spectral.grid(True, alpha=0.3)
            self.ax_spectral.legend()

            # Update n spectrum plot
            self.ax_n.clear()
            self.ax_n.plot(data.wavelengths, data.n_spectrum, "g-", linewidth=2)
            self.ax_n.set_xlabel("Wavelength (nm)")
            self.ax_n.set_ylabel("n")
            self.ax_n.set_title("Refractive Index n")
            self.ax_n.grid(True, alpha=0.3)

            # Update k spectrum plot
            self.ax_k.clear()
            self.ax_k.plot(data.wavelengths, data.k_spectrum, "m-", linewidth=2)
            self.ax_k.set_xlabel("Wavelength (nm)")
            self.ax_k.set_ylabel("k")
            self.ax_k.set_title("Extinction Coefficient k")
            self.ax_k.grid(True, alpha=0.3)

            # Update convergence plot
            self.convergence_evals.append(data.n_evaluations)
            self.convergence_rmse.append(data.best_rmse)

            self.ax_convergence.clear()
            self.ax_convergence.plot(self.convergence_evals, self.convergence_rmse, "k-", linewidth=2)
            self.ax_convergence.set_xlabel("Evaluations")
            self.ax_convergence.set_ylabel("RMSE")
            self.ax_convergence.set_title("Convergence")
            self.ax_convergence.grid(True, alpha=0.3)
            self.ax_convergence.set_yscale("log")

            # Redraw canvas
            self.canvas.draw()

            self.logger.debug(f"Updated live visualization at evaluation {data.n_evaluations}")

        except (ValueError, TypeError, RuntimeError, AttributeError, KeyError, IndexError, FileNotFoundError) as e:
            self.logger.error(f"Failed to update plots: {e}")

    def reset(self):
        """Reset visualizer for new optimization"""
        self.last_update_evals = 0
        self.current_data = None
        self.convergence_evals = []
        self.convergence_rmse = []

        # Clear plots
        self.setup_initial_plots()
        self.canvas.draw()

        # Reset status
        self.status_label.setText("Waiting for optimization data...")

    def get_widget(self) -> QWidget:
        """Get the main widget for embedding in UI"""
        return self.main_widget

    def set_update_interval(self, interval: int):
        """Set the update interval (in evaluations)"""
        self.update_interval = interval
        self.logger.info(f"Update interval set to {interval} evaluations")


# Factory function for easy integration
def create_live_visualizer(parent=None, update_interval: int = 1000) -> LiveOptimizationVisualizer:
    """
    Factory function to create a live visualization widget.

    Args:
        parent: Parent widget
        update_interval: Update interval in evaluations

    Returns:
        Configured LiveOptimizationVisualizer
    """
    visualizer = LiveOptimizationVisualizer(parent)
    visualizer.set_update_interval(update_interval)
    return visualizer
