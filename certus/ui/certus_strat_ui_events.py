from __future__ import annotations
from certus.ui.certus_strat_common import *

class CertusStratEventsMixin:
    def _init_global_shortcuts(self) -> None:
        """Global UX Hotkeys (Pro 2026 Theme)."""

        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.save_configuration)

        QShortcut(QKeySequence("Ctrl+O"), self).activated.connect(self.load_configuration)

        run_opti = QShortcut(QKeySequence("F5"), self)

        run_opti.activated.connect(lambda: self.run_workflow(2) if self.run_step2_btn.isEnabled() else None)

        run_opti_alt = QShortcut(QKeySequence("Ctrl+R"), self)

        run_opti_alt.activated.connect(lambda: self.run_workflow(2) if self.run_step2_btn.isEnabled() else None)

        QShortcut(QKeySequence("Esc"), self).activated.connect(self.close_all_auxiliary_windows)

        install_standard_shortcuts(
            self,
            help=lambda: open_documentation("CERTUS_STRAT"),
            toggle_logs=lambda: self.toggle_details_btn.setChecked(not self.toggle_details_btn.isChecked()),
            zoom_in=getattr(self, "zoom_in_ui", None),
            zoom_out=getattr(self, "zoom_out_ui", None),
            reset_zoom=getattr(self, "reset_ui_zoom", None),
        )

        def _on_config_drop(paths) -> None:
            if paths and hasattr(self, "load_configuration"):
                self.load_configuration(paths[0])
                show_toast(self, f"Loaded: {Path(paths[0]).name}", "success")

        enable_file_drop(self, _on_config_drop, extensions=("json",))

    def timerEvent(self, event) -> None:
        log_timer_id = getattr(self, "_log_timer_id", -1)
        plot_timer_id = getattr(self, "plot_timer", -1)

        if event.timerId() == log_timer_id:
            self._process_log_queue()

        elif event.timerId() == plot_timer_id:
            self.process_plot_queue()

        else:
            super().timerEvent(event)

    def on_toggle_details(self, checked) -> None:

        self.log_text.setVisible(checked)

        self.toggle_details_btn.setText("Hide Details" if checked else "Show Details")

    def close_all_auxiliary_windows(self) -> None:

        self.logger.debug(
            "[STRAT-UI] Closing all auxiliary windows (plot=%d, transmission=%d, json=%d, spectrum=%d, table=%s, live=%s, heatmap=%s, stack=%s, worker_threads=%d)",
            len(getattr(self, "plot_windows", [])),
            len(getattr(self, "transmission_windows", [])),
            len(getattr(self, "json_windows", [])),
            len(getattr(self, "interactive_spectrum_windows", [])),
            bool(getattr(self, "strategies_table_window", None)),
            bool(getattr(self, "live_monitor_window", None)),
            bool(getattr(self, "heatmap_window", None)),
            bool(getattr(self, "stack_visual_window", None)),
            len(getattr(self, "_active_worker_threads", [])),
        )

        lists_to_close = [
            self.plot_windows,
            self.transmission_windows,
            self.json_windows,
            getattr(self, "interactive_spectrum_windows", []),
        ]

        for win_list in lists_to_close:
            for win in win_list[:]:
                try:
                    win.close()

                except (RuntimeError, AttributeError):
                    # Window may already be closed or destroyed

                    pass

            del win_list[:]

        for attr_name in [
            "strategies_table_window",
            "live_monitor_window",
            "heatmap_window",
            "stack_visual_window",
            "_floating_stack_window",
        ]:
            win = getattr(self, attr_name, None)

            if win:
                try:
                    win.close()
                except (RuntimeError, AttributeError):
                    pass

    def copy_logs_to_clipboard(self) -> None:
        """Copy logs to clipboard (delegates to certus_ui.copy_app_logs_to_clipboard)."""

        if copy_app_logs_to_clipboard(self) and hasattr(self, "status_label"):
            self.status_label.setText(CERTUS_UI_STRINGS["logs_copied"])

    def _update_zoom_label(self, factor: float) -> None:
        if hasattr(self, "zoom_label"):
            self.zoom_label.setText(f"Zoom {int(round(factor * 100))}%")

    def _apply_ui_zoom(self, factor: float) -> None:
        apply_app_zoom(
            self,
            factor,
            label_attr="zoom_label",
            stylesheet_fn=None,
            toast_fn=show_toast,
            base_font_size=getattr(CertusTheme, "FONT_SIZE_BASE", 10),
        )

    def detach_stack_window(self) -> None:

        if self._floating_stack_window is not None:
            return

        self.detach_btn.setVisible(False)

        table = self.widgets["stack_table"]

        table.setMinimumWidth(0)

        table.setMaximumWidth(16777215)

        table.setMinimumHeight(0)

        table.setMaximumHeight(16777215)

        table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._floating_stack_window = PopOutWindow(self.stack_group, self, "Stack Definition Manager")

        self._floating_stack_window.resize(600, 800)

        self._floating_stack_window.closed_signal.connect(self.reattach_stack_window)

        self._floating_stack_window.show()

    def reattach_stack_window(self) -> None:

        count = self.design_layout.count()

        self.design_layout.insertWidget(count - 1, self.stack_group)

        table = self.widgets["stack_table"]

        table.setMinimumHeight(115)

        table.setMaximumHeight(150)

        table.setFixedWidth(230)

        table.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.detach_btn.setVisible(True)

        self._floating_stack_window = None

    def _on_material_mode_changed(self, prefix, label) -> None:
        """Enable/disable widgets based on Custom vs Dispersive selection."""

        is_custom = self.widgets[f"{prefix}_type_custom"].isChecked()

        self.widgets[f"n{label}_r"].setEnabled(is_custom)

        self.widgets[f"{prefix}_material_file"].setEnabled(not is_custom)

    def _on_substrate_choice_changed(self, text) -> None:
        """Enable custom index field only when 'Custom' substrate is selected."""

        is_custom = text == "Custom"

        self.widgets["nSub_custom"].setEnabled(is_custom)

    def _init_undo_shortcut(self) -> None:
        """Initializes the UNDO shortcut after the interface is ready"""

        try:
            undo_shortcut = QShortcut(QKeySequence("Ctrl+Z"), self)

            undo_shortcut.activated.connect(self._undo_stack_table)

        except (RuntimeError, TypeError, AttributeError) as e:
            self.logger.warning(f"Could not initialize UNDO shortcut: {e}")

    def _on_stack_table_changed(self, row, col) -> None:
        """Callback called when a cell in stack_table is modified"""

        # Save state only if it is the Multiplier column (col 2)

        if col == 2:
            self._save_undo_state()

    def add_layer(self) -> None:

        self._save_undo_state()

        table = self.widgets["stack_table"]

        row = table.rowCount()

        table.insertRow(row)

        item_num = QTableWidgetItem(str(row + 1))

        item_num.setFlags(item_num.flags() & ~Qt.ItemFlag.ItemIsEditable)

        table.setItem(row, 0, item_num)

        type_str = "H" if row % 2 == 0 else "L"

        item_type = QTableWidgetItem(type_str)

        item_type.setFlags(item_type.flags() & ~Qt.ItemFlag.ItemIsEditable)

        table.setItem(row, 1, item_type)

        table.setItem(row, 2, QTableWidgetItem("1.0"))

    def remove_layer(self) -> None:

        table = self.widgets["stack_table"]

        if table.rowCount() > 0:
            self._save_undo_state()

            table.removeRow(table.rowCount() - 1)

    def closeEvent(self, event) -> None:

        try:
            # Stop all running computation/render threads in parallel to avoid sequential timeouts on exit
            self._stop_all_threads_parallel(timeout_ms=10000)

            if getattr(self, "_log_timer_id", None) is not None:
                self.killTimer(self._log_timer_id)

            if getattr(self, "plot_timer", None) is not None:
                self.killTimer(self.plot_timer)

            self.close_all_auxiliary_windows()

            if hasattr(self, "materials_db"):
                self.materials_db.clear_cache()

            self.logger.info("Application closed.")

        except (RuntimeError, AttributeError):
            logging.getLogger("CERTUS").debug("Silenced exception in %s", __name__, exc_info=True)

        finally:
            event.accept()

