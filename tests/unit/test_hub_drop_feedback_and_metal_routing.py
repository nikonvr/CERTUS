"""The hub says what it did with a drop, and does not guess between the two METAL modules (audit UX 2026-11-18).

Dropping two files opened the first and silently forgot the second; a METAL configuration called `metal_lot.json`
opened METAL SINGLE although the same keys are written by METAL BILAYER (opaque substrate).
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QInputDialog

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "example"
METAL_EXAMPLE = EXAMPLES / "example_metal_single" / "JSON-metal-example.json"


@pytest.fixture
def hub(qapp):
    from CERTUS_HUB import CertusHub

    window = CertusHub()
    try:
        yield window
    finally:
        window.active_processes.clear()
        window.close()


@pytest.fixture
def asked(monkeypatch):
    state: dict = {"offered": None, "label": None, "answer": 0}

    def fake(_parent, _title, label, items, _current=0, _editable=False):
        state["offered"] = list(items)
        state["label"] = label
        return items[state["answer"]], True

    monkeypatch.setattr(QInputDialog, "getItem", staticmethod(fake))
    return state


def _copy(source: Path, folder: Path, name: str) -> Path:
    target = folder / name
    shutil.copyfile(source, target)
    return target


def test_a_generic_metal_name_asks_which_substrate(hub, asked, tmp_path) -> None:
    config = _copy(METAL_EXAMPLE, tmp_path, "metal_lot.json")

    script = hub._module_for_dropped_file(str(config))

    assert asked["offered"] == ["METAL SINGLE", "METAL BILAYER"]
    assert "Transparent Substrate" in asked["label"]
    assert "Opaque Substrate" in asked["label"]
    assert script == "CERTUS_METAL_SINGLE.py"


@pytest.mark.parametrize(
    ("name", "expected"),
    [("metal_single_lot.json", "CERTUS_METAL_SINGLE.py"), ("metal_bilayer_lot.json", "CERTUS_METAL_BILAYER.py")],
)
def test_an_explicit_metal_name_still_routes_without_asking(hub, asked, tmp_path, name, expected) -> None:
    config = _copy(METAL_EXAMPLE, tmp_path, name)

    assert hub._module_for_dropped_file(str(config)) == expected
    assert asked["offered"] is None
