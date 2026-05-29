"""Smoke tests for CERTUS Metal Single UI imports and substrate plumbing."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parent.parent.parent
MODULE_PATH = ROOT / "certus_metal_siNGLE.py"


@pytest.mark.unit
def test_certus_metal_single_module_imports_and_exports() -> None:
    spec = importlib.util.spec_from_file_location("certus_metal_siNGLE", MODULE_PATH)
    assert spec is not None and spec.loader is not None

    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert hasattr(mod, "CertusMetalSingleApp")
    assert hasattr(mod, "_resolve_single_substrate_id")
    assert hasattr(mod, "_get_single_substrate_n_array")
    assert hasattr(mod, "SUBSTRATE_MIN_LAMBDA")


@pytest.mark.unit
def test_certus_metal_single_substrate_resolution_and_fallback() -> None:
    spec = importlib.util.spec_from_file_location("certus_metal_siNGLE", MODULE_PATH)
    assert spec is not None and spec.loader is not None

    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert mod._resolve_single_substrate_id("Fused Silica") == 0
    assert mod._resolve_single_substrate_id("BK7") == 1
    assert mod._resolve_single_substrate_id("D263T eco") == 2
    assert mod._resolve_single_substrate_id("Sapphire") == 3

    wl = np.asarray([400.0, 500.0, 600.0], dtype=np.float64)
    n = mod._get_single_substrate_n_array(999, wl)
    assert n.shape == wl.shape
    assert np.all(np.isfinite(n))
