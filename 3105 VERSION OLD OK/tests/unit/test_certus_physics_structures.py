"""Garde-fou: symboles physiques exposés par le noyau (remplace l'ancienne façade supprimée)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))


@pytest.mark.unit
def test_physics_impl_exports_expected_symbols() -> None:
    mod = pytest.importorskip("_certus_physics_impl")
    assert hasattr(mod, "Layer")
    assert hasattr(mod, "Target")
    assert hasattr(mod, "NKCache")
    assert hasattr(mod, "PGlobalOptimizer")


@pytest.mark.unit
def test_do_not_split_markers_still_present() -> None:
    impl = ROOT / "certus" / "core" / "_certus_physics_impl.py"
    content = impl.read_text(encoding="utf-8", errors="ignore")
    assert "DO NOT SPLIT" in content
