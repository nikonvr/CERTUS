"""Several test glasses in one run: the layers where a NEW test glass enters (`witness_reset_layers`).

The kernel has carried the setting since 2026-08-15 (`010a2c4a`; `witness_base`, `certus_strat_batch.py`); the window
did not show it, and a configuration file could not set it either, since `collect_params` did not route it. This module is the
window's side of it: read what the operator typed, refuse what cannot be read, and say in the status banner how many
test glasses the run will use.

🔴 A FEASIBILITY TOOL, NEVER AN OPTIMISATION (`certus_strat_leviers.py`, `witness_reset_layers`): a new glass forgets
the error made before it. On the components one glass can monitor, every partition measured made the SEEL worse
(48c +73 to +89 %, 35c +10 to +98 %, 75c +110 %); it is what made the 99-layer bandpass manufacturable.

The downstream resolver (`_resolve_witness_resets`) drops what it cannot read. That is right for a configuration
written by a script, wrong for a field an operator types into: a typo would run one test glass and say nothing. The
window therefore refuses the run instead (`problems`), and shows the plan it will apply (`summary`).
"""

from __future__ import annotations

import re
from typing import Any

#: The setting, as the kernel and the configuration files name it.
KEY = "witness_reset_layers"

#: Label of the field. Under it, the window takes no number validator: the value is a list.
LABEL = "New test glass at layers:"

#: What the field lets an operator type: layer numbers, separators, and the brackets of a list a file wrote.
ALLOWED = r"[0-9;,\s\[\]]*"

TOOLTIP = (
    "Layers (counted from 0, the first one on the substrate) where a NEW test glass enters, "
    "separated by ';' -- e.g. 22;42;76 for four glasses. Empty: one test glass for the whole stack.\n"
    "A feasibility tool, never an optimisation: a new glass forgets the error made before it. "
    "On components one glass can monitor, every partition measured made the SEEL worse (+10 to +110 %). "
    "Arm it only when no seed finds a depositable strategy with one glass."
)


def parse(value: Any) -> tuple[list[int], list[str]]:
    """The layers `value` names, sorted and without repeats, and the pieces that are not layer numbers.

    `value` is what the field holds or what a configuration file stores: a text separated by ';', ',' or blanks,
    or a list. Brackets are ignored, so a list a configuration file wrote reads back the same.
    """
    if value is None:
        return [], []
    if isinstance(value, (list, tuple)):
        pieces = [str(item) for item in value]
    else:
        pieces = re.split(r"[;,\s]+", str(value).replace("[", " ").replace("]", " ").strip())
    layers: list[int] = []
    unreadable: list[str] = []
    for piece in pieces:
        piece = piece.strip()
        if not piece:
            continue
        try:
            layer = int(piece)
        except ValueError:
            unreadable.append(piece)
            continue
        if layer not in layers:
            layers.append(layer)
    return sorted(layers), unreadable


def problems(value: Any, n_layers: int, label: str = LABEL.rstrip(":")) -> list[str]:
    """What stops a run on this entry: a piece that is not a layer number, or a layer outside 1 .. n_layers - 1.

    Layer 0 is refused too: it already grows on bare glass, so a new glass there changes nothing.
    """
    layers, unreadable = parse(value)
    out = [f'{label}: "{piece}" is not a layer number.' for piece in unreadable]
    out += [
        f"{label}: layer {layer} is outside 1 .. {n_layers - 1} (layer 0 already grows on bare glass)."
        for layer in layers
        if not 0 < layer < n_layers
    ]
    return out


def summary(value: Any, n_layers: int) -> str:
    """The test glasses the run will use, for the status banner: `?` when the entry cannot be applied as it stands."""
    layers, unreadable = parse(value)
    if unreadable or any(not 0 < layer < n_layers for layer in layers):
        return "TEMOINS ?"
    if not layers:
        return "TEMOINS 1"
    return f"TEMOINS {len(layers) + 1} (neufs aux couches {', '.join(str(layer) for layer in layers)})"
