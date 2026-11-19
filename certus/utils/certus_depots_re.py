"""A reference of the deposit database as a reverse-engineering workbook (lot 2d): measurement, design and index sheets.

The deposit database gives a measured single layer; `references_index.json` gives, for eleven of them, the
Tauc-Lorentz-Urbach parameters and the thickness of a certified fit. Together they make the three sheets RE reads
(`load_reverse_engineering_from_path`): the measured channels, a one-layer design (its QWOT at a reference wavelength
inside the band) on the reference's substrate, and the n, k of the layer on the measured grid.

A NORMALIZED reference (INDEX compares T/T_sub and R/T_sub) is refused: RE models absolute R and T, and turning a
normalized measurement back into an absolute one needs a substrate model, a decision left to the owner. No Qt here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from certus.utils.certus_depots_db import measurement_path


def _tlu_nk(params: dict[str, float], wavelengths_nm: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """n and k of a Tauc-Lorentz-Urbach layer, with the functions INDEX fits with."""
    from certus.core.certus_core import HC_EV_NM
    from certus_physics import epsilon1_TL_analytic, epsilon2_TLU_array, epsilon_to_nk

    energy = HC_EV_NM / np.asarray(wavelengths_nm, dtype=np.float64)
    eps2 = epsilon2_TLU_array(energy, params["Eg"], params["A"], params["E0"], params["C"], params["Eu"])
    eps1 = epsilon1_TL_analytic(energy, params["Eg"], params["A"], params["E0"], params["C"], params["eps_inf"])
    n, k, _ok = epsilon_to_nk(eps1, eps2, 0.5, 15.0, 15.0)
    return np.asarray(n, dtype=np.float64), np.asarray(k, dtype=np.float64)


def _channel_header(entry: dict[str, Any]) -> str:
    """RE column title of a single-channel deposit: channel, angle, unpolarized, measured through the plate."""
    channel = entry["voies"][0]
    angle = channel.get("angle_deg") or 0.0
    return f"{channel['mode']}-{float(angle):g}-avg-BACK"


def re_workbook_sheets(
    reference: dict[str, Any], catalogue_by_id: dict[str, dict[str, Any]], base: Path | None = None,
) -> dict[str, list[list[Any]]]:
    """The rows of the three sheets RE reads, for one reference of `references_index.json`."""
    if reference.get("normalise"):
        raise ValueError(
            f"{reference['nom']}: the reference is normalized (T/T_sub, R/T_sub); RE models absolute R and T, and "
            "de-normalizing needs a substrate model (decision of the owner)"
        )
    entries = [catalogue_by_id[depot_id] for depot_id in reference["depots"]]
    grid = None
    columns: list[tuple[str, np.ndarray]] = []
    for entry in entries:
        if len(entry.get("voies", [])) != 1:
            raise ValueError(f"{entry['id']}: one channel per deposit is expected")
        data = np.loadtxt(measurement_path(entry, base), delimiter=",", skiprows=1, ndmin=2)
        if grid is None:
            grid = data[:, 0]
        elif data.shape[0] != grid.shape[0] or np.max(np.abs(data[:, 0] - grid)) > 1e-6:
            raise ValueError(f"{entry['id']} is not on the grid of {entries[0]['id']}")
        columns.append((_channel_header(entry), data[:, 1]))
    if grid is None:
        raise ValueError(f"{reference['nom']}: no deposit")
    low, high = reference.get("bande_nm") or (None, None)
    keep = np.ones(grid.shape, dtype=bool)
    if low is not None:
        keep &= grid >= float(low)
    if high is not None:
        keep &= grid <= float(high)
    wl = grid[keep]
    if wl.size < 2:
        raise ValueError(f"{reference['nom']}: fewer than two measured points in the band")

    params = reference["parametres"]
    material = str(reference["nom"])
    n, k = _tlu_nk(params, wl)
    lambda_ref = float(np.round(0.5 * (wl[0] + wl[-1])))
    n_ref = float(np.interp(lambda_ref, wl, n))
    qwot = 4.0 * n_ref * float(reference["d_nm"]) / lambda_ref

    measurement = [["Wavelength, nm", *[title for title, _values in columns]]]
    measurement += [[float(w), *[float(values[keep][i]) for _title, values in columns]] for i, w in enumerate(wl)]
    design = [["lambda", lambda_ref, str(reference["substrat"])], [qwot]]
    # RE reads two materials (H and L); the single layer is H, and L repeats it so that both columns are physical.
    index = [["lambda (nm)", f"n_{material}", f"k_{material}", f"n_{material}_L", f"k_{material}_L"]]
    index += [[float(w), float(n[i]), float(k[i]), float(n[i]), float(k[i])] for i, w in enumerate(wl)]
    return {"measurement": measurement, "design": design, "index": index}


def write_re_workbook(
    reference: dict[str, Any], catalogue_by_id: dict[str, dict[str, Any]], path: Path, base: Path | None = None,
) -> Path:
    """Write the RE workbook of one reference (see the module docstring) and return its path."""
    import openpyxl

    sheets = re_workbook_sheets(reference, catalogue_by_id, base)
    workbook = openpyxl.Workbook()
    workbook.remove(workbook.active)
    for name in ("measurement", "design", "index"):
        sheet = workbook.create_sheet(name)
        for row in sheets[name]:
            sheet.append(row)
    workbook.properties.creator = "CERTUS"
    from certus.utils.certus_atomic_io import atomic_save_workbook

    atomic_save_workbook(workbook, path)
    return path
