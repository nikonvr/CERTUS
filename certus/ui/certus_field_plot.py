import pyqtgraph as pg
from PyQt6.QtCore import Qt
from certus.ui.certus_plot import CertusScientificPlot


class CertusFieldPlotWidget(CertusScientificPlot):
    _BASE_COLORS = ("#00AEEF", "#FF3366", "#33CC33", "#FF9900", "#9933CC")

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('title', "Electric Field Distribution")
        kwargs.setdefault('x_label', "Depth z (nm)")
        kwargs.setdefault('y_label', "Normalized Intensity |E|²")

        super().__init__(*args, **kwargs)
        self.plotItem.addLegend(offset=(10, 10))
        self._boundary_items = []
        self._mc_items = []

    def _curve_color(self, index: int, total: int):
        if total <= len(self._BASE_COLORS):
            return pg.mkColor(self._BASE_COLORS[index % len(self._BASE_COLORS)])
        return pg.intColor(index, hues=max(total, 1), alpha=255, lightness=150)

    def _clear_dynamic_items(self):
        for item in self._boundary_items + self._mc_items:
            try:
                self.removeItem(item)
            except Exception:
                pass
        self._boundary_items.clear()
        self._mc_items.clear()

    def _draw_boundaries(self, layer_thicknesses, layer_types=None, sub_name="Substrate", sup_name="Superstrate", max_y=1.0):
        # 1. Draw Substrate region (z < 0)
        region_sub = pg.LinearRegionItem(values=(-100000.0, 0.0), movable=False, brush=pg.mkBrush(pg.mkColor(75, 85, 99, 35)))
        if hasattr(region_sub, 'lines'):
            for l in region_sub.lines:
                l.setPen(pg.mkPen(None))
        self.addItem(region_sub, ignoreBounds=True)
        self._boundary_items.append(region_sub)

        # Draw solid line at z=0
        line_zero = pg.InfiniteLine(
            pos=0.0,
            angle=90,
            pen=pg.mkPen(pg.mkColor('#A0A0A0'), width=1.5, style=Qt.PenStyle.SolidLine),
        )
        self.addItem(line_zero, ignoreBounds=True)
        self._boundary_items.append(line_zero)

        # Draw Substrate label
        from PyQt6.QtGui import QFont
        font = QFont("Outfit", 9, QFont.Weight.Bold)
        label_sub = pg.TextItem(
            text=f"◀ {sub_name}",
            color='#888888',
            anchor=(1.0, 0.5),
        )
        label_sub.setFont(font)
        label_sub.setPos(-20, max_y * 0.9)
        self.addItem(label_sub, ignoreBounds=True)
        self._boundary_items.append(label_sub)

        z_cur = 0.0
        for i, thickness in enumerate(layer_thicknesses or []):
            z_start = z_cur
            z_end = z_cur + thickness
            z_cur = z_end

            # Draw dashed line at boundary (only if it is not the very last boundary)
            if i < len(layer_thicknesses) - 1:
                line = pg.InfiniteLine(
                    pos=z_end,
                    angle=90,
                    pen=pg.mkPen(pg.mkColor('#808080'), style=Qt.PenStyle.DashLine),
                )
                self.addItem(line, ignoreBounds=True)
                self._boundary_items.append(line)

            # Draw semi-transparent background region
            if layer_types and i < len(layer_types):
                # High = 0 (red/orange), Low = 1 (blue)
                color = pg.mkColor(239, 68, 68, 20) if layer_types[i] == 0 else pg.mkColor(59, 130, 246, 20)
                region = pg.LinearRegionItem(values=(z_start, z_end), movable=False, brush=pg.mkBrush(color))
                if hasattr(region, 'lines'):
                    for l in region.lines:
                        l.setPen(pg.mkPen(None))
                self.addItem(region, ignoreBounds=True)
                self._boundary_items.append(region)

            # Draw layer number label in transparency near the bottom
            label_layer = pg.TextItem(
                text=str(i + 1),
                color=pg.mkColor(100, 116, 139, 100),  # Slate color with alpha=100
                anchor=(0.5, 0.5),
            )
            label_layer.setFont(QFont("Outfit", 16, QFont.Weight.Bold))
            label_layer.setPos((z_start + z_end) / 2.0, max_y * 0.05)
            self.addItem(label_layer, ignoreBounds=True)
            self._boundary_items.append(label_layer)

        # 2. Draw Superstrate/Air region (z > z_cur)
        region_sup = pg.LinearRegionItem(values=(z_cur, 100000.0), movable=False, brush=pg.mkBrush(pg.mkColor(251, 191, 36, 25)))
        if hasattr(region_sup, 'lines'):
            for l in region_sup.lines:
                l.setPen(pg.mkPen(None))
        self.addItem(region_sup, ignoreBounds=True)
        self._boundary_items.append(region_sup)

        # Draw solid line at z_cur
        if z_cur > 0:
            line_last = pg.InfiniteLine(
                pos=z_cur,
                angle=90,
                pen=pg.mkPen(pg.mkColor('#A0A0A0'), width=1.5, style=Qt.PenStyle.SolidLine),
            )
            self.addItem(line_last, ignoreBounds=True)
            self._boundary_items.append(line_last)

        # Draw Superstrate label
        label_sup = pg.TextItem(
            text=f"{sup_name} ▶",
            color='#888888',
            anchor=(0.0, 0.5),
        )
        label_sup.setFont(font)
        label_sup.setPos(z_cur + 20, max_y * 0.9)
        self.addItem(label_sup, ignoreBounds=True)
        self._boundary_items.append(label_sup)

    def update_nominal_plot(self, plot_data: dict, clear_first: bool = True, initial_data: dict | None = None):
        if clear_first:
            self.clear()
            self._clear_dynamic_items()
        else:
            for item in self._boundary_items:
                try:
                    self.removeItem(item)
                except Exception:
                    pass
            self._boundary_items.clear()

        # Plot initial data as dashed lines if present for comparison
        if initial_data:
            init_z_coords = initial_data.get('z_coords') or []
            init_E2_values_list = initial_data.get('E2_values_list') or []
            init_lambda_calcs = initial_data.get('lambda_calcs') or []
            n_init_curves = len(init_E2_values_list)
            for i, E2_v in enumerate(init_E2_values_list):
                color = self._curve_color(i, n_init_curves)
                name = f"Initial λ={init_lambda_calcs[i]} nm" if i < len(init_lambda_calcs) else f"Initial Curve {i + 1}"
                self.plot(init_z_coords, E2_v, pen=pg.mkPen(color, width=1.5, style=Qt.PenStyle.DashLine), name=name)

        z_coords = plot_data.get('z_coords') or []
        E2_values_list = plot_data.get('E2_values_list') or []
        lambda_calcs = plot_data.get('lambda_calcs') or []
        ep_c1_cn = plot_data.get('ep_c1_cn') or []
        layer_types = plot_data.get('layer_types')

        if not z_coords or not E2_values_list:
            return

        n_curves = len(E2_values_list)
        for i, E2_v in enumerate(E2_values_list):
            color = self._curve_color(i, n_curves)
            name = f"λ={lambda_calcs[i]} nm" if i < len(lambda_calcs) else f"Curve {i + 1}"
            self.plot(z_coords, E2_v, pen=pg.mkPen(color, width=2), name=name)

        sub_name = plot_data.get('sub_name', 'Substrate')
        sup_name = plot_data.get('sup_name', 'Superstrate')
        max_y = 1.0
        if E2_values_list:
            flat_y = [v for run in E2_values_list for v in run]
            if flat_y:
                max_y = max(flat_y)

        self._draw_boundaries(ep_c1_cn, layer_types, sub_name=sub_name, sup_name=sup_name, max_y=max_y)
        
        # Explicitly set X limits based on actual stack thickness plus a responsive margin,
        # then auto-range only the Y axis to fit the curve heights cleanly.
        total_thickness = z_coords[-1] if z_coords else 0.0
        if total_thickness > 0:
            margin = max(50.0, 0.1 * total_thickness)
            self.plotItem.setXRange(-margin, total_thickness + margin, padding=0.0)
            self.plotItem.getViewBox().enableAutoRange(axis=pg.ViewBox.YAxis, enable=True)
            self.plotItem.getViewBox().autoRange()
        else:
            self.autoRange()

    def update_mc_plot(self, z_coords_mc: list, E2_mc_runs: list, lambda_calcs: list):
        self.clear()
        self._clear_dynamic_items()

        n_lambdas = len(lambda_calcs or [])
        for l_idx in range(n_lambdas):
            base_color = self._curve_color(l_idx, n_lambdas)
            base_color.setAlpha(30)
            pen = pg.mkPen(base_color, width=1)

            runs = E2_mc_runs[l_idx] if l_idx < len(E2_mc_runs) else []
            for run_idx, run_vals in enumerate(runs):
                z_vals = z_coords_mc[run_idx] if run_idx < len(z_coords_mc) else []
                if not z_vals or not run_vals:
                    continue
                item = self.plot(z_vals, run_vals, pen=pen)
                self._mc_items.append(item)
        self.autoRange()


class CertusSpectralPlotWidget(CertusScientificPlot):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('title', "Spectral Response")
        kwargs.setdefault('x_label', "Wavelength (nm)")
        kwargs.setdefault('y_label', "Reflectance")
        super().__init__(*args, **kwargs)
        self.plotItem.addLegend(offset=(10, 10))

    def plot_spectral_response(self, wavelengths: list[float], R_values: list[float], initial_data: dict | None = None):
        self.clear()
        if initial_data:
            init_wls = initial_data.get('wavelengths')
            init_Rs = initial_data.get('R_values')
            if init_wls and init_Rs:
                self.plot(init_wls, init_Rs, pen=pg.mkPen("#FF3366", width=1.5, style=Qt.PenStyle.DashLine), name="Initial R")
        self.plot(wavelengths, R_values, pen=pg.mkPen("#00AEEF", width=2), name="Reflectance")
        self.autoRange()


class CertusIndexProfilePlotWidget(CertusScientificPlot):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('title', "Refractive Index Profile")
        kwargs.setdefault('x_label', "Depth z (nm)")
        kwargs.setdefault('y_label', "Refractive Index n")
        super().__init__(*args, **kwargs)

    def plot_profile(self, z_coords: list[float], n_values: list[float]):
        self.clear()
        self.plot(
            z_coords,
            n_values,
            pen=pg.mkPen("#00AEEF", width=2.5),
            name="n profile",
            fillLevel=0,
            brush=(30, 58, 138, 30)
        )
        self.autoRange()

