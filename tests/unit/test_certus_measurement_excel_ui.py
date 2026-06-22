"""Unit tests: choice of "measurement" sheet (without file dialog)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

cm = pytest.importorskip("certus_measurement_excel_ui", reason="certus_measurement_excel_ui indisponible")


@pytest.mark.unit
class TestPickMeasurementSheetName:
    def test_empty_returns_none(self) -> None:
        assert cm.pick_measurement_sheet_name([], None) is None

    def test_single_sheet(self) -> None:
        assert cm.pick_measurement_sheet_name(["data"], None) == "data"

    def test_prefers_measurement_alias(self) -> None:
        names = ["design", "Measurement_RAW", "summary"]
        assert cm.pick_measurement_sheet_name(names, None) == "Measurement_RAW"
