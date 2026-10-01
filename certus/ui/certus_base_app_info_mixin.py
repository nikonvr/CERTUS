"""The substrate and stack information line of a CERTUS window (moved out of certus_base_app.py, S5.3)."""

import numpy as np

from certus.core.certus_core import NUMERICAL_FAULT_EXCEPTIONS


class CertusAppStackInfoMixin:
    """The substrate and stack information line of a CERTUS window (moved out of certus_base_app.py, S5.3)."""

    def _get_substrate_info_display(self) -> tuple[str, str]:
        """Hook for subclasses to provide substrate type and index display string."""

        return "N/A", "N/A"

    def _stack_info_front_table_cols(self) -> tuple[int, int]:
        """Columns (Mat combo, QWOT spin) for reading layer table in Stack Info."""

        return (0, 1)

    def _stack_info_l0_nm(self) -> float:
        """lambda₀ (nm) for n@lambda₀ in Stack Info."""

        if hasattr(self, "l0_spin"):
            return float(self.l0_spin.value())

        if hasattr(self, "_re_lambda_ref"):
            return float(self._re_lambda_ref)

        return 500.0

    def _stack_info_n_re_at_l0(self, mat_name: str, l0: float) -> float | None:
        """Re(n) at lambda₀ for a layer; None if unknown."""

        if not mat_name or not hasattr(self, "_get_materials"):
            return None

        mats = self._get_materials()

        if not mats or mat_name not in mats:
            return None

        try:
            wls = np.array([float(l0)], dtype=np.float64)

            nk = mats[mat_name].get_nk(wls)

            return float(np.real(np.asarray(nk, dtype=np.complex128).ravel()[0]))

        except NUMERICAL_FAULT_EXCEPTIONS:
            m = mats[mat_name]

            n4 = getattr(m, "n4", None)

            return float(n4) if n4 is not None else None

    def _stack_info_format_layer_line(self, idx1: int, mat_str: str, qwot: float, l0: float) -> str:
        """A 'Layer k: ...' line with Re(n)@lambda₀ formatted to 3 decimals."""

        nr = self._stack_info_n_re_at_l0(mat_str, l0)

        n_s = f"{nr:.3f}" if nr is not None and np.isfinite(nr) else ""

        return f"Layer {idx1}: {mat_str}  n@lambda₀={n_s}  {float(qwot):.4f} QWOT\n"

    def _update_substrate_info(self) -> None:
        """Update stack information window with current/best design (layers in QWOT)."""

        if not getattr(self, "substrate_info_window", None) or not self.substrate_info_window.isVisible():
            return

        substrate_type, substrate_index = self._get_substrate_info_display()

        self.substrate_type_label.setText(substrate_type)

        self.substrate_index_label.setText(substrate_index)

        structure_text = "\n=== DESIGN STRUCTURE ===\n\n"

        best_ep = getattr(self, "_stack_info_best_ep", None)

        l0 = self._stack_info_l0_nm()

        if best_ep is not None and hasattr(self, "_get_front_stack") and hasattr(self, "_get_materials"):
            stack = self._get_front_stack()

            mats = self._get_materials()

            ep = np.asarray(best_ep).flatten()

            n_layers = min(len(stack), len(ep))

            structure_text += f"Total layers: {n_layers} (best so far)\n\n"

            for i in range(n_layers):
                mat_str = getattr(stack[i], "mat", "?")

                d_nm = float(ep[i]) if i < len(ep) else 0.0

                n_val = 1.5

                if mats and stack[i].mat in mats:
                    m = mats[stack[i].mat]

                    n_val = float(getattr(m, "n4", 1.5))

                qwot = (4.0 * n_val * d_nm) / l0 if abs(l0) > 1e-9 else 0.0

                structure_text += self._stack_info_format_layer_line(i + 1, str(mat_str), qwot, l0)

        elif hasattr(self, "front_table"):
            n_layers = self.front_table.rowCount()

            structure_text += f"Total layers: {n_layers}\n\n"

            c_mat, c_qw = self._stack_info_front_table_cols()

            for r in range(n_layers):
                mat_str = "?"

                qwot_f = float("nan")

                cb = self.front_table.cellWidget(r, c_mat)

                if cb and hasattr(cb, "currentText"):
                    mat_str = cb.currentText()

                sb = self.front_table.cellWidget(r, c_qw)

                if sb and hasattr(sb, "value"):
                    try:
                        qwot_f = float(sb.value())

                    except TypeError, ValueError:
                        qwot_f = float("nan")

                if np.isfinite(qwot_f):
                    structure_text += self._stack_info_format_layer_line(r + 1, mat_str, qwot_f, l0)

                else:
                    nr = self._stack_info_n_re_at_l0(mat_str, l0)

                    n_s = f"{nr:.3f}" if nr is not None and np.isfinite(nr) else ""

                    structure_text += f"Layer {r + 1}: {mat_str}  n@lambda₀={n_s}  ? QWOT\n"

        structure_text += f"\n=== SUBSTRATE ===\n\nType: {substrate_type}\nIndex: {substrate_index}\n"

        structure_text += f"\nReference lambda₀: {l0} nm\n"

        best_rmse = getattr(self, "_stack_info_best_rmse", None) or getattr(self, "_workflow_best_rmse", None)

        if best_rmse is not None and np.isfinite(best_rmse):
            structure_text += f"\n=== OPTIMIZATION ===\n\nBest RMSE: {best_rmse:.6f}\n"

        self.structure_text.setText(structure_text)
