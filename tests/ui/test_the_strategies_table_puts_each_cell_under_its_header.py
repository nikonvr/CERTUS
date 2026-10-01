"""In the strategies table, every cell sits under the header that names it (audit v2, plan S5.2, found by the characterization of `_populate_table_row`).

Found 2026-10-01 while moving the column builders of `_populate_table_row` into methods of their own (8ed061b): the header builder lists 18 base columns and then three SEEL
columns, so the blocks start in column 21; the row builder started them in column 17 (`start_col_blocks = 17  # 14 base columns + 3 SEEL`). Commit 3a70f57 (2026-08-12) added four base
columns and moved the SEEL columns to 18 but left the blocks where they were. For every strategy of every run since then:

    column 17 "Dominant defect"    held the text of block 1, written over the ablation cell
    columns 18 and 19 "SEEL"       held block 2 and the first worst layer, written over two of the three SEEL cells
    the "Block n" and "Worst" columns   held the worst layers, shifted by four

The row builder and the header builder now read the same lists (`BASE_HEADERS`, `NOISE_HEADERS`), and these tests read the cells from a real window.
"""

from __future__ import annotations

import os
import re

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import pytest

from certus.ui import certus_strat_table_ui
from certus.ui.certus_strat_table_ui import (
    BASE_HEADERS,
    BLOCKS_FIRST_COLUMN,
    NOISE_HEADERS,
    SEEL_FIRST_COLUMN,
    StrategiesTableWindow,
)

BLOCK_TEXT = re.compile(r"^\d+nm \(L\d+->L\d+\)$")
WORST_TEXT = re.compile(r"^L\d+ \d+\.\d+nm$")
SEEL_TEXT = re.compile(r"^(\d+\.\d{3} nm|R:\d+\.\d{5}|N/A)$")  # a SEEL, the raw RMSE when it cannot be converted, or nothing


def result(blocks: int = 2) -> dict:
    return {
        "strategy": {
            "strategy_id": "s1",
            "n_blocks": blocks,
            "origin": "SMART (merge)",
            "symmetry_score_pct": 72.5,
            "rate_layers": [1, 4],
            "blocks": [{"start": 2 * k, "end": 2 * k + 2, "wavelength": 500.0 + 150 * k, "num_layers": 2} for k in range(blocks)],
            "theoretical_layer_profile": [{"extrema_count": 3}, {"extrema_count": 5}],
        },
        "robustness_score": 0.12,
        "num_unique_wavelengths": blocks,
        "min_resolution": 1.0,
        "limiting_layer": 2,
        "crash_rate": 0.03,
        "monochromator_resolution_nm": 1.5,
        "critical_layer": {"layer": 3, "margin_in_A": 4.2, "cause": "tp_miscount"},
        "ablation": [{"source": "noise", "contribution": 0.4}, {"source": "slit", "contribution": 0.1}],
        "results_per_noise": [
            {"noise_level": level, "rmse_mean": 0.1 * level, "rmse_p95": 0.12 * level, "thicknesses_all": [[100.0, 80.0, 60.0], [103.0, 77.0, 64.0]], "rmse_all": [0.1]}
            for level in (0.5, 1.0, 2.0)
        ],
    }


@pytest.fixture
def window(qapp, monkeypatch):
    win = StrategiesTableWindow(None, [result()], [100.0, 80.0, 60.0])
    yield win
    win.close()


def headers(win) -> list[str]:
    return [win.table.horizontalHeaderItem(c).text() for c in range(win.table.columnCount())]


def text(win, column: int) -> str:
    item = win.table.item(0, column)
    return "" if item is None else item.text()


def test_the_column_constants_follow_the_header_lists():
    assert SEEL_FIRST_COLUMN == len(BASE_HEADERS)
    assert BLOCKS_FIRST_COLUMN == SEEL_FIRST_COLUMN + len(NOISE_HEADERS)


def test_the_window_builds_its_headers_from_the_same_lists(window):
    got = headers(window)
    assert got[: len(BASE_HEADERS)] == list(BASE_HEADERS)
    assert got[SEEL_FIRST_COLUMN : SEEL_FIRST_COLUMN + len(NOISE_HEADERS)] == list(NOISE_HEADERS)
    assert got[BLOCKS_FIRST_COLUMN].startswith("Block 1")


def test_the_blocks_sit_under_the_block_headers_and_nowhere_else(window):
    got = headers(window)
    block_columns = [c for c, h in enumerate(got) if h.startswith("Block ")]
    assert block_columns[0] == BLOCKS_FIRST_COLUMN
    for column in block_columns[:2]:
        assert BLOCK_TEXT.match(text(window, column)), (got[column], text(window, column))
    other = [c for c in range(len(got)) if c not in block_columns and BLOCK_TEXT.match(text(window, c))]
    assert other == [], [(got[c], text(window, c)) for c in other]


def test_the_dominant_defect_is_the_ablation_not_a_block(window):
    column = headers(window).index("Dominant defect")
    assert text(window, column) == "noise +40%"


def test_each_noise_level_has_its_own_seel_cell(window):
    for k, header in enumerate(NOISE_HEADERS):
        column = SEEL_FIRST_COLUMN + k
        assert headers(window)[column] == header
        assert SEEL_TEXT.match(text(window, column)), (header, text(window, column))


def test_the_worst_layers_sit_under_the_worst_headers(window):
    got = headers(window)
    worst = [c for c, h in enumerate(got) if h.startswith("Worst #")]
    assert worst, "no worst-layer column"
    assert WORST_TEXT.match(text(window, worst[0])), (got[worst[0]], text(window, worst[0]))
    assert worst[0] == BLOCKS_FIRST_COLUMN + 2  # two blocks in this result: the header list leaves no gap and no overlap


def test_a_table_with_no_block_still_puts_the_worst_layers_after_the_seel_columns(qapp):
    win = StrategiesTableWindow(None, [result(blocks=1)], [100.0, 80.0, 60.0])
    try:
        got = headers(win)
        first_worst = next(c for c, h in enumerate(got) if h.startswith("Worst #"))
        assert first_worst == BLOCKS_FIRST_COLUMN + 1
    finally:
        win.close()


def test_the_module_no_longer_hard_codes_the_first_block_column():
    source = open(certus_strat_table_ui.__file__, encoding="utf-8-sig").read()
    assert "start_col_blocks = 17" not in source
    assert "target_col = 18 + col_idx" not in source
