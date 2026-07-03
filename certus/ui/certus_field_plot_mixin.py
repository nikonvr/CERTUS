from __future__ import annotations
from certus.ui.certus_field_common import *

class CertusFieldPlotMixin:
    """CertusFieldPlotMixin."""

    def _update_index_profile_plot(self):
        try:
            l0 = self.edit_l0.value()
            n1 = self._get_n_for_material(self.combo_mat_H.currentText(), l0)
            n2 = self._get_n_for_material(self.combo_mat_L.currentText(), l0)
            n_sub = self._get_n_for_material(self.combo_mat_Sub.currentText(), l0)
            n_sup = self._get_n_for_material(self.combo_mat_Sup.currentText(), l0)

            thicknesses = []
            n_vals = []
            for row in range(self.table_layers.rowCount()):
                thick_item = self.table_layers.item(row, 2)
                thick_val = self._safe_float_from_item(thick_item, 0.0)
                mat_str = self._get_layer_material_read_only(row)
                n = n1 if mat_str == "H" else n2

                if thick_val <= 0:
                    qwot_item = self.table_layers.item(row, 1)
                    qwot_val = self._safe_float_from_item(qwot_item, 0.0)
                    thick_val = FieldStackService.calculate_thickness_nm(qwot_val, n, l0)
                
                thicknesses.append(thick_val)
                n_vals.append(n)

            # Do NOT reverse them for index profile plotting. In CERTUS RE/STRAT, 
            # Substrate is at z=0 (left) and Superstrate is at z > 0 (right).
            if not thicknesses:
                z_coords = [0.0, 50.0]
                n_coords = [n_sub, n_sup]
            else:
                z_coords = [0.0, 0.0]
                n_coords = [n_sub, n_vals[0]]
                current_z = 0.0
                for i in range(len(thicknesses)):
                    current_z += thicknesses[i]
                    z_coords.extend([current_z, current_z])
                    if i < len(thicknesses) - 1:
                        n_coords.extend([n_vals[i], n_vals[i+1]])
                    else:
                        n_coords.extend([n_vals[i], n_sup])
                z_coords.extend([current_z + max(50.0, 0.1 * current_z)])
                n_coords.extend([n_sup])

            if hasattr(self, "profile_plot_widget"):
                for target in self._get_plot_targets("index_profile", self.profile_plot_widget):
                    target.plot_profile(z_coords, n_coords)
        except Exception as e:
            self.logger.debug(f"Error updating index profile plot: {e}")

    def detach_current_plot(self) -> None:
        """Clones the active plot tab into a detached floating window.

        Tab order (must match addTab call order in _build_right_panel):
          0 = Overview  (composite — not detachable individually)
          1 = Field           → field_profile
          2 = Spectrum         → spectral_response
          3 = Index          → index_profile
        """
        idx = self.tab_widget.currentIndex()
        if idx == 0:
            # Overview is composite; nothing to detach as a single plot
            show_toast(self, "Overview cannot be detached. Select an individual tab.", "info")
            return
        elif idx == 1:
            plot_name = "field_profile"
            plot_widget = self.plot_widget
            plot_title = "🔭 Electric Field Profile"
        elif idx == 2:
            plot_name = "spectral_response"
            plot_widget = self.spectral_plot_widget
            plot_title = "🌈 Spectral Response"
        elif idx == 3:
            plot_name = "index_profile"
            plot_widget = self.profile_plot_widget
            plot_title = "📊 Index Profile"
        else:
            return

        if plot_name in self.detached_plot_windows:
            win = self.detached_plot_windows[plot_name]
            if win.isVisible():
                win.raise_()
                win.activateWindow()
                return

        import functools
        clone = clone_plot_widget(plot_widget, title_override=plot_title)
        if clone is not None:
            win = DetachedPlotWindow(clone, parent=self, title=plot_title)
            win.closed_signal.connect(functools.partial(self.reattach_plot, plot_name))
            self.detached_plot_windows[plot_name] = win
            win.show()

    def reattach_plot(self, plot_name: str) -> None:
        """Safely close and clean up a detached plot window."""
        if plot_name in self.detached_plot_windows:
            win = self.detached_plot_windows[plot_name]
            win.deleteLater()
            del self.detached_plot_windows[plot_name]

    def _get_plot_targets(self, plot_name: str, primary_widget) -> list:
        targets = []
        if plot_name == "field_profile":
            if hasattr(self, "plot_widget"):
                targets.append(self.plot_widget)
            if hasattr(self, "plot_widget_ov"):
                targets.append(self.plot_widget_ov)
        elif plot_name == "spectral_response":
            if hasattr(self, "spectral_plot_widget"):
                targets.append(self.spectral_plot_widget)
            if hasattr(self, "spectral_plot_widget_ov"):
                targets.append(self.spectral_plot_widget_ov)
        elif plot_name == "index_profile":
            if hasattr(self, "profile_plot_widget"):
                targets.append(self.profile_plot_widget)
            if hasattr(self, "profile_plot_widget_ov"):
                targets.append(self.profile_plot_widget_ov)
        else:
            targets.append(primary_widget)

        if hasattr(self, "detached_plot_windows") and plot_name in self.detached_plot_windows:
            win = self.detached_plot_windows[plot_name]
            if win.isVisible() and hasattr(win, "plot_widget"):
                targets.append(win.plot_widget)
        return targets

    def _build_plot_export_frames(self, plot_data: dict) -> dict[str, pd.DataFrame]:
        return FieldExportService.build_plot_export_frames(plot_data)

    def _build_plot_data(self, result) -> FieldPlotData:
        return FieldPlotData.from_any(result)

    def _set_last_plot_data(self, plot_data):
        self._last_plot_data = FieldPlotData.from_any(plot_data).to_dict()

    def _refresh_result_views(self, plot_data: FieldPlotData, *, clear_first: bool = True) -> None:
        payload = plot_data.to_dict()
        
        # Extract layer types from the stack table
        layer_types = []
        for row in range(self.table_layers.rowCount()):
            layer_types.append(0 if self._normalize_layer_material(row) == "H" else 1)
        payload["layer_types"] = layer_types
        payload["sub_name"] = self.combo_mat_Sub.currentText()
        payload["sup_name"] = self.combo_mat_Sup.currentText()
        
        # Update field profile plots
        for target in self._get_plot_targets("field_profile", self.plot_widget):
            target.update_nominal_plot(payload, clear_first=clear_first, initial_data=self._initial_field_data)
            
        # Update index profile and spectral plots
        self._update_index_profile_plot()
        self._update_spectral_response()
        self._update_metrics_labels(plot_data)
        
        # Populate Field Result table
        if hasattr(self, "table_field_res") and plot_data.z_coords:
            headers = ["z (nm)"] + [f"|E|^2 (λ = {wl:g} nm)" for wl in plot_data.lambda_calcs]
            data = []
            for k in range(len(plot_data.z_coords)):
                row = [f"{plot_data.z_coords[k]:.2f}"]
                for w in range(len(plot_data.lambda_calcs)):
                    row.append(f"{plot_data.E2_values_list[w][k]:.6f}")
                data.append(row)
            self.table_field_res.set_data(headers, data)

        # Populate Design Result table
        if hasattr(self, "table_design_res"):
            params = self._get_params()
            n_H = self._get_n_for_material(self.combo_mat_H.currentText(), params.l0)
            n_L = self._get_n_for_material(self.combo_mat_L.currentText(), params.l0)
            design_headers = ["Layer", "Material", "Thickness (QWOT)", "Physical Thickness (nm)", f"Refractive Index (at {params.l0:g} nm)"]
            design_data = []
            # Add Superstrate row
            n_sup = self._get_n_for_material(self.combo_mat_Sup.currentText(), params.l0)
            design_data.append(["0 (Superstrate)", self.combo_mat_Sup.currentText(), "-", "-", f"{n_sup:.4f}"])
            # Add Stack layers
            for r in range(self.table_layers.rowCount()):
                mat = self.table_layers.item(r, 0).text() if self.table_layers.item(r, 0) else ""
                qwot = self.table_layers.item(r, 1).text() if self.table_layers.item(r, 1) else ""
                thick = self.table_layers.item(r, 2).text() if self.table_layers.item(r, 2) else ""
                idx_val = n_H if mat == "H" else n_L
                design_data.append([
                    str(r + 1),
                    mat,
                    qwot,
                    thick,
                    f"{idx_val:.4f}"
                ])
            # Add Substrate row
            n_sub = self._get_n_for_material(self.combo_mat_Sub.currentText(), params.l0)
            design_data.append([f"{self.table_layers.rowCount() + 1} (Substrate)", self.combo_mat_Sub.currentText(), "-", "-", f"{n_sub:.4f}"])
            self.table_design_res.set_data(design_headers, design_data)

        self._set_last_plot_data(payload)
        self.tab_widget.setCurrentIndex(0)

    def on_worker_plot(self, plot_data: dict, msg: str):
        """Intermediate plot callback during optimization — updates all field targets.

        Uses _get_plot_targets so that the overview widget (plot_widget_ov)
        and any detached window are also refreshed, not just the dedicated tab.
        Throttles redraws to keep the UI responsive during PGlobal.
        """
        if hasattr(self, "status_label"):
            self.status_label.setText(msg)

        now = __import__("time").monotonic()
        last_ts = getattr(self, "_last_field_plot_refresh_ts", 0.0)
        if now - last_ts < 0.12:
            self._pending_field_plot_data = plot_data
            self._pending_field_plot_msg = msg
            return
        self._last_field_plot_refresh_ts = now
        self._pending_field_plot_data = None
        self._pending_field_plot_msg = None

        # _get_plot_targets covers: plot_widget, plot_widget_ov, detached window
        for target in self._get_plot_targets("field_profile", self.plot_widget):
            target.update_nominal_plot(plot_data, initial_data=self._initial_field_data)
        self._set_last_plot_data(plot_data)
