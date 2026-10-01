"""The front stack of a CERTUS window: its layer rows, the add / delete / merge / clean-up actions and the QWOT <-> thickness conversions (moved out of certus_base_app.py, S5.3)."""

import logging
from typing import Any

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QCheckBox, QDoubleSpinBox, QHBoxLayout, QTableWidget, QTableWidgetItem, QWidget

from certus.core.certus_core import CFG, NUMERICAL_FAULT_EXCEPTIONS
from certus_physics import init_thickness
from certus_physics.structures import Layer


class CertusAppFrontStackMixin:
    """The front stack of a CERTUS window: its layer rows, the add / delete / merge / clean-up actions and the QWOT <-> thickness conversions (moved out of certus_base_app.py, S5.3)."""

    def _create_spin(
        self,
        val: float,
        dec: int = 4,
        step: float = 0.01,
        minv: float = 0.0,
        maxv: float = 100.0,
    ) -> QDoubleSpinBox:
        """Creates a QDoubleSpinBox with the given parameters."""

        sb = QDoubleSpinBox()

        sb.setRange(minv, maxv)

        sb.setDecimals(dec)

        sb.setSingleStep(step)

        sb.setValue(val)

        _orig_st = sb.setToolTip
        sb.setToolTip = lambda t: (_orig_st(t), sb.lineEdit().setToolTip(t) if sb.lineEdit() else None)  # type: ignore[assignment]

        return sb

    def _add_front_row(self, mat: str, qwot: float, var: bool, del_checked: bool = False) -> None:
        """Adds row to front layer table"""

        row = self.front_table.rowCount()

        self.front_table.insertRow(row)

        cb = self._create_combo(mat)

        cb.currentIndexChanged.connect(self._merge_adjacent_layers)

        self.front_table.setCellWidget(row, 0, cb)

        sb = self._create_spin(qwot, dec=6)
        sb.setToolTip("Layer optical thickness in QWOT (Quarter-Wave Optical Thickness).")

        def _on_front_qwot_changed(*_args) -> None:
            self._schedule_eval()

        sb.valueChanged.connect(_on_front_qwot_changed)

        self._on_qwot_changed_connection(sb)

        self.front_table.setCellWidget(row, 1, sb)

        it = QTableWidgetItem("N/A")

        it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)

        self.front_table.setItem(row, 2, it)

        # Optimization Toggle (Var)

        chk = QCheckBox()

        chk.setToolTip("Toggle optimization for this layer.")

        chk.setChecked(var)

        cw = QWidget()

        cl = QHBoxLayout(cw)

        cl.addWidget(chk)

        cl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        cl.setContentsMargins(0, 0, 0, 0)

        self.front_table.setCellWidget(row, 3, cw)

        # Delete Toggle (Del)

        del_chk = QCheckBox()

        del_chk.setToolTip("Mark this layer for removal.")

        del_chk.setChecked(del_checked)

        del_cw = QWidget()

        del_cl = QHBoxLayout(del_cw)

        del_cl.addWidget(del_chk)

        del_cl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        del_cl.setContentsMargins(0, 0, 0, 0)

        self.front_table.setCellWidget(row, 4, del_cw)

        self._update_layer_count()

    def _on_qwot_changed_connection(self, spinbox: QDoubleSpinBox) -> None:
        """Hook for extra connections on QWOT spinbox change."""

        pass

    def add_front_layer(self) -> None:
        """Adds a front layer with default H/L sequence"""

        if self.front_table.rowCount() >= CFG.MAX_LAYERS:
            return

        mat = "H"

        if self.front_table.rowCount() > 0:
            prev = self._safe_get_combo_text(self.front_table.rowCount() - 1, 0)

            if prev:
                mat = "L" if prev == "H" else "H"

        self._add_front_row(mat, 1.0, True)

        self._on_layer_added()

        self._schedule_eval()

    def _on_layer_added(self) -> None:
        """Hook for post-layer-addition actions."""

        pass

    def del_front_layer(self) -> None:
        """Removes selected front layers and heals the structure."""

        rows_to_remove = []

        # Check checkboxes first

        for row in range(self.front_table.rowCount()):
            del_cell = self.front_table.cellWidget(row, 4)

            if del_cell:
                del_chk = del_cell.findChild(QCheckBox)

                if del_chk and del_chk.isChecked():
                    rows_to_remove.append(row)

        # Fallback to current row if no checkboxes

        if not rows_to_remove:
            r = self.front_table.currentRow()

            if r < 0 and self.front_table.rowCount() > 0:
                r = self.front_table.rowCount() - 1

            if r >= 0:
                rows_to_remove = [r]

        if rows_to_remove:
            self._save_undo_state()

            for r in sorted(rows_to_remove, reverse=True):
                self.front_table.removeRow(r)

            self._update_layer_count()

            self._on_layer_deleted()

            self._schedule_eval()

    def _on_layer_deleted(self) -> None:
        """Hook for post-layer-deletion actions."""

        pass

    def _get_front_stack(self) -> list[Layer]:
        """Retrieves front stack"""

        try:
            stack = []

            for r in range(self.front_table.rowCount()):
                mat = self._safe_get_combo_text(r, 0)

                if not mat:
                    continue

                qw = self.front_table.cellWidget(r, 1).value()

                var = self.front_table.cellWidget(r, 3).findChild(QCheckBox).isChecked()

                stack.append(Layer(mat, qw, var))

            return stack

        except (AttributeError, ValueError, IndexError) as e:
            logging.debug(f"Could not get front stack: {e}")

            return []

    def _get_back_stack(self) -> list[Layer]:
        """Hook for back-face stack. RE usually doesn't have it."""

        return []

    def _merge_adjacent_layers(self, table: QTableWidget = None) -> None:
        """Merges adjacent layers of same material"""

        if table is None:
            table = getattr(self, "front_table", None)
        if table is None:
            return

        merged = False
        passes = 0

        while passes < 10:
            passes += 1
            found = False
            i = 1

            while i < table.rowCount():
                m_curr = self._safe_get_combo_text(i, 0, table)
                m_prev = self._safe_get_combo_text(i - 1, 0, table)
                if m_curr is None:
                    item_curr = table.item(i, 0)
                    m_curr = item_curr.text() if item_curr else None
                if m_prev is None:
                    item_prev = table.item(i - 1, 0)
                    m_prev = item_prev.text() if item_prev else None

                if m_curr and m_prev and m_curr == m_prev:
                    try:
                        widget_curr = table.cellWidget(i, 1)
                        if widget_curr and hasattr(widget_curr, "value"):
                            q_curr = widget_curr.value()
                        else:
                            item_curr = table.item(i, 1)
                            q_curr = float(item_curr.text()) if item_curr else 0.0

                        widget_prev = table.cellWidget(i - 1, 1)
                        if widget_prev and hasattr(widget_prev, "setValue"):
                            widget_prev.blockSignals(True)
                            widget_prev.setValue(widget_prev.value() + q_curr)
                            widget_prev.blockSignals(False)
                        else:
                            item_prev = table.item(i - 1, 1)
                            if item_prev:
                                val_prev = float(item_prev.text()) + q_curr
                                item_prev.setText(f"{val_prev:.4f}")

                        table.removeRow(i)
                        merged = True
                        found = True
                        self.log(f"Merged adjacent layers ({m_curr})", "INFO")
                        continue

                    except NUMERICAL_FAULT_EXCEPTIONS as e:
                        (self.logger.error(f"Merge error: {e}") if hasattr(self, "logger") and self.logger else None)
                    except (ValueError, AttributeError) as e:
                        logging.debug(f"Merge values error: {e}")

                i += 1

            if not found:
                break

        if hasattr(self, "front_table") and table == self.front_table:
            self._update_layer_count()
            if merged:
                self._schedule_eval()
        elif hasattr(self, "structure_changed"):
            self.structure_changed.emit()
        elif hasattr(self, "stack_panel") and hasattr(self.stack_panel, "structure_changed"):
            self.stack_panel.structure_changed.emit()

    def smart_cleanup(self, table: QTableWidget = None, update_target: bool = True) -> int:
        """
        Smart cleanup: merges identical adjacent materials and removes
        very thin layers (< 1.0 nm) which are likely artifacts.
        """
        if table is None:
            table = getattr(self, "front_table", None)
        if table is None:
            return 0

        removed_count = 0
        changed = False

        # Step 1: Remove very thin layers dynamically based on RMSE
        current_rmse = getattr(self, "_workflow_best_rmse", 1.0)
        multiplier = getattr(self, "_cleanup_threshold_multiplier", 150.0)
        threshold = max(0.05, min(1.0, current_rmse * multiplier))  # Adaptive threshold

        rows_to_remove = []
        for r in range(table.rowCount() - 1, -1, -1):
            thick_item = table.item(r, 2)
            if thick_item:
                try:
                    thickness = float(thick_item.text())
                    if thickness < threshold:
                        rows_to_remove.append(r)
                except ValueError:
                    pass

        if rows_to_remove:
            self.log(f"Smart cleanup: removing {len(rows_to_remove)} layers < {threshold:.2f} nm (adaptive)", "INFO")
            for r in rows_to_remove:
                table.removeRow(r)
            removed_count += len(rows_to_remove)
            changed = True

        # Step 2: Merge identical adjacent materials
        pre_merge_count = table.rowCount()
        self._merge_adjacent_layers(table)
        post_merge_count = table.rowCount()

        merge_diff = pre_merge_count - post_merge_count
        if merge_diff > 0:
            removed_count += merge_diff
            changed = True
            self.log(f"Smart cleanup: merged {merge_diff} adjacent layers", "INFO")

        if changed:
            if hasattr(self, "_update_layer_count") and table == getattr(self, "front_table", None):
                self._update_layer_count()
            elif hasattr(self, "structure_changed"):
                self.structure_changed.emit()
            elif hasattr(self, "stack_panel") and hasattr(self.stack_panel, "structure_changed"):
                self.stack_panel.structure_changed.emit()

        return removed_count

    def _update_layer_count(self) -> None:
        """Updates layer count display"""

        count = self.front_table.rowCount()

        self.layer_count_label.setText(f"{count} layer{'s' if count != 1 else ''}")

    def _update_thickness_display(self) -> None:
        """Updates physics thicknesses (nm) from current QWOT and l0"""

        mats = self._get_materials()

        l0 = 500.0

        if hasattr(self, "l0_spin"):
            l0 = float(self.l0_spin.value())

        elif hasattr(self, "_re_lambda_ref"):
            l0 = float(self._re_lambda_ref)

        stack = self._get_front_stack()

        if stack and mats:
            ep = init_thickness(stack, l0, mats)

            if ep is not None:
                for r, d in enumerate(ep):
                    it = self.front_table.item(r, 2)

                    if it:
                        it.setText(f"{d:.1f}")

                self.ep_current = ep

                self._on_front_thickness_updated()

        stack_b = self._get_back_stack()

        if stack_b and mats:
            ep_b = init_thickness(stack_b, l0, mats)

            if ep_b is not None:
                for r, d in enumerate(ep_b):
                    it = self.back_table.item(r, 2)

                    if it:
                        it.setText(f"{d:.1f}")

                self.ep_back_current = ep_b

    def _on_front_thickness_updated(self) -> None:
        """Hook for post-thickness-update actions."""

        pass

    def _update_qwot_from_ep(self, ep) -> None:
        """Update front-table QWOT from thicknesses (nm)."""

        self.front_table.blockSignals(True)

        ep = np.asarray(ep, dtype=float).ravel()

        for r in range(min(len(ep), self.front_table.rowCount())):
            mat_name = self._safe_get_combo_text(r, 0)

            qw_val = self._ep_nm_to_qwot(ep[r], mat_name)

            sb = self.front_table.cellWidget(r, 1)

            if sb:
                sb.setValue(qw_val)

        self.front_table.blockSignals(False)

    def _ep_nm_to_qwot(self, thickness_nm: float, mat_name: str) -> float:
        """Physical thickness (nm) -> QWOT at current lambda₀ (l0_spin or RE lambda_ref)."""

        mats = self._get_materials()

        l0 = 500.0

        if hasattr(self, "l0_spin"):
            l0 = float(self.l0_spin.value())

        elif hasattr(self, "_re_lambda_ref"):
            l0 = float(self._re_lambda_ref)

        n_val = 1.45

        if mat_name:
            m_obj = mats.get(mat_name)

            if m_obj:
                if hasattr(m_obj, "n4"):
                    n_val = m_obj.n4

                elif isinstance(m_obj, dict):
                    n_val = m_obj.get("n4", 1.45)

        return (4.0 * n_val * float(thickness_nm)) / l0 if abs(l0) > 1e-9 else 0.0

    def reset_qwot(self) -> None:
        """Resets all QWOTs to 1.0"""

        if not hasattr(self, "front_table"):
            return

        for r in range(self.front_table.rowCount()):
            widget = self.front_table.cellWidget(r, 1)

            if widget:
                widget.setValue(1.0)

        self._schedule_eval(True)

    def _create_combo(self, current: str) -> Any:
        """Creates material combo box"""

        from PyQt6.QtWidgets import QComboBox

        from certus.core.certus_core import CFG

        cb = QComboBox()

        cb.setToolTip("Select material.")

        materials = [m for m in CFG.MATERIALS if m != "Substrate" and m != "substrate"]

        cb.addItems(materials)

        if current in materials:
            cb.setCurrentText(current)

        return cb

    def _safe_get_combo_text(self, row: int, col: int, table: QTableWidget = None) -> str | None:
        """Safely gets combo text"""

        if table is None:
            table = self.front_table

        try:
            widget = table.cellWidget(row, col)

            if widget is None:
                return None

            return widget.currentText()

        except (AttributeError, RuntimeError) as e:
            logging.debug(f"Could not get combo value: {e}")

            return None
