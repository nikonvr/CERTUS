"""The UX audit asks a table to sort only if it is a result, and asks for a synthesis view only of an analysis window (plan S6, UX-22).

Two verdicts of `scripts/audit_ux_certus.py` were refined on 2026-10-01, and a refinement that only removes a defect from the count
is exactly what a ratchet must not allow without saying why. So the refinements are DATA with their reasons, and these tests pin them:

    tables      "none sortable" was asked of every table. A table the operator can edit (a layer stack, a list of spectral windows) is an
                input whose row order is data: sorting it describes another filter. Only a read-only table - a result - is judged.
    synthesis   "no synthesis view" was asked of every window. The launcher computes nothing and the two utilities have one output,
                which is their plot or their table: `NO_SYNTHESIS_BY_DESIGN` names the three, with the reason.

Nothing else moved: every other verdict is exercised below on a row that is clean otherwise.
"""

from __future__ import annotations

import pytest

from scripts.audit_ux_certus import MODULES, NO_SYNTHESIS_BY_DESIGN, VITAL_KEYS_BY_MODULE, _verdicts

#: A window with nothing to say against it - the control row of every test below.
CLEAN = {
    "app": "CERTUS_STRAT",
    "plot_pct": 72.0,
    "left_min_px": 400,
    "left_px": 500,
    "panel_hscroll_px": 0,
    "n_tables": 0,
    "tables_sortable": 0,
    "tables_resizable": 0,
    "n_result_tables": 0,
    "result_tables_sortable": 0,
    "result_tables_resizable": 0,
    "missing_vital_keys": [],
    "btn_narrow": 0,
    "btn_short": 0,
    "n_long_labels": 0,
    "has_undo_stack": False,
    "has_undo_key": False,
    "marketing_tabs": 0,
    "input_no_tooltip": 0,
    "btn_no_tooltip": 0,
    "dark_stale": [],
    "low_contrast_light": [],
    "low_contrast_dark": [],
    "a11y_unnamed": [],
    "n_interactive": 30,
    "has_synthesis": True,
    "has_kpi_banner": False,
}


def test_the_control_row_is_clean():
    assert _verdicts(CLEAN) == []


# --- tables ------------------------------------------------------------------------------------------------------


def test_an_editable_table_that_does_not_sort_is_not_a_defect():
    """Three editable tables, none sorted, none resizable: a layer stack, a list of windows, a hidden helper."""
    row = {**CLEAN, "n_tables": 3, "tables_sortable": 0, "tables_resizable": 0}
    assert _verdicts(row) == []


def test_a_result_table_that_does_not_sort_is_a_defect():
    row = {**CLEAN, "n_tables": 2, "n_result_tables": 1, "result_tables_sortable": 0, "result_tables_resizable": 1}
    assert _verdicts(row) == ["1 result tables, none sortable"]


def test_a_result_table_that_cannot_even_be_widened_is_a_second_defect():
    row = {**CLEAN, "n_tables": 1, "n_result_tables": 1, "result_tables_sortable": 0, "result_tables_resizable": 0}
    assert _verdicts(row) == ["1 result tables, none sortable", "1 result tables, neither sortable nor resizable"]


def test_one_sortable_result_table_clears_the_module():
    row = {**CLEAN, "n_tables": 4, "n_result_tables": 3, "result_tables_sortable": 1, "result_tables_resizable": 0}
    assert _verdicts(row) == []


# --- synthesis view -----------------------------------------------------------------------------------------------


def test_the_exempt_windows_are_the_launcher_and_the_two_utilities_and_nothing_else():
    assert set(NO_SYNTHESIS_BY_DESIGN) == {"CERTUS_HUB", "CERTUS_SMOOTHER", "CERTUS_SUBSTRATE_INDEX"}


def test_every_exemption_names_a_real_window_and_gives_a_reason():
    for app, reason in NO_SYNTHESIS_BY_DESIGN.items():
        assert app in MODULES, f"{app} is not a window of the suite"
        assert len(reason.split()) >= 6, f"{app}: the reason is not a sentence: {reason!r}"


def test_the_exempt_windows_are_the_ones_the_audit_already_treats_as_a_launcher_and_utilities():
    """`VITAL_KEYS_BY_MODULE` already says which windows run nothing long. Two lists of the same three names must not drift."""
    assert set(NO_SYNTHESIS_BY_DESIGN) == set(VITAL_KEYS_BY_MODULE)


@pytest.mark.parametrize("app", sorted(NO_SYNTHESIS_BY_DESIGN))
def test_an_exempt_window_without_a_synthesis_is_clean(app):
    row = {**CLEAN, "app": app, "has_synthesis": False, "has_kpi_banner": False}
    assert _verdicts(row) == []


@pytest.mark.parametrize("app", sorted(set(MODULES) - set(NO_SYNTHESIS_BY_DESIGN)))
def test_every_other_window_without_a_synthesis_is_a_defect(app):
    row = {**CLEAN, "app": app, "has_synthesis": False, "has_kpi_banner": False}
    assert _verdicts(row) == ["no synthesis view (neither tab nor KPI banner)"]


def test_a_kpi_strip_is_a_synthesis_too():
    assert _verdicts({**CLEAN, "has_synthesis": False, "has_kpi_banner": True}) == []


# --- the other verdicts did not move -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ({"btn_narrow": 2}, "2 buttons < 60 px wide"),
        ({"btn_short": 1}, "1 buttons < 24 px high"),
        ({"marketing_tabs": 1}, "1 marketing tab(s) in the plot area"),
        ({"missing_vital_keys": ["F5"]}, "missing keys: F5"),
        ({"has_undo_stack": True}, "undo_stack present but no Ctrl+Z"),
        ({"btn_no_tooltip": 3}, "3 buttons without a tooltip"),
    ],
    ids=["narrow", "short", "marketing", "keys", "undo", "tooltip"],
)
def test_the_other_verdicts_still_fire(change, expected):
    assert _verdicts({**CLEAN, **change}) == [expected]
