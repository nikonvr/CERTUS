from __future__ import annotations
from certus.ui.certus_strat_common import *

class InteractiveHeatmapWindow(QWidget):  # <--- Changement ici: QWidget au lieu de QMainWindow
    def __init__(self, parent, raw_data_thickness) -> Any:

        super().__init__(parent)

        layout = QVBoxLayout(self)

        layout.setContentsMargins(0, 0, 0, 0)

        self.plot_widget = CertusScientificPlot(self, "Design Heatmap", "Wavelength (nm)", "Layer Number")

        self.plot_widget.showGrid(x=True, y=True, alpha=0.2)

        # Add widget to layout

        attach_excel_clipboard_context_menu(self.plot_widget)

        layout.addWidget(self.plot_widget.get_toolbar(self))

        layout.addWidget(self.plot_widget)

        if not raw_data_thickness:
            return

        self.layers = sorted(raw_data_thickness.keys())

        self.num_layers = len(self.layers)

        all_wls = set()

        for res_list in raw_data_thickness.values():
            for item in res_list:
                all_wls.add(item["wl"])

        self.sorted_wls = sorted(list(all_wls))

        if not self.sorted_wls:
            return

        wl_map = {wl: i for i, wl in enumerate(self.sorted_wls)}

        max_layer_idx = max(self.layers) if self.layers else 0
        grid = np.full((max_layer_idx + 1, len(self.sorted_wls)), np.nan, dtype=np.float64)

        path_x, path_y = [], []

        for l_idx in self.layers:
            items = raw_data_thickness.get(l_idx, [])

            if items:
                for item in items:
                    w_idx = wl_map.get(item["wl"])

                    if w_idx is not None:
                        grid[l_idx, w_idx] = item["cost"]

                best = min(items, key=lambda x: x["cost"])

                path_x.append(l_idx + 0.5)

                path_y.append(best["wl"])

        max_val = 1.0
        if np.any(np.isfinite(grid)):
            max_val = float(np.nanmax(grid))
        grid_filled = np.nan_to_num(grid, nan=max_val)

        valid_mask = np.isfinite(grid) & (grid > 0)

        if valid_mask.any():
            log_vals = np.log10(grid[valid_mask])

            vmin, vmax = np.percentile(log_vals, 2), np.percentile(log_vals, 98)

            denom = vmax - vmin if vmax != vmin else 1.0

            grid_norm = np.clip((np.log10(grid_filled) - vmin) / denom, 0, 1)

        else:
            grid_norm = np.zeros_like(grid)

        self.img_item = pg.ImageItem(grid_norm)

        # Palette de couleurs (Magma-ish)

        pos = np.linspace(0, 1, 5)

        color = np.array(
            [
                [15, 23, 42, 255],
                [60, 20, 80, 255],
                [180, 40, 80, 255],
                [250, 140, 50, 255],
                [252, 250, 230, 255],
            ],
            dtype=np.ubyte,
        )

        cmap = pg.ColorMap(pos, color)

        self.img_item.setLookupTable(cmap.getLookupTable(0.0, 1.0, 256))

        y0 = self.sorted_wls[0]

        y_range = self.sorted_wls[-1] - y0

        y_scale = y_range / len(self.sorted_wls) if len(self.sorted_wls) > 0 else 1.0

        tr = QTransform()

        tr.translate(0, y0)

        tr.scale(1, y_scale)

        self.img_item.setTransform(tr)

        self.plot_widget.addItem(self.img_item)

        if path_x:
            # Step Plot Construction

            step_x, step_y = [], []

            step_x.append(path_x[0])

            step_y.append(path_y[0])

            for i in range(1, len(path_x)):
                step_x.append(path_x[i])

                step_y.append(path_y[i - 1])

                step_x.append(path_x[i])

                step_y.append(path_y[i])

            self.plot_widget.plot(step_x, step_y, pen=pg.mkPen("c", width=3), name="Optimal Strategy")

        self.plot_widget.setXRange(0, self.num_layers)

        self.plot_widget.setYRange(y0, self.sorted_wls[-1])

        def _heatmap_clipboard_df() -> Any:

            rows = []

            for lk in self.layers:
                for j, wl in enumerate(self.sorted_wls):
                    v = float(grid[lk, j])

                    if np.isfinite(v):
                        rows.append(
                            {
                                "layer_key": int(lk),
                                "wavelength_nm": float(wl),
                                "cost": v,
                            }
                        )

            if not rows:
                return None

            return pd.DataFrame(rows)

        self.plot_widget._certus_clipboard_df_provider = _heatmap_clipboard_df

