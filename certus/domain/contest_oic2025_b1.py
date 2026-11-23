"""Score of Problem B.1 of the OIC 2025 design contest: an immersed three-line polarizing notch filter.

Kruschwitz, Trubetskov and Keck, Appl. Opt. 65(5), A12-A21 (2026), Eq. (2). The coating sits on the hypotenuse
of a cube of index 1.80 and is lit at 45 degrees inside the cube; it must reflect s-polarized light at 450, 550
and 650 nm and transmit the rest from 400 to 700 nm. With Ts, Tp, Rs the coefficients of the coating alone:

    MF = (500 / 3) * sum over the three lines of Ts / Tp
         + #{grid points with Rs >= 99 %} / #{grid points with Ts >= 99 %},

on 3001 wavelengths from 400 to 700 nm every 0.1 nm (H(x) = 1 for x >= 0). Constraints: at most 100 layers, at most
20 um of physical thickness, no limit on the thickness of a layer; materials H 2.25, T 2.15, F 2.00, A 1.65,
L 1.45, M 1.38.

This module scores spectra; it computes none (`certus.domain` does not import `certus.physics`). The spectra
come from the oblique kernels of CERTUS through `certus.domain.immersion.to_air_equivalent`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

INCIDENT_INDEX = 1.80
ANGLE_DEG = 45.0
LINES_NM: tuple[float, float, float] = (450.0, 550.0, 650.0)
THRESHOLD = 0.99
MAX_LAYERS = 100
MAX_PHYSICAL_THICKNESS_NM = 20000.0
MATERIALS: dict[str, float] = {"H": 2.25, "T": 2.15, "F": 2.00, "A": 1.65, "L": 1.45, "M": 1.38}
GRID_POINTS = 3001


def contest_grid() -> np.ndarray:
    """The 3001 wavelengths of the score, 400 to 700 nm every 0.1 nm."""
    return np.round(np.linspace(400.0, 700.0, GRID_POINTS), 4)


@dataclass(frozen=True)
class B1Score:
    """The contest score and its parts."""

    total: float
    contrast_term: float
    heaviside_term: float
    n_rs_at_least_99: int
    n_ts_at_least_99: int
    contrast_at_lines: tuple[float, float, float]


def b1_score(
    rs_grid: np.ndarray,
    ts_grid: np.ndarray,
    ts_lines: np.ndarray,
    tp_lines: np.ndarray,
) -> B1Score:
    """Score Eq. (2) from the s-polarized R and T on the contest grid and the s and p T at the three lines.

    Args:
        rs_grid: Rs on `contest_grid()`, fractions (not percent).
        ts_grid: Ts on the same grid.
        ts_lines: Ts at 450, 550 and 650 nm.
        tp_lines: Tp at the same wavelengths.

    Returns:
        The score; `total` is infinite when no grid point has Ts >= 99 % or a line has Tp = 0.
    """
    rs = np.asarray(rs_grid, dtype=np.float64)
    ts = np.asarray(ts_grid, dtype=np.float64)
    ts_l = np.asarray(ts_lines, dtype=np.float64)
    tp_l = np.asarray(tp_lines, dtype=np.float64)
    if rs.shape != (GRID_POINTS,) or ts.shape != (GRID_POINTS,):
        raise ValueError(f"Rs and Ts must be given on the {GRID_POINTS} contest wavelengths")
    if ts_l.shape != (len(LINES_NM),) or tp_l.shape != (len(LINES_NM),):
        raise ValueError("Ts and Tp must be given at the three lines")
    # A NaN fails every comparison and would drop out of both counts unseen.
    if not (np.all(np.isfinite(rs)) and np.all(np.isfinite(ts)) and np.all(np.isfinite(ts_l)) and np.all(np.isfinite(tp_l))):
        raise ValueError("Rs, Ts and Tp must be finite")
    n_rs = int(np.count_nonzero(rs >= THRESHOLD))
    n_ts = int(np.count_nonzero(ts >= THRESHOLD))
    if np.any(tp_l <= 0.0):
        contrast_term = math.inf
        contrast = (0.0, 0.0, 0.0)
    else:
        contrast_term = 500.0 / 3.0 * float(np.sum(ts_l / tp_l))
        with np.errstate(divide="ignore"):
            ratio = np.where(ts_l > 0.0, tp_l / np.where(ts_l > 0.0, ts_l, 1.0), math.inf)
        contrast = (float(ratio[0]), float(ratio[1]), float(ratio[2]))
    heaviside_term = n_rs / n_ts if n_ts > 0 else math.inf
    return B1Score(
        total=contrast_term + heaviside_term,
        contrast_term=contrast_term,
        heaviside_term=heaviside_term,
        n_rs_at_least_99=n_rs,
        n_ts_at_least_99=n_ts,
        contrast_at_lines=contrast,
    )


def within_contest_rules(thicknesses_nm: np.ndarray, material_indices: np.ndarray) -> bool:
    """True if the design has at most 100 layers, at most 20 um in total and only the contest materials."""
    d = np.asarray(thicknesses_nm, dtype=np.float64)
    n = np.asarray(material_indices, dtype=np.float64)
    if d.ndim != 1 or n.shape != d.shape:
        return False
    allowed = np.array(sorted(MATERIALS.values()))
    return bool(
        d.size <= MAX_LAYERS
        and np.all(d >= 0.0)
        and float(d.sum()) <= MAX_PHYSICAL_THICKNESS_NM
        and np.all(np.isclose(n[:, None], allowed[None, :], rtol=0.0, atol=1e-12).any(axis=1))
    )
