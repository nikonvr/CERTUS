#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Interactive Excel loading of spectral measurements (measurement type sheet).

Shared by Curve Smoother, Substrate Index, etc.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from PyQt6.QtWidgets import QFileDialog, QInputDialog


def pick_measurement_sheet_name(
    sheet_names: list[str],
    parent,
) -> str | None:
    """
    Selects the sheet to load: unique, or name containing "measurement",
    otherwise a dialog box.
    Returns None if the user cancelled the selection.
    """
    if not sheet_names:
        return None
    if len(sheet_names) == 1:
        return sheet_names[0]
    target = next((sn for sn in sheet_names if "measurement" in sn.lower()), None)
    if target:
        return target
    sheet, ok = QInputDialog.getItem(
        parent,
        "Tab selection",
        "Choose sheet containing spectra:",
        sheet_names,
        0,
        False,
    )
    if not ok or not sheet:
        return None
    return str(sheet)


def read_measurement_excel(
    path: str,
    parent,
    *,
    round_wavelength_decimals: int | None = None,
) -> pd.DataFrame | None:
    """
    Reads the workbook *path*; returns the DataFrame of the selected sheet,
    or None if sheet selection is cancelled.
    """
    xl = pd.ExcelFile(path)
    sheet = pick_measurement_sheet_name(list(xl.sheet_names), parent)
    if sheet is None:
        return None
    df = pd.read_excel(xl, sheet_name=sheet)
    if round_wavelength_decimals is not None:
        x_col = df.columns[0]
        df[x_col] = np.round(
            np.asarray(df[x_col].values, dtype=np.float64),
            round_wavelength_decimals,
        )
    return df


def open_measurement_excel_interactive(
    parent,
    *,
    start_dir: str,
    caption: str = "Open Data",
    round_wavelength_decimals: int | None = None,
) -> tuple[pd.DataFrame, str, str] | None:
    """
    File dialog + measurement sheet reading.

    Returns ``(df, path, dir_path)`` or ``None`` if cancelled (file or sheet).
    """
    path, _ = QFileDialog.getOpenFileName(
        parent,
        caption,
        start_dir,
        "Excel Files (*.xlsx *.xls)",
    )
    if not path:
        return None
    df = read_measurement_excel(
        path,
        parent,
        round_wavelength_decimals=round_wavelength_decimals,
    )
    if df is None:
        return None
    return df, path, str(Path(path).parent)
