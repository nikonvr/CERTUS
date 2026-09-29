"""What the operator types in the STRAT fields is read as typed, or refused where he can see it.

`_get_float_safe` answered `float(text)` and, when that failed, the default of the field, with no
message: « 1550,5 » in the control wavelength became 1500 nm, a lone « - » in the spectral step
became 0.2, and the run started on values nobody had typed. The French decimal comma is the
natural way to write 1550.5; the field's validator (C locale) let it stand as an intermediate
state, `hasAcceptableInput()` said no and nothing ever asked. A layer multiplier written with a
comma in the stack table raised a ValueError that `run_workflow` only logged.

Now a comma is read as a decimal point (typed, pasted or set), an entry that is still not a
number stops the run with a message naming the field, and the few values that would break the
spectral grid (a zero step, a negative or reversed range) are refused the same way.
"""

from __future__ import annotations

import pytest
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QMessageBox


@pytest.fixture(autouse=True)
def _windows_end_with_the_test(qapp, monkeypatch):
    from qt_lifecycle import qt_lifecycle

    yield from qt_lifecycle(qapp, monkeypatch, "STRAT numeric entries", main_windows_only=True)


class _Started(Exception):
    """A worker was built: the run went on."""


@pytest.fixture
def window(qapp, monkeypatch):
    from certus.ui.certus_strat_ui import CertusStratApp

    app = CertusStratApp()
    app.started = []
    app.warnings = []

    def worker(*args, **kwargs):
        app.started.append(kwargs)
        raise _Started

    monkeypatch.setattr("certus.ui.certus_strat_ui_worker.WorkerThread", worker)
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: app.warnings.append(a[2])))
    return app


def _run(window) -> None:
    try:
        window.run_workflow(0)
    except _Started:
        pass


def test_a_decimal_comma_is_read_as_a_decimal_point(window) -> None:
    window.widgets["l0"].setText("1550,5")

    assert window.collect_params()["l0"] == 1550.5


def test_a_typed_decimal_comma_is_accepted_by_the_field(window) -> None:
    edit = window.widgets["l0"]
    edit.clear()

    QTest.keyClicks(edit, "1550,5")

    assert edit.hasAcceptableInput()
    assert window.collect_params()["l0"] == 1550.5


def test_a_layer_multiplier_may_be_written_with_a_decimal_comma(window) -> None:
    window.widgets["stack_table"].item(0, 2).setText("0,5")

    assert window.collect_params()["stack_string"].split(",")[0] == "0.5"


def test_a_form_that_reads_well_starts_the_run(window) -> None:
    _run(window)

    assert len(window.started) == 1
    assert window.warnings == []


def test_an_entry_that_is_not_a_number_stops_the_run_and_names_the_field(window) -> None:
    window.widgets["wl_step"].setText("-")

    _run(window)

    assert window.started == []
    [message] = window.warnings
    assert "Spectral Step (nm)" in message
    assert '"-"' in message


@pytest.mark.parametrize(
    ("field", "text", "named"),
    [
        ("l0", "-800", "Center"),
        ("wl_step", "0", "Spectral Step (nm)"),
        ("scan_wl_step", "0", "Candidate lambda Step (nm)"),
    ],
)
def test_a_value_that_breaks_the_spectral_grid_stops_the_run(window, field, text, named) -> None:
    window.widgets[field].setText(text)

    _run(window)

    assert window.started == []
    [message] = window.warnings
    assert named.lower() in message.lower()


def test_a_reversed_spectral_range_stops_the_run(window) -> None:
    window.widgets["wl_range_start"].setText("1700")
    window.widgets["wl_range_end"].setText("1200")

    _run(window)

    assert window.started == []
    assert len(window.warnings) == 1


def test_a_noise_list_that_cannot_be_read_stops_the_run(window) -> None:
    window.widgets["robustness_noise_factors"].setText("0.5; 1; 2")

    _run(window)

    assert window.started == []
    [message] = window.warnings
    assert '"0.5; 1; 2"' in message


def test_the_reader_takes_a_comma_a_space_and_nothing_that_is_not_finite() -> None:
    from certus.utils.certus_numeric_text import parse_decimal

    assert parse_decimal("1550,5") == 1550.5
    assert parse_decimal(" 1 550,5 ") == 1550.5
    assert parse_decimal("1550.5") == 1550.5
    assert parse_decimal("-800") == -800.0
    for refused in ("", "-", "1,5,2", "1,550.5", "abc", "nan", "inf", "-inf"):
        with pytest.raises(ValueError):
            parse_decimal(refused)
