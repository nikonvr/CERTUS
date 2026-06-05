from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QDoubleSpinBox, QTableWidget, QTableWidgetItem

from certus.workers.certus_field_workers_dto import FieldParamsDTO


@dataclass(frozen=True)
class FieldPlotData:
    z_coords: list[float]
    E2_values_list: list[list[float]]
    lambda_calcs: list[float]
    ep_c1_cn: list[float]

    @classmethod
    def from_any(cls, value) -> "FieldPlotData":
        if isinstance(value, dict):
            return cls(
                z_coords=list(value.get("z_coords", []) or []),
                E2_values_list=[list(values) for values in (value.get("E2_values_list", []) or [])],
                lambda_calcs=list(value.get("lambda_calcs", []) or []),
                ep_c1_cn=list(value.get("ep_c1_cn", []) or []),
            )
        return cls(
            z_coords=list(getattr(value, "z_coords", []) or []),
            E2_values_list=[list(values) for values in (getattr(value, "E2_values_list", []) or [])],
            lambda_calcs=list(getattr(value, "lambda_calcs", []) or []),
            ep_c1_cn=list(getattr(value, "ep_c1_cn", []) or []),
        )

    def to_dict(self) -> dict:
        return {
            "z_coords": list(self.z_coords),
            "E2_values_list": [list(values) for values in self.E2_values_list],
            "lambda_calcs": list(self.lambda_calcs),
            "ep_c1_cn": list(self.ep_c1_cn),
        }


class FieldStackService:
    @staticmethod
    def load_stack(table: QTableWidget, emp_factors: list[float], layer_types: list[int] | None = None) -> None:
        table.setColumnCount(3)
        table.setRowCount(0)
        for i, value in enumerate(emp_factors):
            table.insertRow(i)
            if layer_types and i < len(layer_types):
                material = "H" if int(layer_types[i]) == 0 else "L"
            else:
                material = "H" if i % 2 == 0 else "L"

            item_mat = QTableWidgetItem(material)
            item_mat.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_qwot = QTableWidgetItem(f"{float(value):.4f}")
            item_qwot.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_thick = QTableWidgetItem("0.0")
            item_thick.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            table.setItem(i, 0, item_mat)
            table.setItem(i, 1, item_qwot)
            table.setItem(i, 2, item_thick)

    @staticmethod
    def normalize_layer_types(layer_types: list[int] | None, n_layers: int) -> list[int]:
        if layer_types is None or len(layer_types) != n_layers:
            return [i % 2 for i in range(n_layers)]
        return [0 if int(value) == 0 else 1 for value in layer_types]

    @staticmethod
    def calculate_thickness_nm(qwot: float, n: float, l0: float) -> float:
        if n > 0 and l0 > 0:
            return (qwot * l0) / (4.0 * n)
        return 0.0

    @staticmethod
    def calculate_qwot(thickness_nm: float, n: float, l0: float) -> float:
        if n > 0 and l0 > 0:
            return (thickness_nm * 4.0 * n) / l0
        return 0.0


class FieldExportService:
    @staticmethod
    def build_plot_data(result) -> dict:
        return {
            "z_coords": list(getattr(result, "z_coords", []) or []),
            "E2_values_list": [list(values) for values in (getattr(result, "E2_values_list", []) or [])],
            "lambda_calcs": list(getattr(result, "lambda_calcs", []) or []),
            "ep_c1_cn": list(getattr(result, "ep_c1_cn", []) or []),
        }

    @staticmethod
    def build_summary_frame(
        params: FieldParamsDTO,
        combo_mat_H: QComboBox,
        combo_mat_L: QComboBox,
        combo_mat_Sub: QComboBox,
        combo_mat_Sup: QComboBox,
        edit_angle: QDoubleSpinBox,
        combo_pol: QComboBox,
    ) -> pd.DataFrame:
        lambda_calcs_str = ", ".join(f"{value:g}" for value in (params.lambda_calcs or []))
        return pd.DataFrame(
            {
                "Parameter": [
                    "Material H",
                    "Material L",
                    "Substrate",
                    "Superstrate",
                    "λ0 (nm)",
                    "Evaluation λ (nm)",
                    "Angle (deg)",
                    "Polarization",
                ],
                "Value": [
                    combo_mat_H.currentText(),
                    combo_mat_L.currentText(),
                    combo_mat_Sub.currentText(),
                    combo_mat_Sup.currentText(),
                    params.l0,
                    lambda_calcs_str,
                    edit_angle.value(),
                    combo_pol.currentText(),
                ],
            }
        )

    @staticmethod
    def build_plot_export_frames(plot_data: FieldPlotData | dict) -> dict[str, pd.DataFrame]:
        if isinstance(plot_data, FieldPlotData):
            plot_data = plot_data.to_dict()
        z_coords = plot_data.get("z_coords") or []
        e2_values_list = plot_data.get("E2_values_list") or []
        lambda_calcs = plot_data.get("lambda_calcs") or []

        frames: dict[str, pd.DataFrame] = {}
        for idx, e2_values in enumerate(e2_values_list):
            wavelength = lambda_calcs[idx] if idx < len(lambda_calcs) else idx + 1
            frames[f"Field_{idx + 1}"] = pd.DataFrame(
                {
                    "z (nm)": z_coords,
                    "|E|^2": e2_values,
                    "lambda_calc_nm": [wavelength] * len(z_coords),
                }
            )
        return frames
