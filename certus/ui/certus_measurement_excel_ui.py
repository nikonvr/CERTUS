#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Loading interactif Excel  mesures spectrales  (feuille type measurement).

Partage par Curve Smoother, Substrate Index, etc.
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
    Choisit la feuille a load : unique, ou nom contenant  measurement ,
    sinon box de dialogue.
    Retourne None si lutilisateur cancelled la selection.
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
    Lit le classeur *path* ; retourne le DataFrame de la feuille retenue,
    ou None si choix de feuille cancelled.
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
    Dialogue file + lecture feuille mesure.

    Retourne ``(df, path, dir_path)`` ou ``None`` si annulation (file ou feuille).
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
