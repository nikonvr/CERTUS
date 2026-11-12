"""Every number of a status bar is beside the word for what it counts (U4b).

Measured on 2026-11-12 (`scripts/audit_ux_certus.py::unlabelled_counters`, 1440x900): four windows showed bare counters.

    STRAT          three numbers beside three pictograms; only a tooltip said strategies, Monte Carlo runs, spectral points
    DESIGN         "minima" and "evals" at start, lost at the first update of a run; the third number never had a word
    METAL (x2)     "0 | 0 | 0": the pictograms themselves had been lost
    INDEX          "0"

A pictogram is not a label: it renders differently on each system, and here two windows had already lost theirs. Each
counter now carries its word, and the reset puts the numbers back to zero without touching the words.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.audit_ux_certus import MODULES, _run_worker, unlabelled_counters  # noqa: E402


@pytest.mark.parametrize("app", sorted(MODULES))
def test_no_counter_of_the_status_bar_is_a_bare_number(app) -> None:
    row = _run_worker(app, 1440, 900)
    assert "ERROR" not in row, row.get("ERROR")

    assert row["unlabelled_counters"] == [], f"{app} shows numbers nothing names: {row['unlabelled_counters']}"


def test_the_measure_tells_a_named_counter_from_a_bare_one(qapp) -> None:
    from PyQt6.QtWidgets import QLabel, QMainWindow

    window = QMainWindow()
    bar = window.statusBar()
    for text in ("12 minima  |  3.4k evals  |  7", "Best RMSE: 0.368035", "45%", "Zoom 100%", "Ready"):
        bar.addPermanentWidget(QLabel(text))
    window.show()
    qapp.processEvents()
    try:
        assert unlabelled_counters(window) == ["7"]
    finally:
        window.close()
        window.deleteLater()
