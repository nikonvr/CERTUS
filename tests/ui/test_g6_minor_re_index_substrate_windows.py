"""Three window minors of the audit of 2026-11-15 (L6-m4, L5-m6, L6-m3).

L6-m4: reloading an RE configuration let its l0 replace the workbook's lambda_ref, silently (owner: the workbook wins).
L5-m6: INDEX kept the smoothed 4000-5200 nm traces when nobody answered within 5 s (owner: never smooth by default).
L6-m3: the SUBSTRATE fit ran in the GUI thread without pumping events: the bar never redrew, Cancel was read at the end.
"""

from __future__ import annotations

import inspect
import json

import pytest

SAMPLE = "example/example_RE/reverse_sample.xlsx"


@pytest.fixture
def re_window(qapp):
    from CERTUS_RE import CertusREApp

    win = CertusREApp()
    yield win
    win.close()


def test_l6_m4_the_workbook_lambda_ref_wins_with_a_warning(re_window, tmp_path) -> None:
    from pathlib import Path

    assert re_window.load_reverse_engineering_from_path(SAMPLE)
    wb_l0 = float(re_window.l0_spin.value())
    cfg = tmp_path / "re.json"
    cfg.write_text(json.dumps({"workbook_path": str(Path(SAMPLE).resolve()), "l0": wb_l0 + 37.0}), encoding="utf-8")
    logged: list[tuple[str, str]] = []
    original = re_window.log
    re_window.log = lambda message, level="INFO": (logged.append((level, message)), original(message, level))[1]

    assert re_window.load_config(str(cfg))

    assert float(re_window.l0_spin.value()) == wb_l0
    assert any(level == "WARNING" and "workbook's is kept" in message for level, message in logged)


def test_l5_m6_no_answer_keeps_the_raw_measurement() -> None:
    from certus.ui.certus_index_ui_events import CertusIndexEventsMixin

    source = inspect.getsource(CertusIndexEventsMixin._ask_keep_raw_or_smoothed)
    assert "setDefaultButton(btn_raw)" in source
    assert "is not btn_smooth" in source
    assert "smoothed response will be kept" not in source


def test_l6_m3_the_substrate_fit_pumps_events_and_ignores_a_second_click() -> None:
    from certus.ui.certus_substrate_ui import SubstrateIndexGUI

    assert "QApplication.processEvents()" in inspect.getsource(SubstrateIndexGUI.update_progress)
    assert "_calculating" in inspect.getsource(SubstrateIndexGUI.calculate_index)
    assert not hasattr(SubstrateIndexGUI, "_get_clean_fraction_column"), "the dead copy of the presenter's method stays"
