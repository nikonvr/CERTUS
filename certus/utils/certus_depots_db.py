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
