"""Guard against stale API snippets in docs/API_DOCUMENTATION.md."""

from __future__ import annotations

from pathlib import Path

import pytest


DOC_PATH = Path(__file__).resolve().parents[2] / "docs" / "API_DOCUMENTATION.md"


@pytest.mark.unit
def test_api_documentation_uses_current_structures_signatures() -> None:
    text = DOC_PATH.read_text(encoding="utf-8")

    # Legacy snippets that no longer match certus_physics.structures signatures.
    forbidden = [
        "Layer(material=",
        "thickness=",
        "PGlobalConfig(",
        "wavelength_range=",
        "targets=[Target(wavelength=",
    ]
    for bad in forbidden:
        assert bad not in text, f"Stale API snippet found in docs: {bad}"

    # Current expected snippets.
    expected = [
        "Layer(mat=",
        "qwot=",
        "PGlobalConfig.for_index(",
        "Target(lmin=",
    ]
    for token in expected:
        assert token in text, f"Expected API snippet missing in docs: {token}"
