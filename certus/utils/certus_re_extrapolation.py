"""Tell the user when a tabulated index is asked outside its table (the edge value is held constant)."""

import logging

import numpy as np


def warn_once_if_extrapolating(material: object, table_wls: np.ndarray, wls: np.ndarray) -> None:
    """Log one warning per material the first time ``wls`` leaves ``table_wls``."""
    if getattr(material, "_warned_extrapolation", False) or not wls.size:
        return
    lo, hi = float(table_wls.min()), float(table_wls.max())
    if wls.min() < lo or wls.max() > hi:
        material._warned_extrapolation = True  # type: ignore[attr-defined]
        logging.getLogger("CERTUS").warning(
            "Tabulated index covers %.1f-%.1f nm; %.1f-%.1f nm requested: the edge values are held constant",
            lo, hi, float(wls.min()), float(wls.max()),
        )
