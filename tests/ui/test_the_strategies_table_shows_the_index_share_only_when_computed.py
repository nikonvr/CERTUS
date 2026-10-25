"""A11: the strategies table shows an "Index share %" column, last, only when the run computed the index share."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from certus.ui.certus_strat_table_ui import INDEX_SHARE_HEADER, StrategiesTableWindow


def result(share=None) -> dict:
    out = {
        "strategy": {"strategy_id": "s1", "n_blocks": 1, "origin": "ELITE", "rate_layers": [],
                     "blocks": [{"start": 0, "end": 3, "wavelength": 600.0, "num_layers": 3}]},
        "robustness_score": 0.12, "num_unique_wavelengths": 1, "min_resolution": 1.0, "crash_rate": 0.0,
        "results_per_noise": [{"noise_level": lv, "rmse_mean": 0.1, "rmse_p95": 0.12, "thicknesses_all": [[100.0, 80.0, 60.0]],
                               "rmse_all": [0.1]} for lv in (0.5, 1.0, 2.0)],
    }
    if share is not None:
        out.update(index_share=share, rmse2_index_on=4.0e-4, rmse2_index_off=1.0e-4)
    return out


def headers(win) -> list[str]:
    return [win.table.horizontalHeaderItem(c).text() for c in range(win.table.columnCount())]


def test_no_column_without_an_index_share(qapp):
    win = StrategiesTableWindow(None, [result()], [100.0, 80.0, 60.0])
    try:
        assert INDEX_SHARE_HEADER not in headers(win)
    finally:
        win.close()


def test_the_column_is_last_and_holds_the_share_in_percent(qapp):
    win = StrategiesTableWindow(None, [result(0.75)], [100.0, 80.0, 60.0])
    try:
        h = headers(win)
        assert h[-1] == INDEX_SHARE_HEADER
        assert win.table.item(0, len(h) - 1).text() == "75"
    finally:
        win.close()
