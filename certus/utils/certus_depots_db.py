"""The deposit database of `example/database_depots/`: its catalogue, read without Qt.

Measured single layers (Photon RT), one normalized file per sample in the format INDEX loads (`wavelength_nm,T[,R]`,
percent), described by `catalogue.json` (`scripts/importer_base_depots.py` writes both). The window side is
`certus/ui/certus_depots_dialog.py`; this module only reads and labels.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from certus.core.certus_core import get_resource_path


def database_dir() -> Path:
    """The folder of the database, from the sources or from the frozen build alike."""
    return Path(get_resource_path("example/database_depots"))


def load_catalogue(base: Path | None = None) -> list[dict[str, Any]]:
    """The deposits of the catalogue, in its order."""
    folder = base if base is not None else database_dir()
    data = json.loads((folder / "catalogue.json").read_text(encoding="utf-8"))
    return list(data.get("depots", []))


def measurement_path(entry: dict[str, Any], base: Path | None = None) -> Path:
    """The normalized measurement file of a deposit."""
    folder = base if base is not None else database_dir()
    return folder / entry["fichier"]


def attribute(entry: dict[str, Any], key: str) -> str:
    """The material or substrate the name states, or an empty text when it states none."""
    value = entry.get(key)
    return str(value["valeur"]) if value else ""


def channels_label(entry: dict[str, Any]) -> str:
    """The channels of a deposit as an operator reads them: "T 0°, R 8°"."""
    out = []
    for channel in entry.get("voies", []):
        angle = channel.get("angle_deg")
        out.append(channel["mode"] if angle is None else f"{channel['mode']} {angle:g}°")
    return ", ".join(out)


def range_label(entry: dict[str, Any]) -> str:
    """The spectral range of a deposit, in nm."""
    low, high = entry["lambda_nm"]
    return f"{low:.0f}–{high:.0f}"


def _names_differ_by_the_channel_letter(name_a: str, mode_a: str, name_b: str, mode_b: str) -> bool:
    """True when `name_b` is `name_a` with one letter `mode_a` turned into `mode_b`, at one place (case kept)."""
    a, b = name_a.strip(), name_b.strip()
    if len(a) != len(b):
        return False
    differ = [i for i in range(len(a)) if a[i] != b[i]]
    return len(differ) == 1 and a[differ[0]].upper() == mode_a and b[differ[0]].upper() == mode_b


def paired_entry(entry: dict[str, Any], entries: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The other channel of the same sample, named apart by the operator (`NbT3` and `NbR3`), or None.

    Both are single-channel entries of the same workbook, one T and one R, on the same grid, and their sample names
    differ by that one letter at one place; the partner must be the only such entry.
    """
    channels = entry.get("voies", [])
    if len(channels) != 1 or channels[0]["mode"] not in ("T", "R"):
        return None
    mode = channels[0]["mode"]
    other = "R" if mode == "T" else "T"
    found = [
        candidate for candidate in entries
        if candidate is not entry
        and candidate.get("brut") == entry.get("brut")
        and [c["mode"] for c in candidate.get("voies", [])] == [other]
        and candidate.get("lambda_nm") == entry.get("lambda_nm")
        and candidate.get("points") == entry.get("points")
        and _names_differ_by_the_channel_letter(entry["echantillon"], mode, candidate["echantillon"], other)
    ]
    return found[0] if len(found) == 1 else None


def write_side_by_side(entries: list[dict[str, Any]], path: Path, base: Path | None = None) -> Path:
    """Write the T and R columns of single-channel deposits on their common grid (`wavelength_nm,T,R`), the format INDEX loads."""
    import numpy as np

    columns: dict[str, np.ndarray] = {}
    grid = None
    for entry in entries:
        data = np.loadtxt(measurement_path(entry, base), delimiter=",", skiprows=1, ndmin=2)
        if grid is None:
            grid = data[:, 0]
        elif data.shape[0] != grid.shape[0] or np.max(np.abs(data[:, 0] - grid)) > 1e-6:
            raise ValueError(f"{entry['id']} is not on the grid of {entries[0]['id']}")
        columns[entry["voies"][0]["mode"]] = data[:, 1]
    if grid is None:
        raise ValueError("no deposit to write")
    order = [mode for mode in ("T", "R") if mode in columns]
    lines = ["wavelength_nm," + ",".join(order)]
    lines += [",".join([repr(float(w))] + [repr(float(columns[m][i])) for m in order]) for i, w in enumerate(grid)]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
