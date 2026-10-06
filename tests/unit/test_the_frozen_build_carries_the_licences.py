"""The frozen build carries the licences of what it bundles (decided by the owner on 2026-10-06).

Before, the executable held the licence files of five distributions, those PyInstaller's hooks copied for their own
needs, and neither CERTUS's licence nor its third-party notices, while the MIT and BSD terms of most of the others ask
for their notice in a binary distribution, and the release workflow publishes the build as an artifact.
`tools/frozen_licences.py` lists them; `certus_hub.spec` adds them to the build, in `licenses/`.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _collector():
    spec = importlib.util.spec_from_file_location("frozen_licences", ROOT / "tools" / "frozen_licences.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.unit
def test_the_spec_adds_the_licences_to_the_build() -> None:
    spec = (ROOT / "certus_hub.spec").read_text(encoding="utf-8")

    assert "frozen_licences.py" in spec
    assert "a.datas += frozen_licences.licence_toc(" in spec


@pytest.mark.unit
def test_the_top_level_names_cover_modules_and_binaries() -> None:
    names = _collector().top_level_names(
        [("numpy.linalg", "", "PYMODULE")],
        [("numpy.libs/libopenblas.dll", "", "BINARY"), ("llvmlite\\binding\\llvmlite.dll", "", "BINARY")],
    )

    assert names == {"numpy", "llvmlite"}


@pytest.mark.unit
def test_the_licences_of_a_bundled_distribution_and_the_project_s_own_are_listed() -> None:
    toc = _collector().licence_toc({"numpy", "PyQt6"})
    destinations = [destination for destination, _, _ in toc]

    assert "licenses/LICENSE" in destinations
    assert "licenses/THIRD_PARTY_NOTICES.md" in destinations
    assert any(d.startswith("licenses/numpy/") for d in destinations)
    assert any(d.startswith("licenses/pyqt6/") for d in destinations)
    assert len(destinations) == len(set(destinations)), "two licence files would land on the same path"
    assert all(Path(source).is_file() for _, source, _ in toc)
    assert {kind for _, _, kind in toc} == {"DATA"}


@pytest.mark.unit
def test_a_name_no_distribution_provides_adds_nothing() -> None:
    collector = _collector()

    assert collector.licence_toc({"python314"}) == collector.licence_toc(set())
