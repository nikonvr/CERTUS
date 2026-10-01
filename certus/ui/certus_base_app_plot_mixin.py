"""The plots and targets of a CERTUS window: spectrum auto-scale, target scatter, live curves and the detach / reattach of a plot or a table (moved out of certus_base_app.py, S5.3)."""

import functools
import logging
from typing import Any

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QCheckBox, QLabel, QWidget

from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS
from certus.ui.certus_plot import clone_plot_widget
from certus.ui.certus_theme import CertusTheme
from certus.ui.certus_ui_widgets_utils import DetachedPlotWindow
from certus_physics.structures import Target


class CertusAppPlotMixin:
    """The plots and targets of a CERTUS window: spectrum auto-scale, target scatter, live curves and the detach / reattach of a plot or a table (moved out of certus_base_app.py, S5.3)."""

    def open_detached_certus_plot(self, source_plot: QWidget, *, title: str | None = None) -> None:
        """Clones the plot into a maximized window (accessible everywhere for CERTUS apps)."""

        key = f"certus_detach_{id(source_plot)}"

        if key in self.detached_plot_windows:
            w = self.detached_plot_windows[key]

            w.raise_()

            w.activateWindow()

            return

        try:
            clone = clone_plot_widget(source_plot, title_override=title)

            if clone is None:
                return

            disp = (title or "").strip() or "CERTUS Chart"

            win = DetachedPlotWindow(clone, parent=self, title=disp)

            win.closed_signal.connect(functools.partial(self.detached_plot_windows.pop, key, None))

            self.detached_plot_windows[key] = win

            win.show()

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            log = getattr(self, "logger", None)

            if log is not None:
                log.warning("open_detached_certus_plot: %s", e)

            else:
                logging.warning("open_detached_certus_plot: %s", e)

    def _auto_scale_spectrum_y(self, Ts: np.ndarray = None, include_targets: bool = True) -> None:
        """

        Automatically adjusts X and Y axes to include

        spectrum and active targets.

        """

        x_min, x_max = None, None

        y_min, y_max = None, None

        # 1. Analyze calculated data (Spectrum)

        if self.last_result:
            res_vis = self.last_result.get("vis", {})

            wls_data = res_vis.get("l", np.array([]))

            if len(wls_data) > 0:
                x_min, x_max = np.min(wls_data), np.max(wls_data)

                # In oblique mode, analyze all R and T spectra

                if self.last_result.get("oblique_mode", False):
                    spectra_vis = self.last_result.get("spectra_vis", {})

                    all_values = []

                    for spec_data in spectra_vis.values():
                        all_values.extend(spec_data.get("R", []))

                        all_values.extend(spec_data.get("T", []))

                    if all_values:
                        y_min, y_max = np.min(all_values), np.max(all_values)

                elif Ts is not None:
                    y_min, y_max = np.min(Ts), np.max(Ts)

        # 2. Systematic analysis of active targets

        if include_targets:
            if self.oblique_mode:
                active_tgts = [t for t in self._get_oblique_tgts() if t.valid()]

                for t in active_tgts:
                    x_min = min(x_min, t.lmin) if x_min is not None else t.lmin

                    x_max = max(x_max, t.lmax) if x_max is not None else t.lmax

                    target_y_min = min(t.tmin, t.tmax)

                    target_y_max = max(t.tmin, t.tmax)

                    y_min = min(y_min, target_y_min) if y_min is not None else target_y_min

                    y_max = max(y_max, target_y_max) if y_max is not None else target_y_max

            else:
                active_tgts = [t for t in self._get_tgts() if t.valid()]

                for t in active_tgts:
                    x_min = min(x_min, t.lmin) if x_min is not None else t.lmin

                    x_max = max(x_max, t.lmax) if x_max is not None else t.lmax

                    target_y_min = min(t.tmin, t.tmax)

                    target_y_max = max(t.tmin, t.tmax)

                    y_min = min(y_min, target_y_min) if y_min is not None else target_y_min

                    y_max = max(y_max, target_y_max) if y_max is not None else target_y_max

        # 3. Apply scales with 20% margins relative to extremities

        if x_min is not None and x_max is not None:
            # 20% margin relative to each extremity

            x_margin_min = x_min * 0.20

            x_margin_max = x_max * 0.20

            x_display_min = max(200.0, x_min - x_margin_min)  # Reasonable limit: 200 nm

            x_display_max = x_max + x_margin_max  # No hard cap  supports IR

            self.spectrum_plot.setXRange(x_display_min, x_display_max, 0)

        else:
            # No data, use reasonable default range

            self.spectrum_plot.setXRange(200, 3000, 0)

        # For Y axis, we just use Pyqtgraph's native AutoRange so it behaves exactly like the 'A' button
        self.spectrum_plot.plotItem.enableAutoRange(y=True)

    def _calculate_wls_max_with_margin(self, active_targets) -> Any:
        """Calculates lambda max with 20% margin relative to max extremity"""

        if not active_targets:
            return 2000.0

        t_lmax = max(t.lmax for t in active_targets)

        # 20% margin relative to max extremity

        margin = t_lmax * 0.10

        return t_lmax + margin  # No hard cap  supports IR

    def _calculate_wls_min_with_margin(self, active_targets) -> Any:
        """Calculates lambda min with 20% margin relative to min extremity"""

        if not active_targets:
            return 380.0

        t_lmin = min(t.lmin for t in active_targets)

        # 20% margin relative to min extremity

        margin = t_lmin * 0.20

        return max(200.0, t_lmin - margin)  # Reasonable limit: 200 nm

    def _clean_live_curves(self) -> None:
        """Cleans live curves"""

        # Clean curves in normal mode

        if hasattr(self, "_live_curve") and self._live_curve is not None:
            try:
                self.spectrum_plot.removeItem(self._live_curve)

            except (AttributeError, RuntimeError) as e:
                logging.debug(f"Could not remove live curve: {e}")

            self._live_curve = None

        # Clean curves in oblique mode

        if hasattr(self, "_live_curves"):
            for _, curve in list(self._live_curves.items()):
                try:
                    self.spectrum_plot.removeItem(curve)

                except (AttributeError, RuntimeError) as e:
                    logging.debug(f"Could not remove oblique curve: {e}")

            self._live_curves = {}

        if hasattr(self, "_live_points") and self._live_points is not None:
            try:
                self.spectrum_plot.removeItem(self._live_points)

            except (AttributeError, RuntimeError) as e:
                logging.debug(f"Could not remove live points: {e}")

            self._live_points = None

    def _get_plot_targets(self, plot_name: str, primary_widget) -> list:
        """Returns list of widgets to update (primary + detached)"""

        targets = [primary_widget]

        if hasattr(self, "detached_plot_windows") and plot_name in self.detached_plot_windows:
            win = self.detached_plot_windows[plot_name]

            # Ensure window is visible and has the widget reference (added in certus_ui step)

            if win.isVisible() and hasattr(win, "plot_widget"):
                targets.append(win.plot_widget)

        return targets

    def _get_tgts(self) -> list[Target]:
        """Retrieves spectral targets (normal mode)"""

        if self.oblique_mode:
            return []  # In oblique mode, use _get_oblique_tgts()

        targets = []

        for r in range(self.target_table.rowCount()):
            try:
                cw = self.target_table.cellWidget(r, 0)

                if not cw:
                    continue

                chk = cw.findChild(QCheckBox)

                on = chk.isChecked() if chk else False

                vals = []

                for c in range(1, 6):
                    w = self.target_table.cellWidget(r, c)

                    vals.append(w.value() if w else 0.0)

                targets.append(Target(vals[0], vals[1], vals[2], vals[3], vals[4], on))

            except (AttributeError, ValueError, IndexError) as e:
                logging.debug(f"Could not get target row {r}: {e}")

        return targets

    def _rebuild_target_scatter(self, wls: np.ndarray, oblique_mode: bool = False) -> None:
        """Rebuilds target points on plot"""

        if self.target_scatter:
            self.spectrum_plot.removeItem(self.target_scatter)

            self.target_scatter = None

        if len(wls) == 0:
            return

        scatter_pts = []

        if oblique_mode:
            # Oblique Mode: display targets by type (R or T)

            # Use same colors as spectra for consistency

            oblique_tgts = self._get_oblique_tgts()

            color_idx = 0

            for tgt in oblique_tgts:
                if not tgt.valid():
                    continue

                # Color: R in red, T in blue

                tgt_id = (tgt.angle, tgt.pol, tgt.target_type, tgt.lmin, tgt.lmax)

                if hasattr(self, "_oblique_spectrum_colors") and tgt_id in self._oblique_spectrum_colors:
                    color = self._oblique_spectrum_colors[tgt_id]

                else:
                    color = "#dc2626" if tgt.target_type == "R" else "#2563eb"

                brush = pg.mkBrush(*pg.colorTuple(pg.mkColor(color))[:3], 76)  # 30% opacity

                # RE narrow-band targets (tmin==tmax): ONE dot at center wavelength

                if abs(tgt.tmax - tgt.tmin) < 1e-9:
                    wl_center = (tgt.lmin + tgt.lmax) / 2.0

                    scatter_pts.append({"pos": (wl_center, tgt.tmin), "size": 8, "pen": pg.mkPen(None), "brush": brush})

                else:
                    # Wide-band targets: plot on display grid

                    tolerance = 1e-6

                    mask = (wls >= (tgt.lmin - tolerance)) & (wls <= (tgt.lmax + tolerance))

                    if not np.any(mask):
                        continue

                    x_pts = np.clip(wls[mask], tgt.lmin, tgt.lmax)

                    slope = (tgt.tmax - tgt.tmin) / max(tgt.lmax - tgt.lmin, 1e-9)

                    y_pts = tgt.tmin + slope * (x_pts - tgt.lmin)

                    for x, y in zip(x_pts, y_pts, strict=False):
                        if tgt.lmin <= x <= tgt.lmax:
                            scatter_pts.append({"pos": (x, y), "size": 8, "pen": pg.mkPen(None), "brush": brush})

                color_idx += 1

        else:
            # Normal Mode: display T targets

            for t in self._get_tgts():
                if not t.valid():
                    continue

                # Strictly filter wavelengths in target range

                # Use numerical tolerance to avoid precision issues

                tolerance = 1e-6

                mask = (wls >= (t.lmin - tolerance)) & (wls <= (t.lmax + tolerance))

                if not np.any(mask):
                    continue

                x_pts = wls[mask]

                # Ensure points are within [lmin, lmax] range

                x_pts = np.clip(x_pts, t.lmin, t.lmax)

                slope = (t.tmax - t.tmin) / max(t.lmax - t.lmin, 1e-9)

                y_pts = t.tmin + slope * (x_pts - t.lmin)

                for x, y in zip(x_pts, y_pts, strict=False):
                    # Final check: do not plot points outside range

                    if t.lmin <= x <= t.lmax:
                        scatter_pts.append(
                            {
                                "pos": (x, y),
                                "size": 8,
                                "pen": pg.mkPen(None),
                                "brush": pg.mkBrush(
                                    *pg.colorTuple(pg.mkColor(CertusTheme.ACCENT))[:3], 76
                                ),  # 30% opacity
                            }
                        )

        if scatter_pts:
            self.target_scatter = pg.ScatterPlotItem()

            self.target_scatter.addPoints(scatter_pts)

            self.spectrum_plot.addItem(self.target_scatter)

    def _update_spectrum_y_scale(self) -> None:
        """Updates Y scale based on option"""

        auto_scale = self.auto_scale_y_check.isChecked() if hasattr(self, "auto_scale_y_check") else True

        if not auto_scale:
            # Fixed 0-1 scale

            self.spectrum_plot.setYRange(0.0, 1.0, 0)

        else:
            # Auto scale

            self._auto_scale_spectrum_y()

    def _update_target_table_headers(self) -> None:
        """Update table headers by mode (normal/oblique)"""

        if self.oblique_mode:
            self.target_table.setColumnCount(9)

            self.target_table.setHorizontalHeaderLabels(
                [
                    "Active",
                    "Angle (°)",
                    "Pol",
                    "Type",
                    "λ min (nm)",
                    "λ max (nm)",
                    "Val min",
                    "Val max",
                    "Weight",
                ]
            )

        else:
            self.target_table.setColumnCount(6)

            self.target_table.setHorizontalHeaderLabels(["Active", "λ min (nm)", "λ max (nm)", "Tmin", "Tmax", "Weight"])

    def detach_current_plot(self) -> None:
        """Detaches current plot to separate window"""

        current_widget = self.plot_tabs.currentWidget()

        if current_widget is None:
            return

        info = self._get_plot_info(current_widget)

        if info is None:
            return

        plot_name, plot_title = info

        if plot_name in self.detached_plot_windows and self.detached_plot_windows[plot_name].isVisible():
            self.detached_plot_windows[plot_name].raise_()

            return

        try:
            detached_plot_copy = clone_plot_widget(current_widget)

            if detached_plot_copy is None:
                raise ValueError("Could not clone plot")

            if plot_name == "convergence":
                detached_plot_copy.setLogMode(y=True)

                detached_plot_copy.showGrid(x=True, y=True)

            detached_window = DetachedPlotWindow(detached_plot_copy, parent=self, title=plot_title)

            detached_window.closed_signal.connect(functools.partial(self.reattach_plot, plot_name))

            self.detached_plot_windows[plot_name] = detached_window

            detached_window.show()

        except NUMERICAL_FAULT_EXCEPTIONS as e:
            self.log(f"Plot detach failed: {e}", "ERROR")

    def _get_plot_info(self, widget: QWidget) -> tuple[str, str] | None:
        """Hook to identify plot name and title from widget."""

        return None

    def detach_front_table(self) -> None:
        """Detaches layer table to separate window"""

        from certus.workers.certus_spectral_workers import DetachedTableWindow

        if not self.detached_window:
            self.detached_window = DetachedTableWindow(self.front_table, self)

            self.detached_window.finished.connect(self.reattach_front_table)

            self.detached_window.show()

            self.placeholder_label = QLabel("Table Detached")

            self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            self.placeholder_label.setStyleSheet(
                f"background: {CertusTheme.SURFACE}; color: {CertusTheme.TEXT_DISABLED};"
            )

            self.front_container.layout().insertWidget(1, self.placeholder_label)

        else:
            self.detached_window.show()

            self.detached_window.raise_()

    def reattach_front_table(self) -> None:
        """Reattaches layer table"""

        if self.detached_window:
            self.front_container.layout().insertWidget(1, self.front_table)

            if hasattr(self, "placeholder_label"):
                self.placeholder_label.deleteLater()

                del self.placeholder_label

            self.detached_window.deleteLater()

            self.detached_window = None

    def reattach_plot(self, plot_name: str) -> None:
        """Reattaches detached plot"""

        if plot_name not in self.detached_plot_windows:
            return

        detached_window = self.detached_plot_windows[plot_name]

        detached_window.deleteLater()

        del self.detached_plot_windows[plot_name]

    def _monotonic_visual_mode_enabled(self) -> bool:
        """Enable strict non-regression of visualized spectrum during/after workflow."""
        return True

    def _is_valid_rmse_value(self, rmse) -> bool:
        """True if RMSE is finite and non-negative."""

        return rmse is not None and np.isfinite(rmse) and rmse >= 0.0
