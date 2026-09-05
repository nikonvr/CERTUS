from __future__ import annotations
from certus.ui.certus_field_common import *

class CertusFieldStateMixin:
    """CertusFieldStateMixin."""

    def _get_default_splitter_sizes(self) -> list[int]:
        return [520, 1380]



    def on_cleanup(self):
        removed = self.smart_cleanup(self.table_layers)
        if removed > 0:
            show_toast(self, f"Cleaned up {removed} layer(s).", variant="success")
        else:
            show_toast(self, "Stack is already clean.", variant="info")

    def on_needle(self):
        try:
            params = self._get_params()
        except ValueError as err:
            show_toast(self, str(err), "warning")
            return
            
        self._initial_field_data = getattr(self, "_last_plot_data", None)
        self._initial_spectral_data = getattr(self, "_last_spectral_data", None)

        self.btn_calc.setEnabled(False)
        self.btn_opt.setEnabled(False)
        self.btn_mc.setEnabled(False)
        self._start_worker(FieldWorkerRequest(action="needle", params=params))

    def _normalize_layer_material(self, row: int) -> str:
        mat_item = self.table_layers.item(row, 0)
        if mat_item is None:
            mat_item = QTableWidgetItem("H")
            mat_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table_layers.setItem(row, 0, mat_item)
        mat_str = mat_item.text().strip().upper()
        normalized = "H" if mat_str not in {"H", "L"} else mat_str
        if normalized != mat_item.text().strip().upper():
            mat_item.setText(normalized)
        return normalized

    def _safe_float_from_item(self, item: QTableWidgetItem | None, default: float = 0.0) -> float:
        if item is None:
            return default
        try:
            return float(item.text().strip().replace(",", "."))
        except (AttributeError, ValueError):
            return default

    def _parse_lambda_calcs(self) -> list[float]:
        raw = self.edit_lcalc.text().replace(';', ',')
        values = []
        for chunk in raw.split(','):
            token = chunk.strip()
            if not token:
                continue
            try:
                value = float(token)
            except ValueError as exc:
                raise ValueError(f"Invalid wavelength: {token}") from exc
            if value <= 0:
                raise ValueError(f"Wavelength must be positive: {value}")
            values.append(value)
        if not values:
            raise ValueError("Please enter at least one calculation wavelength.")
        return values

    def _get_n_for_material(self, mat_name: str, wl: float) -> float:
        if mat_name == "Air":
            return 1.0
        if self.materials_db and hasattr(self.materials_db, "_db"):
            try:
                db_ref = self.materials_db._db
                name_norm = mat_name.strip().lower()
                if name_norm in db_ref.SUBSTRATE_NAMES:
                    return float(db_ref.get_substrate_index(mat_name, wl).real)
                else:
                    return float(db_ref.get_material_index(mat_name, wl).real)
            except Exception:
                pass
        # Fallbacks to avoid crashes if DB is empty or fails
        if "Ta2O5" in mat_name: return 2.10
        if "Nb" in mat_name: return 2.20
        if "SiO2" in mat_name: return 1.46
        if "BK7" in mat_name: return 1.52
        return 1.5

    def _update_thicknesses(self):
        if self._is_updating_table:
            return
        self._is_updating_table = True
        try:
            l0 = self.edit_l0.value()
            n1 = self._get_n_for_material(self.combo_mat_H.currentText(), l0)
            n2 = self._get_n_for_material(self.combo_mat_L.currentText(), l0)

            for row in range(self.table_layers.rowCount()):
                qwot_item = self.table_layers.item(row, 1)
                thick_item = self.table_layers.item(row, 2)
                if not (qwot_item and thick_item):
                    continue

                qwot_val = self._safe_float_from_item(qwot_item, 0.0)
                mat_str = self._normalize_layer_material(row)
                n = n1 if mat_str == "H" else n2

                thickness_nm = FieldStackService.calculate_thickness_nm(qwot_val, n, l0)

                self.stack_panel.is_updating_table = True
                thick_item.setText(f"{thickness_nm:.2f}")
                self.stack_panel.is_updating_table = False
        finally:
            self._is_updating_table = False
        
        self._update_index_profile_plot()
        self._update_spectral_response()
        self.trigger_auto_calc()

    def _update_qwot_from_thickness(self, row: int):
        if self._is_updating_table or row < 0 or row >= self.table_layers.rowCount():
            return
        self._is_updating_table = True
        try:
            l0 = self.edit_l0.value()
            n1 = self._get_n_for_material(self.combo_mat_H.currentText(), l0)
            n2 = self._get_n_for_material(self.combo_mat_L.currentText(), l0)

            qwot_item = self.table_layers.item(row, 1)
            thick_item = self.table_layers.item(row, 2)
            if not (qwot_item and thick_item):
                return

            thick_val = self._safe_float_from_item(thick_item, 0.0)
            mat_str = self._normalize_layer_material(row)
            n = n1 if mat_str == "H" else n2

            qwot_val = FieldStackService.calculate_qwot(thick_val, n, l0)

            self.stack_panel.is_updating_table = True
            qwot_item.setText(f"{qwot_val:.4f}")
            self.stack_panel.is_updating_table = False
        finally:
            self._is_updating_table = False

        self._update_index_profile_plot()
        self._update_spectral_response()

    def _get_layer_material_read_only(self, row: int) -> str:
        mat_item = self.table_layers.item(row, 0)
        if mat_item is None:
            return "H" if row % 2 == 0 else "L"
        mat_str = mat_item.text().strip().upper()
        return mat_str if mat_str in {"H", "L"} else ("H" if row % 2 == 0 else "L")

    def _update_spectral_response(self):
        try:
            params = self._get_params()
            l0 = params.l0
            emp_factors = params.emp_factors
            layer_types = params.layer_types
            theta_inc = params.theta_inc
            pol_flag = params.pol_flag

            wls = np.linspace(max(350.0, 0.5 * l0), 1.5 * l0, 200)
            R_values = []
            for wl in wls:
                n1 = self._get_n_for_material(self.combo_mat_H.currentText(), wl)
                n2 = self._get_n_for_material(self.combo_mat_L.currentText(), wl)
                n_sub = self._get_n_for_material(self.combo_mat_Sub.currentText(), wl)
                n_sup = self._get_n_for_material(self.combo_mat_Sup.currentText(), wl)

                metrics = calculate_opt_metrics(
                    n1_r=n1,
                    n2_r=n2,
                    nSub_r=n_sub,
                    l0=l0,
                    emp_factors_list=emp_factors,
                    layer_types=layer_types,
                    n_super=n_sup,
                    theta_inc=theta_inc,
                    pol_flag=pol_flag,
                    lambda_calc=wl
                )
                R_values.append(metrics['R'])

            self._last_spectral_data = {
                'wavelengths': list(wls),
                'R_values': R_values
            }

            if hasattr(self, "spectral_plot_widget"):
                for target in self._get_plot_targets("spectral_response", self.spectral_plot_widget):
                    target.plot_spectral_response(list(wls), R_values, initial_data=self._initial_spectral_data)

            if hasattr(self, "table_spectral_res"):
                spec_headers = ["Wavelength (nm)", "Reflectance (R)"]
                spec_data = [[f"{wl:.2f}", f"{r:.6f}"] for wl, r in zip(wls, R_values)]
                self.table_spectral_res.set_data(spec_headers, spec_data)
        except Exception as e:
            self.logger.debug(f"Error updating spectral response: {e}")

    def toggle_detach_stack(self) -> None:
        """Toggle the detachment of the stack panel into a separate window securely."""
        try:
            if self.detached_stack_window is None:
                self.detached_stack_window = DetachedStackWindow(self.stack_panel, parent=self)
                self.detached_stack_window.closed_signal.connect(self.reattach_stack)
                self.detached_plot_windows["stack_structure"] = self.detached_stack_window
                self.stack_panel.set_controls_visible(True)
                self.detached_stack_window.show()
                self.btn_detach_stack.setText("⬡ Reattach Stack")
            else:
                self.detached_stack_window.close()
        except Exception as e:
            logging.error(f"Error toggling detach stack: {e}")

    def reattach_stack(self) -> None:
        """Securely reattach the stack panel to the main interface."""
        try:
            if self.detached_stack_window is not None:
                self.card_stack.body.insertWidget(0, self.stack_panel)
                self.stack_panel.show()
                self.stack_panel.set_controls_visible(False)
                self.btn_detach_stack.setText("⬡ Detach Stack")
                
                try:
                    self.detached_stack_window.closed_signal.disconnect()
                except Exception:
                    pass
                
                if "stack_structure" in self.detached_plot_windows:
                    del self.detached_plot_windows["stack_structure"]
                self.detached_stack_window = None
        except Exception as e:
            logging.error(f"Error reattaching stack: {e}")

    def _apply_theme(self) -> None:
        plots_to_theme = []
        if hasattr(self, "plot_widget"):
            plots_to_theme.extend(self._get_plot_targets("field_profile", self.plot_widget))
        if hasattr(self, "spectral_plot_widget"):
            plots_to_theme.extend(self._get_plot_targets("spectral_response", self.spectral_plot_widget))
        if hasattr(self, "profile_plot_widget"):
            plots_to_theme.extend(self._get_plot_targets("index_profile", self.profile_plot_widget))
            
        if plots_to_theme:
            self._apply_certus_compact_theme(plots=plots_to_theme)
        
        if hasattr(self, "log_text"):
            self.log_text.setStyleSheet(f"""
                QTextEdit {{
                    background-color: {CertusTheme.SURFACE};
                    color: {CertusTheme.TEXT_MAIN};
                    border: 1px solid {CertusTheme.BORDER};
                    border-radius: 4px;
                }}
            """)

    def _setup_shortcuts(self) -> None:
        pass # Managed partly by base class

    def _copy_table_to_clipboard(self, table: ExcelTableWidget) -> None:
        lines = []
        cols = table.columnCount()
        hdr = [table.horizontalHeaderItem(c).text() if table.horizontalHeaderItem(c) else "" for c in range(cols)]
        lines.append("\t".join(hdr))
        for r in range(table.rowCount()):
            row = [table.item(r, c).text() if table.item(r, c) else "" for c in range(cols)]
            lines.append("\t".join(row))
        QApplication.clipboard().setText("\n".join(lines))

    def _copy_field_res_to_clipboard(self) -> None:
        if hasattr(self, "table_field_res"):
            self._copy_table_to_clipboard(self.table_field_res)
            show_toast(self, "Field data copied to clipboard!", "success")

    def _copy_spectral_res_to_clipboard(self) -> None:
        if hasattr(self, "table_spectral_res"):
            self._copy_table_to_clipboard(self.table_spectral_res)
            show_toast(self, "Spectral data copied to clipboard!", "success")

    def _copy_design_res_to_clipboard(self) -> None:
        if hasattr(self, "table_design_res"):
            self._copy_table_to_clipboard(self.table_design_res)
            show_toast(self, "Design data copied to clipboard!", "success")

    def _load_stack(self, emp_factors: list[float], layer_types: list[int] | None = None):
        normalized_layer_types = FieldStackService.normalize_layer_types(layer_types, len(emp_factors))
        FieldStackService.load_stack(self.stack_panel.table_layers, emp_factors, normalized_layer_types)

    def reset_to_defaults(self):
        from certus.utils.certus_reset_framework import reset_app_to_defaults
        return reset_app_to_defaults(self)

    def _load_defaults(self):
        self._skip_auto_calc = True
        try:
            # Restore OpticsPanel defaults
            self.combo_mat_H.setCurrentText("H800-Nb2O5")
            self.combo_mat_L.setCurrentText("H800-SiO2")
            self.combo_mat_Sub.setCurrentText("SiO2")
            self.combo_mat_Sup.setCurrentText("Air")
            self.edit_l0.setValue(1064.0)
            self.edit_lcalc.setText("1064.0")
            self.edit_angle.setValue(0.0)
            self.combo_pol.setCurrentIndex(0) # S (TE)

            # Restore OptimizationPanel defaults
            self.edit_seuil1.setValue(3.0)
            self.edit_seuil2.setValue(25.0)
            self.edit_alpha.setValue(10.0)
            self.edit_mc_error.setValue(2.0)
            self.edit_mc_iter.setValue(50.0)
            self.edit_rmin.setValue(1.0)
            self.edit_rmax.setValue(1.0)
            self.chk_min_field.setChecked(False)
            self.chk_global_opt.setChecked(False)
            self.chk_allow_growth.setChecked(False)
            self.opt_panel.edit_dmin.setValue(5.0)

            # Restore StackPanel table defaults
            self.stack_panel.is_updating_table = True
            self.table_layers.setRowCount(9)
            for i in range(9):
                self.stack_panel.add_row_to_table(i, 1.0)
            self.stack_panel.is_updating_table = False

            # Reset status and labels
            self.lbl_max_e2.setText("Peak |E|² : N/A")
            self.lbl_r.setText("R : N/A")
            
            # Reset internal data
            self.current_result = None
            self._last_plot_data = None
            self._initial_field_data = None
            self._initial_spectral_data = None
            self.pareto_history.clear()
            
            # Reset plot widgets
            self.plot_widget.clear()
            self.plot_widget_ov.clear()
            self.spectral_plot_widget.clear()
            self.spectral_plot_widget_ov.clear()
            self.profile_plot_widget.clear()
            self.profile_plot_widget_ov.clear()
        finally:
            self._skip_auto_calc = False
            self._update_thicknesses()

    def save_config(self):
        try:
            params = self._get_params()
        except Exception:
            show_toast(self, "Invalid configuration", "error")
            return

        filename, _ = QFileDialog.getSaveFileName(self, "Save Configuration", "", "JSON Files (*.json)")
        if not filename:
            return

        data = {
            "mat_H": self.combo_mat_H.currentText(),
            "mat_L": self.combo_mat_L.currentText(),
            "mat_Sub": self.combo_mat_Sub.currentText(),
            "mat_Sup": self.combo_mat_Sup.currentText(),
            "l0": params.l0,
            "lcalc": self.edit_lcalc.text(),
            "emp_factors": params.emp_factors,
            "layer_types": params.layer_types,
            "seuil1": params.seuil_int_1,
            "seuil2": params.seuil_int_2,
            "alpha": params.alpha,
            "theta_inc_deg": self.edit_angle.value(),
            "pol_idx": self.combo_pol.currentIndex(),
            "mc_error": self.edit_mc_error.value(),
            "mc_iter": int(self.edit_mc_iter.value()),
            "rmin": params.rmin,
            "rmax": params.rmax,
            "min_field_active": bool(params.min_field_active),
            "global_opt": bool(params.global_opt),
            "allow_growth": bool(self.chk_allow_growth.isChecked())
        }

        try:
            with open(filename, 'w') as f:
                json.dump(data, f, indent=4)
            show_toast(self, "Configuration saved successfully.", "success")
        except Exception as e:
            show_toast(self, f"Error saving: {e}", "error")

    def load_config(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Load Configuration", "", "JSON Files (*.json)")
        if not filename:
            return

        try:
            with open(filename, 'r') as f:
                data = json.load(f)
            
            def set_combo(combo: QComboBox, text: str):
                idx = combo.findText(text)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                    
            set_combo(self.combo_mat_H, data.get("mat_H", "H800-Nb2O5"))
            set_combo(self.combo_mat_L, data.get("mat_L", "H800-SiO2"))
            set_combo(self.combo_mat_Sub, data.get("mat_Sub", "SiO2"))
            set_combo(self.combo_mat_Sup, data.get("mat_Sup", "Air"))
            
            self.edit_l0.setValue(data.get("l0", 1064.0))
            self.edit_lcalc.setText(str(data.get("lcalc", "1064.0")))
            self.edit_seuil1.setValue(data.get("seuil1", 0.5))
            self.edit_seuil2.setValue(data.get("seuil2", 0.5))
            self.edit_alpha.setValue(data.get("alpha", 10.0))
            
            self.edit_angle.setValue(data.get("theta_inc_deg", 0.0))
            self.combo_pol.setCurrentIndex(data.get("pol_idx", 0))
            self.edit_mc_error.setValue(data.get("mc_error", 2.0))
            self.edit_mc_iter.setValue(data.get("mc_iter", 50))
            self.edit_rmin.setValue(data.get("rmin", 1.0))
            self.edit_rmax.setValue(data.get("rmax", 1.0))
            self.chk_min_field.setChecked(bool(data.get("min_field_active", False)))
            self.chk_global_opt.setChecked(bool(data.get("global_opt", False)))
            self.chk_allow_growth.setChecked(bool(data.get("allow_growth", False)))
            
            emp = data.get("emp_factors", [])
            layer_types = data.get("layer_types", [])

            self._is_updating_table = True
            try:
                self._load_stack(emp, layer_types)
            finally:
                self._is_updating_table = False
            self._update_thicknesses()
            
            show_toast(self, "Configuration loaded.", "success")
        except Exception as e:
            show_toast(self, f"Error loading: {e}", "error")

    def open_help(self):
        show_toast(self, "CERTUS Electric Field Optimization module.", "info")

    def _get_params(self) -> FieldParamsDTO:
        emp_factors = []
        layer_types = []
        for row in range(self.table_layers.rowCount()):
            qwot_item = self.table_layers.item(row, 1)
            if qwot_item is None:
                continue

            qwot_value = self._safe_float_from_item(qwot_item, default=np.nan)
            if not np.isfinite(qwot_value) or qwot_value <= 0:
                raise ValueError(f"Invalid QWOT at row {row + 1}.")

            emp_factors.append(qwot_value)
            layer_types.append(0 if self._normalize_layer_material(row) == "H" else 1)

        if not emp_factors:
            raise ValueError("Stack is empty.")

        lambda_calcs = self._parse_lambda_calcs()
        l0 = self.edit_l0.value()
        if l0 <= 0:
            raise ValueError("Center wavelength must be positive.")

        n1_rs = [self._get_n_for_material(self.combo_mat_H.currentText(), wavelength) for wavelength in lambda_calcs]
        n2_rs = [self._get_n_for_material(self.combo_mat_L.currentText(), wavelength) for wavelength in lambda_calcs]
        nSub_rs = [self._get_n_for_material(self.combo_mat_Sub.currentText(), wavelength) for wavelength in lambda_calcs]
        nSup_rs = [self._get_n_for_material(self.combo_mat_Sup.currentText(), wavelength) for wavelength in lambda_calcs]

        return FieldParamsDTO(
            n1_rs=n1_rs,
            n2_rs=n2_rs,
            nSub_rs=nSub_rs,
            n_supers=nSup_rs,
            l0=l0,
            lambda_calcs=lambda_calcs,
            emp_factors=emp_factors,
            layer_types=layer_types,
            seuil_int_1=self.edit_seuil1.value(),
            seuil_int_2=self.edit_seuil2.value(),
            alpha=self.edit_alpha.value(),
            maxiter=1000,
            theta_inc=np.radians(self.edit_angle.value()),
            pol_flag=self.combo_pol.currentIndex(),
            tolerate_error=self.edit_mc_error.value() / 100.0,
            mc_iterations=int(self.edit_mc_iter.value()),
            rmin=self.edit_rmin.value(),
            rmax=self.edit_rmax.value(),
            min_field_active=self.chk_min_field.isChecked(),
            global_opt=self.chk_global_opt.isChecked(),
            dmin=self.opt_panel.edit_dmin.value(),
        )

    def on_import_design(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Import Design", "", "JSON Files (*.json)")
        if not filename:
            return

        try:
            with open(filename, 'r') as f:
                data = json.load(f)

            # If the design file contains materials and center wavelength config, load them
            for key, combo in [("mat_H", self.combo_mat_H), ("mat_L", self.combo_mat_L), ("mat_Sub", self.combo_mat_Sub), ("mat_Sup", self.combo_mat_Sup)]:
                if key in data:
                    idx = combo.findText(data[key])
                    if idx >= 0:
                        combo.setCurrentIndex(idx)
            if "l0" in data:
                try:
                    self.edit_l0.setValue(float(data["l0"]))
                except (ValueError, TypeError):
                    pass
            if "rmin" in data:
                try:
                    self.edit_rmin.setValue(float(data["rmin"]))
                except (ValueError, TypeError):
                    pass
            if "rmax" in data:
                try:
                    self.edit_rmax.setValue(float(data["rmax"]))
                except (ValueError, TypeError):
                    pass

            self._is_updating_table = True
            try:
                if "emp_factors" in data:
                    layer_types = data.get("layer_types", [])
                    self.table_layers.setRowCount(0)
                    for i, f_val in enumerate(data["emp_factors"]):
                        self.table_layers.insertRow(i)
                        material = None
                        if layer_types and i < len(layer_types):
                            material = "H" if layer_types[i] == 0 else "L"
                        self.stack_panel.add_row_to_table(i, float(f_val), mat_str=material)
                elif "layers" in data:
                    self.table_layers.setRowCount(0)
                    for i, layer in enumerate(data["layers"]):
                        material_name = str(layer.get("material", "H"))
                        thickness_nm = float(layer.get("physical_thickness_nm", 0.0))
                        self.table_layers.insertRow(i)
                        material = "H" if "H" in material_name.upper() else "L"
                        self.stack_panel.add_row_to_table(i, 1.0, mat_str=material)
                        self.table_layers.item(i, 2).setText(f"{thickness_nm:.2f}")
                else:
                    raise ValueError("Unrecognized file format.")
            finally:
                self._is_updating_table = False

            if "layers" in data:
                for i in range(self.table_layers.rowCount()):
                    self._update_qwot_from_thickness(i)
            else:
                self._update_thicknesses()
            
            show_toast(self, "Design imported successfully.", "success")

            # Build and show load summary popup
            sub_label = data.get("mat_Sub") or data.get("substrate_choice") or self.combo_mat_Sub.currentText()
            summary_lines = [
                f"SUBSTRATE: {sub_label}",
                "FACES: ONE FACE (NO BACKSIDE)",
                "",
                f"File: {Path(filename).resolve()}",
                "",
                "Design Parameters:",
                f"  High Index Material (H): {data.get('mat_H') or self.combo_mat_H.currentText()}",
                f"  Low Index Material (L): {data.get('mat_L') or self.combo_mat_L.currentText()}",
                f"  Superstrate: {data.get('mat_Sup') or self.combo_mat_Sup.currentText()}",
                f"  Center Wavelength (l0): {data.get('l0', self.edit_l0.value())} nm",
                "",
                "Structure Details:",
                f"  Total Layers: {self.table_layers.rowCount()}",
            ]
            total_thick = 0.0
            for r in range(self.table_layers.rowCount()):
                thick_item = self.table_layers.item(r, 2)
                if thick_item:
                    try:
                        total_thick += float(thick_item.text().strip())
                    except ValueError:
                        pass
            summary_lines.append(f"  Total Physical Thickness: {total_thick:.2f} nm")

            # Create a vertical list popup mimicking CERTUS STRAT results
            from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QHBoxLayout
            from PyQt6.QtCore import Qt

            dlg = QDialog(self)
            dlg.setWindowTitle("FIELD Load Summary")
            dlg.resize(450, 600)
            lay = QVBoxLayout(dlg)

            info = QLabel("\n".join(summary_lines))
            info.setWordWrap(True)
            lay.addWidget(info)

            tbl = QTableWidget()
            tbl.setColumnCount(3)
            tbl.setHorizontalHeaderLabels(["Mat", "QWOT", "Physical (nm)"])
            tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            tbl.setRowCount(self.table_layers.rowCount())
            
            for row in range(self.table_layers.rowCount()):
                for col in range(3):
                    item = self.table_layers.item(row, col)
                    if item:
                        new_item = QTableWidgetItem(item.text())
                        new_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                        new_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                        tbl.setItem(row, col, new_item)

            lay.addWidget(tbl)

            row_btn = QHBoxLayout()
            row_btn.addStretch()
            btn_close = QPushButton("Close")
            btn_close.clicked.connect(dlg.close)
            row_btn.addWidget(btn_close)
            lay.addLayout(row_btn)

            dlg.exec()

        except Exception as e:
            self.logger.error(f"Import error: {str(e)}")
            show_toast(self, f"Error: {str(e)}", "error")

    def _get_cleanup_dmin_nm(self) -> float:
        """Return the minimum thickness threshold used for post-optimization cleanup."""
        try:
            if hasattr(self, "opt_panel") and hasattr(self.opt_panel, "edit_dmin"):
                return max(0.0, float(self.opt_panel.edit_dmin.value()))
        except Exception:
            pass
        return 5.0

    def _stack_has_layers_below_dmin(self, dmin_nm: float) -> bool:
        if self.table_layers.rowCount() <= 0:
            return False
        for row in range(self.table_layers.rowCount()):
            thick_item = self.table_layers.item(row, 2)
            if thick_item is None:
                continue
            try:
                if float(thick_item.text()) < dmin_nm:
                    return True
            except Exception:
                continue
        return False

    def _remove_thin_layers_strict(self, dmin_nm: float) -> int:
        """Remove every layer thinner than ``dmin_nm`` and merge adjacent identical layers.

        Returns the number of rows removed. This is intentionally deterministic and
        conservative: it never deletes the whole stack and keeps at least one layer.
        """
        if self.table_layers.rowCount() <= 1:
            return 0

        removed_total = 0
        while self.table_layers.rowCount() > 1:
            rows_to_remove: list[int] = []
            for row in range(self.table_layers.rowCount()):
                thick_item = self.table_layers.item(row, 2)
                if thick_item is None:
                    continue
                try:
                    thickness = float(thick_item.text())
                except Exception:
                    continue
                if thickness < dmin_nm:
                    rows_to_remove.append(row)

            # Keep at least one layer
            if len(rows_to_remove) >= self.table_layers.rowCount():
                rows_to_remove = rows_to_remove[:-1]

            if not rows_to_remove:
                break

            for row in reversed(rows_to_remove):
                self.table_layers.removeRow(row)
                removed_total += 1

            if self.table_layers.rowCount() > 1:
                self.rebuild_material_pattern()
                self.smart_cleanup(self.table_layers)
            if not self._stack_has_layers_below_dmin(dmin_nm):
                break

        return removed_total

    def _cleanup_thin_layers_and_reoptimize(self, *, source: str = "optimization") -> bool:
        """Remove layers thinner than dmin and relaunch a local optimization once."""
        dmin_nm = self._get_cleanup_dmin_nm()
        if self.table_layers.rowCount() <= 0 or not self._stack_has_layers_below_dmin(dmin_nm):
            return False

        self.logger.info("[FIELD] Post-%s cleanup triggered (dmin=%.2f nm).", source, dmin_nm)
        self._skip_auto_calc = True
        self._is_updating_table = True
        try:
            removed = self._remove_thin_layers_strict(dmin_nm)
        finally:
            self._is_updating_table = False

        if removed > 0:
            self.logger.info("[FIELD] strict cleanup removed %d thin layer(s).", removed)

        try:
            params = self._get_params()
        except ValueError as e:
            self.logger.warning("[FIELD] cleanup completed but local re-optimization could not start: %s", e)
            self._skip_auto_calc = False
            return True

        params.global_opt = False
        params.synthesis_mode = False
        self.btn_calc.setEnabled(False)
        self.btn_opt.setEnabled(False)
        self.btn_mc.setEnabled(False)
        self._start_worker(FieldWorkerRequest(action="optimize", params=params))
        QTimer.singleShot(250, lambda: setattr(self, "_skip_auto_calc", False))
        return True

    def _compute_cost(self, emp_factors: list[float], layer_types: list[int]) -> float:
        try:
            params = self._get_params()
        except ValueError:
            return float('inf')
        
        from certus.workers.certus_field_workers import top_level_objective_function
        return top_level_objective_function(
            emp_factors,
            params.n1_rs,
            params.n2_rs,
            params.nSub_rs,
            params.l0,
            params.seuil_int_1,
            params.seuil_int_2,
            params.alpha,
            params.integral_points,
            params.n_supers,
            params.theta_inc,
            params.pol_flag,
            params.lambda_calcs,
            layer_types,
            rmin=params.rmin,
            rmax=params.rmax,
            min_field_active=params.min_field_active
        )

    def _revert_to_synthesis_checkpoint(self):
        """Restore the best synthesis checkpoint and re-enable auto-calc.

        Mirrors the pattern of _restore_pareto_champion: _skip_auto_calc is
        reset AFTER the table is populated to avoid spurious intermediate
        auto-calc firings, then immediately unlocked so the UI stays reactive.
        """
        if hasattr(self, "_synthesis_checkpoint") and self._synthesis_checkpoint is not None:
            chk = self._synthesis_checkpoint
            # GUARD: block auto-calc noise during table reload
            self._skip_auto_calc = True
            self._is_updating_table = True
            try:
                FieldStackService.load_stack(self.table_layers, chk["emp_factors"], chk["layer_types"])
            finally:
                self._is_updating_table = False
            self._update_thicknesses()
            # CRITICAL: re-enable auto-calc so the UI stays reactive after revert
            self._skip_auto_calc = False
            self.logger.info(f"Reverted to best synthesis checkpoint (Cost={chk['cost']:.6f})")

    def copy_logs_to_clipboard(self) -> None:
        from certus.ui.certus_ui import copy_app_logs_to_clipboard
        if copy_app_logs_to_clipboard(self):
            show_toast(self, "Logs copied to clipboard!", "success")
            if hasattr(self, "status_label"):
                self.status_label.setText("Logs copied to clipboard!")
        else:
            show_toast(self, "No logs to copy.", "warning")

    def trigger_auto_calc(self):
        if getattr(self, "_skip_auto_calc", False):
            return
        if hasattr(self, 'auto_calc_timer'):
            self.auto_calc_timer.start(300)

    def run_auto_calc(self):
        if hasattr(self, 'worker') and self.worker is not None and self.worker.isRunning():
            if getattr(self.worker, 'request', None) and self.worker.request.action == "calculate":
                self.worker.stop()
                self.auto_calc_timer.start(100)
            return

        try:
            params = self._get_params()
        except ValueError:
            return

        self.btn_calc.setEnabled(False)
        self.btn_opt.setEnabled(False)
        self.btn_mc.setEnabled(False)
        self._start_worker(FieldWorkerRequest(action="calculate", params=params))

    def _update_metrics_labels(self, plot_data: FieldPlotData):
        try:
            flat_e2 = [val for sublist in plot_data.E2_values_list for val in sublist]
            peak_e2 = max(flat_e2) if flat_e2 else 0.0
            self.lbl_max_e2.setText(f"Peak |E|² : {peak_e2:.4f}")
            
            # Now calculate R for each evaluation wavelength
            params = self._get_params()
            r_strs = []
            for i, wl in enumerate(params.lambda_calcs):
                metrics = calculate_opt_metrics(
                    n1_r=params.n1_rs[i],
                    n2_r=params.n2_rs[i],
                    nSub_r=params.nSub_rs[i],
                    l0=params.l0,
                    emp_factors_list=params.emp_factors,
                    layer_types=params.layer_types,
                    n_super=params.n_supers[i],
                    theta_inc=params.theta_inc,
                    pol_flag=params.pol_flag,
                    lambda_calc=wl
                )
                r_strs.append(f"R({wl:g}nm) = {metrics['R']:.4f}")
            
            self.lbl_r.setText(" | ".join(r_strs))
        except Exception as e:
            self.logger.debug(f"Error updating metrics labels: {e}")

    def _ensure_pareto_ui(self) -> bool:
        """Create Pareto window/table lazily and only when Qt is ready."""
        if self.pareto_window is not None:
            return True

        self.pareto_window = QDialog(self)
        self.pareto_window.setWindowTitle("Pareto Front Explorer - CERTUS-FIELD")
        self.pareto_window.setMinimumSize(850, 400)

        p_lay = QVBoxLayout(self.pareto_window)

        lbl = QLabel(
            "Double-click col 1-2 = load Best Cost | "
            "Double-click col 3-4 = load Best MC | "
            "Double-click col 5-6 = load Best Fab (>=5nm)"
        )
        lbl.setStyleSheet("font-size: 12px; margin-bottom: 5px; color: #475569;")
        p_lay.addWidget(lbl)

        self.pareto_table = QTableWidget(0, 8)
        self.pareto_table.setSortingEnabled(True)
        _hdr_pareto = self.pareto_table.horizontalHeader()
        if _hdr_pareto is not None:
            _hdr_pareto.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.pareto_table.setHorizontalHeaderLabels([
            "N Layers", "Best Cost", "d_min Cost",
            "Best MC", "d_min MC", "Best Fab", "d_min Fab",
            "Cost/N"
        ])
        self.pareto_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.pareto_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.pareto_table.verticalHeader().setVisible(False)
        self.pareto_table.setAlternatingRowColors(True)
        
        for i in range(8):
            self.pareto_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)

        self.pareto_table.cellDoubleClicked.connect(self._load_pareto_design)
        p_lay.addWidget(self.pareto_table)

        f_p_btns = QHBoxLayout()

        clr_btn = QPushButton("Clear Pareto")
        clr_btn.setToolTip("Clear the Pareto front table.")
        clr_btn.clicked.connect(self._clear_pareto)

        exp_btn = QPushButton("Export HTML Report")
        exp_btn.setToolTip("Export Pareto front to an HTML report.")
        exp_btn.clicked.connect(self._export_pareto_report)

        f_p_btns.addWidget(clr_btn)
        f_p_btns.addStretch()
        f_p_btns.addWidget(exp_btn)
        p_lay.addLayout(f_p_btns)

        clr_btn.setStyleSheet(CertusTheme.get_button_style("secondary"))
        exp_btn.setStyleSheet(CertusTheme.get_button_style("primary"))

        self._refresh_pareto_table()
        return True

    def _show_pareto_window(self) -> None:
        """Display the Pareto table in a detachable window."""
        if not self._ensure_pareto_ui():
            return
        self._refresh_pareto_table()
        self.pareto_window.show()
        self.pareto_window.raise_()
        self.pareto_window.activateWindow()
        if getattr(self, "_pareto_cleanup_pending", False):
            self._pareto_cleanup_pending = False
            QTimer.singleShot(250, lambda: self._cleanup_thin_layers_and_reoptimize(source="pareto"))

    def _clear_pareto(self) -> None:
        self.pareto_history = {}
        self._refresh_pareto_table()

    def _refresh_pareto_table(self) -> None:
        if getattr(self, "pareto_table", None) is None:
            return
        self.pareto_table.setRowCount(0)
        for d, N in enumerate(sorted(self.pareto_history.keys())):
            self.pareto_table.insertRow(d)
            rec = self.pareto_history[N]
            self._populate_pareto_table_row(d, N, rec)

    def _populate_pareto_table_row(self, row_index: int, n_layers: int, rec: dict) -> None:
        i_layers = QTableWidgetItem(str(n_layers))
        i_layers.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        best_cost = rec.get("best_cost", float("inf"))
        i_cost = QTableWidgetItem(f"{best_cost:.5f}")
        i_cost.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        dmin_r = rec.get("dmin_rmse", 0.0)
        i_dmin_r = QTableWidgetItem(f"{dmin_r:.1f}")
        i_dmin_r.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if dmin_r < 5.0:
            i_dmin_r.setForeground(Qt.GlobalColor.red)

        best_mc = rec.get("best_mc", float("inf"))
        i_mc = QTableWidgetItem(f"{best_mc:.5f}")
        i_mc.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        dmin_m = rec.get("dmin_mc", 0.0)
        i_dmin_m = QTableWidgetItem(f"{dmin_m:.1f}")
        i_dmin_m.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if dmin_m < 5.0:
            i_dmin_m.setForeground(Qt.GlobalColor.red)

        best_fab = rec.get("best_fab", float("inf"))
        i_fab = QTableWidgetItem(f"{best_fab:.5f}" if best_fab < float("inf") else "-")
        i_fab.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if best_fab < float("inf"):
            i_fab.setForeground(Qt.GlobalColor.darkGreen)
        else:
            i_fab.setForeground(Qt.GlobalColor.gray)

        dmin_f = rec.get("dmin_fab", 0.0)
        i_dmin_f = QTableWidgetItem(f"{dmin_f:.1f}" if dmin_f > 0 else "-")
        i_dmin_f.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if dmin_f >= 5.0:
            i_dmin_f.setForeground(Qt.GlobalColor.darkGreen)
        else:
            i_dmin_f.setForeground(Qt.GlobalColor.gray)

        cost_per_n = best_cost / n_layers if n_layers > 0 and best_cost < float("inf") else float("inf")
        i_eff = QTableWidgetItem(f"{cost_per_n * 1000:.4f}" if cost_per_n < float("inf") else "-")
        i_eff.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        self.pareto_table.setItem(row_index, 0, i_layers)
        self.pareto_table.setItem(row_index, 1, i_cost)
        self.pareto_table.setItem(row_index, 2, i_dmin_r)
        self.pareto_table.setItem(row_index, 3, i_mc)
        self.pareto_table.setItem(row_index, 4, i_dmin_m)
        self.pareto_table.setItem(row_index, 5, i_fab)
        self.pareto_table.setItem(row_index, 6, i_dmin_f)
        self.pareto_table.setItem(row_index, 7, i_eff)

    def _update_pareto_record(self, emp_factors: list[float] | None = None, cost_val: float | None = None) -> None:
        """Records current configuration in Pareto history if better."""
        if emp_factors is None:
            emp_factors = []
            layer_types = []
            for r in range(self.table_layers.rowCount()):
                qwot_item = self.table_layers.item(r, 1)
                if qwot_item is not None:
                    emp_factors.append(self._safe_float_from_item(qwot_item, 0.0))
                    layer_types.append(0 if self._normalize_layer_material(r) == "H" else 1)
        else:
            # layer_types says which layer is high-index and which is low. This
            # used to answer both failures with [i % 2 ...] - a perfectly
            # alternating H/L stack that does not exist - and the cost computed
            # from it was then stored in pareto_history and displayed beside the
            # real points, with nothing marking it apart. Measured 2026-09-04:
            # four thicknesses against two materials produced a record carrying
            # type_rmse [0, 1, 0, 1] and dmin 53.19 nm, all of it invented.
            # Refusing the point is an outcome this function already has.
            try:
                params = self._get_params()
                layer_types = list(params.layer_types)
            except (AttributeError, RuntimeError, TypeError, ValueError):
                logging.getLogger("CERTUS").warning(
                    "Pareto point skipped: the stack materials could not be read", exc_info=True
                )
                return
            if len(layer_types) != len(emp_factors):
                logging.getLogger("CERTUS").warning(
                    "Pareto point skipped: %d thicknesses for %d materials",
                    len(emp_factors),
                    len(layer_types),
                )
                return

        if not emp_factors:
            return

        if cost_val is None:
            cost_val = self._compute_cost(emp_factors, layer_types)

        if not np.isfinite(cost_val) or cost_val < 0.0 or cost_val > 1e10:
            return

        N = len(emp_factors)

        try:
            params = self._get_params()
            _, ep_physical = get_layer_properties_from_list(
                params.n1_rs[0], params.n2_rs[0], emp_factors, layer_types, params.l0
            )
            dmin = float(np.min(ep_physical)) if len(ep_physical) > 0 else 0.0
        except (AttributeError, IndexError, RuntimeError, TypeError, ValueError):
            # 0.0 is honest here - the table renders a non-positive dmin as "-",
            # so nothing invented reaches the operator. What was wrong is that a
            # bare `except Exception` swallowed the reason in silence.
            logging.getLogger("CERTUS").warning(
                "Pareto point recorded without a minimum thickness", exc_info=True
            )
            dmin = 0.0
            ep_physical = np.array([])

        mc_cost = cost_val
        rng = np.random.default_rng(42)
        evals = []
        for _ in range(5):
            noise = rng.normal(0, 0.02, size=len(emp_factors))
            noisy_emp = np.maximum(np.array(emp_factors) + noise, 0.01).tolist()
            try:
                c = self._compute_cost(noisy_emp, layer_types)
                if c is not None and np.isfinite(c) and c < 1e20:
                    evals.append(c)
            except Exception:
                pass
        if evals:
            mc_cost = float(np.mean(evals))

        rec = self.pareto_history.setdefault(
            N,
            {
                "best_cost": float("inf"),
                "emp_rmse": None,
                "type_rmse": None,
                "dmin_rmse": 0.0,
                
                "best_mc": float("inf"),
                "emp_mc": None,
                "type_mc": None,
                "dmin_mc": 0.0,
                
                "best_fab": float("inf"),
                "emp_fab": None,
                "type_fab": None,
                "dmin_fab": 0.0,
            }
        )

        updated = False

        if cost_val < rec["best_cost"] - 1e-6:
            rec["best_cost"] = cost_val
            rec["emp_rmse"] = list(emp_factors)
            rec["type_rmse"] = list(layer_types)
            rec["dmin_rmse"] = dmin
            updated = True

        if mc_cost < rec["best_mc"] - 1e-6:
            rec["best_mc"] = mc_cost
            rec["emp_mc"] = list(emp_factors)
            rec["type_mc"] = list(layer_types)
            rec["dmin_mc"] = dmin
            updated = True

        is_fabricable = len(ep_physical) > 0 and np.all(ep_physical >= 5.0)
        if is_fabricable and cost_val < rec["best_fab"] - 1e-6:
            rec["best_fab"] = cost_val
            rec["emp_fab"] = list(emp_factors)
            rec["type_fab"] = list(layer_types)
            rec["dmin_fab"] = dmin
            updated = True

        if updated:
            self._refresh_pareto_table()

    def _load_pareto_design(self, row: int, col: int) -> None:
        try:
            N = int(self.pareto_table.item(row, 0).text())
            rec = self.pareto_history[N]

            load_mc = 3 <= col <= 4
            load_fab = 5 <= col <= 6

            if load_fab and rec.get("emp_fab") is not None:
                self._restore_pareto_champion(rec["emp_fab"], rec["type_fab"])
                self.logger.info(f"Loaded FAB champion for N={N} (Cost={rec['best_fab']:.6f})")
                QTimer.singleShot(300, lambda: self._cleanup_thin_layers_and_reoptimize(source="pareto"))
            elif load_mc and rec.get("emp_mc") is not None:
                self._restore_pareto_champion(rec["emp_mc"], rec["type_mc"])
                self.logger.info(f"Loaded MC champion for N={N} (Cost={rec['best_mc']:.6f})")
                QTimer.singleShot(300, lambda: self._cleanup_thin_layers_and_reoptimize(source="pareto"))
            elif rec.get("emp_rmse") is not None:
                self._restore_pareto_champion(rec["emp_rmse"], rec["type_rmse"])
                self.logger.info(f"Loaded Cost champion for N={N} (Cost={rec['best_cost']:.6f})")
                QTimer.singleShot(300, lambda: self._cleanup_thin_layers_and_reoptimize(source="pareto"))
        except Exception as e:
            self.logger.error(f"Failed to load Pareto design: {e}")

    def _restore_pareto_champion(self, emp_factors: list[float], layer_types: list[int]) -> None:
        """Restore a Pareto champion into the layer table and trigger a fresh calculation."""
        self._skip_auto_calc = True
        self._is_updating_table = True
        try:
            FieldStackService.load_stack(self.table_layers, emp_factors, layer_types)
        finally:
            self._is_updating_table = False

        self._update_thicknesses()

        def _run_calc():
            self._skip_auto_calc = False
            self.on_calc_clicked()

        QTimer.singleShot(200, _run_calc)
